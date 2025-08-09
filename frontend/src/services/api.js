import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      console.log('Unauthorized access');
    }
    
    return Promise.reject(error);
  }
);

// API endpoints
export const apiEndpoints = {
  analyzeSymptoms: (data) => api.post('/api/analyze', {
    symptoms: data.symptoms,
    thread_id: data.thread_id
  }),

  debugFunctionality: (data) => api.post('/api/research-debug', {
    symptom: data.symptom
  }),

  webResearch: (data) => api.post('/api/web-research', {
    thread_id: data.thread_id
  })
};

export default api;