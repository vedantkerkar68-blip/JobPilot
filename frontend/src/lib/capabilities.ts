/**
 * The AI Assistant's capability registry.
 *
 * This file is the single source of truth for what the console can honestly do.
 * A capability is `available` only when a real backend endpoint backs it. The
 * UI must never present an unavailable capability as if it had run.
 */

export type CapabilityId = 'scan-emails' | 'find-jobs' | 'pending-tasks' | 'application-summary';

export type CapabilityState = 'available' | 'unavailable';

export interface Capability {
  id: CapabilityId;
  /** Sequence number rendered as `[01]`. */
  index: string;
  title: string;
  /** One-line description of the request. */
  request: string;
  state: CapabilityState;
  /** What actually happens when this is selected today. */
  reality: string;
  /** The missing integration, when the capability is unavailable. */
  blocker?: string;
  /** Real endpoints this capability reads (empty when nothing is read). */
  endpoints: string[];
}

export const CAPABILITIES: Capability[] = [
  {
    id: 'scan-emails',
    index: '01',
    title: 'SCAN JOB EMAILS',
    request: 'Review job-related email and extract application updates.',
    state: 'unavailable',
    reality: 'No scan is performed.',
    blocker:
      'Requires the existing Gmail-monitor workflow (n8n) to run and publish its results somewhere the API can read. The read-only API exposes no email endpoint, and this frontend never calls n8n directly.',
    endpoints: [],
  },
  {
    id: 'find-jobs',
    index: '02',
    title: 'FIND NEW JOBS',
    request: 'Discover new internship opportunities.',
    state: 'unavailable',
    reality:
      'No discovery is performed. The system can only display listings that already exist in the Job Openings tab, which currently contains zero rows.',
    blocker:
      'Requires the job-search workflow to populate the Job Openings tab. Until it does, GET /api/jobs returns an empty list and this console will not invent listings.',
    endpoints: ['/api/jobs'],
  },
  {
    id: 'pending-tasks',
    index: '03',
    title: 'SHOW PENDING TASKS',
    request: 'List application follow-ups that still need attention.',
    state: 'available',
    reality:
      'Reads the tracker and lists every application in the "pending" category. These are real application records with no outcome recorded yet — not scheduled tasks, and no reminders are created.',
    endpoints: ['/api/applications?status=pending'],
  },
  {
    id: 'application-summary',
    index: '04',
    title: 'APPLICATION SUMMARY',
    request: 'Summarise current application statistics.',
    state: 'available',
    reality: 'Reads the live application analytics and reports the real counters.',
    endpoints: ['/api/analytics/applications'],
  },
];

export function capabilityById(id: CapabilityId): Capability {
  const found = CAPABILITIES.find((capability) => capability.id === id);
  if (!found) throw new Error(`Unknown capability: ${id}`);
  return found;
}

/** Keyword sets used to route free-text requests onto a capability. */
const INTENT_KEYWORDS: Record<CapabilityId, string[]> = {
  'scan-emails': ['email', 'emails', 'mail', 'inbox', 'gmail', 'scan'],
  'find-jobs': ['find', 'search', 'discover', 'new job', 'new jobs', 'opening', 'openings', 'listing'],
  'pending-tasks': ['pending', 'task', 'tasks', 'follow', 'followup', 'follow-up', 'todo', 'to-do', 'waiting'],
  'application-summary': [
    'summary',
    'summarise',
    'summarize',
    'stats',
    'statistics',
    'status',
    'overview',
    'how many',
    'total',
    'report',
  ],
};

/**
 * Best-effort keyword routing. Returns `null` when the request matches nothing
 * the console can do — the UI then states that plainly rather than guessing.
 */
export function classifyIntent(input: string): CapabilityId | null {
  const haystack = input.toLowerCase();
  let best: { id: CapabilityId; hits: number; length: number } | null = null;

  for (const [id, keywords] of Object.entries(INTENT_KEYWORDS) as Array<
    [CapabilityId, string[]]
  >) {
    let hits = 0;
    let length = 0;
    for (const keyword of keywords) {
      if (haystack.includes(keyword)) {
        hits += 1;
        length += keyword.length;
      }
    }
    if (hits > 0) {
      const candidate = { id, hits, length };
      const better =
        !best || hits > best.hits || (hits === best.hits && length > best.length);
      if (better) best = candidate;
    }
  }

  return best?.id ?? null;
}

/**
 * The ordered plan shown for a capability. Steps describe what the console will
 * actually do — the last step always states whether anything was executed.
 */
export function planFor(capability: Capability, subject: string): string[] {
  const label = subject.trim() || capability.request;

  if (capability.state === 'unavailable') {
    return [
      `Interpret request as "${label}"`,
      `Match to capability ${capability.index} · ${capability.title}`,
      capability.blocker ?? 'No integration is connected for this capability.',
      'NOT EXECUTED — no backend capability exists for this action.',
    ];
  }

  return [
    `Interpret request as "${label}"`,
    `Match to capability ${capability.index} · ${capability.title}`,
    `READ ${capability.endpoints.join(' , ')} (read-only)`,
    'EXECUTED — read-only query only; no data was modified.',
  ];
}
