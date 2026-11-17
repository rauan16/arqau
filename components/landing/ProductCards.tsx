"use client";

import {
  ArrowRight,
  BarChart3,
  CalendarClock,
  Check,
  ChevronDown,
  Info,
  Lightbulb,
  MoreHorizontal,
  PieChart,
  Search,
  Sparkles,
  Wallet,
} from "lucide-react";
import type { TranslationKeys } from "@/lib/i18n";
import {
  formatTenge,
  isPresetAvailable,
  scenario,
  shouldShowLabel,
} from "@/lib/demoData";
import type { AnalyticsMetricId } from "@/lib/demoData";
import type { ProductDemo } from "./useProductDemo";
import BrandLogo from "@/components/ui/BrandLogo";

// Locale-agnostic view of the landing copy: any locale satisfies it, and the
// literal string types of a single locale do not leak into the card props.
type Landing = { [Key in keyof TranslationKeys["landing"]]: string };

const cardBase =
  "flex min-h-[430px] w-[min(300px,calc(100vw-64px))] shrink-0 snap-start flex-col rounded-[14px] border p-5 sm:w-[300px] sm:p-6";

// Light and dark cards get their own background/border pair so no conflicting
// utility can silently override the other (a shared `bg-white` used to win over
// `bg-ink`, which turned the dark AI card white and hid its text).
const card = `${cardBase} border-border bg-white`;
const cardDark = `${cardBase} border-white/10 bg-ink`;

const metricAccent: Record<AnalyticsMetricId, { bar: string; active: string; dot: string }> = {
  expenses: { bar: "bg-orange", active: "bg-orange text-white", dot: "bg-orange" },
  income: { bar: "bg-ink", active: "bg-ink text-white", dot: "bg-ink" },
  savings: { bar: "bg-orange-dark", active: "bg-orange-dark text-white", dot: "bg-orange-dark" },
};

const statusLabelKey = {
  comfortable: "productWithdrawStatusComfortable",
  caution: "productWithdrawStatusCaution",
  "high-risk": "productWithdrawStatusHighRisk",
} as const;

const adviceKey = {
  comfortable: "productAiAdviceComfortable",
  caution: "productAiAdviceCaution",
  "high-risk": "productAiAdviceHighRisk",
} as const;

const metricLabelKey = {
  expenses: "productAnalyticsTabExpenses",
  income: "productAnalyticsTabIncome",
  savings: "productAnalyticsTabSavings",
} as const;

const totalLabelKey = {
  expenses: "productAnalyticsTotalExpenses",
  income: "productAnalyticsTotalIncome",
  savings: "productAnalyticsTotalSavings",
} as const;

const periodLabelKey = {
  "7d": "productAnalyticsPeriod7d",
  "30d": "productAnalyticsPeriod30d",
  "3m": "productAnalyticsPeriod3m",
  "6m": "productAnalyticsPeriod6m",
  "12m": "productAnalyticsPeriod12m",
} as const;

function fill(template: string, values: Record<string, string>) {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replace(`{${key}}`, value),
    template,
  );
}

function BrandHeader({ dark = false }: { dark?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span
        className={`flex items-center gap-2 text-[14px] font-extrabold tracking-[0.04em] ${
          dark ? "text-white" : "text-ink"
        }`}
      >
        {/*
          The white-background mark only sits on the light cards. The dark AI
          panel keeps the wordmark on its own so the logo's white box never
          lands on a near-black surface.
        */}
        {dark ? (
          <span className="relative flex h-6 w-6 items-center justify-center rounded-full bg-orange">
            <span className="absolute h-[1.5px] w-3 rotate-[-45deg] rounded-full bg-white" />
          </span>
        ) : (
          <BrandLogo size={26} />
        )}
        ARQAU
      </span>
      {!dark && (
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-cream text-ink-soft">
          <Search size={14} strokeWidth={2.2} />
        </span>
      )}
    </div>
  );
}

export function EmployeeHomeCard({ l }: { l: Landing }) {
  return (
    <div className={card}>
      <BrandHeader />
      <div className="mt-5">
        <p className="text-[17px] font-extrabold leading-tight text-ink">{l.productHomeGreeting}</p>
        <p className="mt-0.5 text-[12px] text-ink-soft">{l.productHomeRole}</p>
      </div>

      <div className="mt-4 rounded-[18px] bg-cream/70 p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11.5px] text-ink-soft">{l.productHomeEarned}</p>
            <p className="numbers mt-1 text-[24px] font-extrabold leading-none tracking-tight text-ink">
              {formatTenge(scenario.earned)}
            </p>
          </div>
          <span className="flex h-8 w-8 items-center justify-center rounded-full border border-ink/10 bg-white text-ink">
            <ArrowRight size={14} />
          </span>
        </div>
      </div>

      <div className="mt-2.5 flex items-center justify-between rounded-[18px] bg-cream/70 px-4 py-3.5">
        <p className="text-[11.5px] text-ink-soft">{l.productHomeAvailable}</p>
        <p className="numbers text-[16px] font-extrabold text-ink">{formatTenge(scenario.available)}</p>
        <span className="text-[10px] text-ink-soft/60">Illustrative demo value only.</span>
      </div>

      <div className="mt-auto flex items-center justify-between rounded-[18px] bg-orange-soft p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-orange text-white">
            <Wallet size={15} strokeWidth={2} />
          </span>
          <div>
            <p className="text-[11px] text-ink-soft">{l.productHomeRecommended}</p>
            <p className="numbers text-[16px] font-extrabold text-ink">{formatTenge(scenario.recommended)}</p>
          </div>
        </div>
        <ArrowRight size={15} className="text-ink" />
      </div>
    </div>
  );
}

export function AnalyticsCard({ l, demo }: { l: Landing; demo: ProductDemo }) {
  const { analytics, metric, period } = demo;
  const accent = metricAccent[metric];
  const metricLabel = l[metricLabelKey[metric]];
  const periodLabel = l[periodLabelKey[period]];
  const points = analytics.points;
  const max = Math.max(...points.map((p) => p.value));
  const gap = analytics.pointCount > 12 ? "gap-[3px]" : analytics.pointCount > 7 ? "gap-1" : "gap-2";
  const barMaxHeight = analytics.pointCount > 12 ? 104 : 116;

  return (
    <div className={card}>
      <div className="flex items-center gap-2">
        <p className="text-[16px] font-extrabold text-ink">{l.productAnalyticsTitle}</p>
        <span className={`h-2 w-2 rounded-full ${accent.dot}`} aria-hidden="true" />
        <span className="truncate text-[11px] font-semibold text-ink-soft">{metricLabel}</span>
      </div>

      <div className="relative mt-3">
        <select
          value={period}
          onChange={(event) => demo.setPeriod(event.target.value as typeof period)}
          aria-label={l.productAnalyticsPeriodLabel}
          className="w-full appearance-none rounded-full border border-border bg-white py-2 pl-3.5 pr-9 text-[11.5px] font-semibold text-ink-soft transition-colors hover:border-ink hover:text-ink focus-ring"
        >
          {(Object.keys(periodLabelKey) as (keyof typeof periodLabelKey)[]).map((id) => (
            <option key={id} value={id}>
              {l[periodLabelKey[id]]}
            </option>
          ))}
        </select>
        <ChevronDown
          size={14}
          className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-ink-soft"
        />
      </div>

      <div
        role="group"
        aria-label={l.productAnalyticsMetricLabel}
        className="mt-4 flex gap-1 rounded-full bg-cream p-1"
      >
        {(["expenses", "income", "savings"] as AnalyticsMetricId[]).map((id) => {
          const isActive = id === metric;
          return (
            <button
              key={id}
              type="button"
              aria-pressed={isActive}
              onClick={() => demo.setMetric(id)}
              className={`flex-1 rounded-full py-1.5 text-center text-[11.5px] font-bold transition-colors focus-ring ${
                isActive ? metricAccent[id].active : "text-ink-soft hover:bg-white hover:text-ink"
              }`}
            >
              {l[metricLabelKey[id]]}
            </button>
          );
        })}
      </div>

      <div
        role="img"
        aria-label={`${metricLabel}, ${periodLabel}. ${l[totalLabelKey[metric]]}: ${formatTenge(analytics.total)}.`}
        className={`mt-4 flex h-[128px] items-end ${gap}`}
      >
        {points.map((point, index) => (
          <div key={`${metric}-${period}-${index}`} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
            <div
              className={`w-full rounded-t-[4px] transition-[height] duration-300 ease-out ${accent.bar}`}
              style={{ height: `${Math.round((point.value / max) * barMaxHeight)}px` }}
            />
            <span
              className={`w-full truncate text-center text-[8.5px] leading-none ${
                shouldShowLabel(index, points.length) ? "text-ink-muted" : "text-transparent"
              }`}
            >
              {shouldShowLabel(index, points.length) ? point.label : "·"}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <p className="flex min-w-0 items-center gap-1.5 text-[10px] text-ink-muted">
          <span className={`h-2 w-2 shrink-0 rounded-full ${accent.dot}`} />
          <span className="truncate">
            {l.productAnalyticsPeak}:{" "}
            <span className="numbers font-bold text-ink-soft">{formatTenge(analytics.peak.value)}</span>
          </span>
        </p>
        <span className="shrink-0 rounded-full bg-cream px-2 py-1 text-[9px] font-bold uppercase tracking-[0.08em] text-orange-dark">
          {l.productDemoTag}
        </span>
      </div>

      <div className="mt-auto flex items-end justify-between gap-3 border-t border-border pt-4">
        <div className="min-w-0">
          <p className="text-[11px] text-ink-soft">{l[totalLabelKey[metric]]}</p>
          <p className="numbers mt-1 text-[15px] font-extrabold leading-none text-ink">
            {formatTenge(analytics.total)}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[11px] text-ink-soft">{l.productAnalyticsAverage}</p>
          <p className="numbers mt-1 text-[13px] font-bold leading-none text-ink-soft">
            {formatTenge(analytics.average)}
          </p>
        </div>
      </div>
    </div>
  );
}

export function WithdrawalCard({ l, demo }: { l: Landing; demo: ProductDemo }) {
  const { amount, guidance, submitState } = demo;
  const unavailableReason = fill(l.productWithdrawUnavailable, {
    amount: formatTenge(scenario.available),
  });
  const canSubmit = submitState === "idle";

  return (
    <div className={card}>
      <div className="flex items-center justify-between">
        <p className="text-[16px] font-extrabold text-ink">{l.productWithdrawTitle}</p>
        <MoreHorizontal size={18} className="text-ink-soft" />
      </div>

      {submitState === "sent" ? (
        <div
          role="status"
          className="mt-6 rounded-[18px] border border-orange/30 bg-orange-soft p-4"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-orange text-white">
            <Check size={16} strokeWidth={3} />
          </span>
          <p className="mt-3 text-[14px] font-extrabold leading-snug text-ink">
            {l.productWithdrawConfirmTitle}
          </p>
          <p className="numbers mt-1 text-[22px] font-extrabold leading-none tracking-[-0.02em] text-ink">
            {formatTenge(amount)}
          </p>
          <p className="mt-2 text-[11.5px] leading-relaxed text-ink-soft">{l.productWithdrawConfirmBody}</p>
          <button
            type="button"
            autoFocus
            onClick={demo.resetWithdrawal}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-full border border-ink bg-white py-2.5 text-[12.5px] font-bold text-ink transition-colors hover:bg-ink hover:text-cream focus-ring"
          >
            {l.productWithdrawConfirmBack}
          </button>
          <p className="mt-2.5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-orange-dark">
            {l.productWithdrawConfirmNote}
          </p>
        </div>
      ) : (
        <>
          <div className="mt-6 flex items-end justify-between gap-2">
            <div>
              <p className="text-[12px] text-ink-soft">{l.productWithdrawAmount}</p>
              <p className="numbers mt-1 text-[34px] font-extrabold leading-none tracking-[-0.03em] text-ink">
                {formatTenge(amount)}
              </p>
            </div>
            <span className="rounded-full bg-cream px-2.5 py-1 text-[10px] font-bold text-orange-dark">
              {l[statusLabelKey[guidance.status]]}
            </span>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-2">
            {demo.presets.map((preset) => {
              const isActive = preset === amount;
              const available = isPresetAvailable(preset, scenario.available);
              return (
                <button
                  key={preset}
                  type="button"
                  aria-pressed={isActive}
                  aria-disabled={available ? undefined : true}
                  title={available ? undefined : unavailableReason}
                  onClick={() => demo.selectAmount(preset)}
                  className={`numbers rounded-full border px-3 py-2 text-[12px] font-bold transition-colors focus-ring ${
                    isActive
                      ? "border-orange bg-orange text-white"
                      : available
                        ? "border-border bg-white text-ink-soft hover:border-ink hover:text-ink"
                        : "cursor-not-allowed border-border bg-cream/60 text-ink-muted opacity-60"
                  }`}
                >
                  {formatTenge(preset)}
                  {!available && <span className="sr-only">{unavailableReason}</span>}
                </button>
              );
            })}
          </div>

          <div className="mt-4 flex items-center justify-between rounded-[14px] bg-cream/70 px-3.5 py-2.5">
            <p className="text-[11px] text-ink-soft">{l.productWithdrawRemaining}</p>
            <p className="numbers text-[12.5px] font-bold text-ink">
              {formatTenge(guidance.remainingAvailable)}
            </p>
          </div>

          <button
            type="button"
            onClick={demo.submitWithdrawal}
            disabled={!canSubmit}
            aria-busy={submitState === "sending"}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-full bg-orange py-3.5 text-[14px] font-bold text-white shadow-[0_16px_28px_-16px_rgba(242,103,34,0.85)] transition-colors hover:bg-orange-dark focus-ring disabled:cursor-progress disabled:opacity-70"
          >
            {submitState === "sending" ? l.productWithdrawSending : l.productWithdrawCta}
            {submitState === "sending" ? null : <ArrowRight size={15} />}
          </button>
        </>
      )}

      <div className="mt-auto flex items-start gap-2.5 rounded-[16px] bg-cream/70 p-3.5">
        <Info size={14} className="mt-0.5 shrink-0 text-ink-soft" />
        <p className="text-[11.5px] leading-relaxed text-ink-soft">{l.productWithdrawNote}</p>
      </div>
      <p className="mt-2 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-orange-dark">
        {l.productWithdrawConfirmNote}
      </p>
    </div>
  );
}

export function AIRecommendationsCard({ l, demo }: { l: Landing; demo: ProductDemo }) {
  const { analytics, amount, guidance, metric, period } = demo;

  const upcomingText = fill(l.productAiRow2Text, {
    amount: formatTenge(scenario.upcomingExpensesTotal),
    days: String(scenario.nextPaydayDays),
  });
  const usualText = fill(l.productAiRow3Text, {
    metric: l[metricLabelKey[metric]],
    total: formatTenge(analytics.total),
    period: l[periodLabelKey[period]],
  });
  const adviceText = fill(l[adviceKey[guidance.status]], {
    amount: formatTenge(amount),
    remaining: formatTenge(guidance.remainingAvailable),
    reserve: formatTenge(scenario.reserveTarget),
    upcoming: formatTenge(scenario.upcomingExpensesTotal),
  });

  const rows = [
    {
      icon: Wallet,
      title: l.productAiRow1Title,
      text: formatTenge(amount),
      note: l[statusLabelKey[guidance.status]],
    },
    { icon: CalendarClock, title: l.productAiRow2Title, text: upcomingText },
    { icon: PieChart, title: l.productAiRow3Title, text: usualText },
    { icon: Lightbulb, title: l.productAiRow4Title, text: adviceText, wrap: true },
  ];
  return (
    <div className={cardDark}>
      <BrandHeader dark />
      <div className="mt-5 flex items-center gap-2">
        <Sparkles size={16} className="text-orange" />
        <p className="text-[16px] font-extrabold text-white">{l.productAiTitle}</p>
      </div>

      <div className="mt-4 space-y-2.5">
        {rows.map((r) => (
          <div key={r.title} className="flex items-start gap-3 rounded-[16px] border border-white/10 bg-white/[0.04] p-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[11px] bg-orange/15 text-orange">
              <r.icon size={15} strokeWidth={2} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] font-bold text-white">{r.title}</p>
              <p
                className={`text-[11px] leading-relaxed text-white/70 ${
                  r.wrap ? "line-clamp-3" : "numbers"
                }`}
              >
                {r.text}
              </p>
              {r.note && <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-orange">{r.note}</p>}
            </div>
            {!r.wrap && <ArrowRight size={14} className="mt-0.5 shrink-0 text-white/50" />}
          </div>
        ))}
      </div>

      <div className="mt-auto flex items-center gap-2 rounded-[16px] bg-orange/10 p-3.5">
        <BarChart3 size={14} className="shrink-0 text-orange" />
        <p className="text-[11.5px] leading-relaxed text-white/75">{l.productAiDemoNote}</p>
      </div>
    </div>
  );
}
