import { useCallback, useRef, useState } from 'react';

import { getApplicationAnalytics, listApplications } from '../api/endpoints';
import { toApiError } from '../api/client';
import type { ApiError } from '../api/client';
import type { ApplicationAnalytics, ApplicationListResponse } from '../api/types';
import { Button } from '../components/ui/Button';
import { CategoryChip, StateChip } from '../components/ui/Chip';
import { Panel } from '../components/ui/Panel';
import { capabilityById, classifyIntent, planFor } from '../lib/capabilities';
import type { Capability, CapabilityId } from '../lib/capabilities';
import { cx } from '../lib/cx';
import { formatNumber, formatPercent, text } from '../lib/format';

interface Message {
  id: number;
  sender: 'user' | 'assistant';
  title?: string;
  text: string;
  steps?: string[];
  statusNote?: string;
  resultView?: {
    capabilityId: CapabilityId;
    applications?: ApplicationListResponse;
    analytics?: ApplicationAnalytics;
  };
}

export function AIAssistant() {
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const sequence = useRef(0);

  const pushMessage = useCallback((msg: Omit<Message, 'id'>) => {
    sequence.current += 1;
    const newMsg: Message = { ...msg, id: sequence.current };
    setMessages((current) => [...current, newMsg]);
  }, []);

  const runCapability = useCallback(
    async (capability: Capability, userQuery?: string) => {
      setBusy(true);
      const queryText = userQuery?.trim() || capability.request;

      // 1. User message
      pushMessage({
        sender: 'user',
        text: queryText,
      });

      // 2. Compute plan steps
      const steps = planFor(capability, queryText);

      try {
        if (capability.state === 'unavailable') {
          pushMessage({
            sender: 'assistant',
            title: capability.title,
            text: `This feature is currently unavailable. ${capability.blocker ?? capability.reality}`,
            steps,
            statusNote: 'Not executed · Backend workflow not connected.',
          });
          return;
        }

        if (capability.id === 'application-summary') {
          const analytics = await getApplicationAnalytics();
          pushMessage({
            sender: 'assistant',
            title: 'Application summary',
            text: `Found ${formatNumber(analytics.total_applications)} tracked applications: ${formatNumber(analytics.pending_applications)} pending, ${formatNumber(analytics.interview_applications)} at interview/assessment stage, ${formatNumber(analytics.rejected_applications)} rejected, and ${formatNumber(analytics.offers)} offer(s).`,
            steps,
            resultView: { capabilityId: 'application-summary', analytics },
          });
          return;
        }

        if (capability.id === 'pending-tasks') {
          const applications = await listApplications({ status: 'pending', page_size: 200 });
          pushMessage({
            sender: 'assistant',
            title: 'Pending applications',
            text: `Retrieved ${formatNumber(applications.total)} applications currently in the pending category. These represent active submissions where no final outcome is recorded.`,
            steps,
            resultView: { capabilityId: 'pending-tasks', applications },
          });
          return;
        }
      } catch (cause: unknown) {
        const apiError: ApiError = toApiError(cause);
        pushMessage({
          sender: 'assistant',
          text: `Request failed: ${apiError.message}`,
        });
      } finally {
        setBusy(false);
      }
    },
    [pushMessage],
  );

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = input.trim();
    if (!query || busy) return;

    setInput('');
    const intent = classifyIntent(query);

    if (!intent) {
      pushMessage({ sender: 'user', text: query });
      pushMessage({
        sender: 'assistant',
        text: 'I can only assist with actions connected to your job pipeline. Try choosing one of the available actions below, such as summarizing applications or reviewing pending records.',
      });
      return;
    }

    void runCapability(capabilityById(intent), query);
  };

  const actionCards: Array<{ id: CapabilityId; label: string; desc: string }> = [
    {
      id: 'scan-emails',
      label: 'Review job-related emails',
      desc: 'Check recent inbox emails for updates from recruiters.',
    },
    {
      id: 'find-jobs',
      label: 'Find new internships',
      desc: 'Search for active openings matching your skill profile.',
    },
    {
      id: 'pending-tasks',
      label: 'Review pending applications',
      desc: 'List active submissions awaiting decisions or follow-ups.',
    },
    {
      id: 'application-summary',
      label: 'Summarize application progress',
      desc: 'Get an instant overview of total counts, response rates, and status.',
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text">Career assistant</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Review your applications and explore your next steps.
        </p>
      </div>

      {/* Action Cards (4 practical actions) */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {actionCards.map((card) => {
          const cap = capabilityById(card.id);
          const isAvailable = cap.state === 'available';

          return (
            <button
              key={card.id}
              type="button"
              onClick={() => void runCapability(cap)}
              disabled={busy}
              className={cx(
                'flex flex-col justify-between text-left rounded-xl border p-4 transition-all',
                'bg-surface hover:border-brand/40 hover:shadow-2xs active:scale-[0.99]',
                isAvailable ? 'border-border' : 'border-border bg-surface-alt/40',
              )}
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-text">{card.label}</span>
                  <StateChip state={cap.state} />
                </div>
                <p className="mt-1.5 text-xs text-text-secondary leading-relaxed">
                  {card.desc}
                </p>
              </div>
              <div className="mt-4 flex items-center justify-between pt-2 border-t border-border/60 text-[11px] text-text-tertiary">
                <span>{isAvailable ? 'Live query' : 'Prototype'}</span>
                <span className="font-semibold text-brand">Select →</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Conversation Area */}
      <Panel title="Assistant conversation" bodyClassName="p-0">
        <div className="flex flex-col min-h-[320px] max-h-[600px] overflow-y-auto p-5 space-y-4">
          {messages.length === 0 ? (
            <div className="my-auto py-8 text-center">
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-brand-light text-brand">
                <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm1 11H9v-2h2v2zm0-4H9V5h2v4z" />
                </svg>
              </div>
              <h3 className="mt-3 text-sm font-semibold text-text">How can I help you today?</h3>
              <p className="mt-1 text-xs text-text-secondary max-w-md mx-auto">
                Select an action from the panels above or type a request below to query your real application data.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void runCapability(capabilityById('application-summary'))}
                >
                  "Summarize my applications"
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void runCapability(capabilityById('pending-tasks'))}
                >
                  "Show pending applications"
                </Button>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={cx(
                  'flex flex-col max-w-2xl rounded-xl p-4 text-sm',
                  msg.sender === 'user'
                    ? 'ml-auto bg-brand text-white'
                    : 'mr-auto bg-surface-alt text-text border border-border',
                )}
              >
                {msg.title ? (
                  <p className="text-xs font-semibold text-brand mb-1">{msg.title}</p>
                ) : null}
                <p className="leading-relaxed">{msg.text}</p>

                {msg.statusNote ? (
                  <p className="mt-2 text-xs font-medium text-amber bg-amber-light px-2.5 py-1 rounded-md">
                    {msg.statusNote}
                  </p>
                ) : null}

                {/* Structured Result Renderers */}
                {msg.resultView?.capabilityId === 'application-summary' &&
                msg.resultView.analytics ? (
                  <div className="mt-3 rounded-lg border border-border bg-surface p-3 text-text">
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      <div>
                        <span className="text-[11px] text-text-tertiary">Total</span>
                        <p className="text-base font-bold tabular-nums">
                          {formatNumber(msg.resultView.analytics.total_applications)}
                        </p>
                      </div>
                      <div>
                        <span className="text-[11px] text-text-tertiary">Pending</span>
                        <p className="text-base font-bold text-amber tabular-nums">
                          {formatNumber(msg.resultView.analytics.pending_applications)}
                        </p>
                      </div>
                      <div>
                        <span className="text-[11px] text-text-tertiary">Interviews</span>
                        <p className="text-base font-bold text-brand tabular-nums">
                          {formatNumber(msg.resultView.analytics.interview_applications)}
                        </p>
                      </div>
                      <div>
                        <span className="text-[11px] text-text-tertiary">Offers</span>
                        <p className="text-base font-bold tabular-nums">
                          {formatNumber(msg.resultView.analytics.offers)}
                        </p>
                      </div>
                      <div>
                        <span className="text-[11px] text-text-tertiary">Rejected</span>
                        <p className="text-base font-bold text-danger tabular-nums">
                          {formatNumber(msg.resultView.analytics.rejected_applications)}
                        </p>
                      </div>
                      <div>
                        <span className="text-[11px] text-text-tertiary">Outcome rate</span>
                        <p className="text-base font-bold tabular-nums">
                          {formatPercent(msg.resultView.analytics.response_rate_percent)}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}

                {msg.resultView?.capabilityId === 'pending-tasks' &&
                msg.resultView.applications ? (
                  <div className="mt-3 rounded-lg border border-border bg-surface p-3 text-text max-h-60 overflow-y-auto">
                    <div className="space-y-2">
                      {msg.resultView.applications.items.slice(0, 10).map((row) => (
                        <div
                          key={row.id}
                          className="flex items-center justify-between border-b border-border/60 pb-1.5 text-xs last:border-b-0"
                        >
                          <div>
                            <span className="font-semibold text-text">{text(row.company, 'Unknown')}</span>
                            <span className="text-text-secondary ml-1.5">· {text(row.role, 'Role')}</span>
                          </div>
                          <CategoryChip category={row.status_category} />
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>

        {/* Input Footer */}
        <form onSubmit={handleSubmit} className="border-t border-border p-4 bg-surface">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about pending tasks, application summary, or search queries…"
              disabled={busy}
              className="field flex-1"
            />
            <Button variant="solid" onClick={() => handleSubmit()} disabled={busy || !input.trim()}>
              {busy ? 'Querying…' : 'Send'}
            </Button>
          </div>
        </form>
      </Panel>
    </div>
  );
}
