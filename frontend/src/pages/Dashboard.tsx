import { useState } from 'react';
import { Inbox, RefreshCw } from 'lucide-react';
import DashboardGrid from '../components/dashboard/DashboardGrid';
import EmptyState from '../components/common/EmptyState';
import ErrorAlert from '../components/common/ErrorAlert';
import GradientButton from '../components/common/GradientButton';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useDashboard } from '../hooks/useDashboard';
import { formatDateTime, formatRelativeTime } from '../utils/formatters';

export default function Dashboard() {
  const { data, stats, loading, error, lastUpdated, refresh } = useDashboard();
  const [dismissedError, setDismissedError] = useState<string | null>(null);
  const showError = error !== null && error !== dismissedError;

  let body;
  if (loading && !data) {
    body = <LoadingSpinner message="Loading dashboard…" />;
  } else if (!data || !stats) {
    body = error ? (
      <ErrorAlert error={error} title="Couldn't load the dashboard" onRetry={() => void refresh()} />
    ) : (
      <EmptyState icon={Inbox} title="No data available" description="The API answered, but returned no dashboard data." />
    );
  } else {
    body = (
      <>
        {showError && (
          <ErrorAlert
            variant="warning"
            title="Showing the last data received"
            error={`Refreshing failed: ${error}`}
            onDismiss={() => setDismissedError(error)}
            className="mb-6"
          />
        )}
        <DashboardGrid data={data} stats={stats} />
      </>
    );
  }

  return (
    <div className="mx-auto max-w-7xl animate-fade-in">
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Dashboard</h1>
          <p className="mt-2 text-slate-600">Invoice exceptions, human decisions, and what Hindsight has learned from them.</p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-slate-500" title={formatDateTime(lastUpdated.toISOString())}>
              Updated {formatRelativeTime(lastUpdated.toISOString())} · refreshes every 10 s
            </span>
          )}
          <GradientButton variant="secondary" size="sm" onClick={() => void refresh()} icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}>
            Refresh
          </GradientButton>
        </div>
      </header>
      {body}
    </div>
  );
}
