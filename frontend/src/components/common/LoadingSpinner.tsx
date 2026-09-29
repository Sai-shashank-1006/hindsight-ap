import { cx } from '../../utils/formatters';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZES = { sm: 'h-6 w-6', md: 'h-10 w-10', lg: 'h-16 w-16' } as const;

export default function LoadingSpinner({ message = 'Loading…', size = 'md', className = '' }: LoadingSpinnerProps) {
  return (
    <div role="status" aria-live="polite" className={cx('flex flex-col items-center justify-center gap-4 py-12', className)}>
      <svg className={cx('animate-spin text-blue-600', SIZES[size])} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.2" />
        <path fill="currentColor" d="M12 2a10 10 0 0 1 10 10h-3a7 7 0 0 0-7-7V2z" />
      </svg>
      <p className="text-sm text-slate-500">{message}</p>
    </div>
  );
}
