import type { Decision, EvidenceLevel, ExceptionType, QueueStatus, Severity, VendorStatus } from '../types';

export const APP_NAME = import.meta.env.VITE_APP_NAME || 'Hindsight AP';

/** Backend origin. Empty means "same origin" (the Vite dev proxy forwards /api and /health). */
export const API_BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '');

export const REQUEST_TIMEOUT_MS = 60_000; // a synchronous Hindsight retain can take several seconds
export const DASHBOARD_POLL_MS = 10_000; // the dashboard is served from the local log: polling is free
export const HEALTH_POLL_MS = 60_000; // /health pings Hindsight, so check it rarely
export const QUEUE_LIMIT = 50;
export const REASON_MAX_LENGTH = 1000;

export const DECISIONS: Decision[] = ['APPROVED', 'REJECTED', 'NEEDS_REVIEW'];

export const DECISION_META: Record<Decision, { label: string; action: string; description: string; badge: string; ring: string }> = {
  APPROVED: {
    label: 'Approved',
    action: 'Approve',
    description: 'Pay the invoice as billed',
    badge: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
    ring: 'peer-checked:border-emerald-500 peer-checked:bg-emerald-50 peer-checked:ring-emerald-500',
  },
  REJECTED: {
    label: 'Rejected',
    action: 'Reject',
    description: 'Return the invoice to the vendor',
    badge: 'bg-red-100 text-red-700 ring-red-200',
    ring: 'peer-checked:border-red-500 peer-checked:bg-red-50 peer-checked:ring-red-500',
  },
  NEEDS_REVIEW: {
    label: 'Needs review',
    action: 'Needs review',
    description: 'Hold it for more investigation',
    badge: 'bg-blue-100 text-blue-700 ring-blue-200',
    ring: 'peer-checked:border-blue-500 peer-checked:bg-blue-50 peer-checked:ring-blue-500',
  },
};

export const SEVERITY_META: Record<Severity, { label: string; badge: string; dot: string }> = {
  CRITICAL: { label: 'Critical', badge: 'bg-red-100 text-red-700 ring-red-200', dot: 'bg-red-500' },
  WARNING: { label: 'Warning', badge: 'bg-amber-100 text-amber-800 ring-amber-200', dot: 'bg-amber-500' },
  INFO: { label: 'Info', badge: 'bg-sky-100 text-sky-700 ring-sky-200', dot: 'bg-sky-500' },
};

export const EXCEPTION_LABELS: Record<ExceptionType, string> = {
  PRICE_MISMATCH: 'Price mismatch',
  QUANTITY_MISMATCH: 'Quantity mismatch',
};

/** Mirrors EVIDENCE_MEANING in the backend. APPROVED requires VERIFIED_MATCH. */
export const EVIDENCE_META: Record<EvidenceLevel, { label: string; meaning: string; badge: string }> = {
  VERIFIED_MATCH: {
    label: 'Verified match',
    meaning: 'A reviewer approved this same vendor, exception type and invoiced amount before.',
    badge: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
  },
  VERIFIED_REJECT: {
    label: 'Verified rejection',
    meaning: 'A reviewer rejected this same vendor, exception type and invoiced amount before.',
    badge: 'bg-red-100 text-red-700 ring-red-200',
  },
  CONFLICT: {
    label: 'Conflicting history',
    meaning: 'Reviewers have both approved and rejected this same exception.',
    badge: 'bg-amber-100 text-amber-800 ring-amber-200',
  },
  NO_EVIDENCE: {
    label: 'No verified precedent',
    meaning: 'No human decision on file for this vendor, exception type and amount, so the agent cannot approve.',
    badge: 'bg-slate-100 text-slate-700 ring-slate-200',
  },
  NOT_REQUIRED: {
    label: 'Matches PO',
    meaning: 'The invoice matches its purchase order. A reviewer still confirms it.',
    badge: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
  },
};

export const QUEUE_STATUS_META: Record<QueueStatus, { label: string; dot: string }> = {
  pending: { label: 'Pending', dot: 'bg-slate-300' },
  processed: { label: 'Awaiting decision', dot: 'bg-amber-400' },
  decided: { label: 'Decided', dot: 'bg-emerald-500' },
};

export const VENDOR_STATUS_META: Record<VendorStatus, { label: string; badge: string; description: string }> = {
  reliable: {
    label: 'Reliable',
    badge: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
    description: 'At least 80% of reviewed exceptions were approved',
  },
  inconsistent: {
    label: 'Inconsistent',
    badge: 'bg-amber-100 text-amber-800 ring-amber-200',
    description: 'Reviewers often reject or hold this vendor’s exceptions',
  },
  new: {
    label: 'New',
    badge: 'bg-blue-100 text-blue-700 ring-blue-200',
    description: 'No human decisions yet',
  },
};

/** The pipeline behind every recommendation, in order. Product copy, not data. */
export const LEARNING_LOOP_STEPS = [
  { title: 'Rules', text: 'Invoice checked against its PO record' },
  { title: 'Recall', text: 'Hindsight searched for this vendor’s past decisions' },
  { title: 'Reflect', text: 'Hindsight reasons over that vendor’s history' },
  { title: 'LLM', text: 'Groq drafts a recommendation' },
  { title: 'Guardrail', text: 'Approval only with a verified human precedent' },
  { title: 'Human', text: 'A reviewer decides and gives a reason' },
  { title: 'Retain', text: 'The decision becomes memory for next time' },
];
