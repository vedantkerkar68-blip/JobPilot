import type { StatusCategory } from '../../api/types';
import { text } from '../../lib/format';
import { CategoryChip } from '../ui/Chip';

/**
 * Status cell: shows the primary status with the semantic category indicator.
 */
export function StatusCell({
  status,
  category,
}: {
  status: string | null;
  category: StatusCategory;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <CategoryChip category={category} />
      {status && status.toLowerCase() !== category ? (
        <span className="text-xs text-text-secondary truncate max-w-[12rem]" title={status}>
          {text(status)}
        </span>
      ) : null}
    </div>
  );
}
