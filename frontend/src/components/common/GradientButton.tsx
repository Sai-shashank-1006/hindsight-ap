import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { LoaderCircle } from 'lucide-react';
import { cx } from '../../utils/formatters';

type Variant = 'primary' | 'success' | 'danger' | 'warning' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface GradientButtonProps {
  children: ReactNode;
  variant?: Variant;
  size?: Size;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  loadingText?: string;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
  fullWidth?: boolean;
  icon?: ReactNode;
  /** Render as a router link instead of a button (no <button> nested inside <a>). */
  to?: string;
  /** Render as an external link, opened in a new tab. */
  href?: string;
  ariaLabel?: string;
}

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-gradient-to-r from-blue-600 to-violet-600 text-white shadow-md shadow-blue-600/20 hover:from-blue-700 hover:to-violet-700 hover:shadow-lg',
  success:
    'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-md shadow-emerald-600/20 hover:from-emerald-600 hover:to-teal-600 hover:shadow-lg',
  danger:
    'bg-gradient-to-r from-red-500 to-orange-500 text-white shadow-md shadow-red-600/20 hover:from-red-600 hover:to-orange-600 hover:shadow-lg',
  warning:
    'bg-gradient-to-r from-amber-500 to-pink-500 text-white shadow-md shadow-amber-600/20 hover:from-amber-600 hover:to-pink-600 hover:shadow-lg',
  secondary: 'bg-white text-slate-700 shadow-sm ring-1 ring-inset ring-slate-200 hover:bg-slate-50 hover:ring-slate-300',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
};

const SIZES: Record<Size, string> = {
  sm: 'h-9 gap-1.5 px-3.5 text-sm',
  md: 'h-11 gap-2 px-5 text-sm',
  lg: 'h-12 gap-2 px-6 text-base',
};

const BASE =
  'inline-flex select-none items-center justify-center whitespace-nowrap rounded-lg font-semibold transition-all duration-200 ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ' +
  'active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:active:scale-100';

export default function GradientButton({
  children,
  variant = 'primary',
  size = 'md',
  onClick,
  disabled = false,
  loading = false,
  loadingText,
  className = '',
  type = 'button',
  fullWidth = false,
  icon,
  to,
  href,
  ariaLabel,
}: GradientButtonProps) {
  const classes = cx(BASE, VARIANTS[variant], SIZES[size], fullWidth && 'w-full', className);
  const content = loading ? (
    <>
      <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
      {loadingText ?? 'Working…'}
    </>
  ) : (
    <>
      {icon}
      {children}
    </>
  );

  if (to && !disabled) {
    return (
      <Link to={to} className={classes} aria-label={ariaLabel}>
        {content}
      </Link>
    );
  }
  if (href && !disabled) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={classes} aria-label={ariaLabel}>
        {content}
      </a>
    );
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      aria-label={ariaLabel}
      className={classes}
    >
      {content}
    </button>
  );
}
