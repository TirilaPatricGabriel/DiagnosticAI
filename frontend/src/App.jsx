import React, { useState } from 'react';
import './App.css';
import { apiEndpoints } from './services/api';

function App() {
  const [symptoms, setSymptoms] = useState('');
  const [charCount, setCharCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationComplete, setConversationComplete] = useState(false);
  const [followUpQuestions, setFollowUpQuestions] = useState([]);
  const [threadId] = useState(() => `thread_${Date.now()}`);
  const [questionAnswers, setQuestionAnswers] = useState({});
  const [extractedData, setExtractedData] = useState({});
  const [showExtractedData, setShowExtractedData] = useState(false);
  const [webResearchResults, setWebResearchResults] = useState({}); // 🆕 NEW STATE

  const handleInputChange = (e) => {
    const value = e.target.value;
    setSymptoms(value);
    setCharCount(value.length);
  };

  const handleQuestionAnswerChange = (questionIndex, value) => {
    setQuestionAnswers(prev => ({
      ...prev,
      [questionIndex]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!symptoms.trim()) {
      alert('Please describe your symptoms.');
      return;
    }

    setIsLoading(true);

    try {
      const response = await apiEndpoints.analyzeSymptoms({
        symptoms: symptoms,
        thread_id: threadId
      });
      
      console.log('Analysis result:', response.data);
      
      if (response.data.is_complete) {
        // Analysis is complete
        setConversationComplete(true);
        setFollowUpQuestions([]);
        setExtractedData(response.data.extracted_data);
        setShowExtractedData(false);
        console.log('Complete analysis:', response.data.extracted_data);
      } else if (response.data.status === 'extracted') {
        // Data extracted, show it and prepare for research
        setShowExtractedData(true);
        setExtractedData(response.data.extracted_data);
        setFollowUpQuestions([]);
      } else {
        // Need more information - show follow-up questions
        setFollowUpQuestions(response.data.follow_up_questions);
        setSymptoms(''); // Clear input for next response
        setCharCount(0);
        setQuestionAnswers({}); // Reset question answers
        setShowExtractedData(false);
      }
      
    } catch (error) {
      console.error('Error analyzing symptoms:', error);
      
      if (error.response) {
        alert(`Analysis failed: ${error.response.data?.detail || 'Server error'}`);
      } else if (error.request) {
        alert('No response from server. Please check your connection.');
      } else {
        alert('Analysis failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleFollowUpSubmit = async (e) => {
    e.preventDefault();
    
    // Check if all questions are answered
    const unansweredQuestions = followUpQuestions.filter((_, index) => 
      !questionAnswers[index] || !questionAnswers[index].trim()
    );
    
    if (unansweredQuestions.length > 0) {
      alert('Please answer all questions before submitting.');
      return;
    }

    setIsLoading(true);

    try {
      // Combine all answers into one text
      const combinedAnswers = followUpQuestions.map((question, index) => 
        `Q: ${question}\nA: ${questionAnswers[index]}`
      ).join('\n\n');

      const response = await apiEndpoints.analyzeSymptoms({
        symptoms: combinedAnswers,
        thread_id: threadId
      });
      
      console.log('Follow-up analysis result:', response.data);
      
      if (response.data.is_complete) {
        // Analysis is complete
        setConversationComplete(true);
        setFollowUpQuestions([]);
        setExtractedData(response.data.extracted_data);
        setShowExtractedData(false);
        console.log('Complete analysis:', response.data.extracted_data);
      } else if (response.data.status === 'extracted') {
        // Data extracted, show it
        setShowExtractedData(true);
        setExtractedData(response.data.extracted_data);
        setFollowUpQuestions([]);
      } else {
        // Still need more information
        setFollowUpQuestions(response.data.follow_up_questions);
        setQuestionAnswers({}); // Reset for new questions
        setShowExtractedData(false);
      }
      
    } catch (error) {
      console.error('Error submitting follow-up:', error);
      alert('Failed to submit answers. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleWebResearch = async () => {
    setIsLoading(true);

    try {
      const response = await apiEndpoints.webResearch({
        thread_id: threadId
      });
      
      console.log('Web research result:', response.data);
      
      // 🔄 UPDATED - Store web research results
      setConversationComplete(true);
      setShowExtractedData(false);
      setExtractedData(response.data.extracted_data);
      setWebResearchResults(response.data.web_research_results || {}); // 🆕 NEW
      
    } catch (error) {
      console.error('Error during web research:', error);
      alert('Web research failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const resetConversation = () => {
    setSymptoms('');
    setCharCount(0);
    setConversationComplete(false);
    setFollowUpQuestions([]);
    setQuestionAnswers({});
    setExtractedData({});
    setShowExtractedData(false);
    setWebResearchResults({}); // 🆕 RESET WEB RESEARCH
  };

  if (conversationComplete) {
    return (
      <div className="container">
        <div className="header">
          <div className="logo-container">
            <div className="logo">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
              </svg>
            </div>
            <h1>Analysis Complete</h1>
          </div>
          <p className="subtitle">Your symptom analysis and medical research completed</p>
        </div>

        <div className="results-section">
          <h3 style={{ color: '#d4d4d8', marginBottom: '20px' }}>Your Symptom Information:</h3>
          
          {extractedData.parsed_symptoms && (
            <div className="result-item">
              <strong>Symptoms:</strong> {extractedData.parsed_symptoms.join(', ')}
            </div>
          )}
          
          {extractedData.body_parts_affected && (
            <div className="result-item">
              <strong>Body Parts Affected:</strong> {extractedData.body_parts_affected.join(', ')}
            </div>
          )}
          
          {extractedData.time_since_start && (
            <div className="result-item">
              <strong>Timeline:</strong> {extractedData.time_since_start}
            </div>
          )}
          
          {extractedData.evolution_of_symptoms && (
            <div className="result-item">
              <strong>Symptom Evolution:</strong> {extractedData.evolution_of_symptoms}
            </div>
          )}
          
          {extractedData.medical_checks && (
            <div className="result-item">
              <strong>Medical Checks:</strong> {extractedData.medical_checks.join(', ')}
            </div>
          )}
        </div>

        {/* 🆕 NEW WEB RESEARCH RESULTS SECTION */}
        {Object.keys(webResearchResults).length > 0 && (
          <div className="results-section" style={{ marginTop: '30px' }}>
            <h3 style={{ color: '#d4d4d8', marginBottom: '20px' }}>Medical Research Results:</h3>
            
            {webResearchResults.possible_conditions && webResearchResults.possible_conditions.length > 0 && (
              <div className="result-item">
                <strong>Possible Conditions:</strong> {webResearchResults.possible_conditions.join(', ')}
              </div>
            )}
            
            {webResearchResults.symptom_explanations && webResearchResults.symptom_explanations.length > 0 && (
              <div className="result-item">
                <strong>Symptom Explanations:</strong>
                <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                  {webResearchResults.symptom_explanations.map((explanation, index) => (
                    <li key={index} style={{ marginBottom: '4px' }}>{explanation}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {webResearchResults.red_flags && webResearchResults.red_flags.length > 0 && (
              <div className="result-item" style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', padding: '16px', borderRadius: '8px' }}>
                <strong style={{ color: '#dc2626' }}>⚠️ Warning Signs:</strong>
                <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                  {webResearchResults.red_flags.map((flag, index) => (
                    <li key={index} style={{ marginBottom: '4px', color: '#dc2626' }}>{flag}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {webResearchResults.search_summary && (
              <div className="result-item">
                <strong>Research Summary:</strong> {webResearchResults.search_summary}
              </div>
            )}
            
            {webResearchResults.confidence_level && (
              <div className="result-item">
                <strong>Confidence Level:</strong> 
                <span style={{ 
                  marginLeft: '8px',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  backgroundColor: webResearchResults.confidence_level === 'high' ? '#dcfce7' : 
                                 webResearchResults.confidence_level === 'medium' ? '#fef3c7' : '#fee2e2',
                  color: webResearchResults.confidence_level === 'high' ? '#166534' : 
                         webResearchResults.confidence_level === 'medium' ? '#92400e' : '#dc2626'
                }}>
                  {webResearchResults.confidence_level}
                </span>
              </div>
            )}
            
            {webResearchResults.additional_questions && webResearchResults.additional_questions.length > 0 && (
              <div className="result-item">
                <strong>Additional Questions to Consider:</strong>
                <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                  {webResearchResults.additional_questions.map((question, index) => (
                    <li key={index} style={{ marginBottom: '4px' }}>{question}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <button 
          onClick={resetConversation}
          className="submit-button"
          style={{ marginTop: '20px' }}
        >
          Start New Analysis
        </button>
      </div>
    );
  }

  if (showExtractedData) {
    return (
      <div className="container">
        <div className="header">
          <div className="logo-container">
            <div className="logo">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
              </svg>
            </div>
            <h1>Data Extracted</h1>
          </div>
          <p className="subtitle">We've gathered your symptom information</p>
        </div>

        <div className="results-section">
          <h3 style={{ color: '#d4d4d8', marginBottom: '20px' }}>Extracted Information:</h3>
          
          {extractedData.parsed_symptoms && (
            <div className="result-item">
              <strong>Symptoms:</strong> {extractedData.parsed_symptoms.join(', ')}
            </div>
          )}
          
          {extractedData.body_parts_affected && (
            <div className="result-item">
              <strong>Body Parts Affected:</strong> {extractedData.body_parts_affected.join(', ')}
            </div>
          )}
          
          {extractedData.time_since_start && (
            <div className="result-item">
              <strong>Timeline:</strong> {extractedData.time_since_start}
            </div>
          )}
          
          {extractedData.evolution_of_symptoms && (
            <div className="result-item">
              <strong>Symptom Evolution:</strong> {extractedData.evolution_of_symptoms}
            </div>
          )}
          
          {extractedData.medical_checks && (
            <div className="result-item">
              <strong>Medical Checks:</strong> {extractedData.medical_checks.join(', ')}
            </div>
          )}
        </div>

        <button 
          onClick={handleWebResearch}
          className={`submit-button ${isLoading ? 'loading' : ''}`}
          disabled={isLoading}
          style={{ marginTop: '20px' }}
        >
          <div className="loading-spinner"></div>
          <svg className="submit-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
          </svg>
          <span>{isLoading ? 'Researching...' : 'Start Medical Research'}</span>
        </button>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="header">
        <div className="logo-container">
          <div className="logo">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
            </svg>
          </div>
          <h1>DiagnosticAI</h1>
        </div>
        <p className="subtitle">AI-powered symptom analysis using medical research</p>
      </div>

      {followUpQuestions.length === 0 ? (
        // Initial symptom input form
        <form onSubmit={handleSubmit}>
          <div className="form-section">
            <label htmlFor="symptoms" className="input-label">Describe your symptoms</label>
            <div className="input-wrapper">
              <textarea 
                id="symptoms" 
                name="symptoms" 
                className="textarea-field"
                placeholder="Tell me about your symptoms - when they started, how they feel, what makes them better or worse..."
                maxLength="1000"
                value={symptoms}
                onChange={handleInputChange}
                required
              />
              <div className="char-counter">
                <span style={{ color: charCount > 800 ? '#ef4444' : '#71717a' }}>
                  {charCount}
                </span>/1000
              </div>
            </div>
          </div>

          <button type="submit" className={`submit-button ${isLoading ? 'loading' : ''}`} disabled={isLoading}>
            <div className="loading-spinner"></div>
            <svg className="submit-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path>
            </svg>
            <span>{isLoading ? 'Analyzing...' : 'Analyze Symptoms'}</span>
          </button>
        </form>
      ) : (
        // Follow-up questions form
        <form onSubmit={handleFollowUpSubmit}>
          <div className="form-section">
            <h3 style={{ color: '#d4d4d8', marginBottom: '20px' }}>Please provide additional information:</h3>
            
            {followUpQuestions.map((question, index) => (
              <div key={index} className="question-item" style={{ marginBottom: '24px' }}>
                <label className="input-label">{question}</label>
                <div className="input-wrapper">
                  <textarea
                    className="textarea-field"
                    style={{ minHeight: '80px' }}
                    placeholder="Your answer..."
                    value={questionAnswers[index] || ''}
                    onChange={(e) => handleQuestionAnswerChange(index, e.target.value)}
                    required
                  />
                </div>
              </div>
            ))}
          </div>

          <button type="submit" className={`submit-button ${isLoading ? 'loading' : ''}`} disabled={isLoading}>
            <div className="loading-spinner"></div>
            <svg className="submit-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path>
            </svg>
            <span>{isLoading ? 'Processing...' : 'Submit Answers'}</span>
          </button>
        </form>
      )}

      <div className="features-grid">
        <div className="feature-card">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
          <div className="feature-title">Research</div>
        </div>
        <div className="feature-card">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
          </svg>
          <div className="feature-title">Instant</div>
        </div>
        <div className="feature-card">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
          </svg>
          <div className="feature-title">Secure</div>
        </div>
        <div className="feature-card">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l9-5-9-5-9 5 9 5z"></path>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z"></path>
          </svg>
          <div className="feature-title">Evidence</div>
        </div>
      </div>

      <div className="warning-section">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.664-.833-2.464 0L4.35 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
        </svg>
        <p className="warning-text">
          <strong>Medical Disclaimer:</strong> This AI provides informational content only. Always consult qualified healthcare professionals for medical diagnosis and treatment.
        </p>
      </div>
    </div>
  );
}

export default App;