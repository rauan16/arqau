"use client";

import Link from "next/link";
import { ArrowUpRight, CalendarClock, ChevronRight, CircleAlert, CircleDollarSign, Plus, Sparkles, Wallet } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, FinanceSummary, EarnedWages, Transaction } from "@/lib/api";

const panel = "rounded-[20px] border border-ink/[0.08] bg-white/70 p-5 shadow-[0_18px_38px_-32px_rgba(21,21,21,0.5)]";

function formatTenge(value: number) {
  return value.toLocaleString("en-US");
}

function EmptyState({ title, description, actionLabel, actionHref }: { title: string; description: string; actionLabel?: string; actionHref?: string; }) {
  return (
    <div className={`${panel} flex flex-col items-start justify-between gap-4`}>
      <div>
        <h2 className="text-[18px] font-bold">{title}</h2>
        <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">{description}</p>
      </div>
      {actionLabel && actionHref && (
        <Link href={actionHref} className="btn-primary px-4 py-2 text-[12px]">
          <Plus size={14} /> {actionLabel}
        </Link>
      )}
    </div>
  );
}

function EarningsCard({ earned }: { earned: EarnedWages | null }) {
  if (!earned || earned.earned_amount_minor === 0) {
    return (
      <EmptyState
        title="Earned wages"
        description="Record your earnings to see your available balance and make informed withdrawal decisions."
        actionLabel="Set earned wages"
        actionHref="/dashboard/finance"
      />
    );
  }

  return (
    <section className={panel}>
      <div className="flex items-center gap-2 text-orange-dark">
        <Wallet size={17} />
        <p className="text-[12px] font-bold uppercase tracking-[0.1em]">Earned wages</p>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-4">
        <div>
          <p className="text-[11px] text-ink-soft">Earned this period</p>
          <p className="mt-1 text-[22px] font-extrabold">{formatTenge(earned.earned_amount_minor)} ₸</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft">Already accessed</p>
          <p className="mt-1 text-[22px] font-extrabold">{formatTenge(earned.accessed_amount_minor)} ₸</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft">Available now</p>
          <p className="mt-1 text-[22px] font-extrabold text-orange-dark">{formatTenge(earned.available_amount_minor)} ₸</p>
        </div>
      </div>
      <div className="mt-6 rounded-[12px] bg-cream px-4 py-3 text-[12px] text-ink-soft">
        Available = Earned − Accessed. Backend calculates the authoritative amount.
      </div>
    </section>
  );
}

function SpendingCard({ summary }: { summary: FinanceSummary | null }) {
  if (!summary || summary.transaction_count === 0) {
    return (
      <EmptyState
        title="Financial activity"
        description="Add income and expenses to start tracking your spending patterns and net balance."
        actionLabel="Add your first transaction"
        actionHref="/dashboard/finance"
      />
    );
  }

  return (
    <section className={panel}>
      <div className="flex items-center gap-2 text-orange-dark">
        <CircleDollarSign size={17} />
        <p className="text-[12px] font-bold uppercase tracking-[0.1em]">Financial activity</p>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-4">
        <div>
          <p className="text-[11px] text-ink-soft">Income</p>
          <p className="mt-1 text-[22px] font-extrabold text-green">+{formatTenge(summary.total_income_minor)} ₸</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft">Expenses</p>
          <p className="mt-1 text-[22px] font-extrabold text-orange-dark">-{formatTenge(summary.total_expense_minor)} ₸</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft">Net balance</p>
          <p className="mt-1 text-[22px] font-extrabold">{formatTenge(summary.net_balance_minor)} ₸</p>
        </div>
      </div>
      <p className="mt-6 text-[12px] text-ink-soft">{summary.transaction_count} transaction{summary.transaction_count !== 1 ? "s" : ""} recorded</p>
    </section>
  );
}

function InsightsCard({ earned }: { earned: EarnedWages | null }) {
  if (!earned || earned.available_amount_minor === 0) {
    return (
      <EmptyState
        title="ARQAU analysis"
        description="Add earned wages and transactions to unlock withdrawal analysis and AI-assisted insights."
        actionLabel="Set up earned wages"
        actionHref="/dashboard/get-money"
      />
    );
  }

  return (
    <section className={panel}>
      <div className="flex items-center gap-2 text-orange">
        <Sparkles size={19} />
        <h2 className="text-[18px] font-bold">ARQAU analysis</h2>
      </div>
      <p className="mt-2 text-[12px] text-ink-soft">Context-aware guidance for your earned income</p>
      <div className="mt-5 space-y-3">
        <Link href="/dashboard/ai" className="flex items-center justify-between rounded-[12px] border border-ink/[0.08] bg-cream px-4 py-3 text-[13px]">
          <span>Withdrawal analysis</span>
          <ChevronRight size={16} className="text-orange-dark" />
        </Link>
        <Link href="/dashboard/ai" className="flex items-center justify-between rounded-[12px] border border-ink/[0.08] bg-cream px-4 py-3 text-[13px]">
          <span>Ask AI assistant</span>
          <ChevronRight size={16} className="text-orange-dark" />
        </Link>
      </div>
    </section>
  );
}

export default function DashboardHome() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [earned, setEarned] = useState<EarnedWages | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [summaryData, earnedData] = await Promise.all([
          api.finance.getSummary(),
          api.ewa.getEarned().catch(() => null),
        ]);
        setSummary(summaryData);
        setEarned(earnedData);
      } catch {
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const displayName = user?.name || user?.email?.split("@")[0] || "Guest";

  if (loading) {
    return (
      <div className="space-y-9">
        <div className="h-[140px] animate-pulse rounded-[20px] bg-white/50" />
        <div className="h-[200px] animate-pulse rounded-[20px] bg-white/50" />
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="h-[200px] animate-pulse rounded-[20px] bg-white/50" />
          <div className="h-[200px] animate-pulse rounded-[20px] bg-white/50" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-9">
      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
        <div>
          <p className="eyebrow mb-4">Personal finance / overview</p>
          <h1 className="text-balance text-[40px] font-extrabold leading-[1] tracking-[-0.04em] sm:text-[56px]">
            Good morning, {displayName}.
          </h1>
          <p className="mt-4 max-w-[560px] text-[16px] leading-relaxed text-ink-soft">
            Earned income, upcoming expenses and your reserve — in one place.
          </p>
        </div>
      </div>

      <EarningsCard earned={earned} />

      <div className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <SpendingCard summary={summary} />
        <InsightsCard earned={earned} />
      </div>
    </div>
  );
}
