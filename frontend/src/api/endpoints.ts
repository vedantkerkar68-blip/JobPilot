import { http } from './client';
import type {
  ApplicationAnalytics,
  ApplicationListResponse,
  ApplicationQuery,
  DashboardResponse,
  HealthResponse,
  JobAnalytics,
  JobListResponse,
  JobQuery,
  MatchingResponse,
  MetaResponse,
  SkillAnalytics,
} from './types';

/**
 * One function per real backend route. Nothing here invents an endpoint.
 *
 * Routes (see `backend/app/main.py`):
 *   GET /api/health
 *   GET /api/dashboard
 *   GET /api/applications        ?status &platform &company &page &page_size
 *   GET /api/jobs                ?location &skill &verification &work_arrangement
 *                                &min_match_score &page &page_size
 *   GET /api/analytics/applications
 *   GET /api/analytics/jobs
 *   GET /api/analytics/skills    ?limit &min_count
 *   GET /api/analytics/matching  ?limit &min_score &include_unmatched
 *   GET /api/meta
 */

type Params = Record<string, string | number | boolean | undefined>;

/** Drop empty/undefined values so axios never sends `?status=`. */
function clean(params: Params): Params {
  const out: Params = {};
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (typeof value === 'string' && value.trim() === '') continue;
    out[key] = typeof value === 'string' ? value.trim() : value;
  }
  return out;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/health', { signal });
  return data;
}

export async function getMeta(signal?: AbortSignal): Promise<MetaResponse> {
  const { data } = await http.get<MetaResponse>('/meta', { signal });
  return data;
}

export async function getDashboard(signal?: AbortSignal): Promise<DashboardResponse> {
  const { data } = await http.get<DashboardResponse>('/dashboard', { signal });
  return data;
}

export async function listApplications(
  query: ApplicationQuery = {},
  signal?: AbortSignal,
): Promise<ApplicationListResponse> {
  const { data } = await http.get<ApplicationListResponse>('/applications', {
    params: clean({
      status: query.status,
      platform: query.platform,
      company: query.company,
      page: query.page,
      page_size: query.page_size,
    }),
    signal,
  });
  return data;
}

export async function listJobs(
  query: JobQuery = {},
  signal?: AbortSignal,
): Promise<JobListResponse> {
  const { data } = await http.get<JobListResponse>('/jobs', {
    params: clean({
      location: query.location,
      skill: query.skill,
      verification: query.verification,
      work_arrangement: query.work_arrangement,
      min_match_score: query.min_match_score,
      page: query.page,
      page_size: query.page_size,
    }),
    signal,
  });
  return data;
}

export async function getApplicationAnalytics(
  signal?: AbortSignal,
): Promise<ApplicationAnalytics> {
  const { data } = await http.get<ApplicationAnalytics>('/analytics/applications', { signal });
  return data;
}

export async function getJobAnalytics(signal?: AbortSignal): Promise<JobAnalytics> {
  const { data } = await http.get<JobAnalytics>('/analytics/jobs', { signal });
  return data;
}

export async function getSkillAnalytics(
  query: { limit?: number; min_count?: number } = {},
  signal?: AbortSignal,
): Promise<SkillAnalytics> {
  const { data } = await http.get<SkillAnalytics>('/analytics/skills', {
    params: clean({ limit: query.limit, min_count: query.min_count }),
    signal,
  });
  return data;
}

export async function getMatching(
  query: { limit?: number; min_score?: number; include_unmatched?: boolean } = {},
  signal?: AbortSignal,
): Promise<MatchingResponse> {
  const { data } = await http.get<MatchingResponse>('/analytics/matching', {
    params: clean({
      limit: query.limit,
      min_score: query.min_score,
      include_unmatched: query.include_unmatched,
    }),
    signal,
  });
  return data;
}
