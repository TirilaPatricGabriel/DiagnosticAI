from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
# from langgraph.checkpoint.postgres import PostgresSaver  # For production

from .shared_state import DiagnosticState
from .symptom_parser_agent import SymptomParserAgent
from .web_research_agent import WebResearchAgent

from langchain_groq import ChatGroq

import os
from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())

class AgentGraph():
    def __init__(self, model_name):
        model = ChatGroq(model=model_name, temperature=0.1, api_key=os.getenv('GROQ_API_KEY'))
        self.system_parser_agent = SymptomParserAgent(model=model)
        self.web_researcher_agent = WebResearchAgent(model=model)

        graph = StateGraph(DiagnosticState)

        graph.set_entry_point('router')

        graph.add_node('router', lambda state: state)
        graph.add_node('symptom_parser', self.system_parser_agent.process)
        graph.add_node('web_researcher', self.web_researcher_agent.process)

        graph.add_conditional_edges(
            'router', 
            self.route_from_entry,
            {
                'symptom_parser': 'symptom_parser', 
                'web_researcher': 'web_researcher'
            }
        )

        graph.add_conditional_edges(
            'symptom_parser',
            self.check_all_data_extracted,
            {'continue': 'symptom_parser', 'ask_user': END, 'continue_to_web_research': END}
        )
        
        graph.add_edge('web_researcher', END)

        checkpointer = MemorySaver()
        self.agent_graph = graph.compile(checkpointer=checkpointer)

    def route_from_entry(self, state: DiagnosticState):
        """Decide where to go from entry point"""
        print(f"Router check: symptom_parsing_finished = {getattr(state, 'symptom_parsing_finished', 'NOT SET')}")
        
        if hasattr(state, 'symptom_parsing_finished') and state.symptom_parsing_finished:
            print("Router -> web_researcher")
            return 'web_researcher'
        else:
            print("Router -> symptom_parser")  
            return 'symptom_parser'
        
    def check_all_data_extracted(self, state: DiagnosticState):
        if not state.symptom_analysis:
            return 'continue'
        
        analysis = state.symptom_analysis
        
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

        if all_data_complete or state.interaction_count >= 5:
            return 'continue_to_web_research'

        if analysis.follow_up_questions and len(analysis.follow_up_questions) > 0:
            return 'ask_user'
        
        return 'continue'