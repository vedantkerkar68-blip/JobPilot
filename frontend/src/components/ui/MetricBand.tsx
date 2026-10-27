import { cx } from '../../lib/cx';
import { formatNumber } from '../../lib/format';

export interface Metric {
  key: string;
  label: string;
  value: number;
  emphasis?: boolean;
  note?: string;
}

interface MetricBandProps {
  metrics: Metric[];
}

export function MetricBand({ metrics }: MetricBandProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {metrics.map((metric) => (
        <div
          key={metric.key}
          className={cx(
            'rounded-lg border p-4',
            metric.emphasis
              ? 'bg-brand text-white border-brand'
              : 'bg-surface border-border',
          )}
        >
          <p
            className={cx(
              'text-xs font-medium',
              metric.emphasis ? 'text-white/70' : 'text-text-secondary',
            )}
          >
            {metric.label}
          </p>
          <p
            className={cx(
              'tnum mt-1 text-2xl font-bold tracking-tight',
              metric.emphasis ? 'text-white' : 'text-text',
            )}
          >
            {formatNumber(metric.value)}
          </p>
          {metric.note ? (
            <p
              className={cx(
                'mt-1 text-xs leading-snug',
                metric.emphasis ? 'text-white/60' : 'text-text-tertiary',
              )}
            >
              {metric.note}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
