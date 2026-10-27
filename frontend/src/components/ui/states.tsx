import type { ReactNode } from 'react';
import type { ApiError } from '../../api/client';
import { errorCode } from '../../api/client';
import { Button } from './Button';
import { cx } from '../../lib/cx';
import type { ClassValue } from '../../lib/cx';

/* -------------------------------------------------------------------------- */
/* Loading                                                                    */
/* -------------------------------------------------------------------------- */

interface LoadingProps {
  label?: string;
  detail?: string;
}

export function LoadingState({ label, detail }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="h-8 w-8 rounded-full border-2 border-border border-t-brand animate-spin" />
      {label ? <p className="text-sm font-medium text-text-secondary">{label}</p> : null}
      {detail ? <p className="text-xs text-text-tertiary max-w-md">{detail}</p> : null}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Error                                                                      */
/* -------------------------------------------------------------------------- */

interface ErrorProps {
  title?: string;
  code?: string;
  error: ApiError;
  onRetry?: () => void;
}

export function ErrorState({ title, error, onRetry }: ErrorProps) {
  return (
    <div className="rounded-lg border border-danger/20 bg-danger-light p-5">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm-.75 3.75a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zM8 11a1 1 0 100 2 1 1 0 000-2z" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-danger">{title ?? errorCode(error)}</p>
          <p className="mt-1 text-sm text-text-secondary leading-relaxed">{error.message}</p>
          {onRetry ? (
            <div className="mt-3">
              <Button size="sm" variant="outline" onClick={onRetry}>
                Try again
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Empty                                                                      */
/* -------------------------------------------------------------------------- */

interface EmptyProps {
  title: string;
  code?: string;
  message: ReactNode;
  children?: ReactNode;
  className?: ClassValue;
}

export function EmptyState({ title, message, children, className }: EmptyProps) {
  return (
    <div
      className={cx(
        'rounded-lg border border-border bg-surface p-8 text-center',
        className,
      )}
    >
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-surface-alt">
        <svg
          className="h-6 w-6 text-text-tertiary"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
          />
        </svg>
      </div>
      <h3 className="mt-4 text-base font-semibold text-text">{title}</h3>
      <div className="mt-2 text-sm text-text-secondary leading-relaxed max-w-md mx-auto">
        {message}
      </div>
      {children ? <div className="mt-5">{children}</div> : null}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Note                                                                       */
/* -------------------------------------------------------------------------- */

interface NoteProps {
  children: ReactNode;
  className?: ClassValue;
}

export function Note({ children, className }: NoteProps) {
  return (
    <p className={cx('text-xs text-text-tertiary leading-relaxed', className)}>{children}</p>
  );
}

/* -------------------------------------------------------------------------- */
/* Table skeleton                                                             */
/* -------------------------------------------------------------------------- */

interface TableSkeletonProps {
  columns: number;
  rows: number;
}

export function TableSkeleton({ columns, rows }: TableSkeletonProps) {
  return (
    <div className="p-4">
      <div className="space-y-3">
        {Array.from({ length: rows }, (_, rowIndex) => (
          <div key={rowIndex} className="flex gap-4">
            {Array.from({ length: columns }, (_, colIndex) => (
              <div key={colIndex} className="h-4 flex-1 rounded shimmer" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
