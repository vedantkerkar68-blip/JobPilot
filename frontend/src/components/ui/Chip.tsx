import type { ReactNode } from 'react';
import type { StatusCategory } from '../../api/types';
import type { ConnectionState } from '../../system/SystemContext';
import { cx } from '../../lib/cx';
import type { ClassValue } from '../../lib/cx';
import { categoryChipClass, verificationChipClass, CATEGORY_LABEL } from '../../lib/status';

interface ChipProps {
  children: ReactNode;
  className?: ClassValue;
  title?: string;
}

export function Chip({ children, className, title }: ChipProps) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        className,
      )}
      title={title}
    >
      {children}
    </span>
  );
}

export function Tag({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <span
      className="inline-flex items-center rounded-md bg-surface-alt border border-border px-2 py-0.5 text-xs text-text-secondary"
      title={title}
    >
      {children}
    </span>
  );
}

export function CategoryChip({ category }: { category: StatusCategory }) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        categoryChipClass(category),
      )}
    >
      {CATEGORY_LABEL[category]}
    </span>
  );
}

export function VerificationChip({ status }: { status: string }) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        verificationChipClass(status),
      )}
    >
      {status}
    </span>
  );
}

function connectionColor(state: ConnectionState): string {
  switch (state) {
    case 'ok':
      return 'bg-brand';
    case 'degraded':
      return 'bg-amber';
    case 'offline':
      return 'bg-danger';
    default:
      return 'bg-text-tertiary';
  }
}

function connectionLabel(state: ConnectionState): string {
  switch (state) {
    case 'ok':
      return 'Connected';
    case 'degraded':
      return 'Degraded';
    case 'offline':
      return 'Offline';
    default:
      return 'Checking';
  }
}

export function StateChip({
  state,
}: {
  state: ConnectionState | 'available' | 'unavailable';
}) {
  const mapped: ConnectionState =
    state === 'available' ? 'ok' : state === 'unavailable' ? 'offline' : state;

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-text-secondary">
      <span className={cx('h-2 w-2 rounded-full', connectionColor(mapped))} />
      {state === 'available'
        ? 'Available'
        : state === 'unavailable'
          ? 'Unavailable'
          : connectionLabel(mapped)}
    </span>
  );
}
