import axios, { AxiosError } from 'axios';

/**
 * Central HTTP client.
 *
 * `VITE_API_BASE_URL` is optional: when it is empty the app issues same-origin
 * relative requests and relies on the Vite dev/preview proxy (`/api` ->
 * `http://127.0.0.1:8000`). See `vite.config.ts` and `.env.example`.
 */
const configuredBase = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '');

export const API_BASE_URL = configuredBase;
export const API_ROOT = `${configuredBase}/api`;

export const http = axios.create({
  baseURL: API_ROOT,
  timeout: 20_000,
  headers: { Accept: 'application/json' },
});

export type ApiErrorKind =
  | 'offline' /* the backend could not be reached at all */
  | 'unavailable' /* reachable, but the data source failed (HTTP 503) */
  | 'server' /* HTTP 5xx that is not a data-source problem */
  | 'request' /* HTTP 4xx — the frontend sent something the API rejected */
  | 'unknown';

export interface ApiError {
  kind: ApiErrorKind;
  status: number | null;
  /** Safe to display: derived from the backend's `detail` field. */
  message: string;
}

const GENERIC_MESSAGE = 'The request failed. Check the backend log for details.';

function extractDetail(payload: unknown): string | null {
  if (typeof payload === 'string' && payload.trim()) {
    return payload.trim();
  }
  if (payload && typeof payload === 'object') {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail.trim();
    }
    // FastAPI validation errors arrive as a list of { loc, msg, type }.
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown; loc?: unknown };
      if (typeof first?.msg === 'string') {
        const where = Array.isArray(first.loc) ? first.loc.join('.') : '';
        return where ? `${where}: ${first.msg}` : first.msg;
      }
    }
  }
  return null;
}

/** Convert any thrown value into a display-safe `ApiError`. */
export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError;
    const status = axiosError.response?.status ?? null;

    if (status === null) {
      return {
        kind: 'offline',
        status: null,
        message: `No response from the backend at ${API_ROOT}. Is uvicorn running on port 8000?`,
      };
    }

    const detail = extractDetail(axiosError.response?.data);

    if (status === 503) {
      return {
        kind: 'unavailable',
        status,
        message: detail ?? 'The configured data source is unavailable.',
      };
    }
    if (status >= 500) {
      return { kind: 'server', status, message: detail ?? GENERIC_MESSAGE };
    }
    if (status >= 400) {
      return { kind: 'request', status, message: detail ?? GENERIC_MESSAGE };
    }
    return { kind: 'unknown', status, message: detail ?? GENERIC_MESSAGE };
  }

  if (error instanceof Error && error.message) {
    return { kind: 'unknown', status: null, message: error.message };
  }
  return { kind: 'unknown', status: null, message: GENERIC_MESSAGE };
}

/** Short uppercase code shown next to an error panel. */
export function errorCode(error: ApiError): string {
  switch (error.kind) {
    case 'offline':
      return 'LINK DOWN';
    case 'unavailable':
      return 'SOURCE UNAVAILABLE';
    case 'server':
      return `SERVER ${error.status ?? 500}`;
    case 'request':
      return `REQUEST ${error.status ?? 400}`;
    default:
      return 'ERROR';
  }
}
