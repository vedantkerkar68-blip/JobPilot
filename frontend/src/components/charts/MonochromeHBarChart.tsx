import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { ChartTooltip } from './ChartTooltip';
import { AXIS_STYLE, CHART_COLORS } from './chartTheme';

export interface BarDatum {
  label: string;
  value: number;
  shade?: string;
}

interface MonochromeHBarChartProps {
  data: BarDatum[];
  unit?: string;
  /** Width of the category axis, in pixels. Long labels need more room. */
  categoryWidth?: number;
  /** Height of one row, in pixels. */
  rowHeight?: number;
  ariaLabel: string;
  /** Optional note under the chart (truncation, coverage, etc.). */
  note?: string;
}

/** Horizontal bars — used when category labels are long. */
export function MonochromeHBarChart({
  data,
  unit = 'records',
  categoryWidth = 160,
  rowHeight = 28,
  ariaLabel,
  note,
}: MonochromeHBarChartProps) {
  if (data.length === 0) {
    return <p className="px-1 py-6 text-xs text-text-tertiary">No data to display.</p>;
  }

  const height = Math.max(160, data.length * rowHeight + 36);

  return (
    <figure className="m-0">
      <div role="img" aria-label={ariaLabel} style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 36, bottom: 4, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={AXIS_STYLE}
              tickLine={false}
              axisLine={{ stroke: CHART_COLORS.grid }}
              height={24}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={categoryWidth}
              tick={AXIS_STYLE}
              tickLine={false}
              axisLine={false}
              interval={0}
            />
            <Tooltip
              cursor={{ fill: 'rgba(36, 107, 80, 0.05)' }}
              content={<ChartTooltip unit={unit} />}
              wrapperStyle={{ outline: 'none' }}
            />
            <Bar dataKey="value" fill={CHART_COLORS.primary} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {data.map((entry) => (
                <Cell key={`hbar-${entry.label}`} fill={entry.shade ?? CHART_COLORS.primary} />
              ))}
              <LabelList
                dataKey="value"
                position="right"
                offset={8}
                style={{ ...AXIS_STYLE, fontSize: 11, fontWeight: 500 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {note ? (
        <figcaption className="mt-2 text-xs text-text-tertiary">{note}</figcaption>
      ) : null}
    </figure>
  );
}
