import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface UserBackground {
  background: string;
}

export interface JobSubmitResponse {
  job_id: string;
  status: string;
  message: string;
  estimated_time: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  created_at: string;
  updated_at: string;
  error?: string;
}

export const submitJob = async (background: UserBackground, paymentId: string): Promise<JobSubmitResponse> => {
  const response = await api.post<JobSubmitResponse>('/api/submit', background, {
    params: { payment_id: paymentId }
  });
  return response.data;
};

export const getJobStatus = async (jobId: string): Promise<JobStatusResponse> => {
  const response = await api.get<JobStatusResponse>(`/api/status/${jobId}`);
  return response.data;
};

export const getJobResults = async (jobId: string): Promise<string> => {
  const response = await api.get(`/api/results/${jobId}/preview`, {
    responseType: 'text',
  });
  return response.data;
};

export const downloadPDF = async (jobId: string): Promise<Blob> => {
  const response = await api.get(`/api/results/${jobId}/download`, {
    responseType: 'blob',
  });
  return response.data;
};

export interface PaymentVerifyResponse {
  valid: boolean;
  payment_id?: string;
  user_id?: string;
  status?: string;
  reason?: string;
}

export const verifyPayment = async (paymentId: string): Promise<PaymentVerifyResponse> => {
  const response = await api.get<PaymentVerifyResponse>(`/api/payment/verify/${paymentId}`);
  return response.data;
};

export default api;
