import { useLocation } from 'react-router-dom';
import { formatNumber } from '../../lib/format';
import { useSystem } from '../../system/SystemContext';
import { Button } from '../ui/Button';
import { ConnectionBadge } from './ConnectionBadge';
import { navItemByPath } from './navItems';

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/**
 * Top bar: Clean, calm header with current section title, connection status,
 * application count, and sync action.
 */
export function Header() {
  const { pathname } = useLocation();
  const item = navItemByPath(pathname);
  const { connection, health, refresh, loading } = useSystem();

  const checks = health?.checks ?? {};
  const uniqueApplications = asNumber(checks['applications_unique']);

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/95 backdrop-blur-xs">
      <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-6">
        {/* Left: Section title & description */}
        <div className="min-w-0">
          <h1 className="text-base font-bold text-text truncate sm:text-lg">
            {item.label}
          </h1>
          <p className="hidden text-xs text-text-secondary truncate sm:block">
            {item.description}
          </p>
        </div>

        {/* Right: Operational indicators */}
        <div className="flex items-center gap-2.5 shrink-0">
          <ConnectionBadge state={connection} />

          {uniqueApplications !== null ? (
            <span className="hidden items-center gap-1.5 rounded-full border border-border bg-surface-alt px-2.5 py-0.5 text-xs text-text-secondary sm:inline-flex">
              <span className="font-semibold text-text tabular-nums">
                {formatNumber(uniqueApplications)}
              </span>
              <span>applications</span>
            </span>
          ) : null}

          <Button
            size="sm"
            variant="outline"
            onClick={refresh}
            disabled={loading}
            prefix="↻"
            className="text-xs"
          >
            {loading ? 'Syncing…' : 'Sync'}
          </Button>
        </div>
      </div>
    </header>
  );
}
