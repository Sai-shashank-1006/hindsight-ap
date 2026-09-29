import type { Decision, Invoice } from './invoice';

/** Every backend error body: {"error": {"code", "message"}}. Success bodies are not wrapped. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}

/** What the axios client rejects with, whatever went wrong. */
export interface ApiError {
  status?: number;
  code: string;
  message: string;
  cancelled?: boolean;
}

export type ProcessInvoiceRequest = Invoice;

export interface StoreDecisionRequest {
  invoice_id: string;
  human_decision: Decision;
  human_reason: string;
}

export interface StoreDecisionResponse {
  success: boolean; // false when a memory should have been stored and wasn't
  retained: boolean; // true only when Hindsight confirmed the retain
  memory_id: string | null;
  message: string;
}

export interface HealthStatus {
  groq: 'configured' | 'missing';
  hindsight: 'reachable' | 'unreachable' | 'missing';
  bank_id: string | null;
  groq_model: string;
}
