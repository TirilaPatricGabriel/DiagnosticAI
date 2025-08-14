from langchain_core.messages import AIMessage, ToolMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.tools import BaseTool, tool
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from .shared_state import SymptomAnalysis, DiagnosticState

class SymptomParserAgent:
    def __init__(self, model=None):
        self.llm = model or ChatGroq(model="llama-3.1-8b")
        self.parser = PydanticOutputParser(pydantic_object=SymptomAnalysis)

        system_message_template = SystemMessagePromptTemplate.from_template("""
            You are a medical symptom analyzer focused on DATA COLLECTION.
            Your job is to systematically extract specific information for each required field.

            CONTEXT: 
            - Previous analysis: {previous_analysis}
            - Full conversation history: {conversation_history}
            - Interaction number: {interaction_count}

            REQUIRED DATA FIELDS TO COLLECT:
            1. parsed_symptoms: Specific symptoms with details (severity, type, characteristics)
            2. body_parts_affected: Exact locations and areas
            3. time_since_start: When symptoms began (be specific: "2 weeks ago", "yesterday", etc.)
            4. evolution_of_symptoms: How symptoms changed over time (better/worse/same, patterns)
            5. medical_checks: Any medical visits, tests, treatments, medications tried

            SYSTEMATIC QUESTIONING APPROACH:
            - First, extract ALL available information from current input AND conversation history
            - Then identify which fields still need data
            - Ask ONLY direct, specific questions to fill missing fields
            - Focus on ONE field per question
            - Be factual and medical, not conversational

            QUESTION GUIDELINES:
            GOOD questions (direct, data-focused):
            - "What is the severity of your headache on a scale of 1-10?"
            - "Which specific part of your head hurts? (front, back, sides, temples)"
            - "Have you taken any medications for this? If yes, which ones?"
            - "When exactly did this start? (date/time if possible)"

            BAD questions (vague, unhelpful):
            - "How do you think X might help you?"
            - "What are your thoughts about Y?"
            - "Would you like to Z?" (unless directly collecting treatment preference data)
            - "How do you feel about..."

            COMPLETION CRITERIA:
            Only return [] for follow_up_questions when you have:
            - At least 2-3 specific symptoms with details
            - Clear body parts affected
            - Specific timeline (not empty)
            - Some evolution information (getting better/worse/patterns)
            - Information about any medical care sought

            STRICT RULES:
            - NO philosophical or exploratory questions
            - NO duplicate questions (check conversation history!)
            - NO vague "how do you think" questions
            - Maximum 3 questions, minimum 1 question (unless complete)
            - Each question must target a specific missing field
            - Use empty string "" for missing strings, empty array [] for missing lists

            {format_instructions}
        """)
        
        human_message_template = HumanMessagePromptTemplate.from_template(
            "Current patient input: {user_request}"
        )

        self.prompt = ChatPromptTemplate.from_messages([
            system_message_template,
            human_message_template
        ])

        self.chain = self.prompt | self.llm | self.parser

    async def process(self, state: DiagnosticState) -> dict:
        """
        Process input and return state updates.
        
        BEST PRACTICE: Return only the fields that should be updated.
        LangGraph will merge these with existing state using reducers.
        """
        format_instructions = self.parser.get_format_instructions()
        
        history_text = "\n".join(state.conversation_history) if state.conversation_history else "No previous conversation"
        previous_analysis = state.symptom_analysis.model_dump() if state.symptom_analysis else "None - first analysis"
        new_interaction_count = state.interaction_count + 1

        new_result = await self.chain.ainvoke({
            'format_instructions': format_instructions,
            'user_request': state.user_request,
            'previous_analysis': previous_analysis,
            'conversation_history': history_text,
            'interaction_count': new_interaction_count
        })

        if state.symptom_analysis:
            merged_analysis = self.merge_analyses(state.symptom_analysis, new_result)
        else:
            merged_analysis = new_result

        new_history_entries = [
            f"Patient Input #{new_interaction_count}: {state.user_request}"
        ]
        
        if merged_analysis.follow_up_questions:
            ai_questions = f"AI Questions #{new_interaction_count}: " + " | ".join(merged_analysis.follow_up_questions)
            new_history_entries.append(ai_questions)

        all_complete = self.is_analysis_complete(merged_analysis, new_interaction_count)

        return {
            'symptom_analysis': merged_analysis,
            'conversation_history': new_history_entries, 
            'interaction_count': new_interaction_count,
            'symptom_parsing_finished': all_complete
        }

    def merge_analyses(self, previous: SymptomAnalysis, new: SymptomAnalysis) -> SymptomAnalysis:
        """
        Safely merge previous analysis with new analysis.
        Always preserve existing data and only ADD new information.
        """
        
        def merge_lists(prev_list, new_list):
            """Add new items to existing list, avoid duplicates"""
            if not prev_list:
                return new_list or []
            if not new_list:
                return prev_list
            
            combined = prev_list.copy()
            
            for new_item in new_list:
                if new_item not in combined:
                    combined.append(new_item)
            
            return combined

        def merge_string(prev_str, new_str):
            """Keep existing string unless it was empty"""
            if not prev_str:
                return new_str or ""
            return prev_str

        return SymptomAnalysis(
            parsed_symptoms=merge_lists(previous.parsed_symptoms, new.parsed_symptoms),
            body_parts_affected=merge_lists(previous.body_parts_affected, new.body_parts_affected),
            time_since_start=merge_string(previous.time_since_start, new.time_since_start),
            evolution_of_symptoms=merge_lists(previous.evolution_of_symptoms, new.evolution_of_symptoms),
            medical_checks=merge_lists(previous.medical_checks or [], new.medical_checks or []),
            follow_up_questions=new.follow_up_questions 
        )
    
    def is_analysis_complete(self, analysis: SymptomAnalysis, interaction_count: int) -> bool:
        required_fields = [
            analysis.parsed_symptoms,
            analysis.body_parts_affected, 
            analysis.time_since_start,
            analysis.evolution_of_symptoms,
            analysis.medical_checks
        ]

        all_data_complete = True
        
        for field in required_fields:
            if field is None:
                all_data_complete = False
                break
            
            if isinstance(field, list) and len(field) == 0:
                all_data_complete = False
                break
                
            if isinstance(field, str) and not field.strip():
                all_data_complete = False
                break

        if all_data_complete or interaction_count >= 5:
            return True
        
        return False