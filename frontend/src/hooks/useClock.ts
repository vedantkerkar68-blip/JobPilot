import { useEffect, useState } from 'react';

/** Ticking clock in UTC, rendered in monospace in the header. */
export function useClock(intervalMs = 1000): Date {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const handle = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(handle);
  }, [intervalMs]);

  return now;
}
