import { SANS } from './chartTheme';

interface ChartTooltipProps {
  active?: boolean;
  payload?: Array<{ value?: number; name?: string }>;
  label?: string;
  unit?: string;
}

export function ChartTooltip({ active, payload, label, unit }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div
      style={{
        fontFamily: SANS,
        fontSize: 12,
        backgroundColor: '#FFFFFF',
        border: '1px solid #E7E8E3',
        borderRadius: 6,
        padding: '8px 12px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
      }}
    >
      {label ? (
        <p style={{ color: '#6F746E', marginBottom: 2, fontSize: 11 }}>{label}</p>
      ) : null}
      {payload.map((entry, index) => (
        <p key={index} style={{ color: '#20231F', fontWeight: 600 }}>
          {entry.value?.toLocaleString('en-US')}
          {unit ? ` ${unit}` : ''}
        </p>
      ))}
    </div>
  );
}
