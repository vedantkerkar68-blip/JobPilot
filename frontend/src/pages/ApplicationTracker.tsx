import { useEffect, useMemo, useState } from 'react';

import { listApplications } from '../api/endpoints';
import type { ApplicationListResponse, ApplicationRecord } from '../api/types';
import { StatusCell } from '../components/domain/StatusCell';
import { Button } from '../components/ui/Button';
import { DataTable } from '../components/ui/DataTable';
import type { Column, SortState } from '../components/ui/DataTable';
import { SelectInput, TextInput } from '../components/ui/Field';
import { Pagination } from '../components/ui/Pagination';
import { Panel } from '../components/ui/Panel';
import { EmptyState, ErrorState, TableSkeleton } from '../components/ui/states';
import { useApi } from '../hooks/useApi';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { formatNumber, text } from '../lib/format';
import { CATEGORY_LABEL, CATEGORY_ORDER } from '../lib/status';

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200];

type SortableValue = string | number | null;

function compareValues(a: SortableValue, b: SortableValue): number {
  const aMissing = a === null || a === undefined || a === '';
  const bMissing = b === null || b === undefined || b === '';
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  const aText = String(a);
  const bText = String(b);
  const numeric = Number(aText) - Number(bText);
  if (!Number.isNaN(numeric) && aText.trim() !== '' && bText.trim() !== '') return numeric;
  return aText.localeCompare(bText);
}

export function ApplicationTracker() {
  const [companyInput, setCompanyInput] = useState('');
  const [status, setStatus] = useState('');
  const [platform, setPlatform] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sort, setSort] = useState<SortState>({ key: 'application_date', direction: 'desc' });

  const company = useDebouncedValue(companyInput, 350);

  useEffect(() => {
    setPage(1);
  }, [company, status, platform, pageSize]);

  const { data, error, loading, reload } = useApi<ApplicationListResponse>(
    (signal) =>
      listApplications(
        {
          company: company.trim() || undefined,
          status: status || undefined,
          platform: platform || undefined,
          page,
          page_size: pageSize,
        },
        signal,
      ),
    [company, status, platform, page, pageSize],
  );

  const columns = useMemo<Array<Column<ApplicationRecord>>>(
    () => [
      {
        key: 'company',
        header: 'Company',
        width: '13rem',
        sortable: true,
        sortValue: (row) => row.company,
        render: (row) => (
          <span className="font-semibold text-text" title={row.tracking_key ?? undefined}>
            {text(row.company, 'Unknown company')}
          </span>
        ),
      },
      {
        key: 'role',
        header: 'Role',
        width: '16rem',
        sortable: true,
        sortValue: (row) => row.role,
        render: (row) => <span className="text-text-secondary">{text(row.role, '—')}</span>,
      },
      {
        key: 'status',
        header: 'Status',
        width: '13rem',
        sortable: true,
        sortValue: (row) => row.status_category,
        render: (row) => <StatusCell status={row.status} category={row.status_category} />,
      },
      {
        key: 'application_date',
        header: 'Applied',
        width: '7.5rem',
        sortable: true,
        sortValue: (row) => row.application_date,
        render: (row) => (
          <span className="tabular-nums text-xs text-text-secondary">
            {text(row.application_date, '—')}
          </span>
        ),
      },
      {
        key: 'latest_update_date',
        header: 'Updated',
        width: '7.5rem',
        sortable: true,
        sortValue: (row) => row.latest_update_date,
        render: (row) => (
          <span className="tabular-nums text-xs text-text-secondary">
            {text(row.latest_update_date, '—')}
          </span>
        ),
      },
      {
        key: 'application_type',
        header: 'Type',
        width: '8rem',
        sortable: true,
        sortValue: (row) => row.application_type,
        render: (row) => (
          <span className="text-xs text-text-tertiary">
            {text(row.application_type, '—')}
          </span>
        ),
      },
      {
        key: 'platform',
        header: 'Platform',
        width: '11rem',
        sortable: true,
        sortValue: (row) => row.platform,
        render: (row) => (
          <span className="text-xs text-text-secondary truncate max-w-[10rem] block" title={row.platform ?? undefined}>
            {text(row.platform, '—')}
          </span>
        ),
      },
      {
        key: 'job_id',
        header: 'Job ID',
        width: '6.5rem',
        sortable: true,
        sortValue: (row) => row.job_id,
        render: (row) => (
          <span className="font-mono text-xs text-text-tertiary">
            {text(row.job_id, '—')}
          </span>
        ),
      },
    ],
    [],
  );

  const statuses = data?.available_statuses ?? [];
  const platforms = data?.available_platforms ?? [];
  const rows = data?.items ?? [];

  const sortedRows = useMemo(() => {
    const column = columns.find((candidate) => candidate.key === sort.key);
    if (!column?.sortValue) return rows;
    const factor = sort.direction === 'asc' ? 1 : -1;
    return [...rows].sort(
      (a, b) => compareValues(column.sortValue!(a), column.sortValue!(b)) * factor,
    );
  }, [rows, columns, sort]);

  const handleSort = (key: string) => {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'asc' },
    );
  };

  const activeFilters = [status, platform, company.trim()].filter(Boolean).length;
  const clearFilters = () => {
    setCompanyInput('');
    setStatus('');
    setPlatform('');
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Applications</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Track every application and see where things stand.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data ? (
            <span className="rounded-full bg-brand-light px-3 py-1 text-xs font-semibold text-brand">
              {formatNumber(data.total)} total applications
            </span>
          ) : null}
          <Button size="sm" variant="outline" onClick={reload} prefix="↻">
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter Controls Toolbar */}
      <div className="rounded-xl border border-border bg-surface p-4 shadow-2xs">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <TextInput
            label="Search company or role"
            placeholder="e.g. Google, Frontend…"
            value={companyInput}
            onChange={(event) => setCompanyInput(event.target.value)}
          />

          <SelectInput
            label="Filter status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            <optgroup label="Categories">
              {CATEGORY_ORDER.map((category) => (
                <option key={category} value={category}>
                  {CATEGORY_LABEL[category]}
                </option>
              ))}
            </optgroup>
            {statuses.length > 0 ? (
              <optgroup label="Recorded status text">
                {statuses.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </optgroup>
            ) : null}
          </SelectInput>

          <SelectInput
            label="Filter platform"
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
          >
            <option value="">All platforms</option>
            {platforms.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </SelectInput>

          <SelectInput
            label="Rows per page"
            value={String(pageSize)}
            onChange={(event) => setPageSize(Number(event.target.value))}
          >
            {PAGE_SIZE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option} rows
              </option>
            ))}
          </SelectInput>
        </div>

        {activeFilters > 0 ? (
          <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs text-text-secondary">
            <span>
              {activeFilters} filter{activeFilters === 1 ? '' : 's'} active
            </span>
            <Button size="sm" variant="ghost" onClick={clearFilters}>
              Clear all filters
            </Button>
          </div>
        ) : null}
      </div>

      {/* Main Table Surface */}
      <Panel
        title="Application records"
        meta={
          data
            ? `Page ${data.page} of ${Math.max(data.total_pages, 1)}`
            : undefined
        }
        bodyClassName="p-0"
      >
        {error && !data ? (
          <div className="p-6">
            <ErrorState error={error} onRetry={reload} />
          </div>
        ) : loading && !data ? (
          <TableSkeleton columns={columns.length} rows={8} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={sortedRows}
              rowKey={(row) => row.id}
              sort={sort}
              onSortChange={handleSort}
              stickyHeader
              empty={
                <EmptyState
                  className="border-0"
                  title="No matching applications"
                  message={
                    activeFilters > 0
                      ? 'No applications match the current query. Try adjusting or clearing your search filters.'
                      : 'No application records are currently stored in your connected sheet.'
                  }
                >
                  {activeFilters > 0 ? (
                    <Button variant="outline" size="sm" onClick={clearFilters}>
                      Clear filters
                    </Button>
                  ) : null}
                </EmptyState>
              }
            />
            {data && data.total > 0 ? (
              <Pagination
                page={data.page}
                totalPages={data.total_pages}
                total={data.total}
                pageSize={data.page_size}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
                pageSizeOptions={PAGE_SIZE_OPTIONS}
              />
            ) : null}
          </>
        )}
      </Panel>
    </div>
  );
}
