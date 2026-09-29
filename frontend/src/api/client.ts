import axios, { type AxiosError, type AxiosInstance } from 'axios';
import { API_BASE_URL, REQUEST_TIMEOUT_MS } from '../utils/constants';
import type { ApiError, ApiErrorBody } from '../types';

const client: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: REQUEST_TIMEOUT_MS,
});

function readToken(): string | null {
  try {
    return window.localStorage.getItem('auth_token');
  } catch {
    return null; // storage can be blocked (private mode, strict settings)
  }
}

client.interceptors.request.use((config) => {
  const token = readToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Every failure becomes {status, code, message}, whatever caused it. */
export function toApiError(error: unknown): ApiError {
  if (axios.isCancel(error)) return { code: 'CANCELLED', message: 'Request cancelled', cancelled: true };
  if (!axios.isAxiosError(error)) {
    return { code: 'UNKNOWN_ERROR', message: error instanceof Error ? error.message : 'Unknown error' };
  }
  const axiosError = error as AxiosError<ApiErrorBody>;
  const status = axiosError.response?.status;
  const body = axiosError.response?.data;
  if (body && typeof body === 'object' && 'error' in body && body.error?.message) {
    return { status, code: body.error.code, message: body.error.message };
  }
  if (axiosError.code === 'ECONNABORTED' || axiosError.code === 'ETIMEDOUT') {
    return { status, code: 'TIMEOUT', message: 'The server took too long to answer. Try again.' };
  }
  if (!axiosError.response) {
    const where = API_BASE_URL || window.location.origin;
    return { code: 'NETWORK_ERROR', message: `Can't reach the Hindsight AP API at ${where}. Is the backend running?` };
  }
  return { status, code: `HTTP_${status}`, message: `Request failed (HTTP ${status})` };
}

client.interceptors.response.use(
  (response) => response.data,
  (error: unknown) => {
    const apiError = toApiError(error);
    if (import.meta.env.DEV && !apiError.cancelled) console.error('API error:', apiError);
    return Promise.reject(apiError);
  },
);

export function isCancelled(error: unknown): boolean {
  return typeof error === 'object' && error !== null && (error as ApiError).cancelled === true;
}

export function errorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null && typeof (error as ApiError).message === 'string') {
    return (error as ApiError).message;
  }
  return fallback;
}

export default client;
