import type { ReactNode } from 'react';
import { cx } from '../../lib/cx';
import type { ClassValue } from '../../lib/cx';

interface PanelProps {
  index?: string;
  title?: string;
  meta?: string;
  tone?: 'default' | 'ink';
  actions?: ReactNode;
  children: ReactNode;
  className?: ClassValue;
  bodyClassName?: ClassValue;
}

export function Panel({
  title,
  meta,
  tone = 'default',
  actions,
  children,
  className,
  bodyClassName,
}: PanelProps) {
  const isInk = tone === 'ink';

  return (
    <section
      className={cx(
        'rounded-lg border overflow-hidden',
        isInk ? 'bg-text border-text text-text-inverse' : 'bg-surface border-border',
        className,
      )}
    >
      {title ? (
        <header
          className={cx(
            'flex items-center justify-between gap-3 px-5 py-3',
            isInk ? 'border-b border-white/10' : 'border-b border-border',
          )}
        >
          <div className="flex items-center gap-3 min-w-0">
            <h3 className={cx('text-sm font-semibold', isInk ? 'text-white' : 'text-text')}>
              {title}
            </h3>
            {meta ? (
              <span className={cx('text-xs', isInk ? 'text-white/50' : 'text-text-tertiary')}>
                {meta}
              </span>
            ) : null}
          </div>
          {actions ? <div className="flex items-center gap-2 shrink-0">{actions}</div> : null}
        </header>
      ) : null}
      <div className={cx(bodyClassName ?? 'p-5')}>{children}</div>
    </section>
  );
}
