import { EXCEPTION_LABELS } from './constants';
import type { ExceptionType, HealthStatus } from '../types';

const LOCALE = 'en-IN';

/** Joins class names, skipping empty ones. */
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

/** ₹550 for whole rupees, ₹550.50 otherwise, with Indian digit grouping (₹1,23,456). */
export function formatCurrency(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return '—';
  const whole = Number.isInteger(amount);
  return new Intl.NumberFormat(LOCALE, {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 2 }).format(value);
}

/** A 0–1 fraction as a percentage: 0.94 → "94%". */
export function formatPercent(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** A variance already in percent: 10 → "10.0%". */
export function formatVariance(percent: number): string {
  return `${percent.toFixed(1)}%`;
}

function toDate(value: string): Date {
  // Date-only strings are calendar dates, not UTC midnight: don't let the time zone shift them.
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]));
  return new Date(value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(LOCALE, { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(LOCALE, { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}

/** Today's date in the browser's time zone, as YYYY-MM-DD (the format the backend accepts). */
export function todayIso(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** "just now", "5 min ago", "3 h ago", then a date. */
export function formatRelativeTime(value: string | null | undefined, now: Date = new Date()): string {
  if (!value) return '—';
  const date = toDate(value);
  const seconds = Math.round((now.getTime() - date.getTime()) / 1000);
  if (Number.isNaN(seconds)) return value;
  if (seconds < 45) return 'just now';
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)} h ago`;
  return formatDate(value);
}

/** "ABC Pharma" → "AP". */
export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('');
}

/** "PRICE_MISMATCH" → "Price mismatch". */
export function humanize(value: string): string {
  if (value in EXCEPTION_LABELS) return EXCEPTION_LABELS[value as ExceptionType];
  const words = value.replace(/_/g, ' ').toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export type SystemTone = 'live' | 'degraded' | 'offline' | 'checking';

/** One word for the whole system: Live only when the API, Groq and Hindsight are all usable. */
export function describeHealth(
  health: HealthStatus | null,
  error: string | null,
  checking: boolean,
): { tone: SystemTone; label: string; detail: string } {
  if (!health && checking) return { tone: 'checking', label: 'Checking…', detail: 'Contacting the API' };
  if (!health) return { tone: 'offline', label: 'Offline', detail: error ?? 'The API is unreachable' };
  const problems = [
    health.hindsight !== 'reachable' && `Hindsight ${health.hindsight}`,
    health.groq !== 'configured' && 'Groq not configured',
  ].filter(Boolean);
  if (problems.length) return { tone: 'degraded', label: 'Degraded', detail: problems.join(' · ') };
  return { tone: 'live', label: 'Live', detail: `Groq and Hindsight connected (bank ${health.bank_id ?? '—'})` };
}

/** Price mismatches compare rupees; quantity mismatches compare units. */
export function formatExceptionValue(type: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return type === 'QUANTITY_MISMATCH' ? `${formatNumber(value)} units` : formatCurrency(value);
}
