import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import BentoCard from '../common/BentoCard';
import { cx } from '../../utils/formatters';

type Tone = 'blue' | 'orange' | 'green' | 'purple';

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon: LucideIcon;
  tone?: Tone;
  className?: string;
}

const TONES: Record<Tone, { from: string; to: string; value: string; icon: string }> = {
  blue: { from: 'from-blue-50', to: 'to-indigo-100/70', value: 'from-blue-600 to-indigo-600', icon: 'from-blue-500 to-indigo-600' },
  orange: { from: 'from-orange-50', to: 'to-rose-100/70', value: 'from-red-600 to-orange-500', icon: 'from-orange-500 to-red-500' },
  green: { from: 'from-emerald-50', to: 'to-teal-100/70', value: 'from-emerald-600 to-teal-600', icon: 'from-emerald-500 to-teal-500' },
  purple: { from: 'from-violet-50', to: 'to-fuchsia-100/70', value: 'from-violet-600 to-fuchsia-600', icon: 'from-violet-500 to-fuchsia-500' },
};

export default function StatCard({ label, value, hint, icon: Icon, tone = 'blue', className = '' }: StatCardProps) {
  const style = TONES[tone];
  return (
    <BentoCard gradient gradientFrom={style.from} gradientTo={style.to} className={className} padding="md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-600">{label}</p>
          <p className={cx('tabular mt-2 bg-gradient-to-r bg-clip-text text-4xl font-bold tracking-tight text-transparent', style.value)}>
            {value}
          </p>
          {hint && <p className="mt-2 text-xs text-slate-500">{hint}</p>}
        </div>
        <span className={cx('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md', style.icon)}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
      </div>
    </BentoCard>
  );
}
