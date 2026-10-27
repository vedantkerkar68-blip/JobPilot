import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './components/layout/AppShell';
import { LoadingState } from './components/ui/states';

/**
 * Six sections, each backed by real endpoints.
 *
 * Routes are code-split so the chart library only loads when a chart-bearing
 * page is opened, keeping the initial payload small.
 */
const CommandOverview = lazy(() =>
  import('./pages/CommandOverview').then((module) => ({ default: module.CommandOverview })),
);
const ApplicationTracker = lazy(() =>
  import('./pages/ApplicationTracker').then((module) => ({ default: module.ApplicationTracker })),
);
const JobIntelligence = lazy(() =>
  import('./pages/JobIntelligence').then((module) => ({ default: module.JobIntelligence })),
);
const AIAssistant = lazy(() =>
  import('./pages/AIAssistant').then((module) => ({ default: module.AIAssistant })),
);
const Analytics = lazy(() =>
  import('./pages/Analytics').then((module) => ({ default: module.Analytics })),
);
const SystemStatus = lazy(() =>
  import('./pages/SystemStatus').then((module) => ({ default: module.SystemStatus })),
);

function RouteFallback() {
  return (
    <LoadingState
      label="LOADING SECTION"
      detail="Fetching the interface module and its data."
    />
  );
}

export function App() {
  return (
    <AppShell>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<CommandOverview />} />
          <Route path="/tracker" element={<ApplicationTracker />} />
          <Route path="/jobs" element={<JobIntelligence />} />
          <Route path="/assistant" element={<AIAssistant />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/system" element={<SystemStatus />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
