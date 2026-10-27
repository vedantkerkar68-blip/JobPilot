import { getApplicationAnalytics, getJobAnalytics, getMatching } from '../api/endpoints';
import type { ApplicationAnalytics, JobAnalytics, MatchingResponse } from '../api/types';
import { FunnelStages } from '../components/charts/FunnelStages';
import { MonochromeHBarChart } from '../components/charts/MonochromeHBarChart';
import { MonochromeLineChart } from '../components/charts/MonochromeLineChart';
import { BarList } from '../components/ui/BarList';
import { Tag } from '../components/ui/Chip';
import { Panel } from '../components/ui/Panel';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/states';
import { useApi } from '../hooks/useApi';
import {
  formatNumber,
  formatPercent,
  humaniseField,
  monthLabel,
  sortedCounts,
} from '../lib/format';
import { CATEGORY_LABEL, CATEGORY_MEANING, CATEGORY_ORDER, CATEGORY_SHADE } from '../lib/status';

const PLATFORM_LIMIT = 8;

export function Analytics() {
  const applications = useApi<ApplicationAnalytics>((signal) =>
    getApplicationAnalytics(signal),
  );
  const jobs = useApi<JobAnalytics>((signal) => getJobAnalytics(signal));
  const matching = useApi<MatchingResponse>((signal) => getMatching({ limit: 50 }, signal));

  if (applications.initialLoading && !applications.data) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Analytics</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Visual insights into application progress, statuses, and search data.
          </p>
        </div>
        <LoadingState label="Loading analytics…" />
      </div>
    );
  }

  if (applications.error && !applications.data) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Analytics</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Visual insights into application progress, statuses, and search data.
          </p>
        </div>
        <ErrorState error={applications.error} onRetry={applications.reload} />
      </div>
    );
  }

  const data = applications.data;
  if (!data) return null;

  const funnelStages = CATEGORY_ORDER.map((category) => ({
    label: CATEGORY_LABEL[category],
    value: data.category_counts[category] ?? 0,
    shade: CATEGORY_SHADE[category],
    note: CATEGORY_MEANING[category],
  }));

  const trend = data.applications_over_time.map((bucket) => ({
    label: monthLabel(bucket.month),
    value: bucket.count,
  }));

  const platformRows = data.applications_by_platform.map((row) => ({
    label: row.platform,
    value: row.count,
  }));

  const typeRows = data.applications_by_type.map((row) => ({
    label: row.application_type,
    value: row.count,
  }));

  const missingRows = Object.entries(data.missing_data_counts)
    .map(([field, count]) => ({ label: humaniseField(field), value: count }))
    .sort((a, b) => b.value - a.value);

  const categorised = CATEGORY_ORDER.reduce(
    (sum, category) => sum + (data.category_counts[category] ?? 0),
    0,
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text">Analytics</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Visual insights into application progress, statuses, and search data.
        </p>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          { label: 'Total Tracked', value: formatNumber(data.total_applications) },
          { label: 'Categorised', value: formatNumber(categorised) },
          { label: 'Active Pipeline', value: formatNumber(data.active_applications) },
          { label: 'Outcome Rate', value: formatPercent(data.response_rate_percent) },
          { label: 'Offers Recorded', value: formatNumber(data.offers) },
          { label: 'Duplicate Groups', value: formatNumber(data.duplicate_groups.length) },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-border bg-surface p-4 shadow-2xs">
            <span className="text-xs font-medium text-text-secondary">{item.label}</span>
            <p className="mt-1 text-xl font-bold text-text tabular-nums">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Main Visuals Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Pipeline Category Breakdown */}
        <Panel
          title="Pipeline status distribution"
          className="lg:col-span-7"
          meta={`${formatNumber(categorised)} classified`}
        >
          <FunnelStages stages={funnelStages} total={data.total_applications} />
        </Panel>

        {/* Raw Status Breakdown */}
        <Panel
          title="Raw status distribution"
          className="lg:col-span-5"
          meta={`${Object.keys(data.status_counts).length} unique`}
        >
          <BarList
            rows={sortedCounts(data.status_counts)}
            total={data.total_applications}
            labelWidth={50}
          />
        </Panel>

        {/* Activity Over Time */}
        <Panel
          title="Applications submitted over time"
          className="lg:col-span-7"
          meta={`${trend.length} month bucket${trend.length === 1 ? '' : 's'}`}
        >
          <MonochromeLineChart
            data={trend}
            unit="applications"
            ariaLabel="Applications per calendar month"
          />
        </Panel>

        {/* Applications by Platform */}
        <Panel
          title="Applications by platform"
          className="lg:col-span-5"
          meta={`${platformRows.length} platforms`}
        >
          {platformRows.length === 0 ? (
            <p className="text-xs text-text-tertiary">No platform data recorded.</p>
          ) : (
            <BarList rows={platformRows} total={data.total_applications} labelWidth={50} />
          )}
        </Panel>

        {/* Platform Volume Chart */}
        {platformRows.length > 0 ? (
          <Panel
            title="Platform volume comparison"
            className="lg:col-span-7"
            meta={`Top ${Math.min(PLATFORM_LIMIT, platformRows.length)}`}
          >
            <MonochromeHBarChart
              data={platformRows.slice(0, PLATFORM_LIMIT)}
              unit="applications"
              ariaLabel="Applications per platform"
              categoryWidth={160}
            />
          </Panel>
        ) : null}

        {/* Application Types */}
        <Panel
          title="Application types"
          className={platformRows.length > 0 ? 'lg:col-span-5' : 'lg:col-span-12'}
          meta={`${typeRows.length} types`}
        >
          <BarList rows={typeRows} total={data.total_applications} labelWidth={45} />
        </Panel>

        {/* Data Quality & Missing Fields */}
        <Panel
          title="Data completeness"
          className="lg:col-span-12"
          meta={`${data.duplicate_groups.length} duplicate groups`}
        >
          {missingRows.length === 0 ? (
            <p className="text-xs text-text-secondary">All spreadsheet fields are populated.</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <BarList rows={missingRows} showShare={false} labelWidth={45} />
              <div className="flex flex-col justify-center text-xs text-text-secondary leading-relaxed space-y-2">
                <p>
                  Gaps represent empty fields in your spreadsheet. They are accounted for honestly
                  and never imputed or estimated.
                </p>
                <p>
                  {data.duplicate_groups.length === 0
                    ? 'No duplicates detected across application records.'
                    : `${data.duplicate_groups.length} duplicate groups were identified and grouped.`}
                </p>
              </div>
            </div>
          )}
        </Panel>
      </div>

      {/* Job-Market Analytics (Honest Empty State handling) */}
      <div className="mt-2">
        <h2 className="text-lg font-bold text-text mb-3">Job market intelligence</h2>
        {jobs.error && !jobs.data ? (
          <ErrorState error={jobs.error} onRetry={jobs.reload} />
        ) : !jobs.data ? (
          <LoadingState label="Loading job market data…" />
        ) : jobs.data.total_listings === 0 ? (
          <EmptyState
            title="No job listings data yet"
            message={
              <>
                Market analytics like requested skills, hiring locations, and role arrangements
                require listings in the Job Openings tab. As listings are collected, insights and
                matching scores against your{' '}
                {(matching.data?.interests ?? []).length} configured interests will display here.
              </>
            }
          >
            {matching.data?.interests && matching.data.interests.length > 0 ? (
              <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                {matching.data.interests.map((interest) => (
                  <Tag key={interest}>{interest}</Tag>
                ))}
              </div>
            ) : null}
          </EmptyState>
        ) : (
          <Panel title="Listings by location" meta={`${jobs.data.total_listings} total`}>
            <MonochromeHBarChart
              data={jobs.data.listings_by_location.map((row) => ({
                label: row.location,
                value: row.count,
              }))}
              unit="listings"
              ariaLabel="Listings per location"
            />
          </Panel>
        )}
      </div>
    </div>
  );
}
