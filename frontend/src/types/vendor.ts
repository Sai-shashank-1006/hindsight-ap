import type { Decision, ExceptionType, Severity } from './invoice';

export type VendorStatus = 'reliable' | 'inconsistent' | 'new';

export interface VendorException {
  invoice_id: string;
  type: ExceptionType;
  severity: Severity;
  variance_percent: number;
  created_at: string;
}

export interface VendorProfile {
  name: string;
  payment_terms: string;
  historical_prices: number[];
  total_decisions: number;
  approval_rate: number; // 0-1
  status: VendorStatus;
  recent_exceptions: VendorException[];
}

export interface TimelineEvent {
  timestamp: string;
  event: 'processed' | 'decided';
  invoice_id: string;
  detail: string;
  recommendation: Decision | null;
  decision: Decision | null;
  retained: boolean | null;
}
