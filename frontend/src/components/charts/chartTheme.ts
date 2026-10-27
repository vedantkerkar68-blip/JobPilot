/**
 * Shared chart theme constants for Recharts.
 * Uses the new warm design palette.
 */

export const SANS = "'Manrope', 'Inter', sans-serif";
export const MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace";

export const CHART_COLORS = {
  primary: '#246B50',
  secondary: '#3A9B74',
  tertiary: '#9B9F99',
  amber: '#C18B45',
  danger: '#A33E32',
  grid: '#E7E8E3',
  text: '#6F746E',
  background: '#F0F1EC',
};

export const AXIS_STYLE = {
  fontFamily: SANS,
  fontSize: 11,
  fill: CHART_COLORS.text,
};

export const TOOLTIP_STYLE: React.CSSProperties = {
  fontFamily: SANS,
  fontSize: 12,
  backgroundColor: '#FFFFFF',
  border: '1px solid #E7E8E3',
  borderRadius: 6,
  padding: '8px 12px',
  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
};

// Re-export for backward compatibility
export { SANS as GROTESK };
