import client from './client';
import type {
  DashboardData,
  DashboardStats,
  HealthStatus,
  ProcessInvoiceRequest,
  QueuedInvoice,
  RecommendationResult,
  StoreDecisionRequest,
  StoreDecisionResponse,
  TimelineEvent,
  VendorProfile,
} from '../types';

// The response interceptor unwraps bodies, so each call resolves to the payload itself.
const get = <T>(url: string, signal?: AbortSignal) => client.get<T, T>(url, { signal });
const post = <T>(url: string, body: unknown, signal?: AbortSignal) => client.post<T, T>(url, body, { signal });

export const invoiceAPI = {
  /** Rules → recall → reflect → LLM → guardrail. Nothing is stored. */
  processInvoice: (data: ProcessInvoiceRequest, signal?: AbortSignal) =>
    post<RecommendationResult>('/api/v1/invoice/process', data, signal),

  /** Records the human decision and retains it in Hindsight. Check `retained`. */
  storeDecision: (data: StoreDecisionRequest) => post<StoreDecisionResponse>('/api/v1/invoice/store-decision', data),

  /** The next invoice in the queue that hasn't been processed. 404 (queue_empty) when done. */
  getNextInvoice: (signal?: AbortSignal) => get<QueuedInvoice>('/api/v1/invoice/next', signal),

  getInvoices: (limit = 10, signal?: AbortSignal) => get<QueuedInvoice[]>(`/api/v1/invoices?limit=${limit}`, signal),
};

export const dashboardAPI = {
  getDashboard: (signal?: AbortSignal) => get<DashboardData>('/api/v1/dashboard', signal),
  getStats: (signal?: AbortSignal) => get<DashboardStats>('/api/v1/dashboard/stats', signal),
};

export const vendorAPI = {
  getVendorProfile: (vendorName: string, signal?: AbortSignal) =>
    get<VendorProfile>(`/api/v1/vendor/${encodeURIComponent(vendorName)}`, signal),

  getAllVendors: (signal?: AbortSignal) => get<VendorProfile[]>('/api/v1/vendors', signal),

  getVendorTimeline: (vendorName: string, signal?: AbortSignal) =>
    get<TimelineEvent[]>(`/api/v1/vendor/${encodeURIComponent(vendorName)}/timeline`, signal),
};

export const systemAPI = {
  /** Which services are configured and reachable. Pings Hindsight, so poll it rarely. */
  getHealth: (signal?: AbortSignal) => get<HealthStatus>('/health', signal),
};
