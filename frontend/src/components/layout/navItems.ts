export interface NavItem {
  id: string;
  label: string;
  path: string;
  description: string;
}

/**
 * The six core product areas of JobPilot.
 */
export const NAV_ITEMS: NavItem[] = [
  {
    id: 'overview',
    label: 'Overview',
    path: '/',
    description: 'Summary of applications, progress, and recent activity.',
  },
  {
    id: 'applications',
    label: 'Applications',
    path: '/tracker',
    description: 'Track and manage your internship applications.',
  },
  {
    id: 'jobs',
    label: 'Discover Jobs',
    path: '/jobs',
    description: 'Explore opportunities matching your interests.',
  },
  {
    id: 'assistant',
    label: 'AI Assistant',
    path: '/assistant',
    description: 'Career assistance and application planning.',
  },
  {
    id: 'analytics',
    label: 'Analytics',
    path: '/analytics',
    description: 'Visual insights into pipeline progress and trends.',
  },
  {
    id: 'system',
    label: 'System Status',
    path: '/system',
    description: 'Backend health, data sources, and diagnostics.',
  },
];

export function navItemByPath(pathname: string): NavItem {
  const exact = NAV_ITEMS.find((item) => item.path === pathname);
  if (exact) return exact;
  const nested = NAV_ITEMS.filter((item) => item.path !== '/').find((item) =>
    pathname.startsWith(item.path),
  );
  return nested ?? NAV_ITEMS[0]!;
}
