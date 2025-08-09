from pydantic import BaseModel, Field
from typing import Optional, List, Annotated
from operator import add

def accumulate_conversation(left: List[str], right: List[str]) -> List[str]:
    """Accumulate conversation history without duplicates"""
    if not left:
        return right or []
    if not right:
        return left
    
    result = left.copy()
    for item in right:
        if item not in result:  
            result.append(item)
    return result

def increment_counter(left: int, right: int) -> int:
    """Take the maximum of two integers (for incrementing counter)"""
    if left is None:
        return right or 0
    if right is None:
        return left
    return max(left, right)

class SymptomAnalysis(BaseModel):
    parsed_symptoms: list[str] = Field(description="Individual symptoms extracted")
    body_parts_affected: list[str] = Field(description="Body parts affected of symptoms")
    time_since_start: str = Field(description="Time since symptoms started")
    evolution_of_symptoms: list[str] = Field(description="How the symptoms evolved")
    medical_checks: Optional[list[str]] = Field(description="The result of possible medical checks around the symptoms")
    follow_up_questions: Optional[list[str]] = []

class WebResearchAgentInformation(BaseModel):
    possible_conditions: List[str] = Field(description="Potential medical conditions found")
    symptom_explanations: List[str] = Field(description="Explanations for symptoms")
    red_flags: List[str] = Field(description="Warning signs found")
    additional_questions: List[str] = Field(description="Questions for better diagnosis")
    search_summary: str = Field(description="Summary of research findings")
    confidence_level: str = Field(description="Confidence in findings: high/medium/low")
    needs_more_research: bool = Field(description="Whether more specific research is needed")
    iteration: int = Field(description='Number of the iteration')
    previous_search_results: list[str] = Field(description='Previous research results')

class DocumentResearchAgentInformation(BaseModel):
    key_findings: List[str] = Field(description="Key medical information found")
    possible_conditions: List[str] = Field(description="Possible conditions from literature")
    warning_signs: List[str] = Field(description="Important warning signs found")
    recommendations: str = Field(description="Medical recommendations")
    confidence: str = Field(description="high/medium/low confidence in findings")

class DiagnosticState(BaseModel):
    user_request: str
    symptom_parsing_finished: bool = False
    
    symptom_analysis: Optional[SymptomAnalysis] = None
    web_search_agent_information: Optional[WebResearchAgentInformation] = None
    document_research_agent_information: Optional[DocumentResearchAgentInformation] = None
    
    conversation_history: Annotated[List[str], accumulate_conversation] = Field(
        default_factory=list, 
        description="Full conversation history"
    )
    
    interaction_count: Annotated[int, increment_counter] = Field(
        default=0, 
        description="Number of interactions in this session"
    )