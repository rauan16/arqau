"use client";

// ---------------------------------------------------------------------------
// Shared presentation layer for the authenticated dashboard overview.
//
// Every component in this file is pure presentation: it receives already
// resolved data (or a "ready" status) and renders it. Nothing here talks to
// the network, reads auth state or mutates anything.
//
// The authenticated home (`DashboardHome`) owns data fetching and passes API
// data in. The public demo passes locally computed demo data of the exact same
// shape in, so both surfaces render one identical layout from one source.
// ---------------------------------------------------------------------------

import Link from "next/link";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import {
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  ChartNoAxesCombined,
  ChevronRight,
  CircleAlert,
  Info,
  Loader2,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useLocale, useTranslation } from "@/lib/language-context";
import {
  EWAResultResponse,
  FinancialContext,
  Transaction,
  WithdrawalDecisionResponse,
} from "@/lib/api";
import { compactTenge, formatMinorAsTenge } from "@/lib/money";
import { locales } from "@/lib/i18n";

export const cardPanel = "rounded-[24px] border border-ink/[0.07] bg-white p-5 shadow-[0_18px_38px_-32px_rgba(22,20,18,0.5)] sm:p-6";
export const beigePanel = "rounded-[24px] border border-ink/[0.07] bg-[#f0e9e2] p-5 shadow-[0_18px_38px_-32px_rgba(22,20,18,0.5)] sm:p-6";
export const inputLike = "rounded-[10px] border border-ink/10 bg-white px-3 py-1.5 text-[12px] font-semibold text-ink focus-ring";

export type Locale = "en" | "ru";
export type OverviewCopy = typeof locales.en.overview;
export type SourceStatus = "loading" | "ready" | "error";
export type MetricKey = "expenses" | "income" | "savings";
export type PeriodMonths = 3 | 6 | 12;

export const DAY_MS = 24 * 60 * 60 * 1000;
const SLIDER_STEP_MINOR = 100000;
const HERO_SEGMENTS = 11;
const SLIDER_SEGMENTS = 10;

/** Renders a link, or an inert inline element when no destination is supplied. */
function OptionalLink({
  href,
  className,
  children,
}: {
  href: string | null;
  className: string;
  children: ReactNode;
}) {
  if (href === null) return <span className={className}>{children}</span>;
  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

export interface ActivityItem {
  id: string;
  kind: "withdrawal" | "income" | "expense";
  title: string;
  date: Date | null;
  amountMinor: number;
  statusLabel: string;
}

export interface ChartData {
  labels: string[];
  values: number[];
  monthsWithData: number;
  totalMonths: number;
  total: number;
  delta: number | null;
}

export function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatShortDate(date: Date, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", { day: "numeric", month: "short" }).format(date);
}

export function formatLongDate(date: Date, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", { day: "numeric", month: "long" }).format(date);
}

export function formatWeekdayDate(date: Date, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
}

function formatMonthLabel(date: Date, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", { month: "short" }).format(date);
}

function formatActivityDate(date: Date, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function greetingKeyForHour(hour: number): "greetingMorning" | "greetingAfternoon" | "greetingEvening" {
  if (hour < 12) return "greetingMorning";
  if (hour < 18) return "greetingAfternoon";
  return "greetingEvening";
}

export function dayUnitWord(count: number, locale: Locale, o: OverviewCopy) {
  if (locale === "en") return count === 1 ? o.dayUnitOne : o.dayUnitMany;
  const mod100 = count % 100;
  const mod10 = count % 10;
  if (mod100 >= 11 && mod100 <= 14) return o.dayUnitMany;
  if (mod10 === 1) return o.dayUnitOne;
  if (mod10 >= 2 && mod10 <= 4) return o.dayUnitFew;
  return o.dayUnitMany;
}

function withdrawalStatusLabel(status: string, o: OverviewCopy) {
  switch (status) {
    case "pending":
      return o.statusPending;
    case "approved":
      return o.statusApproved;
    case "rejected":
      return o.statusRejected;
    case "completed":
      return o.statusCompleted;
    case "cancelled":
      return o.statusCancelled;
    default:
      return status;
  }
}

/**
 * Round an axis interval up to a readable 1 / 2 / 2.5 / 5 / 10 step so chart
 * gridlines land on whole numbers (e.g. 25 000 ₸) instead of arbitrary splits.
 */
function niceStep(rawStep: number): number {
  if (!Number.isFinite(rawStep) || rawStep <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  const stepped = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  return stepped * magnitude;
}

export function buildActivityItems(
  transactions: Transaction[],
  recentRequests: FinancialContext["withdrawal_history"]["recent_requests"],
  o: OverviewCopy,
): ActivityItem[] {
  const items: ActivityItem[] = [];

  for (const request of recentRequests) {
    items.push({
      id: `request-${request.id}`,
      kind: "withdrawal",
      title: o.withdrawal,
      date: parseDate(request.created_at),
      amountMinor: request.amount_minor,
      statusLabel: withdrawalStatusLabel(request.status, o),
    });
  }

  for (const tx of transactions) {
    const income = tx.type === "income";
    items.push({
      id: `transaction-${tx.id}`,
      kind: income ? "income" : "expense",
      title: tx.merchant || tx.category || (income ? o.incomeFallback : o.expenseFallback),
      date: parseDate(tx.date ?? tx.created_at ?? null),
      amountMinor: tx.amount_minor,
      statusLabel: income ? o.incomeFallback : o.expenseFallback,
    });
  }

  return items.sort((a, b) => (b.date?.getTime() ?? 0) - (a.date?.getTime() ?? 0));
}

export function buildChartData(transactions: Transaction[], metric: MetricKey, months: PeriodMonths, locale: Locale): ChartData {
  const now = new Date();
  const monthBuckets = new Map<string, { expenses: number; income: number }>();

  for (const tx of transactions) {
    const date = parseDate(tx.date ?? tx.created_at ?? null);
    if (!date) continue;
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    const bucket = monthBuckets.get(key) ?? { expenses: 0, income: 0 };
    if (tx.type === "income") bucket.income += tx.amount_minor;
    else bucket.expenses += tx.amount_minor;
    monthBuckets.set(key, bucket);
  }

  const pick = (bucket: { expenses: number; income: number }) =>
    metric === "income" ? bucket.income : metric === "expenses" ? bucket.expenses : bucket.income - bucket.expenses;

  const windowKeys: string[] = [];
  const labels: string[] = [];
  for (let offset = months - 1; offset >= 0; offset -= 1) {
    const date = new Date(now.getFullYear(), now.getMonth() - offset, 1);
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    windowKeys.push(key);
    labels.push(formatMonthLabel(date, locale));
  }

  const values = windowKeys.map((key) => {
    const bucket = monthBuckets.get(key);
    return bucket ? pick(bucket) : 0;
  });

  const previousKeys: string[] = [];
  for (let offset = months * 2 - 1; offset >= months; offset -= 1) {
    const date = new Date(now.getFullYear(), now.getMonth() - offset, 1);
    previousKeys.push(`${date.getFullYear()}-${date.getMonth()}`);
  }

  let previousTotal = 0;
  let hasPreviousData = false;
  for (const key of previousKeys) {
    const bucket = monthBuckets.get(key);
    if (!bucket) continue;
    hasPreviousData = true;
    previousTotal += pick(bucket);
  }

  const total = values.reduce((sum, value) => sum + value, 0);
  const delta =
    hasPreviousData && previousTotal !== 0 ? Math.round(((total - previousTotal) / Math.abs(previousTotal)) * 100) : null;

  return {
    labels,
    values,
    monthsWithData: windowKeys.filter((key) => monthBuckets.has(key)).length,
    totalMonths: months,
    total,
    delta,
  };
}

export function SectionError({ section, onRetry }: { section: string; onRetry: () => void }) {
  const { t } = useTranslation();
  const o = t.overview;
  return (
    <section className={`${cardPanel} flex flex-col items-start gap-3`}>
      <div className="flex items-center gap-2 text-orange-dark">
        <CircleAlert size={17} />
        <h2 className="text-[15px] font-bold">{o.errorTitle}</h2>
      </div>
      <p className="text-[13px] leading-relaxed text-ink-soft">
        {o.sectionError.replace("{section}", section)}
      </p>
      <button type="button" onClick={onRetry} className="btn-secondary inline-flex items-center gap-2 text-[13px]">
        <RefreshCw size={14} /> {o.retry}
      </button>
    </section>
  );
}

export function HeroEarningsCard({ calculation, status, onRetry }: { calculation: EWAResultResponse | null; status: SourceStatus; onRetry: () => void }) {
  const { t } = useTranslation();
  const locale = useLocale();
  const o = t.overview;
  const fmt = (minor: number) => formatMinorAsTenge(minor, locale);

  if (status === "error") return <SectionError section={o.sectionEarnings} onRetry={onRetry} />;
  if (!calculation) return <div className={`${cardPanel} h-[220px] animate-pulse`} />;

  const available = calculation.available_amount_minor;
  const earned = calculation.earned_amount_minor;
  const salary = calculation.salary_amount_minor;

  if (earned <= 0) {
    return (
      <section className={cardPanel}>
        <div className="flex items-center gap-2 text-orange">
          <Wallet size={17} />
          <p className="text-[13px] font-semibold text-ink-soft">{o.availableNow}</p>
        </div>
        <h2 className="mt-5 text-[22px] font-extrabold tracking-[-0.03em]">{o.emptyTitle}</h2>
        <p className="mt-2 max-w-[420px] text-[13px] leading-relaxed text-ink-soft">{o.emptyDescription}</p>
      </section>
    );
  }

  const rest = Math.max(0, earned - available);
  const share = Math.min(1, Math.max(0, available / earned));

  const start = parseDate(calculation.pay_period_start);
  const end = parseDate(calculation.pay_period_end);
  const calculationDate = parseDate(calculation.calculation_date);
  const period =
    start && end && calculationDate
      ? (() => {
          const totalDays = Math.round((end.getTime() - start.getTime()) / DAY_MS) + 1;
          const dayNumber = Math.round((calculationDate.getTime() - start.getTime()) / DAY_MS) + 1;
          const nextPayday = new Date(end.getTime() + DAY_MS);
          const daysToPayday = Math.round((nextPayday.getTime() - calculationDate.getTime()) / DAY_MS);
          if (totalDays <= 0 || dayNumber < 1 || dayNumber > totalDays || daysToPayday < 0) return null;
          return { start, end, totalDays, dayNumber, daysToPayday, progress: dayNumber / totalDays };
        })()
      : null;

  return (
    <section className={cardPanel}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[13px] font-semibold text-ink-soft">{o.availableNow}</p>
          <p className="mt-2 text-[52px] font-extrabold leading-none tracking-[-0.035em] text-ink numbers sm:text-[62px]">
            {fmt(available)}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[13px] font-semibold text-ink-soft">{o.salary}</p>
          <p className="mt-2 text-[24px] font-extrabold tracking-tight text-ink numbers sm:text-[28px]">{fmt(salary)}</p>
        </div>
        <div className="text-right">
          <p className="text-[13px] font-semibold text-ink-soft">{o.earned}</p>
          <p className="mt-2 text-[24px] font-extrabold tracking-tight text-ink numbers sm:text-[28px]">{fmt(earned)}</p>
        </div>
      </div>

      <div className="mt-6 flex gap-1.5" role="presentation">
        {Array.from({ length: HERO_SEGMENTS }, (_, index) => (
          <div
            key={index}
            data-testid="hero-segment"
            className={`h-2.5 flex-1 rounded-full ${index / HERO_SEGMENTS < share ? "bg-orange" : "bg-cream-soft"}`}
          />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-10 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-orange" aria-hidden="true" />
          <span className="text-[13px] font-bold numbers">{fmt(available)}</span>
          <span className="text-[12px] text-ink-soft">{o.availableToWithdraw}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-ink/20" aria-hidden="true" />
          <span className="text-[13px] font-bold numbers">{fmt(rest)}</span>
          <span className="text-[12px] text-ink-soft">{o.remainingEarned}</span>
        </div>
      </div>

      {period && (
        <div className="mt-6 border-t border-ink/[0.07] pt-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[13px] font-semibold text-ink">
              {o.payPeriod
                .replace("{start}", formatLongDate(period.start, locale))
                .replace("{end}", formatLongDate(period.end, locale))}
            </p>
            <p className="text-[13px] font-bold text-ink numbers">
              {o.dayOfPeriod.replace("{day}", String(period.dayNumber)).replace("{total}", String(period.totalDays))}
            </p>
          </div>
          <div className="relative mt-3 h-1.5 rounded-full bg-cream-soft" role="presentation">
            <div className="h-full rounded-full bg-orange" style={{ width: `${period.progress * 100}%` }} />
            <div
              className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-orange bg-white"
              style={{ left: `${period.progress * 100}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between gap-3 text-[12px] text-ink-soft">
            <span className="numbers">{formatShortDate(period.start, locale)}</span>
            <span className="font-bold text-orange">
              {o.paydayInDays
                .replace("{days}", String(period.daysToPayday))
                .replace("{unit}", dayUnitWord(period.daysToPayday, locale, o))}
            </span>
            <span className="numbers">{formatShortDate(period.end, locale)}</span>
          </div>
        </div>
      )}
    </section>
  );
}

export function ActivitySection({
  items,
  transactionsStatus,
  contextStatus,
  onRetry,
  historyHref = "/dashboard/history",
}: {
  items: ActivityItem[];
  transactionsStatus: SourceStatus;
  contextStatus: SourceStatus;
  onRetry: () => void;
  /** Destination of the "view full history" link. */
  historyHref?: string | null;
}) {
  const { t } = useTranslation();
  const locale = useLocale();
  const o = t.overview;
  const fmt = (minor: number) => formatMinorAsTenge(minor, locale);

  const failedSources: string[] = [];
  if (transactionsStatus === "error") failedSources.push(o.sectionActivity);
  if (contextStatus === "error") failedSources.push(o.sectionActivity);
  return (
    <section>
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-[18px] font-extrabold tracking-[-0.02em]">{o.recentActivity}</h2>
        <OptionalLink href={historyHref} className="inline-flex items-center gap-1 text-[13px] font-semibold text-orange hover:text-orange-dark">
          {o.allHistory} <ChevronRight size={15} />
        </OptionalLink>
      </div>

      {failedSources.length > 0 && (
        <div className="mt-4 flex items-center justify-between gap-3 rounded-[12px] border border-orange/25 bg-orange-soft px-4 py-3">
          <p className="text-[12px] font-semibold text-orange-dark">{o.sectionError.replace("{section}", o.sectionActivity)}</p>
          <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 text-[12px] font-bold text-orange-dark">
            <RefreshCw size={13} /> {o.retry}
          </button>
        </div>
      )}

      {items.length === 0 ? (
        <div className="mt-4 border-t border-ink/[0.07] pt-6">
          <h3 className="text-[15px] font-bold">{o.activityEmptyTitle}</h3>
          <p className="mt-2 max-w-[420px] text-[13px] leading-relaxed text-ink-soft">{o.activityEmptyDescription}</p>
        </div>
      ) : (
        <ul className="mt-4">
          {items.map((item) => {
            const income = item.kind === "income";
            const Icon = item.kind === "withdrawal" ? ArrowUpRight : income ? TrendingUp : ArrowDownLeft;
            return (
              <li key={item.id} className="flex items-center gap-3 border-t border-ink/[0.07] py-3.5 first:border-t-0 first:pt-0">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-cream-soft text-orange">
                  <Icon size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-bold">{item.title}</p>
                  <p className="mt-0.5 text-[12px] text-ink-soft numbers">
                    {item.date ? formatActivityDate(item.date, locale) : "—"}
                  </p>
                </div>
                <div className="text-right">
                  <p className={`text-[15px] font-extrabold numbers ${income ? "text-green-600" : "text-ink"}`}>
                    {income ? "+" : "−"}
                    {fmt(item.amountMinor)}
                  </p>
                  <p className="mt-0.5 text-[12px] text-ink-soft">{item.statusLabel}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function AnalyticsChart({ data }: { data: ChartData }) {
  const positiveMax = Math.max(0, ...data.values);
  const negativeMin = Math.min(0, ...data.values);
  const positiveStep = niceStep(positiveMax / 4);
  const negativeStep = negativeMin < 0 ? niceStep(Math.abs(negativeMin) / 4) : 0;
  const axisTop = positiveStep * 4;
  const axisBottom = -negativeStep * 4;
  const span = axisTop - axisBottom || 1;
  const zeroPct = (axisTop / span) * 100;
  const peak = Math.max(1, ...data.values.map((value) => Math.abs(value)));

  const gridlines =
    negativeStep > 0
      ? [axisTop, positiveStep * 3, positiveStep * 2, positiveStep, 0, -negativeStep, negativeStep * -2, negativeStep * -3, axisBottom]
      : [axisTop, positiveStep * 3, positiveStep * 2, positiveStep, 0];
  const position = (value: number) => ((axisTop - value) / span) * 100;

  return (
    <div className="mt-5">
      <div className="flex gap-2">
        <div className="relative h-[170px] w-10 shrink-0">
          {gridlines.map((value, index) => (
            <span
              key={index}
              className="absolute right-0 -translate-y-1/2 text-[10px] font-semibold text-ink-soft/70 numbers"
              style={{ top: `${position(value)}%` }}
            >
              {compactTenge(value)}
            </span>
          ))}
        </div>
        <div className="relative h-[170px] flex-1">
          {gridlines.map((value, index) => (
            <div
              key={index}
              className="absolute inset-x-0 border-t border-dashed border-ink/[0.08]"
              style={{ top: `${position(value)}%` }}
            />
          ))}
          <div className="absolute inset-x-0 border-t border-ink/15" style={{ top: `${zeroPct}%` }} />
          <div className="absolute inset-0 flex items-end gap-1.5">
            {data.values.map((value, index) => {
              const positiveHeight = value > 0 ? (value / axisTop) * 100 : 0;
              const negativeHeight = value < 0 ? (Math.abs(value) / Math.abs(axisBottom || 1)) * 100 : 0;
              const opacity = value === 0 ? 0 : 0.45 + 0.55 * (Math.abs(value) / peak);
              return (
                <div key={index} data-testid="chart-bar" className="relative h-full flex-1">
                  {positiveHeight > 0 && (
                    <div className="absolute inset-x-0 top-0" style={{ height: `${zeroPct}%` }}>
                      <div
                        className="absolute bottom-0 w-full rounded-t-[5px] bg-orange"
                        style={{ height: `${positiveHeight}%`, opacity }}
                      />
                    </div>
                  )}
                  {negativeHeight > 0 && (
                    <div className="absolute inset-x-0 bottom-0" style={{ height: `${100 - zeroPct}%` }}>
                      <div
                        className="absolute top-0 w-full rounded-b-[5px] bg-orange-dark"
                        style={{ height: `${negativeHeight}%`, opacity }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div className="mt-2 flex gap-2 pl-12">
        {data.labels.map((label, index) => (
          <span
            key={index}
            data-testid="chart-month-label"
            className="flex-1 text-center text-[10px] font-semibold text-ink-soft numbers"
          >
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function AnalyticsCard({ transactions, status, onRetry }: { transactions: Transaction[] | null; status: SourceStatus; onRetry: () => void }) {
  const { t } = useTranslation();
  const locale = useLocale();
  const o = t.overview;
  const [metric, setMetric] = useState<MetricKey>("expenses");
  const [months, setMonths] = useState<PeriodMonths>(6);

  const data = useMemo(() => buildChartData(transactions ?? [], metric, months, locale), [transactions, metric, months, locale]);
  const fmt = (minor: number) => formatMinorAsTenge(minor, locale);
  const totalLabel = metric === "income" ? o.totalIncome : metric === "expenses" ? o.totalExpenses : o.totalSavings;
  const totalSign = metric === "expenses" ? "−" : "+";
  const signedTotal = `${data.total < 0 ? "−" : totalSign}${fmt(Math.abs(data.total))}`;

  const metricOptions: Array<{ key: MetricKey; label: string }> = [
    { key: "expenses", label: o.metricExpenses },
    { key: "income", label: o.metricIncome },
    { key: "savings", label: o.metricSavings },
  ];
  const periodOptions: Array<{ value: PeriodMonths; label: string }> = [
    { value: 3, label: o.period3 },
    { value: 6, label: o.period6 },
    { value: 12, label: o.period12 },
  ];

  if (status === "error") return <SectionError section={o.sectionAnalytics} onRetry={onRetry} />;
  if (status === "loading" || transactions === null) return <div className={`${cardPanel} h-[300px] animate-pulse`} />;

  return (
    <section className={cardPanel}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{o.analytics}</h2>
        <select
          aria-label={o.periodAria}
          className={inputLike}
          value={months}
          onChange={(event) => setMonths(Number(event.target.value) as PeriodMonths)}
        >
          {periodOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 flex gap-1.5" role="group" aria-label={o.metricAria}>
        {metricOptions.map((option) => {
          const active = option.key === metric;
          return (
            <button
              key={option.key}
              type="button"
              data-testid="metric-tab"
              data-metric={option.key}
              aria-pressed={active}
              onClick={() => setMetric(option.key)}
              className={`rounded-full px-3 py-1.5 text-[12px] font-bold transition-colors ${
                active ? "bg-orange-soft text-orange" : "text-ink-soft hover:bg-cream-soft hover:text-ink"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {data.monthsWithData === 0 ? (
        <div className="mt-6 rounded-[14px] bg-cream-soft px-4 py-8 text-center">
          <p className="text-[13px] font-bold">{o.insufficientHistory}</p>
          <p className="mx-auto mt-2 max-w-[280px] text-[12px] leading-relaxed text-ink-soft">{o.chartEmptyDescription}</p>
        </div>
      ) : (
        <AnalyticsChart data={data} />
      )}

      <div className="mt-5 flex items-center justify-between gap-3 border-t border-ink/[0.07] pt-4">
        <div>
          <p className="text-[12px] text-ink-soft">{totalLabel}</p>
          <p className="mt-1 text-[20px] font-extrabold tracking-tight numbers">{signedTotal}</p>
        </div>
        {data.delta !== null && (
          <span
            className="rounded-full bg-cream-soft px-3 py-1.5 text-[12px] font-bold text-ink numbers"
            aria-label={o.deltaAria}
          >
            {data.delta >= 0
              ? o.deltaUp.replace("{value}", String(Math.abs(data.delta)))
              : o.deltaDown.replace("{value}", String(Math.abs(data.delta)))}
          </span>
        )}
      </div>

      {data.monthsWithData > 0 && data.monthsWithData < data.totalMonths && (
        <p className="mt-3 text-[11px] text-ink-soft">
          {o.partialData.replace("{shown}", String(data.monthsWithData)).replace("{total}", String(data.totalMonths))}
        </p>
      )}
    </section>
  );
}

export function InsightsCard({
  context,
  status,
  onRetry,
  spendingHref = "/dashboard/finance",
  aiHref = "/dashboard/ai",
}: {
  context: FinancialContext | null;
  status: SourceStatus;
  onRetry: () => void;
  /** Destination of the spending-total link. */
  spendingHref?: string | null;
  /** Destination of the two secondary links. */
  aiHref?: string | null;
}) {
  const { t } = useTranslation();
  const locale = useLocale();
  const o = t.overview;
  const fmt = (minor: number) => formatMinorAsTenge(minor, locale);

  if (status === "error") return <SectionError section={o.sectionInsights} onRetry={onRetry} />;
  if (status === "loading" || context === null) return <div className={`${beigePanel} h-[260px] animate-pulse`} />;

  const spendingAvailable = context.spending.available && context.spending.total_spending_minor !== null;
  const spendingTotal = context.spending.total_spending_minor ?? 0;

  return (
    <section className={beigePanel}>
      <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{o.insights}</h2>

      {spendingAvailable ? (
        <ul className="mt-4">
          <li className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/70 text-orange-dark">
              <ChartNoAxesCombined size={16} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-bold">{o.usualSpending}</p>
              <p className="mt-0.5 text-[12px] text-ink-soft">{o.usualSpendingHint}</p>
            </div>
            <OptionalLink href={spendingHref} className="text-[16px] font-extrabold numbers hover:text-orange">
              {fmt(spendingTotal)}
            </OptionalLink>
          </li>
        </ul>
      ) : (
        <p className="mt-4 text-[13px] leading-relaxed text-ink-soft">{o.spendingEmpty}</p>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-ink/[0.07] pt-4">
        <OptionalLink href={aiHref} className="inline-flex items-center gap-1 text-[13px] font-bold text-orange-dark hover:text-orange">
          {o.openAI} <ChevronRight size={15} />
        </OptionalLink>
        <OptionalLink href={aiHref} className="inline-flex items-center gap-1 text-[13px] font-bold text-orange-dark hover:text-orange">
          {o.withdrawalBreakdown} <ChevronRight size={15} />
        </OptionalLink>
      </div>
    </section>
  );
}

/**
 * Presentation for the AI guidance card. It owns no network call: the caller
 * supplies the current amount, any decision to render and the actions.
 */
export function AiGuidancePanelView({
  availableMinor,
  amountMinor,
  onAmountChange,
  decision,
  decisionError,
  analyzing,
  onAnalyze,
  contextNote,
  whyHref = "/dashboard/ai",
  getMoneyHref = "/dashboard/get-money",
  whatIfHref = "/dashboard/what-if",
}: {
  availableMinor: number;
  amountMinor: number;
  onAmountChange: (minor: number) => void;
  decision: WithdrawalDecisionResponse | null;
  decisionError: string | null;
  analyzing: boolean;
  onAnalyze: () => void;
  /** Optional extra context rendered above the analysis note (demo only). */
  contextNote?: ReactNode;
  whyHref?: string | null;
  getMoneyHref?: string | null;
  whatIfHref?: string | null;
}) {
  const { t } = useTranslation();
  const locale = useLocale();
  const o = t.overview;
  const fmt = (minor: number) => formatMinorAsTenge(minor, locale);

  return (
    <section className="relative overflow-hidden rounded-[24px] bg-near-black p-5 shadow-[0_30px_70px_-40px_rgba(22,20,18,0.5)] sm:p-6">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(120% 90% at 0% 0%, rgba(242,103,34,0.28) 0%, rgba(242,103,34,0) 55%)" }}
        aria-hidden="true"
      />
      <div className="relative">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="rounded-full border border-orange/40 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.1em] text-orange">
            {o.aiBadge}
          </span>
          <OptionalLink
            href={whyHref}
            className="inline-flex items-center gap-1.5 rounded-full border border-cream/20 px-3 py-1.5 text-[11px] font-semibold text-cream/70 transition-colors hover:border-cream/40 hover:text-cream"
          >
            <Info size={12} /> {o.whyThisAmount}
          </OptionalLink>
        </div>

        <p className="mt-5 text-[13px] font-semibold text-cream/55">{o.amountToAnalyze}</p>
        <p className="mt-2 text-[46px] font-extrabold leading-none tracking-[-0.035em] text-cream numbers sm:text-[56px]">
          {fmt(amountMinor)}
        </p>

        <div className="mt-6">
          <div className="relative h-3">
            <div className="absolute inset-x-0 top-1/2 flex h-2.5 -translate-y-1/2 gap-1.5" aria-hidden="true">
              {Array.from({ length: SLIDER_SEGMENTS }, (_, index) => (
                <div
                  key={index}
                  data-testid="slider-segment"
                  className={`h-2.5 flex-1 rounded-full ${
                    availableMinor > 0 && index / SLIDER_SEGMENTS <= amountMinor / availableMinor
                      ? "bg-orange"
                      : "bg-cream/15"
                  }`}
                />
              ))}
            </div>
            <input
              type="range"
              aria-label={o.sliderAria}
              aria-valuetext={fmt(amountMinor)}
              className="slider-orange relative h-3 w-full"
              min={0}
              max={availableMinor}
              step={SLIDER_STEP_MINOR}
              value={Math.min(amountMinor, availableMinor)}
              disabled={availableMinor <= 0}
              onChange={(event) => onAmountChange(Number(event.target.value))}
            />
          </div>
          <div className="mt-2 flex justify-between text-[11px] font-semibold text-cream/55 numbers">
            <span>{fmt(0)}</span>
            <span>{fmt(availableMinor)}</span>
          </div>
        </div>

        {contextNote && <p className="mt-5 text-[12px] leading-relaxed text-cream/55">{contextNote}</p>}
        <p className="mt-5 text-[12px] leading-relaxed text-cream/55">{o.analysisNote}</p>

        {decisionError && (
          <p className="mt-4 rounded-[10px] border border-red-400/30 bg-red-500/10 px-3 py-2 text-[12px] font-semibold text-red-200">
            {decisionError}
          </p>
        )}

        {decision && (
          <div className="mt-5 rounded-[14px] border border-cream/10 bg-cream/[0.06] p-4">
            <p className={`text-[13px] font-bold ${decision.requestable ? "text-green-300" : "text-orange"}`}>
              {decision.requestable ? o.decisionRequestable : o.decisionNotRequestable}
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-cream/80">{decision.decision.status_explanation}</p>
            {decision.blocking_reasons.length > 0 && (
              <ul className="mt-2 space-y-1">
                {decision.blocking_reasons.map((reason, index) => (
                  <li key={index} className="text-[12px] leading-relaxed text-cream/70">
                    • {reason}
                  </li>
                ))}
              </ul>
            )}
            {decision.decision.key_facts.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {decision.decision.key_facts.slice(0, 3).map((fact) => (
                  <li key={fact.code} className="flex gap-2 text-[12px] leading-relaxed text-cream/70">
                    <Sparkles size={13} className="mt-0.5 shrink-0 text-orange" />
                    <span>{fact.text}</span>
                  </li>
                ))}
              </ul>
            )}
            {decision.decision.data_limitations.length > 0 && (
              <p className="mt-3 text-[11px] leading-relaxed text-cream/50">
                {decision.decision.data_limitations.join(" ")}
              </p>
            )}
            {decision.decision.ai_metadata.fallback_used && (
              <p className="mt-3 text-[11px] leading-relaxed text-cream/50">{t.ai.fallbackNotice}</p>
            )}
            <p className="mt-3 text-[11px] leading-relaxed text-cream/45">{decision.decision.disclaimer}</p>
            {decision.requestable && (
              <OptionalLink href={getMoneyHref} className="btn-primary mt-4 w-full justify-center px-4 py-3 text-[13px]">
                {o.getAmount.replace("{amount}", fmt(amountMinor))} <ArrowUpRight size={15} className="btn-arrow" />
              </OptionalLink>
            )}
          </div>
        )}

        <div className="mt-5 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={onAnalyze}
            disabled={analyzing || amountMinor <= 0}
            className="btn-primary flex-1 justify-center px-4 py-3 text-[13px] disabled:opacity-60"
          >
            {analyzing ? (
              <>
                <Loader2 size={15} className="animate-spin" /> {o.analyzing}
              </>
            ) : (
              <>
                <Sparkles size={15} /> {o.analyze} {fmt(amountMinor)}
              </>
            )}
          </button>
          <OptionalLink
            href={whatIfHref}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-full border border-cream/25 px-4 py-3 text-[13px] font-bold text-cream transition-colors hover:border-cream/50"
          >
            <ArrowLeftRight size={15} /> {o.whatIf}
          </OptionalLink>
        </div>
      </div>
    </section>
  );
}

export function LoadingOverview() {
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      <div className="h-[300px] animate-pulse rounded-[24px] bg-white/50" />
      <div className="grid items-start gap-5 lg:grid-cols-[1.06fr_0.94fr]">
        <div className="h-[280px] animate-pulse rounded-[24px] bg-white/50" />
        <div className="h-[380px] animate-pulse rounded-[24px] bg-white/50" />
      </div>
      <p className="sr-only">{t.overview.loading}</p>
    </div>
  );
}
