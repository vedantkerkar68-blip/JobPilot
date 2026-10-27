import type { ReactNode } from 'react';

interface DefinitionItem {
  label: string;
  value: ReactNode;
  mono?: boolean;
}

interface DefinitionListProps {
  items: DefinitionItem[];
  columns?: number;
}

export function DefinitionList({ items, columns = 2 }: DefinitionListProps) {
  const gridClass =
    columns === 4
      ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4'
      : columns === 3
        ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'
        : 'grid-cols-1 sm:grid-cols-2';

  return (
    <dl className={`grid gap-x-6 gap-y-3 ${gridClass}`}>
      {items.map((item) => (
        <div key={item.label}>
          <dt className="text-xs text-text-tertiary">{item.label}</dt>
          <dd
            className={`mt-0.5 text-sm ${item.mono ? 'font-mono text-xs' : ''} text-text`}
          >
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
