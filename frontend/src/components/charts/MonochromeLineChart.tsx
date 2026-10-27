import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { ChartTooltip } from './ChartTooltip';
import { AXIS_STYLE, CHART_COLORS } from './chartTheme';

export interface LineDatum {
  label: string;
  value: number;
}

interface MonochromeLineChartProps {
  data: LineDatum[];
  unit?: string;
  height?: number;
  ariaLabel: string;
}

/**
 * Trend line with a subtle forest green gradient band beneath it.
 */
export function MonochromeLineChart({
  data,
  unit = 'applications',
  height = 240,
  ariaLabel,
}: MonochromeLineChartProps) {
  if (data.length === 0) {
    return <p className="px-1 py-6 text-xs text-text-tertiary">No data to display.</p>;
  }

  return (
    <div role="img" aria-label={ariaLabel} style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_COLORS.primary} stopOpacity={0.2} />
              <stop offset="100%" stopColor={CHART_COLORS.primary} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
          <XAxis
            dataKey="label"
            tick={AXIS_STYLE}
            axisLine={{ stroke: CHART_COLORS.grid }}
            tickLine={false}
          />
          <YAxis
            tick={AXIS_STYLE}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
            width={32}
          />
          <Tooltip
            cursor={{ stroke: CHART_COLORS.primary, strokeWidth: 1, strokeDasharray: '3 3' }}
            content={<ChartTooltip unit={unit} />}
            wrapperStyle={{ outline: 'none' }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={CHART_COLORS.primary}
            strokeWidth={2}
            fill="url(#areaGradient)"
            isAnimationActive={false}
            dot={{ r: 3, fill: CHART_COLORS.primary, stroke: '#FFFFFF', strokeWidth: 1.5 }}
            activeDot={{ r: 5, fill: CHART_COLORS.primary, stroke: '#FFFFFF', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
