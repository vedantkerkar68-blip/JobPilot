import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AXIS_STYLE, CHART_COLORS } from './chartTheme';
import { ChartTooltip } from './ChartTooltip';

interface Datum {
  label: string;
  value: number;
  shade?: string;
}

interface MonochromeBarChartProps {
  data: Datum[];
  unit?: string;
  ariaLabel?: string;
}

export function MonochromeBarChart({ data, unit, ariaLabel }: MonochromeBarChartProps) {
  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-text-tertiary">No data available.</p>
    );
  }

  return (
    <div role="img" aria-label={ariaLabel} className="w-full" style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
          <XAxis dataKey="label" tick={AXIS_STYLE} axisLine={{ stroke: CHART_COLORS.grid }} tickLine={false} />
          <YAxis tick={AXIS_STYLE} axisLine={false} tickLine={false} width={40} />
          <Tooltip content={<ChartTooltip unit={unit} />} />
          <Bar dataKey="value" fill={CHART_COLORS.primary} radius={[4, 4, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
