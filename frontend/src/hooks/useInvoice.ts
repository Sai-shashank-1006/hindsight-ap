import { useCallback, useEffect, useRef, useState } from 'react';
import { invoiceAPI } from '../api/endpoints';
import { errorMessage, isCancelled } from '../api/client';
import { QUEUE_LIMIT } from '../utils/constants';
import type {
  Decision,
  ProcessInvoiceRequest,
  QueueSummary,
  QueuedInvoice,
  RecommendationResult,
  StoreDecisionResponse,
} from '../types';

/**
 * One invoice through the loop: process it (rules → recall → reflect → LLM → guardrail), then store
 * the human decision. Failures land in `error`; the actions resolve to null instead of throwing.
 */
export const useInvoice = () => {
  const [result, setResult] = useState<RecommendationResult | null>(null);
  const [invoice, setInvoice] = useState<ProcessInvoiceRequest | null>(null);
  const [outcome, setOutcome] = useState<StoreDecisionResponse | null>(null);
  const [decided, setDecided] = useState<Decision | null>(null); // what the human chose, once stored
  const [processing, setProcessing] = useState(false);
  const [storing, setStoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Bumped on every new request and on reset, so a slow answer for an invoice the reviewer has
  // already moved away from is ignored instead of overwriting the screen.
  const generation = useRef(0);

  const processInvoice = useCallback(async (invoiceData: ProcessInvoiceRequest) => {
    const current = ++generation.current;
    setProcessing(true);
    setError(null);
    setOutcome(null);
    setDecided(null);
    try {
      const data = await invoiceAPI.processInvoice(invoiceData);
      if (current !== generation.current) return null;
      setResult(data);
      setInvoice(invoiceData);
      return data;
    } catch (err) {
      if (current === generation.current) setError(errorMessage(err, 'Failed to process the invoice'));
      return null;
    } finally {
      if (current === generation.current) setProcessing(false);
    }
  }, []);

  const storeDecision = useCallback(async (invoiceId: string, decision: Decision, reason: string) => {
    const current = generation.current;
    setStoring(true);
    setError(null);
    try {
      const response = await invoiceAPI.storeDecision({
        invoice_id: invoiceId,
        human_decision: decision,
        human_reason: reason.trim(),
      });
      if (current === generation.current) {
        setOutcome(response);
        setDecided(decision);
      }
      return response;
    } catch (err) {
      if (current === generation.current) setError(errorMessage(err, 'Failed to store the decision'));
      return null;
    } finally {
      if (current === generation.current) setStoring(false);
    }
  }, []);

  const reset = useCallback(() => {
    generation.current += 1;
    setResult(null);
    setInvoice(null);
    setOutcome(null);
    setDecided(null);
    setError(null);
    setProcessing(false);
    setStoring(false);
  }, []);

  const clearError = useCallback(() => setError(null), []);
  /** Back to the decision form, e.g. to resubmit after Hindsight failed to store the memory. */
  const clearOutcome = useCallback(() => setOutcome(null), []);

  return {
    result,
    invoice,
    outcome,
    decided,
    processing,
    storing,
    loading: processing || storing,
    error,
    processInvoice,
    storeDecision,
    reset,
    clearError,
    clearOutcome,
  };
};

interface QueueState {
  invoices: QueuedInvoice[]; // one page, each with its status: pending, processed (awaiting a decision) or decided
  summary: QueueSummary | null; // counts for the whole queue
  offset: number; // the page's first position in the queue
  loading: boolean;
  error: string | null;
}

/**
 * The invoice queue, a page at a time. It opens on the page holding the first invoice that still needs
 * a decision, and then stays on its page when refreshed, so a just-decided invoice stays on screen.
 */
export const useInvoiceQueue = (limit: number = QUEUE_LIMIT) => {
  const [state, setState] = useState<QueueState>({ invoices: [], summary: null, offset: 0, loading: true, error: null });
  const [version, setVersion] = useState(0);
  const page = useRef<number | null>(null); // the page's offset; null: the first open invoice's page

  useEffect(() => {
    const controller = new AbortController();
    invoiceAPI
      .getQueueSummary(controller.signal)
      .then((summary) => {
        const offset = page.current ?? Math.floor((summary.first_open ?? 0) / limit) * limit;
        page.current = offset;
        return invoiceAPI
          .getInvoices(limit, offset, controller.signal)
          .then((invoices) => setState({ invoices, summary, offset, loading: false, error: null }));
      })
      .catch((err: unknown) => {
        if (!isCancelled(err)) {
          setState((current) => ({ ...current, loading: false, error: errorMessage(err, 'Failed to load the invoice queue') }));
        }
      });
    return () => controller.abort();
  }, [limit, version]);

  /** Reloads in the background; the current page stays on screen meanwhile. */
  const refresh = useCallback(() => setVersion((current) => current + 1), []);

  /** Shows the page starting at `offset`, or with null the page holding the first open invoice. */
  const showPage = useCallback((offset: number | null) => {
    page.current = offset;
    setVersion((current) => current + 1);
  }, []);

  return { ...state, limit, refresh, showPage };
};
