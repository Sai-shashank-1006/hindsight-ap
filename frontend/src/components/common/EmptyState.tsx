import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { cx } from '../../utils/formatters';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: 'neutral' | 'success' | 'warning';
  compact?: boolean;
  className?: string;
}

const TONES = {
  neutral: 'from-slate-100 to-slate-50 text-slate-400',
  success: 'from-emerald-100 to-teal-50 text-emerald-600',
  warning: 'from-amber-100 to-orange-50 text-amber-600',
} as const;

export default function EmptyState({ icon: Icon, title, description, action, tone = 'neutral', compact = false, className = '' }: EmptyStateProps) {
  return (
    <div className={cx('flex flex-col items-center justify-center text-center', compact ? 'py-8' : 'py-16', className)}>
      <div className={cx('flex items-center justify-center rounded-2xl bg-gradient-to-br', compact ? 'mb-3 h-12 w-12' : 'mb-4 h-16 w-16', TONES[tone])}>
        <Icon className={compact ? 'h-6 w-6' : 'h-8 w-8'} aria-hidden="true" />
      </div>
      <h3 className={cx('font-semibold text-slate-900', compact ? 'text-base' : 'text-xl')}>{title}</h3>
      {description && <div className="mt-1.5 max-w-md text-sm text-slate-500">{description}</div>}
      {action && <div className="mt-5 flex flex-wrap items-center justify-center gap-3">{action}</div>}
    </div>
  );
}
