import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import { getDashboard } from '../api/endpoints';
import type { ApplicationRecord, DashboardResponse } from '../api/types';
import { MonochromeBarChart } from '../components/charts/MonochromeBarChart';
import { MonochromeLineChart } from '../components/charts/MonochromeLineChart';
import { StatusCell } from '../components/domain/StatusCell';
import { Button, ButtonLink } from '../components/ui/Button';
import { DataTable } from '../components/ui/DataTable';
import type { Column } from '../components/ui/DataTable';
import { Panel } from '../components/ui/Panel';
import { ErrorState, LoadingState } from '../components/ui/states';
import { useApi } from '../hooks/useApi';
import { formatNumber, formatPercent, monthLabel, text } from '../lib/format';
import { CATEGORY_LABEL, CATEGORY_ORDER, CATEGORY_SHADE } from '../lib/status';

export function CommandOverview() {
  const { data, error, initialLoading, reload } = useApi<DashboardResponse>((signal) =>
    getDashboard(signal),
  );

  const recentColumns = useMemo<Array<Column<ApplicationRecord>>>(
    () => [
      {
        key: 'company',
        header: 'Company',
        width: '13rem',
        render: (row) => (
          <span className="font-semibold text-text">{text(row.company, 'Unknown company')}</span>
        ),
      },
      {
        key: 'role',
        header: 'Role',
        width: '16rem',
        render: (row) => (
          <span className="text-text-secondary">{text(row.role, 'Unknown role')}</span>
        ),
      },
      {
        key: 'status',
        header: 'Status',
        width: '13rem',
        render: (row) => <StatusCell status={row.status} category={row.status_category} />,
      },
      {
        key: 'latest_update_date',
        header: 'Updated',
        width: '8rem',
        render: (row) => (
          <span className="tabular-nums text-xs text-text-secondary">
            {text(row.latest_update_date, '—')}
          </span>
        ),
      },
      {
        key: 'platform',
        header: 'Platform',
        width: '12rem',
        render: (row) => (
          <span className="text-xs text-text-tertiary">{text(row.platform, '—')}</span>
        ),
      },
    ],
    [],
  );

  if (initialLoading && !data) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Your internship search</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Keep track of applications, follow-ups, and opportunities in one place.
          </p>
        </div>
        <LoadingState label="Loading dashboard" detail="Fetching application and search pipeline data…" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Your internship search</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Keep track of applications, follow-ups, and opportunities in one place.
          </p>
        </div>
        <ErrorState error={error} onRetry={reload} />
      </div>
    );
  }

  if (!data) return null;

  const apps = data.applications;
  const jobs = data.jobs;

  const categoryChart = CATEGORY_ORDER.map((category) => ({
    label: CATEGORY_LABEL[category],
    value: apps.category_counts[category] ?? 0,
    shade: CATEGORY_SHADE[category],
  }));

  const trend = apps.applications_over_time.map((bucket) => ({
    label: monthLabel(bucket.month),
    value: bucket.count,
  }));

  return (
    <div className="flex flex-col gap-6">
      {/* Welcome header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Your internship search</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Keep track of applications, follow-ups, and opportunities in one place.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ButtonLink to="/tracker" variant="solid" size="sm">
            View all applications
          </ButtonLink>
          <Button size="sm" variant="outline" onClick={reload} prefix="↻">
            Refresh
          </Button>
        </div>
      </div>

      {/* Metrics Section: One strong primary metric + compact secondary group */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Primary metric card */}
        <div className="flex flex-col justify-between rounded-xl border border-brand/20 bg-brand p-5 text-white shadow-xs lg:col-span-4">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-white/80 uppercase tracking-wider">
                Total Pipeline
              </span>
              <span className="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-medium text-white">
                {apps.active_applications} active
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="font-bold text-4xl tracking-tight text-white tabular-nums">
                {formatNumber(apps.total_applications)}
              </span>
              <span className="text-sm text-white/70">applications tracked</span>
            </div>
          </div>
          <div className="mt-4 border-t border-white/15 pt-3">
            <p className="text-xs text-white/80">
              Decided outcome rate: <strong className="font-semibold text-white">{formatPercent(apps.response_rate_percent)}</strong>
            </p>
          </div>
        </div>

        {/* Secondary metrics grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:col-span-8">
          {/* Pending */}
          <div className="flex flex-col justify-between rounded-xl border border-border bg-surface p-4 shadow-2xs">
            <span className="text-xs font-medium text-text-secondary">Pending</span>
            <div className="my-2">
              <span className="font-bold text-2xl text-amber tabular-nums">
                {formatNumber(apps.pending_applications)}
              </span>
            </div>
            <span className="text-[11px] text-text-tertiary">Awaiting response</span>
          </div>

          {/* Interviews */}
          <div className="flex flex-col justify-between rounded-xl border border-border bg-surface p-4 shadow-2xs">
            <span className="text-xs font-medium text-text-secondary">Interviews</span>
            <div className="my-2">
              <span className="font-bold text-2xl text-brand tabular-nums">
                {formatNumber(apps.interview_applications)}
              </span>
            </div>
            <span className="text-[11px] text-text-tertiary">Assessment / stage</span>
          </div>

          {/* Offers */}
          <div className="flex flex-col justify-between rounded-xl border border-border bg-surface p-4 shadow-2xs">
            <span className="text-xs font-medium text-text-secondary">Offers</span>
            <div className="my-2">
              <span className="font-bold text-2xl text-text tabular-nums">
                {formatNumber(apps.offers)}
              </span>
            </div>
            <span className="text-[11px] text-text-tertiary">Recorded offers</span>
          </div>

          {/* Rejected */}
          <div className="flex flex-col justify-between rounded-xl border border-border bg-surface p-4 shadow-2xs">
            <span className="text-xs font-medium text-text-secondary">Rejected</span>
            <div className="my-2">
              <span className="font-bold text-2xl text-danger tabular-nums">
                {formatNumber(apps.rejected_applications)}
              </span>
            </div>
            <span className="text-[11px] text-text-tertiary">Closed outcomes</span>
          </div>
        </div>
      </div>

      {/* Balanced Two-column Charts: Pipeline Progress + Activity Over Time */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Panel
          title="Pipeline progress by status"
          className="lg:col-span-7"
          meta={`${formatNumber(apps.total_applications)} tracked`}
        >
          <MonochromeBarChart
            data={categoryChart}
            unit="applications"
            ariaLabel="Applications grouped by status category"
          />
        </Panel>

        <Panel
          title="Application activity over time"
          className="lg:col-span-5"
          meta={`${trend.length} month${trend.length === 1 ? '' : 's'}`}
        >
          <MonochromeLineChart
            data={trend}
            unit="applications"
            ariaLabel="Applications submitted per calendar month"
          />
        </Panel>
      </div>

      {/* Recent Applications Section */}
      <Panel
        title="Recent applications"
        meta={`${apps.recent_applications.length} latest`}
        actions={
          <Link
            to="/tracker"
            className="text-xs font-semibold text-brand hover:text-brand-hover inline-flex items-center gap-1"
          >
            View all <span>→</span>
          </Link>
        }
        bodyClassName="p-0"
      >
        <DataTable
          columns={recentColumns}
          rows={apps.recent_applications}
          rowKey={(row) => row.id}
          empty={
            <div className="p-8 text-center text-sm text-text-tertiary">
              No applications recorded yet.
            </div>
          }
        />
      </Panel>

      {/* Job Discovery Callout (honest handling of 0 listings) */}
      {jobs.total_listings === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-5">
          <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-sm font-semibold text-text">Discover internships</h2>
              <p className="mt-1 text-xs text-text-secondary leading-relaxed max-w-xl">
                The job discovery list is currently empty. Once verified listings are saved to the
                connected spreadsheet, relevant internship opportunities and interest matches will appear here.
              </p>
            </div>
            <ButtonLink to="/jobs" variant="outline" size="sm" className="shrink-0">
              Explore opportunities
            </ButtonLink>
          </div>
        </div>
      ) : (
        <Panel title="Top matching opportunities" meta={`${data.top_matches.length} matched`}>
          <p className="text-sm text-text-secondary">
            {formatNumber(data.top_matches.length)} verified opportunities matched your preferences.
          </p>
        </Panel>
      )}
    </div>
  );
}
