import type { ReactNode } from 'react';
import { cx } from '../../lib/cx';

export interface SortState {
  key: string;
  direction: 'asc' | 'desc';
}

export interface Column<T> {
  key: string;
  header: string;
  width?: string;
  sortable?: boolean;
  sortValue?: (row: T) => string | number | null;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  sort?: SortState;
  onSortChange?: (key: string) => void;
  stickyHeader?: boolean;
  empty?: ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  sort,
  onSortChange,
  stickyHeader,
  empty,
}: DataTableProps<T>) {
  if (rows.length === 0 && empty) {
    return <>{empty}</>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className={cx(stickyHeader && 'sticky top-0 z-10')}>
            {columns.map((col) => {
              const isSorted = sort?.key === col.key;
              const arrow = isSorted
                ? sort.direction === 'asc'
                  ? ' ↑'
                  : ' ↓'
                : '';

              return (
                <th
                  key={col.key}
                  scope="col"
                  style={col.width ? { width: col.width, minWidth: col.width } : undefined}
                  className={cx(
                    'bg-surface-alt px-4 py-2.5 text-xs font-semibold text-text-secondary border-b border-border',
                    col.sortable && 'cursor-pointer select-none hover:text-text',
                  )}
                  onClick={
                    col.sortable && onSortChange ? () => onSortChange(col.key) : undefined
                  }
                >
                  {col.header}
                  {arrow}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className="border-b border-border last:border-b-0 hover:bg-surface-alt/50 transition-colors"
            >
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-3 text-sm">
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
