// Shapes returned by the FastAPI backend (api.py / app/models.py). Keep in sync with it.

export type Decision = 'APPROVED' | 'REJECTED' | 'NEEDS_REVIEW';
export type ExceptionType = 'PRICE_MISMATCH' | 'QUANTITY_MISMATCH';
export type Severity = 'CRITICAL' | 'WARNING' | 'INFO';
export type EvidenceLevel = 'VERIFIED_MATCH' | 'VERIFIED_REJECT' | 'CONFLICT' | 'NO_EVIDENCE' | 'NOT_REQUIRED';
export type MemoryStatus = 'ok' | 'unavailable';
export type QueueStatus = 'pending' | 'processed' | 'decided';

export interface Invoice {
  invoice_id: string;
  vendor: string;
  invoice_price: number;
  quantity: number;
  invoice_date: string; // YYYY-MM-DD
  po_price?: number | null; // informational: checks always use the PO record
  po_id?: string | null;
  invoice_total?: number | null;
  item?: string | null;
}

export interface QueuedInvoice extends Invoice {
  status: QueueStatus;
}

export interface PurchaseOrder {
  po_id: string;
  vendor: string;
  expected_price: number;
  expected_quantity: number;
  po_date: string;
}

export interface InvoiceException {
  type: ExceptionType;
  severity: Severity;
  expected_value: number;
  actual_value: number;
  variance_percent: number; // absolute, e.g. 10.0 for 10%
  reason: string;
}

/** A vendor-matched decision recalled from Hindsight for this request. */
export interface HindsightMemory {
  text: string; // what Hindsight returned (an extracted fact)
  vendor: string;
  invoice_id: string | null;
  exception_type: string;
  po_price: number | null;
  invoice_price: number | null;
  expected_value: number | null;
  actual_value: number | null;
  decision: Decision;
  human_reason: string;
  created_at: string | null; // ISO 8601
}

export interface RecommendationResult {
  invoice_id: string;
  vendor: string;
  exception_detected: InvoiceException | null; // the most severe one
  exceptions: InvoiceException[];
  hindsight_memories: HindsightMemory[];
  reflection: string | null;
  memory_status: MemoryStatus;
  evidence_level: EvidenceLevel;
  recommendation: Decision;
  confidence: number; // 0-1
  explanation: string;
}

/** A retained decision, as listed on the dashboard (from the local decision log). */
export interface MemorySummary {
  memory_id: string;
  invoice_id: string;
  vendor: string;
  exception_types: string[];
  decision: Decision;
  human_reason: string;
  created_at: string;
}

export interface DashboardData {
  total_processed: number;
  total_exceptions: number;
  approval_rate: number; // 0-1
  active_vendors: number;
  recent_memories: MemorySummary[];
  exception_breakdown: { type: string; count: number }[];
}

export interface DashboardStats {
  total_processed: number;
  total_exceptions: number;
  total_decisions: number;
  memories_retained: number;
  pending_decisions: number;
  approval_rate: number; // 0-1
  active_vendors: number;
}
