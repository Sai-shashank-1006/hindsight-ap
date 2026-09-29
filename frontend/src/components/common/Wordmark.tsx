import { APP_NAME } from '../../utils/constants';
import { cx } from '../../utils/formatters';

/** "Pay" plus a teal-to-violet "Sage", as in the logo. Any other VITE_APP_NAME renders plainly. */
export default function Wordmark({ className = '' }: { className?: string }) {
  if (APP_NAME !== 'PaySage') return <span className={cx('font-extrabold tracking-tight', className)}>{APP_NAME}</span>;
  return (
    <span className={cx('font-extrabold tracking-tight', className)}>
      Pay
      <span className="bg-gradient-to-r from-teal-300 via-sky-400 to-violet-400 bg-clip-text text-transparent">Sage</span>
    </span>
  );
}
