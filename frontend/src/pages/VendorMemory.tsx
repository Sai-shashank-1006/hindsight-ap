import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, History, Search, SearchX, TriangleAlert } from 'lucide-react';
import BentoCard from '../components/common/BentoCard';
import EmptyState from '../components/common/EmptyState';
import ErrorAlert from '../components/common/ErrorAlert';
import GradientButton from '../components/common/GradientButton';
import LoadingSpinner from '../components/common/LoadingSpinner';
import VendorCard from '../components/vendor/VendorCard';
import VendorStats from '../components/vendor/VendorStats';
import VendorTimeline from '../components/vendor/VendorTimeline';
import { useVendorMemory, useVendors } from '../hooks/useVendorMemory';
import { SEVERITY_META, VENDOR_STATUS_META } from '../utils/constants';
import { cx, formatDateTime, formatVariance, humanize, initials } from '../utils/formatters';
import type { VendorStatus } from '../types';

type Filter = 'all' | VendorStatus;
const FILTERS: Filter[] = ['all', 'reliable', 'inconsistent', 'new'];

function VendorList() {
  const { vendors, loading, error, refresh } = useVendors();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');

  const needle = query.trim().toLowerCase();
  const shown = vendors.filter((vendor) => (filter === 'all' || vendor.status === filter) && vendor.name.toLowerCase().includes(needle));
  const count = (value: Filter) => (value === 'all' ? vendors.length : vendors.filter((vendor) => vendor.status === value).length);
  const learned = vendors.filter((vendor) => vendor.total_decisions > 0).length;

  let body;
  if (loading) {
    body = <LoadingSpinner message="Loading vendor profiles…" />;
  } else if (error && vendors.length === 0) {
    body = <ErrorAlert error={error} title="Couldn't load vendors" onRetry={() => void refresh()} />;
  } else if (vendors.length === 0) {
    body = (
      <EmptyState
        mascot="firstDay"
        title="No vendor data yet"
        action={<GradientButton to="/review">Review invoices</GradientButton>}
      />
    );
  } else {
    body = (
      <>
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <label className="relative block w-full lg:max-w-sm">
            <span className="sr-only">Search vendors</span>
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search vendors"
              className="h-11 w-full rounded-xl border border-slate-300 bg-white pl-10 pr-3.5 text-sm shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </label>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
            {FILTERS.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                aria-pressed={filter === value}
                className={cx(
                  'rounded-full px-3.5 py-1.5 text-sm font-medium transition-all',
                  filter === value ? 'bg-slate-900 text-white shadow-sm' : 'bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50',
                )}
              >
                {value === 'all' ? 'All' : VENDOR_STATUS_META[value].label} <span className="tabular opacity-70">{count(value)}</span>
              </button>
            ))}
          </div>
        </div>

        {shown.length === 0 ? (
          <EmptyState compact icon={SearchX} title="No vendors match" description="Try another name or status." />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {shown.map((vendor) => (
              <VendorCard key={vendor.name} vendor={vendor} />
            ))}
          </div>
        )}
      </>
    );
  }

  return (
    <div className="mx-auto max-w-7xl animate-fade-in">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Vendor memory</h1>
        <p className="mt-2 text-slate-600">
          What the agent has learned, vendor by vendor. Memory never crosses vendors.
          {vendors.length > 0 && (
            <span className="text-slate-500">
              {' '}
              {learned} of {vendors.length} vendors have human decisions on file.
            </span>
          )}
        </p>
      </header>
      {body}
    </div>
  );
}

function VendorDetail({ name }: { name: string }) {
  const { profile, timeline, loading, error, notFound, refresh } = useVendorMemory(name);

  let body;
  if (loading) {
    body = <LoadingSpinner message={`Loading ${name}…`} />;
  } else if (notFound) {
    body = (
      <EmptyState
        mascot="lost"
        title={`No vendor named “${name}”`}
        description="It has no profile and no processed invoices."
        action={<GradientButton to="/vendors">All vendors</GradientButton>}
      />
    );
  } else if (error || !profile) {
    body = <ErrorAlert error={error ?? 'No data returned'} title="Couldn't load this vendor" onRetry={() => void refresh()} />;
  } else {
    const status = VENDOR_STATUS_META[profile.status];
    body = (
      <>
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 text-lg font-bold text-white shadow-lg">
              {initials(profile.name)}
            </span>
            <div className="min-w-0">
              <h1 className="truncate text-3xl font-bold tracking-tight text-slate-900">{profile.name}</h1>
              <p className="mt-1 text-sm text-slate-600">Payment terms: {profile.payment_terms}</p>
            </div>
          </div>
          <span className={cx('self-start rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset sm:self-auto', status.badge)}>{status.label}</span>
        </header>

        <VendorStats vendor={profile} />

        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <BentoCard
            className="lg:col-span-2"
            hoverable={false}
            icon={<History className="h-5 w-5" aria-hidden="true" />}
            title="Timeline"
            subtitle="Agent reviews and reviewer decisions, newest first"
          >
            <VendorTimeline events={timeline} />
          </BentoCard>
          <BentoCard hoverable={false} icon={<TriangleAlert className="h-5 w-5" aria-hidden="true" />} title="Recent exceptions">
            {profile.recent_exceptions.length === 0 ? (
              <EmptyState compact icon={TriangleAlert} title="None yet" description={`No exceptions recorded for ${profile.name}.`} />
            ) : (
              <ul className="space-y-3">
                {profile.recent_exceptions.map((exception) => (
                  <li key={`${exception.invoice_id}-${exception.type}`} className="rounded-xl border border-slate-200 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-slate-900">{humanize(exception.type)}</span>
                      <span className={cx('rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset', SEVERITY_META[exception.severity].badge)}>
                        {SEVERITY_META[exception.severity].label}
                      </span>
                    </div>
                    <p className="tabular mt-1 text-xs text-slate-500">
                      <span className="font-mono">{exception.invoice_id}</span> · {formatVariance(exception.variance_percent)} ·{' '}
                      {formatDateTime(exception.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <GradientButton variant="secondary" size="sm" to="/review" fullWidth className="mt-5">
              Review invoices
            </GradientButton>
          </BentoCard>
        </div>
      </>
    );
  }

  return (
    <div className="mx-auto max-w-7xl animate-fade-in">
      <Link to="/vendors" className="mb-6 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-600 hover:text-slate-900">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All vendors
      </Link>
      {body}
    </div>
  );
}

export default function VendorMemory() {
  const { name } = useParams();
  // Keyed so switching vendors starts from a clean loading state.
  return name ? <VendorDetail key={name} name={name} /> : <VendorList />;
}
