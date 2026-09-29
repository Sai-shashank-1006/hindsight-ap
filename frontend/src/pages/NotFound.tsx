import { useLocation } from 'react-router-dom';
import EmptyState from '../components/common/EmptyState';
import GradientButton from '../components/common/GradientButton';
import { MASCOT_STATES } from '../utils/mascot';

export default function NotFound() {
  const { pathname } = useLocation();
  return (
    <div className="mx-auto max-w-3xl animate-fade-in">
      <EmptyState
        mascot="lost"
        title="Page not found"
        description={
          <>
            “{MASCOT_STATES.lost.line}” Nothing lives at{' '}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-700">{pathname}</code>.
          </>
        }
        action={
          <>
            <GradientButton to="/">Go to the dashboard</GradientButton>
            <GradientButton variant="secondary" to="/review">
              Review invoices
            </GradientButton>
          </>
        }
      />
    </div>
  );
}
