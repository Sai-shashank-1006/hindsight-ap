import { useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { BrainCircuit, Cpu, Database, FileSearch, HardDrive, LayoutDashboard, RefreshCw, Server, X, type LucideIcon } from 'lucide-react';
import Mascot from '../common/Mascot';
import { cx } from '../../utils/formatters';
import type { HealthStatus } from '../../types';

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  health: HealthStatus | null;
  healthError: string | null;
  checking: boolean;
  onRefreshHealth: () => void;
}

const NAV: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/review', label: 'Review invoices', icon: FileSearch },
  { to: '/vendors', label: 'Vendor memory', icon: BrainCircuit },
];

type Tone = 'ok' | 'warn' | 'bad' | 'idle';
const TONE_DOT: Record<Tone, string> = { ok: 'bg-emerald-500', warn: 'bg-amber-500', bad: 'bg-red-500', idle: 'bg-slate-300' };

function StatusRow({ icon: Icon, label, value, tone }: { icon: LucideIcon; label: string; value: string; tone: Tone }) {
  return (
    <li className="flex items-start gap-3 py-2">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <p className="truncate text-sm font-medium text-slate-800" title={value}>
          {value}
        </p>
      </div>
      <span className={cx('mt-1.5 h-2 w-2 shrink-0 rounded-full', TONE_DOT[tone])} aria-hidden="true" />
    </li>
  );
}

/** Where the invoices and the decision log live: "MySQL · synthetic", "Files · demo". */
function dataStatus(health: HealthStatus | null): { value: string; tone: Tone } {
  if (!health) return { value: '—', tone: 'idle' };
  const source = health.data_source ?? 'files';
  const name = source === 'files' ? 'Files' : source === 'mysql' ? 'MySQL' : source === 'sqlite' ? 'SQLite' : source;
  if (health.database === 'unreachable') return { value: `${name} unreachable`, tone: 'bad' };
  return { value: health.dataset ? `${name} · ${health.dataset}` : name, tone: 'ok' };
}

function SidebarContent({ onNavigate, health, healthError, checking, onRefreshHealth }: {
  onNavigate: () => void;
  health: HealthStatus | null;
  healthError: string | null;
  checking: boolean;
  onRefreshHealth: () => void;
}) {
  const apiTone: Tone = health ? 'ok' : checking ? 'idle' : 'bad';
  const groqTone: Tone = !health ? 'idle' : health.groq === 'configured' ? 'ok' : 'warn';
  const memoryTone: Tone = !health ? 'idle' : health.hindsight === 'reachable' ? 'ok' : health.hindsight === 'missing' ? 'warn' : 'bad';

  return (
    <div className="flex h-full flex-col gap-6">
      <nav aria-label="Main">
        <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Workspace</p>
        <ul className="space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cx(
                    'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-gradient-to-r from-blue-600/10 to-violet-600/10 text-blue-700 ring-1 ring-inset ring-blue-600/15'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={cx('h-[18px] w-[18px] shrink-0', isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600')} aria-hidden="true" />
                    {label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <section aria-labelledby="system-heading" className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-card">
        <div className="flex items-center justify-between">
          <h2 id="system-heading" className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            System
          </h2>
          <button
            type="button"
            onClick={onRefreshHealth}
            disabled={checking}
            className="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
            aria-label="Re-check system status"
          >
            <RefreshCw className={cx('h-3.5 w-3.5', checking && 'animate-spin')} aria-hidden="true" />
          </button>
        </div>
        <ul className="mt-1 divide-y divide-slate-100">
          <StatusRow icon={Server} label="API" value={health ? 'Reachable' : checking ? 'Checking…' : healthError ?? 'Unreachable'} tone={apiTone} />
          <StatusRow
            icon={Cpu}
            label="LLM (Groq)"
            value={!health ? '—' : health.groq === 'configured' ? health.groq_model : 'Not configured'}
            tone={groqTone}
          />
          <StatusRow
            icon={Database}
            label="Memory (Hindsight)"
            value={!health ? '—' : health.hindsight === 'reachable' ? `Bank ${health.bank_id ?? '—'}` : health.hindsight === 'missing' ? 'Not configured' : 'Unreachable'}
            tone={memoryTone}
          />
          <StatusRow icon={HardDrive} label="Data" {...dataStatus(health)} />
        </ul>
      </section>

      <div className="mt-auto rounded-2xl bg-gradient-to-br from-slate-900 to-[#1a1f4a] p-4 text-slate-300">
        <Mascot pose="wise" tone="violet" size="sm" />
        <p className="mt-3 text-xs leading-relaxed">
          Only <span className="font-semibold text-white">human decisions</span> are stored as memory. The agent never approves an
          exception without a verified precedent for the same vendor.
        </p>
      </div>
    </div>
  );
}

export default function Sidebar({ open, onClose, health, healthError, checking, onRefreshHealth }: SidebarProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const content = (
    <SidebarContent onNavigate={onClose} health={health} healthError={healthError} checking={checking} onRefreshHealth={onRefreshHealth} />
  );

  return (
    <>
      <aside className="hidden w-64 shrink-0 border-r border-slate-200/70 bg-white/60 backdrop-blur lg:block">
        <div className="scroll-thin sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto p-4">{content}</div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            type="button"
            className="absolute inset-0 h-full w-full animate-fade-in bg-slate-900/40 backdrop-blur-sm"
            onClick={onClose}
            aria-label="Close navigation"
          />
          <aside id="mobile-navigation" className="scroll-thin relative flex h-full w-72 max-w-[85vw] animate-slide-in-left flex-col overflow-y-auto bg-slate-50 p-4 shadow-2xl">
            <div className="mb-4 flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-2 text-slate-500 hover:bg-slate-200/70 hover:text-slate-900"
                aria-label="Close navigation"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            {content}
          </aside>
        </div>
      )}
    </>
  );
}
