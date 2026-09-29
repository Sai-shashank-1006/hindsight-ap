import { useState, type FormEvent } from 'react';
import {
  ArrowRight,
  BrainCircuit,
  CircleCheck,
  CircleX,
  Eye,
  Gavel,
  Info,
  RotateCcw,
  Send,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react';
import BentoCard from '../common/BentoCard';
import GradientButton from '../common/GradientButton';
import { DECISION_META, DECISIONS, REASON_MAX_LENGTH } from '../../utils/constants';
import { cx } from '../../utils/formatters';
import { validateDecision, validateReason } from '../../utils/validators';
import type { Decision, StoreDecisionResponse } from '../../types';

interface DecisionFormProps {
  vendor: string;
  onSubmit: (decision: Decision, reason: string) => void | Promise<unknown>;
  submitting?: boolean;
  /** The agent's recommendation, marked on its option. Nothing is pre-selected: the human decides. */
  recommendation?: Decision;
  /** Once stored, the form shows what happened instead. */
  outcome?: StoreDecisionResponse | null;
  onNext?: () => void;
  nextLabel?: string;
  onEditAgain?: () => void;
  className?: string;
}

const ICONS: Record<Decision, LucideIcon> = { APPROVED: CircleCheck, REJECTED: CircleX, NEEDS_REVIEW: Eye };

function DecisionInputs({
  vendor,
  onSubmit,
  submitting = false,
  recommendation,
  className = '',
}: Pick<DecisionFormProps, 'vendor' | 'onSubmit' | 'submitting' | 'recommendation' | 'className'>) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<{ decision?: string; reason?: string }>({});

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const found = { decision: validateDecision(decision) ?? undefined, reason: validateReason(reason) ?? undefined };
    setErrors(found);
    if (found.decision || found.reason || !decision) return;
    await onSubmit(decision, reason);
  };

  const reset = () => {
    setDecision(null);
    setReason('');
    setErrors({});
  };

  return (
    <BentoCard
      className={className}
      hoverable={false}
      icon={<Gavel className="h-5 w-5" aria-hidden="true" />}
      title="Your decision"
      subtitle="The final say is yours. Your reason is what Hindsight remembers."
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <fieldset>
          <legend className="sr-only">Decision</legend>
          <div className="grid gap-3 sm:grid-cols-3">
            {DECISIONS.map((option) => {
              const meta = DECISION_META[option];
              const Icon = ICONS[option];
              return (
                <label key={option} className="relative cursor-pointer">
                  <input
                    type="radio"
                    name="decision"
                    value={option}
                    checked={decision === option}
                    onChange={() => {
                      setDecision(option);
                      setErrors((current) => ({ ...current, decision: undefined }));
                    }}
                    className="peer sr-only"
                  />
                  <div
                    className={cx(
                      'flex h-full flex-col gap-1 rounded-xl border-2 border-slate-200 bg-white p-3.5 transition-all duration-200',
                      'hover:border-slate-300 peer-checked:ring-1 peer-focus-visible:ring-2 peer-focus-visible:ring-blue-500 peer-focus-visible:ring-offset-2',
                      meta.ring,
                    )}
                  >
                    <span className="flex items-center gap-2 whitespace-nowrap text-sm font-semibold text-slate-900">
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      {meta.action}
                    </span>
                    <span className="text-xs text-slate-500">{meta.description}</span>
                    {recommendation === option && (
                      <span className="mt-1 self-start rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-semibold text-violet-700">
                        Agent suggests
                      </span>
                    )}
                  </div>
                </label>
              );
            })}
          </div>
          {errors.decision && (
            <p className="mt-2 text-sm text-red-600" role="alert">
              {errors.decision}
            </p>
          )}
        </fieldset>

        <div>
          <label htmlFor="decision-reason" className="text-sm font-medium text-slate-700">
            Reason
          </label>
          <textarea
            id="decision-reason"
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
              if (errors.reason) setErrors((current) => ({ ...current, reason: undefined }));
            }}
            rows={3}
            maxLength={REASON_MAX_LENGTH}
            placeholder="e.g. Contract price changed from ₹500 to ₹550 effective 2026-07-01"
            aria-invalid={Boolean(errors.reason)}
            aria-describedby="decision-reason-help"
            className={cx(
              'mt-1.5 w-full resize-y rounded-xl border bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm transition-colors placeholder:text-slate-400',
              'focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20',
              errors.reason ? 'border-red-400' : 'border-slate-300',
            )}
          />
          <div id="decision-reason-help" className="mt-1.5 flex items-start justify-between gap-3 text-xs">
            {errors.reason ? (
              <span className="text-red-600" role="alert">
                {errors.reason}
              </span>
            ) : (
              <span className="text-slate-500">Stored in Hindsight as memory for {vendor} only.</span>
            )}
            <span className="tabular shrink-0 text-slate-400">
              {reason.length}/{REASON_MAX_LENGTH}
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <GradientButton
            type="submit"
            variant="success"
            fullWidth
            loading={submitting}
            loadingText="Saving to Hindsight…"
            icon={<Send className="h-4 w-4" aria-hidden="true" />}
          >
            Submit decision
          </GradientButton>
          <GradientButton
            variant="secondary"
            onClick={reset}
            disabled={submitting}
            icon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
            className="sm:w-auto"
          >
            Reset
          </GradientButton>
        </div>
      </form>
    </BentoCard>
  );
}

function DecisionOutcome({
  outcome,
  vendor,
  onNext,
  nextLabel = 'Next invoice',
  onEditAgain,
  className = '',
}: { outcome: StoreDecisionResponse } & Pick<DecisionFormProps, 'vendor' | 'onNext' | 'nextLabel' | 'onEditAgain' | 'className'>) {
  const look = outcome.retained
    ? { from: 'from-emerald-50', to: 'to-teal-50', Icon: BrainCircuit, icon: 'text-emerald-600', title: 'Remembered in Hindsight' }
    : outcome.success
      ? { from: 'from-blue-50', to: 'to-violet-50', Icon: Info, icon: 'text-blue-600', title: 'Decision recorded' }
      : { from: 'from-amber-50', to: 'to-orange-50', Icon: TriangleAlert, icon: 'text-amber-600', title: 'Recorded, but not remembered' };

  return (
    <BentoCard gradient gradientFrom={look.from} gradientTo={look.to} hoverable={false} className={cx('animate-slide-up', className)}>
      <div role="status" aria-live="polite">
        <div className="flex items-start gap-3">
          <look.Icon className={cx('mt-0.5 h-6 w-6 shrink-0', look.icon)} aria-hidden="true" />
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-slate-900">{look.title}</h2>
            <p className="mt-1 text-sm text-slate-700">{outcome.message}</p>
            {outcome.retained && (
              <p className="mt-2 text-sm text-slate-600">
                The next {vendor} invoice with this exception will recall it
                {outcome.memory_id && (
                  <>
                    {' '}
                    (<span className="font-mono text-xs">{outcome.memory_id}</span>)
                  </>
                )}
                .
              </p>
            )}
            {!outcome.success && (
              <p className="mt-2 text-sm text-slate-600">
                Fix the problem shown in the System panel, then submit again. A resubmission replaces the decision; it never duplicates it.
              </p>
            )}
          </div>
        </div>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          {onNext && (
            <GradientButton onClick={onNext} icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />} fullWidth>
              {nextLabel}
            </GradientButton>
          )}
          {!outcome.success && onEditAgain && (
            <GradientButton variant="secondary" onClick={onEditAgain} icon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}>
              Submit again
            </GradientButton>
          )}
        </div>
      </div>
    </BentoCard>
  );
}

export default function DecisionForm({ outcome, ...props }: DecisionFormProps) {
  if (outcome) return <DecisionOutcome outcome={outcome} {...props} />;
  return <DecisionInputs {...props} />;
}
