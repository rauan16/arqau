"use client";

import { Transaction } from "@/lib/api";
import { compactTenge } from "@/lib/money";

export type ChartMetric = "expenses" | "income" | "savings";
export type ChartPeriod = 1 | 3 | 6 | 12;

export interface SpendingChartData {
  labels: string[];
  values: number[];
  monthsWithData: number;
  totalMonths: number;
  total: number;
  delta: number | null;
}

/**
 * Round an axis interval up to a readable 1 / 2 / 2.5 / 5 / 10 step so chart
 * gridlines land on whole amounts instead of arbitrary splits.
 */
export function niceStep(rawStep: number): number {
  if (!Number.isFinite(rawStep) || rawStep <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  const stepped = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  return stepped * magnitude;
}

function monthLabel(date: Date, locale: "en" | "ru") {
  return new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", { month: "short" }).format(date);
}

function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * Aggregates real transactions into monthly buckets for the selected metric and
 * period. The previous-period total is only reported when transactions actually
 * exist there, so a delta is never invented.
 */
export function buildChartData(
  transactions: Transaction[],
  metric: ChartMetric,
  months: ChartPeriod,
  locale: "en" | "ru",
  referenceDate: Date = new Date(),
): SpendingChartData {
  const now = referenceDate;
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
    labels.push(monthLabel(date, locale));
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
    hasPreviousData && previousTotal !== 0
      ? Math.round(((total - previousTotal) / Math.abs(previousTotal)) * 100)
      : null;

  return {
    labels,
    values,
    monthsWithData: windowKeys.filter((key) => monthBuckets.has(key)).length,
    totalMonths: months,
    total,
    delta,
  };
}

export function SpendingChart({ data }: { data: SpendingChartData }) {
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
