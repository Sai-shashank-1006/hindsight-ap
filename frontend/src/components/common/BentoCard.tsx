import type { ReactNode } from 'react';
import { cx } from '../../utils/formatters';

interface BentoCardProps {
  children: ReactNode;
  gradient?: boolean;
  gradientFrom?: string;
  gradientTo?: string;
  className?: string;
  hoverable?: boolean;
  /** Optional header: title on the left, action (a link or button) on the right. */
  title?: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  as?: 'div' | 'section' | 'article';
  padding?: 'none' | 'md' | 'lg';
}

const PADDING = { none: '', md: 'p-5', lg: 'p-6' } as const;

export default function BentoCard({
  children,
  gradient = false,
  gradientFrom = 'from-blue-50',
  gradientTo = 'to-violet-50',
  className = '',
  hoverable = true,
  title,
  subtitle,
  icon,
  action,
  as: Tag = 'div',
  padding = 'lg',
}: BentoCardProps) {
  return (
    <Tag
      className={cx(
        'relative flex min-w-0 flex-col rounded-2xl border border-slate-200/80 shadow-card transition-all duration-300',
        gradient ? `bg-gradient-to-br ${gradientFrom} ${gradientTo}` : 'bg-white',
        hoverable && 'hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lift',
        PADDING[padding],
        className,
      )}
    >
      {title && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            {icon && (
              <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-900/[0.04] text-slate-600">
                {icon}
              </span>
            )}
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-slate-900">{title}</h2>
              {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
            </div>
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      {children}
    </Tag>
  );
}
