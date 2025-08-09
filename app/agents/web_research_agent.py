from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_groq import ChatGroq
from langchain.tools import BaseTool, tool
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from .shared_state import DiagnosticState, WebResearchAgentInformation
from langchain_core.output_parsers import PydanticOutputParser
import re
import asyncio
from typing import Dict, List, Optional

search_wrapper = DuckDuckGoSearchAPIWrapper(
    region="us-en",  
    safesearch="moderate",
    time="y",  
    max_results=5
)
search = DuckDuckGoSearchResults(api_wrapper=search_wrapper)

def clean_search_results(results: str) -> str:
    """Clean and filter search results for medical relevance"""
    if not results or results == "No good DuckDuckGo Search Result was found":
        return "No relevant medical information found."
    
    # Remove non-English or irrelevant content
    lines = results.split('\n')
    filtered_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        non_ascii_ratio = sum(1 for c in line if ord(c) > 127) / len(line) if line else 0
        if non_ascii_ratio > 0.3:
            continue
            
        filtered_lines.append(line)
    
    return '\n'.join(filtered_lines[:10]) if filtered_lines else "No relevant medical information found."

@tool
async def web_search_for_single_symptom(symptom: str = '') -> dict:
    """
    Search the web for medical information about a single symptom.
    
    Args:
        symptom: The symptom to search for (e.g., "headache", "chest pain")
        
    Returns:
        Dictionary containing search query, results, and status
    """
    if not symptom or not symptom.strip():
        return {'query': '', 'results': 'No symptom provided', 'status': 'error'}
    
    clean_symptom = symptom.strip().lower()
    
    medical_queries = [
        f"{clean_symptom} medical causes symptoms treatment",
        f"{clean_symptom} health condition diagnosis symptoms",
        f"what causes {clean_symptom} medical reasons"
    ]
    
    best_result = None
    best_query = ""
    
    for query in medical_queries:
        try:
            result = await search.ainvoke(query)
            cleaned_result = clean_search_results(str(result))
            
            if cleaned_result and "No relevant medical information found" not in cleaned_result:
                best_result = cleaned_result
                best_query = query
                break
                
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Search attempt failed for query '{query}': {e}")
            continue
    
    if best_result:
        print(f"Successful search - Query: {best_query}")
        print(f"Results: {best_result[:200]}...")
        return {
            'query': best_query,
            'results': best_result,
            'status': 'success'
        }
    else:
        fallback_result = f"Unable to find specific medical information for '{symptom}'. This could indicate a need for medical consultation."
        return {
            'query': medical_queries[0],
            'results': fallback_result,
            'status': 'limited'
        }

@tool
async def web_search_multiple_symptoms_together(symptoms: list[str]) -> dict:
    """
    Search for medical conditions that could cause multiple symptoms together.
    
    Args:
        symptoms: List of symptoms to search for as a combination
        
    Returns:
        Dictionary containing search query, results, and status
    """
    if not symptoms or len(symptoms) == 0:
        return {
            'query': '',
            'results': 'No symptoms provided',
            'status': 'error'
        }
    
    clean_symptoms = [s.strip().lower() for s in symptoms if s.strip()]
    if not clean_symptoms:
        return {
            'query': '',
            'results': 'No valid symptoms provided',
            'status': 'error'
        }
    
    symptoms_text = ', '.join(clean_symptoms)
    
    medical_queries = [
        f"{symptoms_text} together medical condition diagnosis",
        f"conditions causing {symptoms_text} simultaneously symptoms",
        f"{symptoms_text} combination medical causes differential diagnosis",
        f"what disease causes {symptoms_text} together medical"
    ]
    
    best_result = None
    best_query = ""
    
    for query in medical_queries:
        try:
            print(f"Multi-symptom search query: {query}")
            result = await search.ainvoke(query)
            cleaned_result = clean_search_results(str(result))
            
            if cleaned_result and "No relevant medical information found" not in cleaned_result:
                best_result = cleaned_result
                best_query = query
                break
                
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Multi-symptom search failed for query '{query}': {e}")
            continue
    
    if best_result:
        return {
            'query': best_query,
            'results': best_result,
            'symptoms_searched': symptoms,
            'status': 'success'
        }
    else:
        fallback_result = f"Unable to find specific information about the combination of {symptoms_text}. Multiple symptoms together may require professional medical evaluation."
        return {
            'query': medical_queries[0],
            'results': fallback_result,
            'symptoms_searched': symptoms,
            'status': 'limited'
        }

@tool
async def search_medical_red_flags(symptoms: str) -> dict:
    """
    Search specifically for emergency warning signs and red flags related to symptoms.
    
    Args:
        symptoms: Symptoms to check for red flags and emergency signs
        
    Returns:
        Dictionary containing search query, results, and status
    """
    if not symptoms or not symptoms.strip():
        return {
            'query': '',
            'results': 'No symptoms provided',
            'status': 'error'
        }
    
    clean_symptoms = symptoms.strip().lower()
    
    emergency_queries = [
        f"{clean_symptoms} emergency warning signs when to see doctor immediately",
        f"{clean_symptoms} red flags urgent medical attention",
        f"{clean_symptoms} serious symptoms emergency room hospital",
        f"dangerous {clean_symptoms} warning signs emergency medical care"
    ]
    
    best_result = None
    best_query = ""
    
    for query in emergency_queries:
        try:
            print(f"Red flags search query: {query}")
            result = await search.ainvoke(query)
            cleaned_result = clean_search_results(str(result))
            
            if cleaned_result and "No relevant medical information found" not in cleaned_result:
                best_result = cleaned_result
                best_query = query
                break
                
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Red flags search failed for query '{query}': {e}")
            continue
    
    if best_result:
        return {
            'query': best_query,
            'results': best_result,
            'symptoms_searched': symptoms,
            'status': 'success'
        }
    else:
        fallback_result = f"Could not find specific emergency information for '{symptoms}'. When in doubt about serious symptoms, seek immediate medical attention."
        return {
            'query': emergency_queries[0],
            'results': fallback_result,
            'symptoms_searched': symptoms,
            'status': 'limited'
        }

class WebResearchAgent:
    def __init__(self, model):
        self.model = model or ChatGroq(model='llama-3.1-8b-instant', temperature=0.1)
        self.parser = PydanticOutputParser(pydantic_object=WebResearchAgentInformation)
        self.tools = [web_search_for_single_symptom, web_search_multiple_symptoms_together, search_medical_red_flags]
        
        system_message = SystemMessagePromptTemplate.from_template("""
            You are an expert medical research agent that searches the web for symptom information and provides evidence-based analysis.

            CORE RESPONSIBILITIES:
            1. Systematically research patient symptoms using available tools
            2. Analyze and synthesize medical information from web sources
            3. Identify potential conditions, causes, and explanations
            4. Flag emergency warning signs and red flags
            5. Provide confidence-rated summaries of findings

            RESEARCH METHODOLOGY:
            - Begin with individual symptom analysis using web_search_for_single_symptom
            - Progress to symptom combination searches using web_search_multiple_symptoms_together
            - Always investigate emergency signs using search_medical_red_flags
            - Cross-reference findings across multiple searches for reliability
            - Prioritize recent, authoritative medical sources

            SEARCH STRATEGY:
            - Use precise medical terminology when possible
            - Search for both common and rare conditions
            - Look for patterns and symptom clusters
            - Identify differential diagnosis possibilities
            - Focus on actionable medical information

            SAFETY PROTOCOLS:
            - Always err on the side of caution for patient safety
            - Immediately flag potential emergency situations
            - Recommend medical consultation for serious symptoms
            - Avoid definitive diagnoses - suggest possibilities only
            - Maximum 5 tool calls to maintain efficiency

            ANALYSIS FRAMEWORK:
            When search results are limited or unclear:
            - Acknowledge limitations honestly
            - Recommend professional medical evaluation
            - Focus on what information is available
            - Suggest follow-up questions for healthcare providers

            OUTPUT REQUIREMENTS:
            Provide structured analysis including:
            - Possible medical conditions found (with likelihood if determinable)
            - Clear explanations of symptoms and their medical significance
            - Emergency warning signs and red flags (if any)
            - Confidence level: high/medium/low based on search result quality
            - Recommendation for additional research or medical consultation

            CURRENT CASE CONTEXT:
            Patient symptoms: {symptoms}
            Research iteration: {iteration}
            Previous findings: {previous_context}
                                                                   
            Format your response according to these specifications:
            {format_instructions}
        """)

        human_message = HumanMessagePromptTemplate.from_template("""
            Conduct comprehensive medical research on these symptoms:

            PRIMARY SYMPTOMS: {symptoms}

            ADDITIONAL CONTEXT:
            - Affected body parts: {body_parts}
            - Symptom timeline: {timeline} 
            - Symptom evolution: {evolution}
            - Previous medical evaluations: {medical_checks}

            Execute your research plan systematically and provide a thorough medical analysis based on your findings.
        """)

        self.prompt = ChatPromptTemplate.from_messages([
            system_message, 
            human_message,
            MessagesPlaceholder(variable_name='agent_scratchpad')
        ])

        self.agent = create_tool_calling_agent(
            llm=self.model,
            tools=self.tools,
            prompt=self.prompt
        )

        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            max_iterations=5,  
            early_stopping_method="generate",
            handle_parsing_errors=True,
            verbose=True
        )

    async def process(self, state: DiagnosticState) -> dict:
        """
        Enhanced process method with improved error handling and fallback mechanisms
        """
        format_instructions = self.parser.get_format_instructions()
        
        # Extract symptom information
        if state.symptom_analysis:
            symptoms = state.symptom_analysis.parsed_symptoms or []
            body_parts = state.symptom_analysis.body_parts_affected or []
            timeline = state.symptom_analysis.time_since_start or "Not specified"
            evolution = state.symptom_analysis.evolution_of_symptoms or []
            medical_checks = state.symptom_analysis.medical_checks or []
        else:
            symptoms = []
            body_parts = []
            timeline = "Not specified"
            evolution = []
            medical_checks = []
        
        # Extract previous research context
        if state.web_search_agent_information:
            iteration = state.web_search_agent_information.iteration + 1
            previous_context = state.web_search_agent_information.previous_search_results or []
        else:
            iteration = 1
            previous_context = []
        
        # Prepare context strings
        symptoms_str = ", ".join(symptoms) if symptoms else "No symptoms specified"
        body_parts_str = ", ".join(body_parts) if body_parts else "Not specified"
        evolution_str = ", ".join(evolution) if evolution else "Not specified"
        medical_checks_str = ", ".join(medical_checks) if medical_checks else "None reported"
        previous_context_str = "\n".join(previous_context) if previous_context else "No previous research"

        print(f"Starting medical research - Iteration {iteration}")
        print(f"Symptoms to research: {symptoms_str}")

        try:
            response = await self.executor.ainvoke({
                'symptoms': symptoms_str,
                'iteration': iteration,
                'previous_context': previous_context_str,
                'format_instructions': format_instructions,
                'body_parts': body_parts_str,
                'timeline': timeline,
                'evolution': evolution_str,
                'medical_checks': medical_checks_str
            })

            print(f"Research completed. Raw response: {response}")
            
            # Parse the structured response
            try:
                parsed_result = self.parser.parse(response['output'])
                print(f"Successfully parsed research results")
                
                return {
                    'web_search_agent_information': parsed_result
                }
                
            except Exception as parse_error:
                print(f"Parsing error: {parse_error}")
                print(f"Raw output to parse: {response['output']}")
                
                fallback_result = WebResearchAgentInformation(
                    possible_conditions=["Unable to parse research results - recommend medical consultation"],
                    symptom_explanations=[f"Research conducted but parsing failed: {str(parse_error)}"],
                    red_flags=["Parsing error may have missed important information"],
                    additional_questions=["Please consult healthcare provider for proper evaluation"],
                    search_summary=f"Research iteration {iteration} completed but results could not be properly parsed",
                    confidence_level="low",
                    needs_more_research=True,
                    iteration=iteration,
                    previous_search_results=previous_context + [f"Parse error on iteration {iteration}"]
                )
                
                return {
                    'web_search_agent_information': fallback_result
                }
            
        except Exception as e:
            print(f"Critical error in web research process: {e}")
            
            error_result = WebResearchAgentInformation(
                possible_conditions=[],
                symptom_explanations=[],
                red_flags=["Research system error - seek immediate medical attention if symptoms are severe"],
                additional_questions=["Could not complete automated research - please consult healthcare provider"],
                search_summary=f"Research failed due to system error: {str(e)}",
                confidence_level="low",
                needs_more_research=True,
                iteration=iteration,
                previous_search_results=previous_context + [f"System error on iteration {iteration}: {str(e)}"]
            )
            
            return {
                'web_search_agent_information': error_result
            }