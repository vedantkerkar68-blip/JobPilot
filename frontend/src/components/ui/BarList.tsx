import { formatNumber } from '../../lib/format';

interface BarListRow {
  label: string;
  value: number;
}

interface BarListProps {
  rows: BarListRow[];
  total?: number;
  showShare?: boolean;
  labelWidth?: number;
}

export function BarList({ rows, total, showShare = true, labelWidth }: BarListProps) {
  const max = rows.reduce((m, r) => Math.max(m, r.value), 0);

  return (
    <div className="flex flex-col gap-2">
      {rows.map((row) => {
        const pct = max > 0 ? (row.value / max) * 100 : 0;
        const share =
          total && total > 0 ? ((row.value / total) * 100).toFixed(1) : null;

        return (
          <div key={row.label} className="flex items-center gap-3">
            <span
              className="text-xs text-text-secondary truncate shrink-0"
              style={labelWidth ? { width: `${labelWidth}%` } : { width: '40%' }}
              title={row.label}
            >
              {row.label}
            </span>
            <div className="flex-1 h-5 bg-surface-alt rounded overflow-hidden">
              <div
                className="h-full bg-brand/15 rounded transition-all duration-300"
                style={{ width: `${Math.max(pct, 2)}%` }}
              />
            </div>
            <span className="tnum text-xs font-medium text-text tabular-nums shrink-0 w-10 text-right">
              {formatNumber(row.value)}
            </span>
            {showShare && share !== null ? (
              <span className="tnum text-xs text-text-tertiary tabular-nums shrink-0 w-12 text-right">
                {share}%
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
