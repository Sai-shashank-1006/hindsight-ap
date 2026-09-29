import { useMemo, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CircleCheck, FilePlus2, Inbox, ListChecks, Play, ScanSearch } from 'lucide-react';
import BentoCard from '../components/common/BentoCard';
import EmptyState from '../components/common/EmptyState';
import ErrorAlert from '../components/common/ErrorAlert';
import GradientButton from '../components/common/GradientButton';
import LoadingSpinner from '../components/common/LoadingSpinner';
import DecisionForm from '../components/invoice/DecisionForm';
import ExceptionBadge from '../components/invoice/ExceptionBadge';
import HindsightMemoriesCard from '../components/invoice/HindsightMemoriesCard';
import InvoiceDetailsCard from '../components/invoice/InvoiceDetailsCard';
import InvoiceUpload from '../components/invoice/InvoiceUpload';
import RecommendationCard from '../components/invoice/RecommendationCard';
import { useInvoice, useInvoiceQueue } from '../hooks/useInvoice';
import { useVendors } from '../hooks/useVendorMemory';
import { QUEUE_STATUS_META } from '../utils/constants';
import { cx, formatCurrency } from '../utils/formatters';
import type {
  Decision,
  ProcessInvoiceRequest,
  QueueStatus,
  QueuedInvoice,
  RecommendationResult,
  StoreDecisionResponse,
} from '../types';

type Mode = 'queue' | 'manual';

/** The request body for a queued invoice: everything but its queue status. */
function toRequest(invoice: QueuedInvoice): ProcessInvoiceRequest {
  const { invoice_id, vendor, invoice_price, quantity, invoice_date, po_price, po_id, invoice_total, item } = invoice;
  return { invoice_id, vendor, invoice_price, quantity, invoice_date, po_price, po_id, invoice_total, item };
}

function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  const options: { id: Mode; label: string; icon: ReactNode }[] = [
    { id: 'queue', label: 'Queue', icon: <ListChecks className="h-4 w-4" aria-hidden="true" /> },
    { id: 'manual', label: 'Enter manually', icon: <FilePlus2 className="h-4 w-4" aria-hidden="true" /> },
  ];
  return (
    <div role="tablist" aria-label="Review mode" className="inline-flex self-start rounded-xl bg-slate-200/60 p-1 sm:self-auto">
      {options.map(({ id, label, icon }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={mode === id}
          onClick={() => onChange(id)}
          className={cx(
            'inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold transition-all',
            mode === id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900',
          )}
        >
          {icon}
          {label}
        </button>
      ))}
    </div>
  );
}

function QueueStrip({ invoices, currentId, onSelect }: { invoices: QueuedInvoice[]; currentId?: string; onSelect: (id: string) => void }) {
  return (
    <nav aria-label="Invoice queue" className="scroll-thin -mx-1 mb-6 flex gap-2 overflow-x-auto px-1 pb-2">
      {invoices.map((invoice, index) => {
        const active = invoice.invoice_id === currentId;
        const status = QUEUE_STATUS_META[invoice.status];
        return (
          <button
            key={invoice.invoice_id}
            type="button"
            onClick={() => onSelect(invoice.invoice_id)}
            aria-current={active ? 'true' : undefined}
            className={cx(
              'flex min-w-[11.5rem] shrink-0 flex-col rounded-xl border px-3 py-2.5 text-left transition-all duration-200',
              active
                ? 'border-blue-500 bg-white shadow-md ring-2 ring-blue-500/20'
                : 'border-slate-200 bg-white/70 hover:border-slate-300 hover:bg-white',
            )}
          >
            <span className="flex items-center justify-between gap-2 text-xs text-slate-500">
              <span>#{index + 1}</span>
              <span className="inline-flex items-center gap-1">
                <span className={cx('h-1.5 w-1.5 rounded-full', status.dot)} aria-hidden="true" />
                {status.label}
              </span>
            </span>
            <span className="mt-1 font-mono text-sm font-semibold text-slate-900">{invoice.invoice_id}</span>
            <span className="truncate text-xs text-slate-600">
              {invoice.vendor} · {formatCurrency(invoice.invoice_price)}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

interface WorkspaceProps {
  invoice: ProcessInvoiceRequest;
  status?: QueueStatus;
  result: RecommendationResult | null;
  outcome: StoreDecisionResponse | null;
  processing: boolean;
  storing: boolean;
  onRun?: () => void;
  onSubmit: (decision: Decision, reason: string) => Promise<unknown>;
  onNext: () => void;
  nextLabel: string;
  onEditAgain: () => void;
}

/** One invoice: ready to run, or the agent's result with the decision form beside it. */
function Workspace({ invoice, status, result, outcome, processing, storing, onRun, onSubmit, onNext, nextLabel, onEditAgain }: WorkspaceProps) {
  if (!result) {
    return (
      <div className="grid gap-6 lg:grid-cols-5">
        <InvoiceDetailsCard invoice={invoice} status={status} className="lg:col-span-3" />
        <BentoCard className="lg:col-span-2" hoverable={false} gradient gradientFrom="from-blue-50" gradientTo="to-violet-50">
          <ScanSearch className="h-8 w-8 text-violet-600" aria-hidden="true" />
          <h2 className="mt-3 text-lg font-semibold text-slate-900">Ready when you are</h2>
          <p className="mt-1 text-sm text-slate-600">The agent will:</p>
          <ol className="mt-3 space-y-2 text-sm text-slate-700">
            <li className="flex gap-2">
              <span className="font-semibold text-violet-600">1.</span> Check the invoice against its purchase order
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-violet-600">2.</span> Recall {invoice.vendor}'s past decisions from Hindsight
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-violet-600">3.</span> Recommend, approving only with a verified precedent
            </li>
          </ol>
          <GradientButton
            size="lg"
            fullWidth
            className="mt-6"
            onClick={onRun}
            loading={processing}
            loadingText="Checking rules, memory and model…"
            icon={<Play className="h-4 w-4" aria-hidden="true" />}
          >
            Run the agent
          </GradientButton>
          <p className="mt-3 text-center text-xs text-slate-500">Nothing is stored until you decide.</p>
        </BentoCard>
      </div>
    );
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <div className="space-y-6 lg:sticky lg:top-24">
        <InvoiceDetailsCard invoice={invoice} status={status} />
        <BentoCard
          hoverable={false}
          title="Rule engine"
          subtitle={result.exceptions.length ? `${result.exceptions.length} exception${result.exceptions.length === 1 ? '' : 's'} against the PO record` : 'Checked against the PO record'}
        >
          {result.exceptions.length > 0 ? (
            <div className="space-y-3">
              {result.exceptions.map((exception) => (
                <ExceptionBadge key={exception.type} exception={exception} detailed />
              ))}
            </div>
          ) : (
            <EmptyState compact tone="success" icon={CircleCheck} title="Matches the purchase order" description="No price or quantity exception. Confirm it with a decision." />
          )}
        </BentoCard>
      </div>

      <div className="space-y-6">
        <RecommendationCard result={result} />
        {result.exceptions.length > 0 && (
          <HindsightMemoriesCard
            memories={result.hindsight_memories}
            reflection={result.reflection}
            memoryStatus={result.memory_status}
            vendor={result.vendor}
          />
        )}
        <DecisionForm
          key={result.invoice_id}
          vendor={result.vendor}
          recommendation={result.recommendation}
          onSubmit={onSubmit}
          submitting={storing}
          outcome={outcome}
          onNext={onNext}
          nextLabel={nextLabel}
          onEditAgain={onEditAgain}
        />
      </div>
    </div>
  );
}

export default function InvoiceReview() {
  const [params, setParams] = useSearchParams();
  const mode: Mode = params.get('mode') === 'manual' ? 'manual' : 'queue';
  const selectedId = params.get('invoice');
  const queue = useInvoiceQueue();
  const { vendors } = useVendors();
  const review = useInvoice();

  // Queue mode shows the invoice named in the URL, else the first one without a human decision.
  const current = useMemo(() => {
    if (mode !== 'queue') return null;
    return (
      queue.invoices.find((invoice) => invoice.invoice_id === selectedId) ??
      queue.invoices.find((invoice) => invoice.status !== 'decided') ??
      null
    );
  }, [mode, queue.invoices, selectedId]);

  const shown: ProcessInvoiceRequest | null = mode === 'queue' ? (current ? toRequest(current) : null) : review.invoice;
  const result = review.result && shown && review.result.invoice_id === shown.invoice_id ? review.result : null;
  const nextPending = queue.invoices.find((invoice) => invoice.status !== 'decided' && invoice.invoice_id !== shown?.invoice_id);
  const decidedCount = queue.invoices.filter((invoice) => invoice.status === 'decided').length;
  const position = current ? queue.invoices.findIndex((invoice) => invoice.invoice_id === current.invoice_id) + 1 : 0;

  const setMode = (next: Mode) => {
    review.reset();
    setParams(next === 'manual' ? { mode: 'manual' } : {});
  };

  const selectInvoice = (invoiceId: string) => {
    review.reset();
    setParams({ invoice: invoiceId });
  };

  const runAgent = async () => {
    if (!current) return;
    // Pin the invoice in the URL so the screen stays on it after its status changes.
    setParams({ invoice: current.invoice_id }, { replace: true });
    const data = await review.processInvoice(toRequest(current));
    if (data) void queue.refresh();
  };

  const submitDecision = async (decision: Decision, reason: string) => {
    if (!result) return null;
    const response = await review.storeDecision(result.invoice_id, decision, reason);
    if (response) void queue.refresh();
    return response;
  };

  const goToNext = () => {
    review.reset();
    setParams(nextPending ? { invoice: nextPending.invoice_id } : {});
  };

  let content: ReactNode;
  if (mode === 'manual') {
    content =
      result && shown ? (
        <Workspace
          invoice={shown}
          result={result}
          outcome={review.outcome}
          processing={review.processing}
          storing={review.storing}
          onSubmit={submitDecision}
          onNext={review.reset}
          nextLabel="Enter another invoice"
          onEditAgain={review.clearOutcome}
        />
      ) : (
        <InvoiceUpload
          onProcess={(invoice) => void review.processInvoice(invoice)}
          processing={review.processing}
          vendorNames={vendors.map((vendor) => vendor.name)}
        />
      );
  } else if (queue.loading) {
    content = <LoadingSpinner message="Loading the invoice queue…" />;
  } else if (queue.error && queue.invoices.length === 0) {
    content = <ErrorAlert error={queue.error} title="Couldn't load the invoice queue" onRetry={() => void queue.refresh()} />;
  } else if (queue.invoices.length === 0) {
    content = (
      <EmptyState
        icon={Inbox}
        title="The queue is empty"
        description="The backend has no invoices in its queue file (DATA_DIR / INVOICES_FILE). You can still enter one by hand."
        action={<GradientButton onClick={() => setMode('manual')}>Enter an invoice</GradientButton>}
      />
    );
  } else {
    content = (
      <>
        <QueueStrip invoices={queue.invoices} currentId={current?.invoice_id} onSelect={selectInvoice} />
        {current && shown ? (
          <Workspace
            invoice={shown}
            status={current.status}
            result={result}
            outcome={review.outcome}
            processing={review.processing}
            storing={review.storing}
            onRun={() => void runAgent()}
            onSubmit={submitDecision}
            onNext={goToNext}
            nextLabel={nextPending ? `Next invoice: ${nextPending.invoice_id}` : 'Finish the queue'}
            onEditAgain={review.clearOutcome}
          />
        ) : (
          <EmptyState
            tone="success"
            icon={CircleCheck}
            title="All invoices reviewed"
            description="Every invoice in the queue has a human decision. The dashboard and vendor pages show what was learned."
            action={
              <>
                <GradientButton to="/">Back to dashboard</GradientButton>
                <GradientButton variant="secondary" to="/vendors">
                  Vendor memory
                </GradientButton>
              </>
            }
          />
        )}
      </>
    );
  }

  return (
    <div className="mx-auto max-w-7xl animate-fade-in">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          {mode === 'queue' && queue.invoices.length > 0 && (
            <span className="mb-3 inline-flex rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">
              {position > 0 ? `Invoice ${position} of ${queue.invoices.length}` : `${queue.invoices.length} invoices`} ·{' '}
              {decidedCount} decided
            </span>
          )}
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Invoice review</h1>
          <p className="mt-2 text-slate-600">Run the agent, check its evidence, then decide. Your reason becomes Hindsight memory.</p>
        </div>
        <ModeSwitch mode={mode} onChange={setMode} />
      </header>

      <ErrorAlert error={review.error} onDismiss={review.clearError} className="mb-6" />
      {content}
    </div>
  );
}
