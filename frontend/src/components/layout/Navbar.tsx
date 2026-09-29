import { Link } from 'react-router-dom';
import { Database, Menu } from 'lucide-react';
import Mascot from '../common/Mascot';
import Wordmark from '../common/Wordmark';
import { APP_NAME, APP_TAGLINE } from '../../utils/constants';
import { cx, describeHealth, type SystemTone } from '../../utils/formatters';
import type { HealthStatus } from '../../types';

interface NavbarProps {
  health: HealthStatus | null;
  healthError: string | null;
  checking: boolean;
  menuOpen: boolean;
  onOpenMenu: () => void;
}

const DOT: Record<SystemTone, string> = {
  live: 'bg-emerald-400',
  degraded: 'bg-amber-400',
  offline: 'bg-red-500',
  checking: 'bg-slate-400',
};

export default function Navbar({ health, healthError, checking, menuOpen, onOpenMenu }: NavbarProps) {
  const status = describeHealth(health, healthError, checking);

  return (
    <header className="sticky top-0 z-30 h-16 border-b border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900 to-slate-800 text-white shadow-lg">
      <div className="mx-auto flex h-full max-w-[1440px] items-center gap-3 px-4 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={onOpenMenu}
          aria-label="Open navigation"
          aria-expanded={menuOpen}
          aria-controls="mobile-navigation"
          className="-ml-1 rounded-lg p-2 text-slate-300 transition-colors hover:bg-white/10 hover:text-white lg:hidden"
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </button>

        <Link to="/" className="group flex min-w-0 items-center gap-3" aria-label={`${APP_NAME} home`}>
          <Mascot pose="calm" tone="teal" size="xs" animate={false} className="transition-transform duration-300 group-hover:scale-110" />
          <span className="min-w-0 leading-tight">
            <Wordmark className="block truncate text-xl" />
            <span className="hidden truncate text-xs text-slate-400 sm:block">{APP_TAGLINE}</span>
          </span>
        </Link>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          {health?.bank_id && (
            <span
              className="hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs text-slate-300 ring-1 ring-inset ring-white/10 md:inline-flex"
              title="Hindsight memory bank"
            >
              <Database className="h-3.5 w-3.5" aria-hidden="true" />
              {health.bank_id}
            </span>
          )}
          <span
            className="inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1.5 text-sm ring-1 ring-inset ring-white/10"
            title={status.detail}
            aria-label={`System status: ${status.label}. ${status.detail}`}
          >
            <span className="relative flex h-2 w-2">
              {status.tone === 'live' && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
              <span className={cx('relative inline-flex h-2 w-2 rounded-full', DOT[status.tone])} />
            </span>
            <span className="text-slate-200">{status.label}</span>
          </span>
        </div>
      </div>
    </header>
  );
}
