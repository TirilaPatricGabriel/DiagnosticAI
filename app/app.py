import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agents.agent_graph import AgentGraph
from .agents.shared_state import DiagnosticState
from .agents.web_research_agent import (
    web_search_for_single_symptom,
    web_search_multiple_symptoms_together
)

# App lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DiagnosticAI FastAPI server starting up")
    yield
    logger.info("DiagnosticAI FastAPI server shutting down")

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan, title="DiagnosticAI API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    filename='diagnosticai.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Pydantic Models
class SymptomRequest(BaseModel):
    symptoms: str
    thread_id: str = 'default'

class WebResearchRequest(BaseModel):
    thread_id: str = 'default'

class AnalysisResponse(BaseModel):
    status: str
    is_complete: bool
    follow_up_questions: List[str] = []
    extracted_data: Dict[str, Any] = {}

class DebugRequest(BaseModel):
    symptom: str = ''

class DebugMultipleRequest(BaseModel):
    symptoms: List[str] = []

# Initialize agent
agent = AgentGraph(model_name='llama-3.3-70b-versatile')

# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "DiagnosticAI"}

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_symptoms(request: SymptomRequest):
    """Analyze patient symptoms through multi-agent system"""
    try:
        config = {'configurable': {'thread_id': request.thread_id}}
        input_data = {"user_request": request.symptoms}
        
        # Check existing state
        try:
            current_state = await agent.agent_graph.aget_state(config=config)
            interaction_count = current_state.values.get('interaction_count', 0) if current_state.values else 0
            logger.info(f"Thread {request.thread_id} - Interactions: {interaction_count}")
        except Exception as e:
            logger.warning(f"State check failed: {e}")
        
        # Run agent graph
        await agent.agent_graph.ainvoke(input_data, config=config)
        
        # Get final state
        final_state = await agent.agent_graph.aget_state(config=config)
        if not final_state or not final_state.values:
            raise HTTPException(status_code=500, detail="Failed to get final state")
        
        state_values = final_state.values
        symptom_analysis = state_values.get('symptom_analysis')
        conversation_history = state_values.get('conversation_history', [])
        interaction_count = state_values.get('interaction_count', 0)

        # Check completion
        temp_state = DiagnosticState(
            user_request=request.symptoms,
            symptom_analysis=symptom_analysis,
            conversation_history=conversation_history,
            interaction_count=interaction_count,
            web_search_agent_information=state_values.get('web_search_agent_information'),
            document_research_agent_information=state_values.get('document_research_agent_information')
        )

        check_result = agent.check_all_data_extracted(temp_state)
        logger.info(f"Check result: {check_result}")

        if check_result == 'continue_to_web_research':
            is_complete = False  
            status = "extracted" 
            follow_up_questions = []
        elif check_result == 'ask_user':
            is_complete = False
            status = "needs_info"  
            follow_up_questions = symptom_analysis.follow_up_questions if symptom_analysis else []
        else:
            is_complete = False
            status = "continuing"  
            follow_up_questions = ["Could you provide more details about your symptoms?"]


        return AnalysisResponse(
            status=status,  
            is_complete=is_complete,
            follow_up_questions=follow_up_questions,
            extracted_data=symptom_analysis.model_dump() if symptom_analysis else {}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed - Thread: {request.thread_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/debug/state/{thread_id}")
async def debug_state(thread_id: str):
    """Debug endpoint to inspect conversation state"""
    try:
        config = {'configurable': {'thread_id': thread_id}}
        state = await agent.agent_graph.aget_state(config=config)
        
        if state and state.values:
            return {
                "thread_id": thread_id,
                "state_exists": True,
                "conversation_history": state.values.get('conversation_history', []),
                "interaction_count": state.values.get('interaction_count', 0),
                "has_symptom_analysis": state.values.get('symptom_analysis') is not None,
                "has_web_research": state.values.get('web_search_agent_information') is not None
            }
        else:
            return {"thread_id": thread_id, "state_exists": False}
    except Exception as e:
        return {"thread_id": thread_id, "error": str(e)}
    


class WebResearchResults(BaseModel):
    possible_conditions: List[str] = []
    symptom_explanations: List[str] = []
    red_flags: List[str] = []
    additional_questions: List[str] = []
    search_summary: str = ""
    confidence_level: str = ""
    needs_more_research: bool = False
    iteration: int = 0
    previous_search_results: List[str] = []

class WebResearchResponse(BaseModel):
    status: str
    is_complete: bool
    web_research_results: Optional[WebResearchResults] = None
    extracted_data: Dict[str, Any] = {}
    message: str = "Web research completed successfully"


@app.post('/api/web-research', response_model=WebResearchResponse)
async def web_research(request: WebResearchRequest):
    try:
        thread_id = request.thread_id
        config = {'configurable': {'thread_id': thread_id}}

        await agent.agent_graph.ainvoke({}, config=config)
        
        final_state = await agent.agent_graph.aget_state(config=config)
        
        if not final_state or not final_state.values:
            raise HTTPException(status_code=500, detail="Failed to get final state after web research")
        
        state_values = final_state.values
        
        web_research_info = state_values.get('web_search_agent_information')
        symptom_analysis = state_values.get('symptom_analysis')
        
        return WebResearchResponse(
            status="success",
            is_complete=True,
            web_research_results=WebResearchResults(**web_research_info.model_dump()) if web_research_info else None,
            extracted_data=symptom_analysis.model_dump() if symptom_analysis else {}
        )
        
    except Exception as e:
        logger.error(f"Web research failed - Thread: {thread_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Web research failed: {str(e)}")











# DEBUG
@app.post('/api/debug/research-single')
async def debug_single_research(request: DebugRequest):
    """Debug single symptom research"""
    try:
        result = await web_search_for_single_symptom.ainvoke({'symptom': request.symptom})
        return {'status': 'success', 'result': result}
    except Exception as e:
        logger.error(f"Single research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/debug/research-multiple')
async def debug_multiple_research(request: DebugMultipleRequest):
    """Debug multiple symptom research"""
    try:
        result = await web_search_multiple_symptoms_together.ainvoke({'symptoms': request.symptoms})
        return {'status': 'success', 'result': result}
    except Exception as e:
        logger.error(f"Multiple research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))







































@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "DiagnosticAI"}

@app.get("/api/debug/state/{thread_id}")
async def debug_state(thread_id: str):
    """Debug endpoint to inspect conversation state"""
    try:
        config = {'configurable': {'thread_id': thread_id}}
        state = await agent.agent_graph.aget_state(config=config)
        
        if state and state.values:
            return {
                "thread_id": thread_id,
                "state_exists": True,
                "conversation_history": state.values.get('conversation_history', []),
                "interaction_count": state.values.get('interaction_count', 0),
                "has_symptom_analysis": state.values.get('symptom_analysis') is not None,
                "full_state": state.values
            }
        else:
            return {
                "thread_id": thread_id,
                "state_exists": False
            }
    except Exception as e:
        return {"error": str(e), "thread_id": thread_id}