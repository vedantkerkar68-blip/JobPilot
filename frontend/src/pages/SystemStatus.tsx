import { API_ROOT } from '../api/client';
import { Button } from '../components/ui/Button';
import { Tag } from '../components/ui/Chip';
import { DefinitionList } from '../components/ui/DefinitionList';
import { Panel } from '../components/ui/Panel';
import { ErrorState, LoadingState } from '../components/ui/states';
import { ConnectionBadge } from '../components/layout/ConnectionBadge';
import { CAPABILITIES } from '../lib/capabilities';
import { cx } from '../lib/cx';
import { formatNumber, formatUtcTimestamp } from '../lib/format';
import { useSystem } from '../system/SystemContext';

interface EndpointRow {
  method: 'GET';
  path: string;
  description: string;
  mutates: boolean;
}

const ENDPOINTS: EndpointRow[] = [
  { method: 'GET', path: '/api/health', description: 'Backend and data-source health status', mutates: false },
  { method: 'GET', path: '/api/dashboard', description: 'Consolidated dashboard metrics', mutates: false },
  { method: 'GET', path: '/api/applications', description: 'Application records, filters, and pagination', mutates: false },
  { method: 'GET', path: '/api/jobs', description: 'Job openings, filters, and pagination', mutates: false },
  { method: 'GET', path: '/api/analytics/applications', description: 'Pipeline analytics and status breakdown', mutates: false },
  { method: 'GET', path: '/api/analytics/jobs', description: 'Job opening and market metrics', mutates: false },
  { method: 'GET', path: '/api/analytics/skills', description: 'Skill frequency across job openings', mutates: false },
  { method: 'GET', path: '/api/analytics/matching', description: 'Interest and preference match scoring', mutates: false },
  { method: 'GET', path: '/api/meta', description: 'System metadata and user preference keywords', mutates: false },
];

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null;
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null;
}

export function SystemStatus() {
  const { health, meta, healthError, metaError, connection, lastCheckedAt, refresh, loading } =
    useSystem();

  const checks = health?.checks ?? {};
  const dataError = asString(checks['data_error']);
  const applicationsRows = asNumber(checks['applications_rows']);
  const uniqueApplications = asNumber(checks['applications_unique']);
  const jobRows = asNumber(checks['job_openings_rows']);
  const uniqueJobs = asNumber(checks['job_openings_unique']);
  const sheetsConfigured = asBoolean(checks['google_sheets_configured']);
  const cached = asBoolean(checks['cached']);
  const fetchedAt = asString(checks['fetched_at']);
  const applicationsTab = asString(checks['applications_tab']);
  const jobTab = asString(checks['job_openings_tab']);

  const connectionItems = [
    { label: 'Connection status', value: <ConnectionBadge state={connection} /> },
    { label: 'Backend service', value: health ? `${health.app} v${health.version}` : '—', mono: true },
    { label: 'Environment', value: health?.environment ?? '—', mono: true },
    { label: 'Data source', value: health?.data_source ?? '—', mono: true },
    { label: 'API base URL', value: API_ROOT, mono: true },
    { label: 'Last checked', value: lastCheckedAt ? formatUtcTimestamp(lastCheckedAt.toISOString()) : '—', mono: true },
    { label: 'Backend timestamp', value: formatUtcTimestamp(health?.timestamp), mono: true },
  ];

  const dataSourceItems = [
    {
      label: 'Applications tab',
      value: applicationsTab ?? (health?.data_source === 'csv' ? 'CSV fallback' : '—'),
      mono: true,
    },
    {
      label: 'Job openings tab',
      value: jobTab ?? (health?.data_source === 'csv' ? 'CSV fallback' : '—'),
      mono: true,
    },
    {
      label: 'Google Sheets credentials',
      value: sheetsConfigured === null ? '—' : sheetsConfigured ? 'Configured' : 'Not configured',
      mono: true,
    },
    {
      label: 'Application records read',
      value: applicationsRows === null ? '—' : formatNumber(applicationsRows),
      mono: true,
    },
    {
      label: 'Unique applications',
      value: uniqueApplications === null ? '—' : formatNumber(uniqueApplications),
      mono: true,
    },
    {
      label: 'Job opening rows',
      value: jobRows === null ? '—' : formatNumber(jobRows),
      mono: true,
    },
    {
      label: 'Unique job listings',
      value: uniqueJobs === null ? '—' : formatNumber(uniqueJobs),
      mono: true,
    },
    {
      label: 'Snapshot fetched',
      value: formatUtcTimestamp(fetchedAt),
      mono: true,
    },
    {
      label: 'Cached in memory',
      value: cached === null ? '—' : cached ? 'Yes' : 'No',
      mono: true,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">System Status</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Backend health, connected data sources, and capability verification.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={refresh} disabled={loading} prefix="↻">
          {loading ? 'Checking…' : 'Re-check status'}
        </Button>
      </div>

      {connection === 'degraded' && dataError ? (
        <ErrorState
          title="Data source warning"
          error={{ kind: 'unavailable', status: 503, message: dataError }}
          onRetry={refresh}
        />
      ) : null}

      {healthError && !health ? (
        <ErrorState
          title="Backend unreachable"
          error={healthError}
          onRetry={refresh}
        />
      ) : null}

      {!health && !healthError ? <LoadingState label="Connecting to backend…" /> : null}

      {health ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel title="Connection & Runtime" meta={health.status.toUpperCase()}>
            <DefinitionList items={connectionItems} columns={2} />
          </Panel>

          <Panel title="Data Source Integration" meta={(health.data_source).toUpperCase()}>
            <DefinitionList items={dataSourceItems} columns={2} />
          </Panel>
        </div>
      ) : null}

      {metaError && !meta ? (
        <ErrorState title="Configuration unavailable" error={metaError} onRetry={refresh} />
      ) : null}

      {meta ? (
        <Panel title="Configured Search Interests" meta="Preference Matching">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div>
              <span className="text-xs font-semibold text-text-secondary">Target Interest Keywords</span>
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {meta.interests.map((interest) => (
                  <li key={interest}>
                    <Tag>{interest}</Tag>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <span className="text-xs font-semibold text-text-secondary">Preferred Locations</span>
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {meta.preferred_locations.map((place) => (
                  <li key={place}>
                    <Tag>{place}</Tag>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Panel>
      ) : null}

      {/* Capability Verification Matrix */}
      <Panel
        title="Feature capability matrix"
        meta={`${CAPABILITIES.filter((c) => c.state === 'available').length} of ${CAPABILITIES.length} connected`}
        bodyClassName="p-0"
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="bg-surface-alt border-b border-border text-xs font-semibold text-text-secondary">
                <th className="px-4 py-2.5">Feature</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Integration backing</th>
                <th className="px-4 py-2.5">Current state</th>
              </tr>
            </thead>
            <tbody>
              {CAPABILITIES.map((cap) => (
                <tr key={cap.id} className="border-b border-border last:border-b-0 hover:bg-surface-alt/40">
                  <td className="px-4 py-3 font-semibold text-text">{cap.title}</td>
                  <td className="px-4 py-3">
                    <span
                      className={cx(
                        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                        cap.state === 'available'
                          ? 'bg-brand-light text-brand'
                          : 'bg-surface-alt text-text-tertiary',
                      )}
                    >
                      {cap.state === 'available' ? 'Available' : 'Unavailable'}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-text-secondary">
                    {cap.endpoints.length > 0 ? cap.endpoints.join(', ') : 'None'}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary max-w-sm">
                    {cap.state === 'available' ? cap.reality : (cap.blocker ?? cap.reality)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* API Endpoint Inventory */}
      <Panel
        title="Backend API routes"
        meta={`${ENDPOINTS.length} endpoints · Read-only`}
        bodyClassName="p-0"
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="bg-surface-alt border-b border-border text-xs font-semibold text-text-secondary">
                <th className="px-4 py-2.5">Method</th>
                <th className="px-4 py-2.5">Route</th>
                <th className="px-4 py-2.5">Description</th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map((endpoint) => (
                <tr key={endpoint.path} className="border-b border-border last:border-b-0 hover:bg-surface-alt/40">
                  <td className="px-4 py-2.5 font-mono text-xs font-semibold text-brand">
                    {endpoint.method}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-text">
                    {endpoint.path}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-text-secondary">
                    {endpoint.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
