import { CircleAlert, Info, RefreshCw, TriangleAlert, X } from 'lucide-react';
import { cx } from '../../utils/formatters';

interface ErrorAlertProps {
  error: string | null;
  title?: string;
  variant?: 'error' | 'warning' | 'info';
  onDismiss?: () => void;
  onRetry?: () => void;
  className?: string;
}

const STYLES = {
  error: { box: 'border-red-200 bg-red-50', title: 'text-red-900', text: 'text-red-800', icon: 'text-red-600', Icon: CircleAlert },
  warning: { box: 'border-amber-200 bg-amber-50', title: 'text-amber-900', text: 'text-amber-800', icon: 'text-amber-600', Icon: TriangleAlert },
  info: { box: 'border-blue-200 bg-blue-50', title: 'text-blue-900', text: 'text-blue-800', icon: 'text-blue-600', Icon: Info },
} as const;

export default function ErrorAlert({ error, title, variant = 'error', onDismiss, onRetry, className = '' }: ErrorAlertProps) {
  if (!error) return null;
  const style = STYLES[variant];
  const Icon = style.Icon;

  return (
    <div role="alert" className={cx('animate-fade-in rounded-xl border p-4', style.box, className)}>
      <div className="flex items-start gap-3">
        <Icon className={cx('mt-0.5 h-5 w-5 shrink-0', style.icon)} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <h3 className={cx('font-semibold', style.title)}>{title ?? (variant === 'error' ? 'Something went wrong' : 'Heads up')}</h3>
          <p className={cx('mt-1 break-words text-sm', style.text)}>{error}</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className={cx('mt-3 inline-flex items-center gap-1.5 text-sm font-semibold hover:underline', style.title)}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Try again
            </button>
          )}
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss"
            className={cx('rounded-md p-1 transition-colors hover:bg-black/5', style.icon)}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}
