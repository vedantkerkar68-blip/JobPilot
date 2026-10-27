import type { ReactNode } from 'react';
import { useSystem } from '../../system/SystemContext';
import { Header } from './Header';
import { SideNav, TopNav } from './SideNav';

function AppFooter() {
  const { health, meta } = useSystem();
  const source = meta?.data_source ?? health?.data_source;

  return (
    <footer className="border-t border-border bg-surface px-4 py-3 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-text-tertiary">
        <p>
          JobPilot <span className="text-text-secondary">v{meta?.version ?? health?.version ?? '0.1.0'}</span>
          {source ? (
            <span> · Source: <span className="text-text-secondary capitalize">{source}</span></span>
          ) : null}
        </p>
        <p>Internship tracking and career intelligence</p>
      </div>
    </footer>
  );
}

/** Application frame: responsive desktop sidebar and mobile top nav. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bg lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      <SideNav />
      <div className="flex min-w-0 flex-col min-h-screen">
        <Header />
        <TopNav />
        <main id="main" className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
          {children}
        </main>
        <AppFooter />
      </div>
    </div>
  );
}
