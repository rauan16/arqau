"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  buildAnalytics,
  defaultAnalyticsMetric,
  defaultAnalyticsPeriod,
  getRecommendedWithdrawal,
  getWithdrawalGuidance,
  isPresetAvailable,
  scenario,
  withdrawalPresets,
} from "@/lib/demoData";
import type {
  AnalyticsLabels,
  AnalyticsMetricId,
  AnalyticsPeriodId,
  AnalyticsSummary,
  WithdrawalGuidance,
} from "@/lib/demoData";

export type DemoSubmitState = "idle" | "sending" | "sent";

export type ProductDemo = {
  metric: AnalyticsMetricId;
  period: AnalyticsPeriodId;
  amount: number;
  analytics: AnalyticsSummary;
  guidance: WithdrawalGuidance;
  presets: readonly number[];
  submitState: DemoSubmitState;
  setMetric: (metric: AnalyticsMetricId) => void;
  setPeriod: (period: AnalyticsPeriodId) => void;
  selectAmount: (amount: number) => void;
  submitWithdrawal: () => void;
  resetWithdrawal: () => void;
};

const CONFIRM_DELAY_MS = 650;

/**
 * Shared state for the Product demo cards.
 *
 * Every card reads from the same source, so changing the metric, the period or
 * the withdrawal amount keeps the chart, the summary values and the AI panel
 * consistent. The submission flow is a local demo state only — nothing leaves
 * the browser and no payment API is called.
 */
export function useProductDemo(labels: AnalyticsLabels): ProductDemo {
  const [metric, setMetric] = useState<AnalyticsMetricId>(defaultAnalyticsMetric);
  const [period, setPeriod] = useState<AnalyticsPeriodId>(defaultAnalyticsPeriod);
  const [amount, setAmount] = useState<number>(getRecommendedWithdrawal);
  const [submitState, setSubmitState] = useState<DemoSubmitState>("idle");

  const analytics = useMemo(() => buildAnalytics(metric, period, labels), [metric, period, labels]);
  const guidance = useMemo(() => getWithdrawalGuidance(amount), [amount]);
  const presets = useMemo(() => withdrawalPresets, []);

  useEffect(() => {
    if (submitState !== "sending") return;
    const timer = window.setTimeout(() => setSubmitState("sent"), CONFIRM_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [submitState]);

  const selectAmount = useCallback((next: number) => {
    if (!isPresetAvailable(next, scenario.available)) return;
    setAmount(next);
    setSubmitState("idle");
  }, []);

  const submitWithdrawal = useCallback(() => {
    setSubmitState((current) => (current === "sending" ? current : "sending"));
  }, []);

  const resetWithdrawal = useCallback(() => {
    setSubmitState("idle");
  }, []);

  return {
    metric,
    period,
    amount,
    analytics,
    guidance,
    presets,
    submitState,
    setMetric,
    setPeriod,
    selectAmount,
    submitWithdrawal,
    resetWithdrawal,
  };
}
