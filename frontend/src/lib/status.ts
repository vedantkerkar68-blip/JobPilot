import type { MatchTier, StatusCategory } from '../api/types';

/** Canonical display order, matching `analytics.CATEGORY_ORDER` on the backend. */
export const CATEGORY_ORDER: StatusCategory[] = [
  'pending',
  'interview',
  'rejected',
  'offer',
  'other',
];

export const CATEGORY_LABEL: Record<StatusCategory, string> = {
  pending: 'Pending',
  interview: 'Interview',
  rejected: 'Rejected',
  offer: 'Offer',
  other: 'Other',
};

/**
 * Plain-language meaning of each category, taken from how the backend derives
 * them (`analytics.py`). Used in legends and tooltips so the UI never implies
 * a status means more than it does.
 */
export const CATEGORY_MEANING: Record<StatusCategory, string> = {
  pending:
    'Submitted or acknowledged, with no outcome recorded yet. Includes "Application Submitted", "Applied", "No Change" and "Drive Announcement Received".',
  interview:
    'An assessment or interview stage has been reached, e.g. "Assessment Invitation Received" or "Assessment Completed & Submitted".',
  rejected: 'An outcome of rejection, e.g. "Rejected" or "Not Shortlisted / Rejected".',
  offer: 'An offer recorded in the sheet.',
  other:
    'Status text that matched no rule. It is never guessed into another category.',
};

/**
 * Status chip styling using semantic colors on the new warm palette.
 */
export function categoryChipClass(category: StatusCategory): string {
  switch (category) {
    case 'offer':
      return 'bg-brand text-white border-brand';
    case 'interview':
      return 'bg-brand-light text-brand border-brand/20';
    case 'pending':
      return 'bg-amber-light text-amber border-amber/20';
    case 'rejected':
      return 'bg-danger-light text-danger border-danger/20';
    case 'other':
    default:
      return 'bg-surface-alt text-text-tertiary border-border';
  }
}

/**
 * Chart colors for each status category.
 */
export const CATEGORY_SHADE: Record<StatusCategory, string> = {
  offer: '#246B50',
  interview: '#3A9B74',
  pending: '#C18B45',
  rejected: '#A33E32',
  other: '#9B9F99',
};

export const TIER_LABEL: Record<MatchTier, string> = {
  strong: 'Strong',
  good: 'Good',
  moderate: 'Moderate',
  weak: 'Weak',
};

/**
 * Verification chip styling using the new palette.
 */
export function verificationChipClass(status: string): string {
  const key = status.trim().toLowerCase();
  if (key === 'verified') return 'bg-brand-light text-brand border-brand/20';
  if (key === 'rejected' || key === 'invalid') return 'bg-danger-light text-danger border-danger/20';
  if (key === 'pending' || key === 'unverified')
    return 'bg-amber-light text-amber border-amber/20';
  return 'bg-surface-alt text-text-tertiary border-border';
}

export function isVerified(status: string): boolean {
  return status.trim().toLowerCase() === 'verified';
}
