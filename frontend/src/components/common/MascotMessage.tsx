import type { ReactNode } from 'react';
import Mascot from './Mascot';
import { cx } from '../../utils/formatters';
import { MASCOT_STATES, type MascotStateId, type MascotTone } from '../../utils/mascot';

interface MascotMessageProps {
  state: MascotStateId;
  /** Replaces the state's default line, e.g. to name the vendor. */
  line?: string;
  detail?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  /** 'dark' for use on the dark hero cards. */
  variant?: 'light' | 'dark';
  /** Announce changes to screen readers (for states that follow an action). */
  live?: boolean;
  className?: string;
}

const TITLE: Record<MascotTone, string> = {
  teal: 'text-teal-600',
  blue: 'text-blue-600',
  violet: 'text-violet-600',
  amber: 'text-amber-600',
  red: 'text-red-600',
  emerald: 'text-emerald-600',
};

const TITLE_DARK: Record<MascotTone, string> = {
  teal: 'text-teal-300',
  blue: 'text-blue-300',
  violet: 'text-violet-300',
  amber: 'text-amber-300',
  red: 'text-red-300',
  emerald: 'text-emerald-300',
};

const BORDER: Record<MascotTone, string> = {
  teal: 'border-teal-200 before:border-teal-200',
  blue: 'border-blue-200 before:border-blue-200',
  violet: 'border-violet-200 before:border-violet-200',
  amber: 'border-amber-200 before:border-amber-200',
  red: 'border-red-200 before:border-red-200',
  emerald: 'border-emerald-200 before:border-emerald-200',
};

/** The mascot with a speech bubble: what it thinks about the current situation. */
export default function MascotMessage({ state: stateId, line, detail, size = 'md', variant = 'light', live = false, className = '' }: MascotMessageProps) {
  const state = MASCOT_STATES[stateId];
  const dark = variant === 'dark';

  return (
    <div
      className={cx('flex items-start gap-4', className)}
      role={live ? 'status' : undefined}
      aria-live={live ? 'polite' : undefined}
    >
      <Mascot pose={state.pose} tone={state.tone} size={size} />
      <div
        className={cx(
          'relative mt-1 min-w-0 flex-1 animate-fade-in rounded-2xl border px-4 py-3',
          // the bubble's tail, pointing at the mascot
          "before:absolute before:-left-[7px] before:top-5 before:h-3 before:w-3 before:rotate-45 before:border-b before:border-l before:content-['']",
          dark ? 'border-white/15 bg-white/10 before:border-white/15 before:bg-[#1a2140]' : cx('bg-white before:bg-white', BORDER[state.tone]),
        )}
      >
        <p className={cx('text-[11px] font-semibold uppercase tracking-wider', dark ? TITLE_DARK[state.tone] : TITLE[state.tone])}>
          {state.title}
        </p>
        <p className={cx('mt-0.5 font-medium leading-snug', size === 'sm' ? 'text-sm' : 'text-[15px]', dark ? 'text-white' : 'text-slate-800')}>
          “{line ?? state.line}”
        </p>
        {detail && <div className={cx('mt-1.5 text-xs', dark ? 'text-slate-300' : 'text-slate-500')}>{detail}</div>}
      </div>
    </div>
  );
}
