import { useEffect, useState } from 'react';

import { getMatching, getSkillAnalytics, listJobs } from '../api/endpoints';
import type {
  JobListResponse,
  JobRecord,
  MatchingResponse,
  SkillAnalytics,
} from '../api/types';
import { BarList } from '../components/ui/BarList';
import { Button, ButtonLink } from '../components/ui/Button';
import { Tag, VerificationChip } from '../components/ui/Chip';
import { SelectInput, TextInput } from '../components/ui/Field';
import { Pagination } from '../components/ui/Pagination';
import { Panel } from '../components/ui/Panel';
import { EmptyState, ErrorState, LoadingState, TableSkeleton } from '../components/ui/states';
import { useApi } from '../hooks/useApi';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { formatNumber, text } from '../lib/format';
import { isVerified } from '../lib/status';

const SCORE_OPTIONS = [0, 25, 50, 75];

function ListingCard({ job }: { job: JobRecord }) {
  const fields: Array<[string, string | null]> = [
    ['Location', job.location],
    ['Arrangement', job.work_arrangement],
    ['Duration', job.duration],
    ['Stipend', job.stipend],
    ['Start Date', job.start_date],
    ['Deadline', job.application_deadline],
    ['Eligibility', job.eligibility],
    ['Found', job.date_found],
  ];

  return (
    <article className="rounded-xl border border-border bg-surface p-5 shadow-2xs transition-shadow hover:shadow-xs">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
        <div>
          <h2 className="text-base font-bold text-text">
            {text(job.title, 'Untitled Internship')}
          </h2>
          <p className="mt-0.5 text-sm font-medium text-text-secondary">
            {text(job.company, 'Company unknown')}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <VerificationChip status={job.verification_status} />
          {!isVerified(job.verification_status) ? (
            <span className="rounded-md bg-amber-light px-2 py-0.5 text-xs text-amber font-medium">
              Unverified
            </span>
          ) : null}
        </div>
      </header>

      {/* Grid of job attributes */}
      <div className="grid grid-cols-2 gap-3 py-3 sm:grid-cols-4 text-xs">
        {fields.map(([label, value]) => (
          <div key={label} className="flex flex-col">
            <span className="text-text-tertiary">{label}</span>
            <span className="mt-0.5 font-medium text-text">{text(value, '—')}</span>
          </div>
        ))}
      </div>

      {job.skills.length > 0 ? (
        <div className="border-t border-border pt-3">
          <span className="text-xs font-medium text-text-secondary">Required Skills</span>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {job.skills.map((skill) => (
              <li key={skill}>
                <Tag>{skill}</Tag>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {job.fit_assessment ? (
        <div className="border-t border-border pt-3 mt-3">
          <span className="text-xs font-medium text-text-secondary">Assessment / Notes</span>
          <p className="mt-1 text-xs text-text-secondary leading-relaxed">{job.fit_assessment}</p>
        </div>
      ) : null}

      <footer className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
        <span className="text-[11px] text-text-tertiary">ID #{job.id}</span>
        <div className="flex items-center gap-2">
          {job.source_url ? (
            <a
              href={job.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-text-secondary hover:text-text underline"
            >
              Source ↗
            </a>
          ) : null}
          {job.application_url ? (
            <a
              href={job.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-md bg-brand px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-hover transition-colors"
            >
              Apply ↗
            </a>
          ) : (
            <span className="text-xs text-text-tertiary">No direct link</span>
          )}
        </div>
      </footer>
    </article>
  );
}

export function JobIntelligence() {
  const [location, setLocation] = useState('');
  const [verification, setVerification] = useState('');
  const [skillInput, setSkillInput] = useState('');
  const [arrangementInput, setArrangementInput] = useState('');
  const [minScore, setMinScore] = useState('0');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const skill = useDebouncedValue(skillInput, 350);
  const arrangement = useDebouncedValue(arrangementInput, 350);

  useEffect(() => {
    setPage(1);
  }, [location, verification, skill, arrangement, minScore, pageSize]);

  const { data, error, loading, initialLoading, reload } = useApi<JobListResponse>(
    (signal) =>
      listJobs(
        {
          location: location || undefined,
          verification: verification || undefined,
          skill: skill.trim() || undefined,
          work_arrangement: arrangement.trim() || undefined,
          min_match_score: Number(minScore) > 0 ? Number(minScore) : undefined,
          page,
          page_size: pageSize,
        },
        signal,
      ),
    [location, verification, skill, arrangement, minScore, page, pageSize],
  );

  const matching = useApi<MatchingResponse>((signal) =>
    getMatching({ limit: 50, min_score: 0 }, signal),
  );

  const skills = useApi<SkillAnalytics>((signal) =>
    getSkillAnalytics({ limit: 20, min_count: 1 }, signal),
  );

  const locations = data?.available_locations ?? [];
  const verifications = data?.available_verification_statuses ?? [];
  const activeFilters = [
    location,
    verification,
    skill.trim(),
    arrangement.trim(),
    Number(minScore) > 0 ? minScore : '',
  ].filter(Boolean).length;

  const clearFilters = () => {
    setLocation('');
    setVerification('');
    setSkillInput('');
    setArrangementInput('');
    setMinScore('0');
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Discover internships</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Find relevant opportunities and review how well they match your interests.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data ? (
            <span className="rounded-full bg-surface-alt px-3 py-1 text-xs font-semibold text-text-secondary">
              {formatNumber(data.total)} listings available
            </span>
          ) : null}
          <Button size="sm" variant="outline" onClick={reload} prefix="↻">
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter Controls */}
      <div className="rounded-xl border border-border bg-surface p-4 shadow-2xs">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <TextInput
            label="Keyword / Skill"
            placeholder="e.g. Python, React…"
            value={skillInput}
            onChange={(event) => setSkillInput(event.target.value)}
          />

          <SelectInput
            label="Location"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
          >
            <option value="">All locations</option>
            {locations.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </SelectInput>

          <SelectInput
            label="Verification status"
            value={verification}
            onChange={(event) => setVerification(event.target.value)}
          >
            <option value="">Any verification state</option>
            {verifications.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </SelectInput>

          <TextInput
            label="Work arrangement"
            placeholder="e.g. Remote, Hybrid…"
            value={arrangementInput}
            onChange={(event) => setArrangementInput(event.target.value)}
          />

          <SelectInput
            label="Minimum match score"
            value={minScore}
            onChange={(event) => setMinScore(event.target.value)}
          >
            {SCORE_OPTIONS.map((option) => (
              <option key={option} value={String(option)}>
                {option === 0 ? 'No minimum score' : `${option}+ score`}
              </option>
            ))}
          </SelectInput>
        </div>

        {activeFilters > 0 ? (
          <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs text-text-secondary">
            <span>{activeFilters} filter{activeFilters === 1 ? '' : 's'} active</span>
            <Button size="sm" variant="ghost" onClick={clearFilters}>
              Clear filters
            </Button>
          </div>
        ) : null}
      </div>

      {/* Main Listings Area / Empty State */}
      <Panel
        title="Opportunity listings"
        meta={data && data.total > 0 ? `Page ${data.page} of ${Math.max(data.total_pages, 1)}` : undefined}
        bodyClassName="p-0"
      >
        {error && !data ? (
          <div className="p-6">
            <ErrorState error={error} onRetry={reload} />
          </div>
        ) : (initialLoading || loading) && !data ? (
          <TableSkeleton columns={3} rows={4} />
        ) : data && data.total === 0 ? (
          <EmptyState
            className="border-0 py-12"
            title="No opportunities yet"
            message={
              <>
                Your job discovery list is currently empty. Once verified listings are available in
                the connected data source, they'll appear here for you to review and track.
              </>
            }
          >
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button onClick={reload} variant="outline" size="sm" prefix="↻">
                Check again
              </Button>
              <ButtonLink to="/" variant="solid" size="sm">
                Return to overview
              </ButtonLink>
            </div>
          </EmptyState>
        ) : (
          <div className="flex flex-col gap-4 p-5">
            {(data?.items ?? []).map((job) => (
              <ListingCard key={job.id} job={job} />
            ))}
            {data && data.total > 0 ? (
              <Pagination
                page={data.page}
                totalPages={data.total_pages}
                total={data.total}
                pageSize={data.page_size}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
              />
            ) : null}
          </div>
        )}
      </Panel>

      {/* Explanatory Cards: Scoring and Skills */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="How matching works">
          {matching.error && !matching.data ? (
            <ErrorState error={matching.error} onRetry={matching.reload} />
          ) : !matching.data ? (
            <LoadingState label="Loading preferences…" />
          ) : (
            <div className="flex flex-col gap-3 text-xs leading-relaxed text-text-secondary">
              <p>{matching.data.scoring_note}</p>
              <div>
                <span className="font-semibold text-text">Your tracked interests:</span>
                <ul className="mt-1.5 flex flex-wrap gap-1.5">
                  {matching.data.interests.map((interest) => (
                    <li key={interest}>
                      <Tag>{interest}</Tag>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="font-semibold text-text">Preferred locations:</span>
                <ul className="mt-1.5 flex flex-wrap gap-1.5">
                  {matching.data.preferred_locations.map((place) => (
                    <li key={place}>
                      <Tag>{place}</Tag>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </Panel>

        <Panel title="Market skill demand">
          {skills.error && !skills.data ? (
            <ErrorState error={skills.error} onRetry={skills.reload} />
          ) : !skills.data ? (
            <LoadingState label="Loading skill analytics…" />
          ) : skills.data.total_listings === 0 ? (
            <div className="py-4 text-center">
              <p className="text-sm font-medium text-text">No skills on record yet</p>
              <p className="mt-1 text-xs text-text-secondary max-w-sm mx-auto">
                Skill frequency is compiled from active job listings. As new opportunities are added,
                in-demand skills will rank here automatically.
              </p>
            </div>
          ) : (
            <BarList
              rows={skills.data.skills.map((row) => ({
                label: row.skill,
                value: row.count,
              }))}
              total={skills.data.total_skill_mentions}
              labelWidth={45}
            />
          )}
        </Panel>
      </div>
    </div>
  );
}
