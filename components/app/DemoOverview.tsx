"use client";

// ---------------------------------------------------------------------------
// Public demo overview.
//
// The demo renders the authenticated dashboard layout from local demo data.
// There is no fetch, no auth context read and no mutation endpoint anywhere in
// this subtree: every section below is the same component the signed-in home
// page uses, fed by `lib/demoOverview` from `lib/demoStore`.
// ---------------------------------------------------------------------------

import Link from "next/link";
import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useLocale, useTranslation } from "@/lib/language-context";
import {
  commitDemoState,
  demoUserName,
  formatDemoAmount,
  resetDemoState,
  useDemoState,
  type DemoState,
} from "@/lib/demoStore";
import { buildDemoDecision, buildDemoOverview, type DemoOverview as DemoOverviewData } from "@/lib/demoOverview";
import {
  AiGuidancePanelView,
  ActivitySection,
  AnalyticsCard,
  HeroEarningsCard,
  InsightsCard,
  buildActivityItems,
  formatWeekdayDate,
  greetingKeyForHour,
  type SourceStatus,
} from "@/components/app/DashboardOverview";

/** The demo "analysis" result type is derived, so the demo never imports the API module. */
type DemoDecision = ReturnType<typeof buildDemoDecision>;

/** Amount the demo starts from: the largest one that keeps bills and reserve intact. */
function initialAmount(state: DemoState, overview: DemoOverviewData): number {
  return Math.min(state.available, Math.max(0, overview.comfortableWithdrawal));
}

/**
 * Demo AI guidance card. Same view as the authenticated card, but the
 * "analysis" is the demo store's own deterministic scenario evaluation —
 * never an API call and never a state change.
 */
function DemoAiGuidance({ state, overview }: { state: DemoState; overview: DemoOverviewData }) {
  const { t } = useTranslation();
  const locale = useLocale();
  const [amount, setAmount] = useState(() => initialAmount(state, overview));
  const [decision, setDecision] = useState<DemoDecision | null>(null);

  const fmt = (value: number) => formatDemoAmount(value, locale);

  return (
    <AiGuidancePanelView
      availableMinor={state.available * 100}
      amountMinor={amount * 100}
      onAmountChange={(minor) => setAmount(Math.round(minor / 100))}
      decision={decision}
      decisionError={null}
      analyzing={false}
      onAnalyze={() => setDecision(buildDemoDecision(state, amount, locale))}
      contextNote={
        <>
          {t.demo.planUpcomingBills}: {fmt(overview.upcomingBillsTotal)} · {t.demo.planReserveTarget}:{" "}
          {fmt(overview.reserveTarget)}
        </>
      }
      whyHref="/demo/ai"
      getMoneyHref="/demo/get-money"
      whatIfHref="/demo/what-if"
    />
  );
}

function DemoGreeting() {
  const { t } = useTranslation();
  const locale = useLocale();
  const o = t.overview;
  const greeting = o[greetingKeyForHour(new Date().getHours())].replace("{name}", demoUserName(locale));
  return (
    <div>
      <p className="mb-4 text-[13px] font-semibold text-ink-soft">{formatWeekdayDate(new Date(), locale)}</p>
      <h1 className="text-balance text-[38px] font-extrabold leading-[1] tracking-[-0.04em] sm:text-[54px]">{greeting}</h1>
    </div>
  );
}

/**
 * The demo state is a shared external store (this browser's localStorage,
 * namespaced under `arqau-demo-state`), read with `useDemoState` so every
 * demo page reflects edits made anywhere and survives refresh.
 */
export default function DemoOverview() {
  const { t } = useTranslation();
  const o = t.overview;
  const state = useDemoState();

  const overview = useMemo(() => buildDemoOverview(state), [state]);
  const activityItems = useMemo(
    () => buildActivityItems(overview.transactions, [], o).slice(0, 4),
    [overview, o],
  );

  const status: SourceStatus = "ready";
  // The demo has nothing to refetch, so the failure affordance is never used.
  const noop = () => {};

  return (
    <div className="space-y-6">
      <DemoGreeting />

      <div className="flex flex-wrap items-center gap-3 rounded-[16px] border border-orange/25 bg-orange-soft px-4 py-3">
        <span className="rounded-full bg-orange px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-cream">
          {t.demo.persistentBadge}
        </span>
        <p className="text-[12.5px] font-semibold text-orange-dark">{t.demo.persistentBadgeLong}</p>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            aria-label={t.demo.resetDemoAria}
            onClick={() => commitDemoState(resetDemoState())}
            className="inline-flex items-center gap-1.5 rounded-full border border-orange/40 px-3 py-1.5 text-[12px] font-bold text-orange-dark transition-colors hover:border-orange hover:bg-white/50"
          >
            <RefreshCw size={13} /> {t.demo.resetDemo}
          </button>
          <Link href="/signup" className="btn-primary inline-flex items-center gap-1.5 px-4 py-2 text-[12px]">
            {t.auth.signupButton}
          </Link>
        </div>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[1.58fr_1fr]">
        <HeroEarningsCard calculation={overview.calculation} status={status} onRetry={noop} />
        <DemoAiGuidance state={state} overview={overview} />
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[1.73fr_1fr_1fr]">
        <ActivitySection
          items={activityItems}
          transactionsStatus={status}
          contextStatus={status}
          onRetry={noop}
          historyHref="/demo/history"
        />
        <AnalyticsCard transactions={overview.transactions} status={status} onRetry={noop} />
        <InsightsCard
          context={overview.context}
          status={status}
          onRetry={noop}
          spendingHref="/demo/finance"
          aiHref="/demo/ai"
        />
      </div>
    </div>
  );
}
