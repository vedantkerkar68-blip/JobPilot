import { formatNumber } from '../../lib/format';

interface FunnelStage {
  label: string;
  value: number;
  shade: string;
  note: string;
}

interface FunnelStagesProps {
  stages: FunnelStage[];
  total: number;
}

export function FunnelStages({ stages, total }: FunnelStagesProps) {
  const max = stages.reduce((m, s) => Math.max(m, s.value), 0);

  return (
    <div className="flex flex-col gap-3">
      {stages.map((stage) => {
        const pct = max > 0 ? (stage.value / max) * 100 : 0;
        const share = total > 0 ? ((stage.value / total) * 100).toFixed(1) : '0.0';

        return (
          <div key={stage.label} className="flex items-center gap-3">
            <span className="text-xs font-medium text-text-secondary w-20 shrink-0">
              {stage.label}
            </span>
            <div className="flex-1 h-7 bg-surface-alt rounded-md overflow-hidden relative">
              <div
                className="h-full rounded-md transition-all duration-500"
                style={{
                  width: `${Math.max(pct, 3)}%`,
                  backgroundColor: stage.shade,
                  opacity: 0.75,
                }}
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium text-text-secondary tabular-nums">
                {formatNumber(stage.value)}
              </span>
            </div>
            <span className="text-xs text-text-tertiary tabular-nums w-12 text-right shrink-0">
              {share}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
