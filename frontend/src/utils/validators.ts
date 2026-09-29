// Client-side validation. It mirrors the backend's rules so problems show next to the field;
// the backend still validates everything (422 with {"error": ...}).

import { DECISIONS, REASON_MAX_LENGTH } from './constants';
import type { Decision, ProcessInvoiceRequest } from '../types';

export interface InvoiceFormValues {
  invoice_id: string;
  vendor: string;
  invoice_price: string;
  quantity: string;
  invoice_date: string;
  po_price: string;
}

export type FieldErrors = Partial<Record<keyof InvoiceFormValues, string>>;

export const EMPTY_INVOICE_FORM: InvoiceFormValues = {
  invoice_id: '',
  vendor: '',
  invoice_price: '',
  quantity: '',
  invoice_date: '',
  po_price: '',
};

/** YYYY-MM-DD and a real calendar date (no 2026-02-30). */
export function isIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function positiveNumber(raw: string): number | null {
  const value = Number(raw.trim().replace(/[₹,\s]/g, ''));
  return raw.trim() !== '' && Number.isFinite(value) && value > 0 ? value : null;
}

export function validateInvoiceForm(values: InvoiceFormValues): { errors: FieldErrors; invoice: ProcessInvoiceRequest | null } {
  const errors: FieldErrors = {};
  const invoiceId = values.invoice_id.trim();
  const vendor = values.vendor.trim().replace(/\s+/g, ' ');
  const price = positiveNumber(values.invoice_price);
  const quantity = positiveNumber(values.quantity);
  const poPrice = values.po_price.trim() ? positiveNumber(values.po_price) : null;

  if (!invoiceId) errors.invoice_id = 'Invoice ID is required';
  if (!vendor) errors.vendor = 'Vendor is required';
  if (price === null) errors.invoice_price = 'Enter a price above zero';
  if (quantity === null || !Number.isInteger(quantity)) errors.quantity = 'Enter a whole number of units above zero';
  if (!isIsoDate(values.invoice_date)) errors.invoice_date = 'Use a valid date (YYYY-MM-DD)';
  if (values.po_price.trim() && poPrice === null) errors.po_price = 'Leave empty or enter a price above zero';

  if (Object.keys(errors).length > 0) return { errors, invoice: null };
  return {
    errors,
    invoice: {
      invoice_id: invoiceId,
      vendor,
      invoice_price: price as number,
      quantity: quantity as number,
      invoice_date: values.invoice_date,
      ...(poPrice !== null ? { po_price: poPrice } : {}),
    },
  };
}

export function validateDecision(decision: Decision | null): string | null {
  return decision && DECISIONS.includes(decision) ? null : 'Choose approve, reject or needs review';
}

export function validateReason(reason: string): string | null {
  const trimmed = reason.trim();
  if (!trimmed) return 'A reason is required: it is what Hindsight will remember';
  if (trimmed.length > REASON_MAX_LENGTH) return `Keep the reason under ${REASON_MAX_LENGTH} characters`;
  return null;
}

function toFormValues(raw: Record<string, unknown>): InvoiceFormValues {
  const text = (key: string) => (raw[key] === undefined || raw[key] === null ? '' : String(raw[key]));
  return {
    invoice_id: text('invoice_id'),
    vendor: text('vendor'),
    invoice_price: text('invoice_price'),
    quantity: text('quantity'),
    invoice_date: text('invoice_date'),
    po_price: text('po_price'),
  };
}

/** A JSON file with one invoice or a list of them. Each is validated like the form. */
export function parseInvoiceJson(content: string): { invoices: ProcessInvoiceRequest[]; error: string | null } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return { invoices: [], error: 'The file is not valid JSON' };
  }
  const items = Array.isArray(parsed) ? parsed : [parsed];
  if (items.length === 0) return { invoices: [], error: 'The file contains no invoices' };

  const invoices: ProcessInvoiceRequest[] = [];
  for (const [index, item] of items.entries()) {
    if (typeof item !== 'object' || item === null || Array.isArray(item)) {
      return { invoices: [], error: `Item ${index + 1} is not an invoice object` };
    }
    const { errors, invoice } = validateInvoiceForm(toFormValues(item as Record<string, unknown>));
    if (!invoice) {
      const [field, message] = Object.entries(errors)[0] ?? ['invoice', 'is invalid'];
      return { invoices: [], error: `Invoice ${index + 1}: ${field} (${message})` };
    }
    invoices.push(invoice);
  }
  return { invoices, error: null };
}
