import alarmed from '../../assets/mascot/alarmed.webp';
import calm from '../../assets/mascot/calm.webp';
import processing from '../../assets/mascot/processing.webp';
import puzzled from '../../assets/mascot/puzzled.webp';
import resolved from '../../assets/mascot/resolved.webp';
import thinking from '../../assets/mascot/thinking.webp';
import wise from '../../assets/mascot/wise.webp';
import { cx } from '../../utils/formatters';
import type { MascotPose, MascotTone } from '../../utils/mascot';

const POSES: Record<MascotPose, string> = { alarmed, calm, processing, puzzled, resolved, thinking, wise };

const SIZES = {
  xs: 'h-9 w-9 rounded-lg',
  sm: 'h-14 w-14 rounded-xl',
  md: 'h-20 w-20 rounded-2xl',
  lg: 'h-28 w-28 rounded-3xl',
  xl: 'h-36 w-36 rounded-3xl',
} as const;

// A coloured halo that matches the mood (the art itself is drawn for a dark background).
const GLOWS: Record<MascotTone, string> = {
  teal: 'shadow-[0_0_28px_-6px_rgba(45,212,191,0.7)] ring-teal-300/30',
  blue: 'shadow-[0_0_28px_-6px_rgba(59,130,246,0.7)] ring-blue-300/30',
  violet: 'shadow-[0_0_28px_-6px_rgba(139,92,246,0.7)] ring-violet-300/30',
  amber: 'shadow-[0_0_28px_-6px_rgba(245,158,11,0.7)] ring-amber-300/30',
  red: 'shadow-[0_0_28px_-6px_rgba(239,68,68,0.7)] ring-red-300/30',
  emerald: 'shadow-[0_0_28px_-6px_rgba(16,185,129,0.7)] ring-emerald-300/30',
};

// Each pose moves a little differently: alarm shakes once, the rest breathe.
const MOTION: Record<MascotPose, string> = {
  alarmed: 'motion-safe:animate-wiggle',
  processing: 'motion-safe:animate-bob',
  thinking: 'motion-safe:animate-float',
  puzzled: 'motion-safe:animate-float',
  resolved: 'motion-safe:animate-pop',
  wise: 'motion-safe:animate-float',
  calm: 'motion-safe:animate-float',
};

interface MascotProps {
  pose: MascotPose;
  tone?: MascotTone;
  size?: keyof typeof SIZES;
  animate?: boolean;
  /** Spoken to screen readers. Omit when a caption next to the mascot already says it. */
  label?: string;
  className?: string;
}

export default function Mascot({ pose, tone = 'violet', size = 'md', animate = true, label, className = '' }: MascotProps) {
  return (
    <span
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cx(
        'relative inline-flex shrink-0 overflow-hidden bg-[#0b1024] ring-1 ring-inset transition-shadow duration-500',
        SIZES[size],
        GLOWS[tone],
        animate && MOTION[pose],
        className,
      )}
    >
      <img src={POSES[pose]} alt="" draggable={false} decoding="async" className="h-full w-full select-none object-cover" />
    </span>
  );
}
