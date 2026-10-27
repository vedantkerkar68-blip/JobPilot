import { cx } from '../../lib/cx';
import type { ConnectionState } from '../../system/SystemContext';

const LABEL: Record<ConnectionState, string> = {
  ok: 'Connected',
  degraded: 'Degraded',
  offline: 'Offline',
  checking: 'Checking…',
};

const DOT_COLOR: Record<ConnectionState, string> = {
  ok: 'bg-brand',
  degraded: 'bg-amber',
  offline: 'bg-danger',
  checking: 'bg-text-tertiary animate-pulse',
};

const BADGE_STYLE: Record<ConnectionState, string> = {
  ok: 'border-brand/20 bg-brand-light text-brand',
  degraded: 'border-amber/20 bg-amber-light text-amber',
  offline: 'border-danger/20 bg-danger-light text-danger',
  checking: 'border-border bg-surface-alt text-text-secondary',
};

interface ConnectionBadgeProps {
  state: ConnectionState;
  /** Long-form explanation, surfaced as a tooltip. */
  detail?: string;
  className?: string;
}

export function ConnectionBadge({ state, detail, className }: ConnectionBadgeProps) {
  return (
    <span
      title={detail ?? LABEL[state]}
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        BADGE_STYLE[state],
        className,
      )}
    >
      <span className={cx('h-1.5 w-1.5 rounded-full', DOT_COLOR[state])} aria-hidden="true" />
      <span>{LABEL[state]}</span>
      <span className="sr-only">Backend status: {LABEL[state]}</span>
    </span>
  );
}
