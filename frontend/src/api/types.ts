/**
 * TypeScript mirrors of `backend/app/schemas.py`.
 *
 * These are hand-written to match the Pydantic models one-to-one. If the
 * backend schema changes, change it here too. No field is invented: every
 * property below is returned by the live API.
 */

export type StatusCategory = 'pending' | 'interview' | 'rejected' | 'offer' | 'other';

/* -------------------------------------------------------------------------- */
/* Applications                                                               */
/* -------------------------------------------------------------------------- */

export interface ApplicationRecord {
  id: number;
  company: string | null;
  role: string | null;
  application_type: string | null;
  /** ISO `YYYY-MM-DD`. */
  application_date: string | null;
  /** ISO `YYYY-MM-DD`. */
  latest_update_date: string | null;
  /** Raw status text exactly as stored in the spreadsheet. */
  status: string | null;
  /** Category derived by the backend's ordered status rules. */
  status_category: StatusCategory;
  job_id: string | null;
  platform: string | null;
  notes: string | null;
  tracking_key: string | null;
  has_application_date: boolean;
  duplicate_count: number;
}

export interface ApplicationListResponse {
  items: ApplicationRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  /** Distinct raw statuses, suitable for a filter dropdown. */
  available_statuses: string[];
  /** Distinct raw platforms, suitable for a filter dropdown. */
  available_platforms: string[];
}

export interface StatusCategoryInfo {
  category: StatusCategory;
  count: number;
}

export interface DuplicateGroup {
  key_tier: string;
  key: string;
  count: number;
}

export interface PlatformCount {
  platform: string;
  count: number;
}

export interface TypeCount {
  application_type: string;
  count: number;
}

export interface MonthCount {
  /** Month bucket in `YYYY-MM` format. */
  month: string;
  count: number;
}

export interface ApplicationAnalytics {
  total_applications: number;
  /** Raw status text -> count. */
  status_counts: Record<string, number>;
  /** Raw status text -> { category, count }. */
  status_categories: Record<string, StatusCategoryInfo>;
  category_counts: Record<string, number>;
  unclassified_applications: number;
  pending_applications: number;
  interview_applications: number;
  rejected_applications: number;
  offers: number;
  active_applications: number;
  response_rate_percent: number;
  applications_by_platform: PlatformCount[];
  applications_by_type: TypeCount[];
  applications_over_time: MonthCount[];
  recent_applications: ApplicationRecord[];
  /** Field name -> number of records missing it. */
  missing_data_counts: Record<string, number>;
  duplicate_groups: DuplicateGroup[];
  generated_at: string;
}

/* -------------------------------------------------------------------------- */
/* Jobs                                                                       */
/* -------------------------------------------------------------------------- */

export interface JobRecord {
  id: number;
  company: string | null;
  title: string | null;
  location: string | null;
  work_arrangement: string | null;
  start_date: string | null;
  duration: string | null;
  stipend: string | null;
  eligibility: string | null;
  application_deadline: string | null;
  required_skills: string | null;
  fit_assessment: string | null;
  /** Self-reported by the sheet owner — not an independent verification. */
  verification_status: string;
  application_url: string | null;
  source_url: string | null;
  date_found: string | null;
  unique_job_key: string | null;
  skills: string[];
}

export interface JobListResponse {
  items: JobRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  available_locations: string[];
  available_verification_statuses: string[];
}

export interface LocationCount {
  location: string;
  count: number;
}

export interface CompanyCount {
  company: string;
  count: number;
}

export interface WorkArrangementCount {
  work_arrangement: string;
  count: number;
}

export interface SkillCount {
  skill: string;
  count: number;
}

export interface VerificationCount {
  verification_status: string;
  count: number;
}

export interface JobAnalytics {
  total_listings: number;
  listings_by_location: LocationCount[];
  listings_by_company: CompanyCount[];
  listings_by_work_arrangement: WorkArrangementCount[];
  top_skills: SkillCount[];
  listings_by_verification_status: VerificationCount[];
  missing_data_counts: Record<string, number>;
  duplicate_groups: DuplicateGroup[];
  generated_at: string;
}

export interface SkillAnalytics {
  total_listings: number;
  total_skill_mentions: number;
  unique_skills: number;
  skills: SkillCount[];
  min_count: number;
  generated_at: string;
}

/* -------------------------------------------------------------------------- */
/* Matching                                                                   */
/* -------------------------------------------------------------------------- */

export type MatchTier = 'strong' | 'good' | 'moderate' | 'weak';

export interface JobMatch {
  job_id: number;
  company: string | null;
  title: string | null;
  location: string | null;
  work_arrangement: string | null;
  required_skills: string[];
  verification_status: string | null;
  application_url: string | null;
  score: number;
  tier: MatchTier;
  matched_interests: string[];
  matched_locations: string[];
  reasons: string[];
}

export interface MatchingResponse {
  matches: JobMatch[];
  total_listings: number;
  matched_listings: number;
  min_score: number;
  include_unmatched: boolean;
  interests: string[];
  preferred_locations: string[];
  scoring_note: string;
  generated_at: string;
}

/* -------------------------------------------------------------------------- */
/* Dashboard, health, meta                                                    */
/* -------------------------------------------------------------------------- */

export interface DashboardResponse {
  applications: ApplicationAnalytics;
  jobs: JobAnalytics;
  top_matches: JobMatch[];
  source: string;
  /** Human-readable freshness string produced by the backend, e.g. "4 min ago". */
  data_freshness: string;
  cached: boolean;
  fetched_at: string | null;
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  app: string;
  version: string;
  environment: string;
  data_source: string;
  timestamp: string;
  /**
   * Untyped by design: the backend adds keys such as `applications_rows`,
   * `fetched_at` and `data_error`. Read it defensively.
   */
  checks: Record<string, unknown>;
}

export interface MetaResponse {
  app: string;
  version: string;
  environment: string;
  data_source: string;
  applications_tab: string;
  job_openings_tab: string;
  cache_ttl_seconds: number;
  status_categories: StatusCategory[];
  interests: string[];
  preferred_locations: string[];
}

/* -------------------------------------------------------------------------- */
/* Query shapes                                                               */
/* -------------------------------------------------------------------------- */

export interface ApplicationQuery {
  status?: string;
  platform?: string;
  company?: string;
  page?: number;
  page_size?: number;
}

export interface JobQuery {
  location?: string;
  skill?: string;
  verification?: string;
  work_arrangement?: string;
  min_match_score?: number;
  page?: number;
  page_size?: number;
}
