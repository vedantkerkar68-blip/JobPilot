export type ClassValue = string | false | null | undefined;

/** Tiny class-name joiner. Avoids a dependency for a one-line concern. */
export function cx(...values: ClassValue[]): string {
  return values.filter(Boolean).join(' ');
}
