import { cx } from '../../lib/cx';
import type { ClassValue } from '../../lib/cx';

interface RuleProps {
  variant?: 'default' | 'ticks';
  className?: ClassValue;
}

export function Rule({ variant = 'default', className }: RuleProps) {
  return (
    <hr
      className={cx(
        'border-0 h-px',
        variant === 'ticks' ? 'bg-border border-dashed' : 'bg-border',
        className,
      )}
    />
  );
}
