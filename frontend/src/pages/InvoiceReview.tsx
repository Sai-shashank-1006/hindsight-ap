import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, CircleCheck, FilePlus2, ListChecks, Play } from 'lucide-react';
import BentoCard from '../components/common/BentoCard';
import EmptyState from '../components/common/EmptyState';
import ErrorAlert from '../components/common/ErrorAlert';
import GradientButton from '../components/common/GradientButton';
import LoadingSpinner from '../components/common/LoadingSpinner';
import MascotMessage from '../components/common/MascotMessage';
import DecisionForm from '../components/invoice/DecisionForm';
import ExceptionBadge from '../components/invoice/ExceptionBadge';
import HindsightMemoriesCard from '../components/invoice/HindsightMemoriesCard';
import InvoiceDetailsCard from '../components/invoice/InvoiceDetailsCard';
import InvoiceUpload from '../components/invoice/InvoiceUpload';
import RecommendationCard from '../components/invoice/RecommendationCard';
import { useInvoice, useInvoiceQueue } from '../hooks/useInvoice';
import { useVendors } from '../hooks/useVendorMemory';
import { QUEUE_STATUS_META } from '../utils/constants';
import { cx, formatCurrency, formatExceptionValue } from '../utils/formatters';
import { PROCESSING_NARRATION, stateForExceptions, stateForResult } from '../utils/mascot';
import type {
  Decision,
  ProcessInvoiceRequest,
  QueueStatus,
  QueueSummary,
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

/** The facts behind the mascot's read of a result, in one line. */
function resultDetail(result: RecommendationResult): string | undefined {
  const count = result.hindsight_memories.length;
  const past = `${count} past decision${count === 1 ? '' : 's'} for ${result.vendor} in Hindsight`;
  switch (stateForResult(result)) {
    case 'recommendApproval':
    case 'knownException':
    case 'knownRejection':
      return past;
    case 'unusual': {
      const exception = result.exception_detected;
      return exception ? `${past}, none at ${formatExceptionValue(exception.type, exception.actual_value)}` : past;
    }
    case 'riskyUnknown':
      return `Nothing in Hindsight for ${result.vendor} yet.`;
    case 'needsReview':
      return 'Reviewers both approved and rejected this same exception before.';
    case 'memoryOffline':
      return 'No history was checked for this invoice.';
    default:
      return undefined;
  }
}

/**
 * While the agent runs, the mascot narrates the pipeline's steps in the order they really happen
 * (rules, then Hindsight recall). It stays on the last step until the answer arrives.
 */
function ProcessingNarration() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setStep((current) => Math.min(current + 1, PROCESSING_NARRATION.length - 1)), 1400);
    return () => window.clearInterval(timer);
  }, []);
  return <MascotMessage key={step} state={PROCESSING_NARRATION[step]} live />;
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

const count = (value: number) => value.toLocaleString('en-IN');

/** Which part of a long queue is on screen, with previous/next page buttons. */
function QueuePager({ summary, offset, shown, limit, onPage }: {
  summary: QueueSummary;
  offset: number;
  shown: number;
  limit: number;
  onPage: (offset: number) => void;
}) {
  const button = 'inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 font-semibold text-slate-600 transition-colors hover:bg-slate-200/70 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-40';
  return (
    <div className="mb-2 flex items-center justify-between gap-3 text-xs text-slate-500">
      <span>
        Invoices {count(offset + 1)}–{count(offset + shown)} of {count(summary.total)} · {count(summary.total - summary.decided)} without a decision
      </span>
      <span className="flex shrink-0 gap-1">
        <button type="button" className={button} disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - limit))}>
          <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Previous
        </button>
        <button type="button" className={button} disabled={offset + limit >= summary.total} onClick={() => onPage(offset + limit)}>
          Next
          <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </span>
    </div>
  );
}

function QueueStrip({ invoices, offset = 0, currentId, onSelect }: {
  invoices: QueuedInvoice[];
  offset?: number; // the page's first position in the queue
  currentId?: string;
  onSelect: (id: string) => void;
}) {
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
              <span>#{count(offset + index + 1)}</span>
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
  decided: Decision | null;
  processing: boolean;
  storing: boolean;
  onRun?: () => void;
  onSubmit: (decision: Decision, reason: string) => Promise<unknown>;
  onNext: () => void;
  nextLabel: string;
  onEditAgain: () => void;
}

/** One invoice: ready to run, or the agent's result with the decision form beside it. */
function Workspace({
  invoice,
  status,
  result,
  outcome,
  decided,
  processing,
  storing,
  onRun,
  onSubmit,
  onNext,
  nextLabel,
  onEditAgain,
}: WorkspaceProps) {
  if (!result) {
    return (
      <div className="grid gap-6 lg:grid-cols-5">
        <InvoiceDetailsCard invoice={invoice} status={status} className="lg:col-span-3" />
        <BentoCard className="lg:col-span-2" hoverable={false} gradient gradientFrom="from-blue-50" gradientTo="to-violet-50">
          {processing ? (
            <ProcessingNarration />
          ) : (
            <MascotMessage state="ready" line={`Let’s see what ${invoice.vendor}’s invoice is hiding…`} />
          )}
          <p className="mt-5 text-sm text-slate-600">The agent will:</p>
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
              <MascotMessage state={stateForExceptions(result.exceptions)} size="sm" className="mb-4" />
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
        <MascotMessage state={stateForResult(result)} detail={resultDetail(result)} live />
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
          decided={decided}
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
  const total = queue.summary?.total ?? queue.invoices.length;
  const decidedCount = queue.summary?.decided ?? queue.invoices.filter((invoice) => invoice.status === 'decided').length;
  const moreOpen = decidedCount < total; // on another page, when nextPending is undefined
  const position = current ? queue.offset + queue.invoices.findIndex((invoice) => invoice.invoice_id === current.invoice_id) + 1 : 0;

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
    if (!nextPending && moreOpen) queue.showPage(null); // the page holding the first open invoice
  };

  const showPage = (offset: number | null) => {
    review.reset();
    setParams({});
    queue.showPage(offset);
  };

  let content: ReactNode;
  if (mode === 'manual') {
    content =
      result && shown ? (
        <Workspace
          invoice={shown}
          result={result}
          outcome={review.outcome}
          decided={review.decided}
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
        mascot="emptyQueue"
        title="The queue is empty"
        description="The backend has no invoices in its queue file (DATA_DIR / INVOICES_FILE). You can still enter one by hand."
        action={<GradientButton onClick={() => setMode('manual')}>Enter an invoice</GradientButton>}
      />
    );
  } else {
    content = (
      <>
        {queue.summary && queue.summary.total > queue.invoices.length && (
          <QueuePager summary={queue.summary} offset={queue.offset} shown={queue.invoices.length} limit={queue.limit} onPage={showPage} />
        )}
        <QueueStrip invoices={queue.invoices} offset={queue.offset} currentId={current?.invoice_id} onSelect={selectInvoice} />
        {current && shown ? (
          <Workspace
            invoice={shown}
            status={current.status}
            result={result}
            outcome={review.outcome}
            decided={review.decided}
            processing={review.processing}
            storing={review.storing}
            onRun={() => void runAgent()}
            onSubmit={submitDecision}
            onNext={goToNext}
            nextLabel={nextPending ? `Next invoice: ${nextPending.invoice_id}` : moreOpen ? 'Next open invoice' : 'Finish the queue'}
            onEditAgain={review.clearOutcome}
          />
        ) : moreOpen ? (
          <EmptyState
            mascot="smarter"
            title="Every invoice on this page has a decision"
            description={`${count(total - decidedCount)} more in the queue still need one.`}
            action={<GradientButton onClick={() => showPage(null)}>Go to the next open invoice</GradientButton>}
          />
        ) : (
          <EmptyState
            mascot="smarter"
            title="All invoices reviewed"
            description={
              <>
                “Every decision makes me a little wiser.” All {decidedCount} invoices in the queue have a human decision; the
                dashboard and vendor pages show what was learned.
              </>
            }
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
              {position > 0 ? `Invoice ${count(position)} of ${count(total)}` : `${count(total)} invoices`} · {count(decidedCount)}{' '}
              decided
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
