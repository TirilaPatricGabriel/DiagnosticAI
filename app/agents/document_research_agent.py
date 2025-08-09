from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.tools import BaseTool, StructuredTool, Tool, tool
from langchain_core.prompts import HumanMessagePromptTemplate, SystemMessagePromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from .shared_state import DiagnosticState, DocumentResearchAgentInformation
import os

class DocumentResearchAgent:
    def __init__(self, model=None, pdf_directory="./medical_pdfs"):
        self.model = model or ChatGroq(model='llama-3.1-8b', temperature=0.01)
        self.parser = PydanticOutputParser(pydantic_object=DocumentResearchAgentInformation)
        self.pdf_directory = pdf_directory
        
        self.knowledge_base = None
        self.retriever = None
        self._initialize_rag_system()
        
        self.tools = self._create_rag_tools()

        system_message = SystemMessagePromptTemplate.from_template("""
            You are a medical document research agent that searches through medical literature and documents.
            
            Your job is to:
            1. Research patient symptoms using medical documents
            2. Find relevant medical information from reliable sources
            3. Identify potential conditions and explanations
            4. Look for important warnings or red flags
            5. Provide evidence-based medical insights
            
            IMPORTANT: You provide information for educational purposes only.
            Always recommend consulting healthcare professionals for actual medical advice.
            
            Patient Information:
            - Symptoms: {symptoms}
            - Body parts affected: {body_parts}
            - Timeline: {timeline}
            - Evolution: {evolution}
            - Previous medical care: {medical_checks}
            
            Use your tools to research this case thoroughly from medical documents.
            
            {format_instructions}
        """)

        human_message = HumanMessagePromptTemplate.from_template("""
            Please research the following medical case using available medical documents:
            
            Primary symptoms to research: {symptoms}
            
            Additional context:
            - Affected body parts: {body_parts}
            - Symptom timeline: {timeline}
            - How symptoms evolved: {evolution}
            - Previous medical care: {medical_checks}
            
            Provide comprehensive findings from medical literature.
        """)

        self.prompt = ChatPromptTemplate.from_messages([
            system_message, 
            human_message
        ])

        self.agent = create_tool_calling_agent(
            llm=self.model,
            tools=self.tools,
            prompt=self.prompt
        )

        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=5,
            early_stopping_method='generate',
            handle_parsing_errors=True
        )

    def _initialize_rag_system(self):
        """Initialize RAG system with PDF documents"""
        try:
            if not os.path.exists(self.pdf_directory):
                os.makedirs(self.pdf_directory)
                print(f"Created {self.pdf_directory}. Add your medical PDF files there.")
                return
            
            loader = DirectoryLoader(
                self.pdf_directory,
                glob="**/*.pdf",
                loader_cls=PyPDFLoader
            )
            documents = loader.load()
            
            if not documents:
                print("No PDF files found. Add medical PDFs to process.")
                return
            
            print(f"Loaded {len(documents)} document pages from PDFs")
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            texts = text_splitter.split_documents(documents)
            print(f"Split into {len(texts)} text chunks")
            
            embeddings = OpenAIEmbeddings()
            self.knowledge_base = FAISS.from_documents(texts, embeddings)
            
            self.retriever = self.knowledge_base.as_retriever(
                search_kwargs={"k": 5}
            )
            
            print("RAG system initialized successfully!")
            
        except Exception as e:
            print(f"Error initializing RAG system: {e}")
            self.knowledge_base = None
            self.retriever = None

    def _create_rag_tools(self):
        """Create RAG-based tools for document research"""
        
        @tool
        async def search_medical_documents(query: str) -> dict:
            """
            Search through medical documents for information about symptoms or conditions.
            
            Args:
                query: Medical query to search for (symptoms, conditions, etc.)
                
            Returns:
                Dictionary with search results from medical documents
            """
            if not self.retriever:
                return {
                    'results': 'Medical document database not available',
                    'sources': [],
                    'status': 'error'
                }
            
            try:
                docs = await self.retriever.aget_relevant_documents(query)
                
                results = []
                sources = []
                
                for doc in docs:
                    results.append(doc.page_content[:500]) 
                    source = doc.metadata.get('source', 'Unknown source')
                    if source not in sources:
                        sources.append(source)
                
                return {
                    'results': results,
                    'sources': sources,
                    'status': 'success',
                    'query': query
                }
                
            except Exception as e:
                return {
                    'results': f'Search failed: {str(e)}',
                    'sources': [],
                    'status': 'error'
                }
        
        @tool
        async def lookup_medical_conditions(conditions: str) -> dict:
            """
            Look up specific medical conditions in the document database.
            
            Args:
                conditions: Medical conditions to research
                
            Returns:
                Dictionary with detailed condition information
            """
            if not self.retriever:
                return {
                    'information': 'Document database not available',
                    'status': 'error'
                }
            
            try:
                query = f"diagnosis treatment {conditions}"
                docs = await self.retriever.aget_relevant_documents(query)
                
                information = []
                sources = []
                
                for doc in docs:
                    information.append(doc.page_content[:400])
                    source = doc.metadata.get('source', 'Unknown')
                    if source not in sources:
                        sources.append(source)
                
                return {
                    'information': information,
                    'sources': sources,
                    'status': 'success'
                }
                
            except Exception as e:
                return {
                    'information': f'Lookup failed: {str(e)}',
                    'status': 'error'
                }
        
        @tool
        async def find_warning_signs(symptoms: str) -> dict:
            """
            Find warning signs and red flags for given symptoms in medical documents.
            
            Args:
                symptoms: Symptoms to check for warning signs
                
            Returns:
                Dictionary with warning sign information
            """
            if not self.retriever:
                return {
                    'warnings': [],
                    'status': 'error'
                }
            
            try:
                query = f"warning signs red flags emergency {symptoms}"
                docs = await self.retriever.aget_relevant_documents(query)
                
                warnings = []
                sources = []
                
                for doc in docs:
                    warnings.append(doc.page_content[:300])
                    source = doc.metadata.get('source', 'Unknown')
                    if source not in sources:
                        sources.append(source)
                
                return {
                    'warnings': warnings,
                    'sources': sources,
                    'status': 'success'
                }
                
            except Exception as e:
                return {
                    'warnings': [],
                    'status': 'error'
                }
        
        if self.retriever:
            return [search_medical_documents, lookup_medical_conditions, find_warning_signs]
        else:
            @tool
            async def placeholder_search(query: str) -> dict:
                """Placeholder search when document database is not available"""
                return {
                    'results': 'Document database not initialized. Add PDF files to the medical_pdfs directory.',
                    'status': 'unavailable'
                }
            
            return [placeholder_search]

    async def process(self, state: DiagnosticState) -> dict:
        """
        Process the diagnostic state and return document research results.
        """
        try:
            format_instructions = self.parser.get_format_instructions()
            
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
            
            symptoms_str = ", ".join(symptoms) if symptoms else "No symptoms specified"
            body_parts_str = ", ".join(body_parts) if body_parts else "Not specified"
            evolution_str = ", ".join(evolution) if evolution else "Not specified"
            medical_checks_str = ", ".join(medical_checks) if medical_checks else "None"

            response = await self.executor.ainvoke({
                'format_instructions': format_instructions,
                'symptoms': symptoms_str,
                'body_parts': body_parts_str,
                'timeline': timeline,
                'evolution': evolution_str,
                'medical_checks': medical_checks_str
            })

            parsed_result = self.parser.parse(response['output'])
            
            return {
                'document_research_information': parsed_result
            }
            
        except Exception as e:
            print(f"Error in document research process: {e}")
            
            error_result = DocumentResearchAgentInformation(
                research_summary=f"Document research failed: {str(e)}",
                confidence_level="low",
                key_findings=[],
                possible_conditions=[],
                warning_signs=[],
                recommendations="Please consult a healthcare professional"
            )
            
            return {
                'document_research_information': error_result
            }