import { useCallback, useEffect, useRef, useState } from 'react';
import { invoiceAPI } from '../api/endpoints';
import { errorMessage, isCancelled } from '../api/client';
import { QUEUE_LIMIT } from '../utils/constants';
import type {
  Decision,
  ProcessInvoiceRequest,
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
      if (current === generation.current) setOutcome(response);
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

/** The invoice queue with each invoice's status: pending, processed (awaiting a decision) or decided. */
export const useInvoiceQueue = (limit: number = QUEUE_LIMIT) => {
  const [state, setState] = useState<{ invoices: QueuedInvoice[]; loading: boolean; error: string | null }>({
    invoices: [],
    loading: true,
    error: null,
  });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    invoiceAPI.getInvoices(limit, controller.signal).then(
      (invoices) => setState({ invoices, loading: false, error: null }),
      (err: unknown) => {
        if (!isCancelled(err)) {
          setState((current) => ({ ...current, loading: false, error: errorMessage(err, 'Failed to load the invoice queue') }));
        }
      },
    );
    return () => controller.abort();
  }, [limit, version]);

  /** Reloads in the background; the current list stays on screen meanwhile. */
  const refresh = useCallback(() => setVersion((current) => current + 1), []);

  return { ...state, refresh };
};
