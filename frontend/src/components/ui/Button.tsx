import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { cx } from '../../lib/cx';
import type { ClassValue } from '../../lib/cx';

type Variant = 'solid' | 'outline' | 'ghost';
type Size = 'sm' | 'md';

interface ButtonProps {
  variant?: Variant;
  size?: Size;
  prefix?: string;
  children: ReactNode;
  className?: ClassValue;
  disabled?: boolean;
  onClick?: () => void;
}

const BASE =
  'inline-flex items-center justify-center gap-1.5 font-medium transition-colors duration-150 rounded-md whitespace-nowrap select-none';

function sizeClass(size: Size): string {
  return size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm';
}

function variantClass(variant: Variant): string {
  switch (variant) {
    case 'solid':
      return 'bg-brand text-white border border-brand hover:bg-brand-hover active:bg-brand-hover';
    case 'outline':
      return 'bg-surface text-text border border-border hover:bg-surface-alt active:bg-surface-alt';
    case 'ghost':
      return 'bg-transparent text-text-secondary border border-transparent hover:bg-surface-alt active:bg-surface-alt';
  }
}

export function Button({
  variant = 'outline',
  size = 'md',
  prefix,
  children,
  className,
  disabled,
  onClick,
}: ButtonProps) {
  return (
    <button
      type="button"
      className={cx(
        BASE,
        sizeClass(size),
        variantClass(variant),
        disabled && 'opacity-50 cursor-not-allowed pointer-events-none',
        className,
      )}
      disabled={disabled}
      onClick={onClick}
    >
      {prefix ? <span aria-hidden="true">{prefix}</span> : null}
      {children}
    </button>
  );
}

interface ButtonLinkProps {
  to: string;
  variant?: Variant;
  size?: Size;
  children: ReactNode;
  className?: ClassValue;
}

export function ButtonLink({
  to,
  variant = 'outline',
  size = 'md',
  children,
  className,
}: ButtonLinkProps) {
  return (
    <Link
      to={to}
      className={cx(BASE, sizeClass(size), variantClass(variant), className)}
    >
      {children}
    </Link>
  );
}
