"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Calendar,
  ChevronDown,
  ChevronRight,
  Filter,
  Info,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  TrendingUp,
  X,
} from "lucide-react";
import { useLocale, useTranslation } from "@/lib/language-context";
import {
  addDemoTransaction,
  commitDemoState,
  computeDemoCategories,
  computeDemoMonths,
  computeDemoTotals,
  deleteDemoTransaction,
  editDemoTransaction,
  formatDemoAmount,
  getCategoryLabel,
  getDemoCategories,
  resetDemoState,
  useDemoState,
  evaluateDemoScenario,
  demoRecommendedAmount,
  computeDemoSavings,
  computeUpcomingTotal,
  upcomingBills,
  type DemoState,
  type DemoScenarioStatus,
} from "@/lib/demoStore";
import { buildChartData, SpendingChart, type ChartMetric, type ChartPeriod } from "@/components/app/SpendingChart";
import { Transaction } from "@/lib/api";
import { buildDemoDecision, buildDemoOverview, type DemoOverview as DemoOverviewData } from "@/lib/demoOverview";
import { AiGuidancePanelView } from "@/components/app/DashboardOverview";

const panel = "rounded-[24px] border border-ink/[0.07] bg-white p-5 shadow-[0_18px_38px_-32px_rgba(22,20,18,0.5)] sm:p-6";
const finInput = "w-full rounded-[12px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-orange-deep";
const pillActive = "bg-orange-soft text-orange";
const pillIdle = "text-ink-soft hover:bg-cream-soft hover:text-ink";

const periodOptions: Array<{ value: ChartPeriod; label: string }> = [
  { value: 1, label: "1M" },
  { value: 3, label: "3M" },
  { value: 6, label: "6M" },
  { value: 12, label: "12M" },
];
const metricOptions: Array<{ key: ChartMetric; label: string }> = [
  { key: "expenses", label: "Expenses" },
  { key: "income", label: "Income" },
  { key: "savings", label: "Savings" },
];
const filterOptions: Array<{ key: "all" | "income" | "expense"; label: string }> = [
  { key: "all", label: "All" },
  { key: "income", label: "Income" },
  { key: "expense", label: "Expense" },
];

function Pill({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={`rounded-full px-3 py-1.5 text-[12px] font-bold transition-colors ${active ? pillActive : pillIdle}`}>
      {label}
    </button>
  );
}

function AddTransactionForm({
  t,
  e,
  categories,
  saving,
  error,
  onSubmit,
  onCancel,
}: {
  t: ReturnType<typeof useTranslation>["t"];
  e: ReturnType<typeof useTranslation>["t"]["expenses"];
  categories: string[];
  saving: boolean;
  error: string | null;
  onSubmit: (input: { type: "income" | "expense"; amount: number; category: string; merchant: string; description: string; date: string }) => void;
  onCancel: () => void;
}) {
  const [txType, setTxType] = useState<"income" | "expense">("expense");
  const [txAmount, setTxAmount] = useState("");
  const [txCategory, setTxCategory] = useState("");
  const [txMerchant, setTxMerchant] = useState("");
  const [txDescription, setTxDescription] = useState("");
  const [txDate, setTxDate] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  function submit() {
    const amount = Number(txAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setLocalError(e.amountInvalid);
      return;
    }
    if (txDate && !/^\d{4}-\d{2}-\d{2}$/.test(txDate)) {
      setLocalError(e.dateInvalid);
      return;
    }
    setLocalError(null);
    onSubmit({ type: txType, amount, category: txCategory, merchant: txMerchant, description: txDescription, date: txDate });
  }

  return (
    <section className={panel}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{e.addTransaction}</h2>
        <button type="button" onClick={onCancel} className="text-[13px] font-semibold text-ink-soft hover:text-orange">
          {e.cancel}
        </button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_1fr]">
        <div className="flex gap-2 sm:col-span-1">
          <button type="button" onClick={() => setTxType("income")} className={`flex-1 rounded-[12px] border px-3 py-2.5 text-[13px] font-semibold transition-colors ${txType === "income" ? "border-orange bg-orange-soft text-orange" : "border-ink/10 hover:border-orange/30"}`}>{e.typeIncome}</button>
          <button type="button" onClick={() => setTxType("expense")} className={`flex-1 rounded-[12px] border px-3 py-2.5 text-[13px] font-semibold transition-colors ${txType === "expense" ? "border-orange bg-orange-soft text-orange-dark" : "border-ink/10 hover:border-orange/30"}`}>{e.typeExpense}</button>
        </div>
        <input type="number" value={txAmount} onChange={(event) => setTxAmount(event.target.value)} placeholder={e.amount} aria-label={e.amount} className={`${finInput} numbers`} />
        <input value={txCategory} list="demo-finance-categories" onChange={(event) => setTxCategory(event.target.value)} placeholder={e.category} aria-label={e.category} className={finInput} />
        <input value={txMerchant} onChange={(event) => setTxMerchant(event.target.value)} placeholder={e.merchant} aria-label={e.merchant} className={finInput} />
        <input value={txDescription} onChange={(event) => setTxDescription(event.target.value)} placeholder={e.description} aria-label={e.description} className={finInput} />
        <input type="date" value={txDate} onChange={(event) => setTxDate(event.target.value)} aria-label={t.demo.date} className={`${finInput} numbers`} />
        <button type="button" onClick={submit} disabled={saving || !txAmount} className="btn-primary w-full justify-center disabled:opacity-50 sm:col-span-1">
          {saving ? e.saving : e.save}
        </button>
      </div>
      <datalist id="demo-finance-categories">
        {categories.map((category) => (
          <option key={category} value={category} />
        ))}
      </datalist>
      {(localError || error) && (
        <p className="mt-3 text-[12px] font-semibold text-red-600">{localError || error}</p>
      )}
    </section>
  );
}
function EditTransactionRow({
  tx,
  locale,
  t,
  e,
  editingId,
  editDraft,
  setEditDraft,
  onEdit,
  onDelete,
}: {
  tx: { id: string; type: "income" | "expense"; amount: number; category: string; merchant?: string; description?: string; date: string };
  locale: "en" | "ru";
  t: ReturnType<typeof useTranslation>["t"];
  e: ReturnType<typeof useTranslation>["t"]["expenses"];
  editingId: string | null;
  editDraft: { type: "income" | "expense"; amount: string; category: string; merchant: string; description: string; date: string } | null;
  setEditDraft: (draft: { type: "income" | "expense"; amount: string; category: string; merchant: string; description: string; date: string } | null) => void;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const isEditing = editingId === tx.id;
  const draft = isEditing ? editDraft : null;
  const fmt = (value: number) => formatDemoAmount(value, locale);

  return (
    <li className="rounded-[12px] border border-ink/[0.07] bg-white/70 p-3">
      {isEditing && draft ? (
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_1fr_auto]">
          <select value={draft.type} onChange={(event) => setEditDraft(draft ? { ...draft, type: event.target.value as "income" | "expense" } : null)} className="rounded-[10px] border border-ink/10 bg-cream px-3 py-2 text-[13px] outline-none focus:border-orange-deep">
            <option value="income">{e.typeIncome}</option>
            <option value="expense">{e.typeExpense}</option>
          </select>
          <input type="number" value={draft.amount} onChange={(event) => setEditDraft(draft ? { ...draft, amount: event.target.value } : null)} className="rounded-[10px] border border-ink/10 bg-cream px-3 py-2 text-[13px] outline-none focus:border-orange-deep numbers" />
          <input value={draft.category} onChange={(event) => setEditDraft(draft ? { ...draft, category: event.target.value } : null)} className="rounded-[10px] border border-ink/10 bg-cream px-3 py-2 text-[13px] outline-none focus:border-orange-deep" />
          <input type="date" value={draft.date} onChange={(event) => setEditDraft(draft ? { ...draft, date: event.target.value } : null)} className="rounded-[10px] border border-ink/10 bg-cream px-3 py-2 text-[13px] outline-none focus:border-orange-deep numbers" />
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={() => onEdit(tx.id)} className="rounded-full bg-orange px-3 py-1.5 text-[11px] font-bold text-cream">{e.save}</button>
            <button type="button" onClick={() => setEditDraft(null)} className="rounded-full border border-ink/10 px-3 py-1.5 text-[11px] font-bold text-ink-soft">{e.cancel}</button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {tx.type === "income" ? (
              <ArrowUpRight size={18} className="text-green-600" />
            ) : (
              <ArrowDownLeft size={18} className="text-orange" />
            )}
            <div>
              <p className="text-[13px] font-semibold text-ink">{tx.category || e.expensesLabel}</p>
              <p className="text-[11px] text-ink-soft">
                {tx.merchant || tx.description || t.demo.emptyDescription} - {tx.date}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-[14px] font-bold numbers ${tx.type === "income" ? "text-green-600" : "text-orange"}`}>
              {tx.type === "income" ? "+" : "-"}
              {fmt(tx.amount)}
            </span>
            <span className="flex items-center gap-1.5">
              <button type="button" onClick={() => onEdit(tx.id)} className="rounded-full border border-ink/10 px-3 py-1.5 text-[11px] font-bold text-ink-soft hover:border-orange/30">{e.edit}</button>
              <button type="button" onClick={() => onDelete(tx.id)} className="rounded-full border border-red-200 px-3 py-1.5 text-[11px] font-bold text-red-600 hover:bg-red-50">{e.delete}</button>
            </span>
          </div>
        </div>
      )}
    </li>
  );
}

export function DemoFinancePage() {
  const { t } = useTranslation();
  const locale = useLocale();
  const o = t.overview;
  const e = t.expenses;
  const f = t.finance;
  const state = useDemoState();

  const [metric, setMetric] = useState<ChartMetric>("expenses");
  const [period, setPeriod] = useState<ChartPeriod>(6);
  const [filter, setFilter] = useState<"all" | "income" | "expense">("all");
  const [query, setQuery] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [txType, setTxType] = useState<"income" | "expense">("expense");
  const [txAmount, setTxAmount] = useState("");
  const [txCategory, setTxCategory] = useState("");
  const [txMerchant, setTxMerchant] = useState("");
  const [txDescription, setTxDescription] = useState("");
  const [txDate, setTxDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const transactions: Transaction[] = useMemo(
    () =>
      state.transactions.map((tx) => ({
        id: tx.id,
        user_id: "demo",
        type: tx.type,
        amount_minor: Math.round(tx.amount * 100),
        category: tx.category,
        merchant: tx.merchant,
        description: tx.description,
        date: `${tx.date}T00:00:00`,
        created_at: `${tx.date}T00:00:00`,
      })),
    [state.transactions]
  );

  const totals = useMemo(() => computeDemoTotals(state), [state]);
  const chartData = useMemo(() => buildChartData(transactions, metric, period, locale), [
    transactions,
    metric,
    period,
    locale,
  ]);

  const fmt = (minor: number) => formatDemoAmount(minor / 100, locale);

  const visibleTransactions = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return transactions.filter((tx) => {
      if (filter !== "all" && tx.type !== filter) return false;
      if (!needle) return true;
      return [tx.merchant, tx.category, tx.description].some((value) => value?.toLowerCase().includes(needle));
    });
  }, [transactions, filter, query]);

  function handleAddTransaction() {
    const amount = Number(txAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError(e.amountInvalid);
      return;
    }
    if (txDate && !/^\d{4}-\d{2}-\d{2}$/.test(txDate)) {
      setError(e.dateInvalid);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const { state: next } = addDemoTransaction(state, {
        type: txType,
        amount,
        category: txCategory,
        merchant: txMerchant || undefined,
        description: txDescription || undefined,
        date: txDate,
      });
      commitDemoState(next);
      setTxAmount("");
      setTxCategory("");
      setTxMerchant("");
      setTxDescription("");
      setTxDate("");
      setShowAdd(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-4 text-[13px] font-semibold text-ink-soft">{o.analytics}</p>
          <h1 className="text-balance text-[38px] font-extrabold leading-[1] tracking-[-0.04em] sm:text-[54px]">{e.title}</h1>
          <p className="mt-3 max-w-[560px] text-[15px] leading-relaxed text-ink-soft">{e.subtitle}</p>
        </div>
        <button type="button" onClick={() => setShowAdd(!showAdd)} className="btn-primary px-4 py-2.5 text-[13px]">
          <Plus size={15} /> {e.addTransaction}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-[12px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {showAdd && (
        <AddTransactionForm
          t={t}
          e={e}
          categories={getDemoCategories(locale)}
          saving={saving}
          error={error}
          onSubmit={handleAddTransaction}
          onCancel={() => setShowAdd(false)}
        />
      )}

      <section className="overflow-hidden rounded-[24px] border border-ink/[0.07] bg-white shadow-[0_18px_38px_-32px_rgba(22,20,18,0.5)]">
        <div className="grid gap-px bg-ink/[0.07] sm:grid-cols-2 lg:grid-cols-4">
          <div className="bg-white p-5">
            <p className="text-[13px] font-semibold text-ink-soft">{e.income}</p>
            <p className="mt-3 text-[30px] font-extrabold leading-none tracking-[-0.03em] text-ink numbers">{fmt(totals.income * 100)}</p>
          </div>
          <div className="bg-white p-5">
            <p className="text-[13px] font-semibold text-ink-soft">{e.expensesLabel}</p>
            <p className="mt-3 text-[30px] font-extrabold leading-none tracking-[-0.03em] text-ink numbers">{fmt(totals.expense * 100)}</p>
          </div>
          <div className="bg-white p-5">
            <p className="text-[13px] font-semibold text-ink-soft">{e.netBalance}</p>
            <p className="mt-3 text-[30px] font-extrabold leading-none tracking-[-0.03em] text-ink numbers">{totals.net >= 0 ? "+" : ""}{fmt(totals.net * 100)}</p>
          </div>
          <div className="bg-white p-5">
            <p className="text-[13px] font-semibold text-ink-soft">{e.transactions}</p>
            <p className="mt-3 text-[30px] font-extrabold leading-none tracking-[-0.03em] text-ink numbers">{totals.transactionCount}</p>
          </div>
        </div>
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <section className={panel}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{e.transactions}</h2>
            <div className="flex gap-1.5" role="group" aria-label={e.transactions}>
              {filterOptions.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  data-testid="demo-finance-filter"
                  data-filter={option.key}
                  aria-pressed={filter === option.key}
                  onClick={() => setFilter(option.key)}
                  className={`rounded-full px-3 py-1.5 text-[12px] font-bold transition-colors ${
                    filter === option.key ? "bg-orange-soft text-orange" : "text-ink-soft hover:bg-cream-soft hover:text-ink"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <input
              id="demo-fin-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={f.searchPlaceholder}
              aria-label={f.searchAria}
              className="w-[220px] rounded-full border border-ink/10 bg-cream px-4 py-2 text-[13px] outline-none transition-colors focus:border-orange-deep"
            />
          </div>
          {visibleTransactions.length === 0 ? (
            <p className="mt-6 text-[14px] text-ink-soft">{e.noTransactions}</p>
          ) : (
            <div className="mt-6 space-y-3">
              {visibleTransactions.slice(0, 50).map((tx) => (
                <div key={tx.id} className="flex items-center justify-between border-b border-ink/[0.06] pb-3 text-[13px] last:border-0">
                  <div>
                    <p className="font-semibold">{tx.merchant || tx.category || tx.type}</p>
                    <p className="text-ink-soft">{tx.date ? new Date(tx.date).toLocaleDateString(locale === "ru" ? "ru-RU" : "en-US") : ""}</p>
                  </div>
                  <span className={`font-bold numbers ${tx.type === "income" ? "text-green-600" : "text-orange-dark"}`}>
                    {tx.type === "income" ? "+" : "-"}{fmt(tx.amount_minor)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className={panel}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{f.chartTitle}</h2>
            <div className="flex gap-1.5" role="group" aria-label={f.periodAria}>
              {periodOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  data-testid="demo-finance-period"
                  data-period={String(option.value)}
                  aria-pressed={period === option.value}
                  onClick={() => setPeriod(option.value)}
                  className={`rounded-full px-3 py-1.5 text-[12px] font-bold transition-colors ${
                    period === option.value ? "bg-orange-soft text-orange" : "text-ink-soft hover:bg-cream-soft hover:text-ink"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4 flex gap-1.5" role="group" aria-label={f.metricAria}>
            {metricOptions.map((option) => (
              <button
                key={option.key}
                type="button"
                data-testid="demo-finance-metric"
                data-metric={option.key}
                aria-pressed={metric === option.key}
                onClick={() => setMetric(option.key)}
                className={`rounded-full px-3 py-1.5 text-[12px] font-bold transition-colors ${
                  metric === option.key ? "bg-orange-soft text-orange" : "text-ink-soft hover:bg-cream-soft hover:text-ink"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          {chartData.monthsWithData === 0 ? (
            <div className="mt-6 rounded-[14px] bg-cream-soft px-4 py-8 text-center">
              <p className="text-[13px] font-bold">{f.insufficientHistory}</p>
              <p className="mx-auto mt-2 max-w-[280px] text-[12px] leading-relaxed text-ink-soft">{f.chartEmptyDescription}</p>
            </div>
          ) : (
            <SpendingChart data={chartData} />
          )}
        </section>
      </div>
    </div>
  );
}

export function DemoHistoryPage() {
  const { t } = useTranslation();
  const locale = useLocale();
  const h = t.history;
  const e = t.expenses;
  const state = useDemoState();

  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "income" | "expense">("all");
  const [periodFilter, setPeriodFilter] = useState<"all" | "1" | "3" | "6" | "12">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const transactions = state.transactions;
  const totals = computeDemoTotals(state);
  const fmt = (value: number) => formatDemoAmount(value, locale);

  const visibleTransactions = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const cutoff = periodFilter === "all" ? null : new Date(new Date().setMonth(new Date().getMonth() - Number(periodFilter)));
    return transactions
      .filter((tx) => {
        if (typeFilter !== "all" && tx.type !== typeFilter) return false;
        if (cutoff && new Date(tx.date) < cutoff) return false;
        if (!needle) return true;
        return [tx.category, tx.merchant, tx.description].some((value) => value?.toLowerCase().includes(needle));
      })
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [transactions, typeFilter, query, periodFilter]);

  const monthGroups = useMemo(() => {
    const byMonth = new Map<string, { label: string; entries: typeof visibleTransactions }>();
    for (const tx of visibleTransactions) {
      const date = new Date(tx.date);
      const key = `${date.getFullYear()}-${date.getMonth()}`;
      const bucket = byMonth.get(key);
      if (bucket) {
        bucket.entries.push(tx);
      } else {
        const label = new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", {
          month: "long",
          year: "numeric",
        }).format(date);
        byMonth.set(key, { label, entries: [tx] });
      }
    }
    return Array.from(byMonth.entries())
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([, group]) => ({ label: group.label, entries: group.entries }));
  }, [visibleTransactions, locale]);

  const selected = visibleTransactions.find((tx) => tx.id === selectedId) ?? visibleTransactions[0] ?? null;

  const typeOptions: Array<{ id: "all" | "income" | "expense"; label: string }> = [
    { id: "all", label: h.typeAll },
    { id: "income", label: h.typeIncome },
    { id: "expense", label: h.typeExpense },
  ];

  const periodOptions: Array<{ id: "all" | "1" | "3" | "6" | "12"; label: string }> = [
    { id: "all", label: h.allPeriods },
    { id: "1", label: h.lastMonth },
    { id: "3", label: h.last3Months },
    { id: "6", label: h.last6Months },
    { id: "12", label: h.last12Months },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-4 text-[13px] font-semibold text-ink-soft">{h.eyebrow}</p>
          <h1 className="text-balance text-[38px] font-extrabold leading-[1] tracking-[-0.04em] sm:text-[54px]">{h.title}</h1>
          <p className="mt-3 max-w-[560px] text-[15px] leading-relaxed text-ink-soft">{h.readOnlyNote}</p>
        </div>
      </div>

      <section className={panel}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={h.searchPlaceholder}
              aria-label={h.searchPlaceholder}
              className="w-full rounded-[12px] border border-ink/[0.12] bg-cream py-2.5 pl-9 pr-3 text-[14px] outline-none transition-colors focus:border-orange-deep"
            />
          </div>
          <div className="relative sm:w-[220px]">
            <Calendar size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft" />
            <select
              value={periodFilter}
              onChange={(event) => setPeriodFilter(event.target.value as "all" | "1" | "3" | "6" | "12")}
              aria-label={h.period}
              className="w-full appearance-none rounded-[12px] border border-ink/[0.12] bg-cream py-2.5 pl-9 pr-8 text-[13px] font-semibold outline-none transition-colors focus:border-orange-deep"
            >
              {periodOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
            <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-soft" />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2" role="group" aria-label={h.filterByType}>
          {typeOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              aria-pressed={typeFilter === option.id}
              onClick={() => setTypeFilter(option.id)}
              className={`rounded-full px-3.5 py-1.5 text-[12.5px] font-bold transition-colors ${
                typeFilter === option.id ? "bg-orange text-white" : "bg-cream text-ink-soft hover:bg-cream-soft hover:text-ink"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      {visibleTransactions.length === 0 ? (
        <section className={panel}>
          <h2 className="text-[18px] font-bold">{h.emptyTitle}</h2>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">{h.emptyDescription}</p>
        </section>
      ) : (
        <>
          <section className={panel}>
            <div className="grid gap-px bg-ink/[0.07] sm:grid-cols-2 lg:grid-cols-4">
              <div className="bg-white p-5">
                <p className="text-[13px] font-semibold text-ink-soft">{h.summaryIncome}</p>
                <p className="mt-3 text-[30px] font-extrabold leading-none tracking-[-0.03em] text-ink numbers">
                  +{fmt(totals.income)}
                </p>
              </div>
              <div className="bg-white p-5">
                <p className="text-[13px] font-semibold text-ink-soft">{h.summaryExpense}</p>
                <p className="mt-3 text-[30px] font-extrabold leading-none tracking-[-0.03em] text-ink numbers">
                  {fmt(totals.expense)}
                </p>
              </div>
              <div className="bg-white p-5">
                <p className="text-[13px] font-semibold text-ink-soft">{h.summaryNet}</p>
                <p className="mt-3 text-[30px] font-extrabold leading-none tracking-[-0.03em] text-ink numbers">
                  {totals.net >= 0 ? "+" : ""}{fmt(totals.net)}
                </p>
              </div>
              <div className="bg-white p-5">
                <p className="text-[13px] font-semibold text-ink-soft">{h.transactions}</p>
                <p className="mt-3 text-[30px] font-extrabold leading-none tracking-[-0.03em] text-ink numbers">
                  {totals.transactionCount}
                </p>
              </div>
            </div>
          </section>

          <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] gap-6">
            <section className={panel}>
              <div className="mt-4 space-y-3">
                {monthGroups.map((group) => (
                  <div key={group.label}>
                    <h3 className="text-[13px] font-extrabold text-ink-soft tracking-tight mb-2">{group.label}</h3>
                    <div className="space-y-2">
                      {group.entries.map((tx) => {
                        const badge =
                          tx.type === "income"
                            ? { label: h.incomeBadge, tone: "bg-green-100 text-green-700" }
                            : { label: h.expenseBadge, tone: "bg-ink/10 text-ink-soft" };
                        return (
                          <div
                            key={tx.id}
                            onClick={() => setSelectedId(selectedId === tx.id ? null : tx.id)}
                            className={`flex items-center justify-between border-b border-ink/[0.06] pb-3 px-2 last:border-0 cursor-pointer hover:bg-cream/30 rounded-[8px] transition-colors ${
                              selectedId === tx.id ? "bg-orange/10" : ""
                            }`}
                            role="button"
                            tabIndex={0}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                setSelectedId(selectedId === tx.id ? null : tx.id);
                              }
                            }}
                          >
                            <div>
                              <p className="font-semibold">{tx.merchant || getCategoryLabel(tx.category, locale) || tx.type}</p>
                              <p className="text-[12px] text-ink-soft">
                                {new Date(tx.date).toLocaleDateString(locale === "ru" ? "ru-RU" : "en-US")}
                              </p>
                            </div>
                            <span className={`font-bold numbers ${tx.type === "income" ? "text-green-600" : "text-orange-dark"}`}>
                              {tx.type === "income" ? "+" : "-"}{fmt(tx.amount)}
                            </span>
                            <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-bold ${badge.tone}`}>
                              {badge.label}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </section>
            <section className={panel}>
              {selected ? (
                <div className="space-y-4">
                  <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{h.detailsTitle}</h2>
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-4 rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
                      <div className="flex flex-col gap-1">
                        <p className="text-[12px] font-semibold text-ink-soft">{h.type}</p>
                        <p className="font-bold">{selected.type === "income" ? h.incomeBadge : h.expenseBadge}</p>
                      </div>
                      <span className={`font-bold text-[20px] numbers ${selected.type === "income" ? "text-green-600" : "text-orange-dark"}`}>
                        {selected.type === "income" ? "+" : "-"}{fmt(selected.amount)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
                      <p className="text-[12px] font-semibold text-ink-soft">{h.date}</p>
                      <p className="text-ink-soft">{new Date(selected.date).toLocaleDateString(locale === "ru" ? "ru-RU" : "en-US")}</p>
                    </div>
                    {selected.category && (
                      <div className="flex items-center justify-between rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
                        <p className="text-[12px] font-semibold text-ink-soft">{h.category}</p>
                        <p className="text-ink-soft">{getCategoryLabel(selected.category, locale)}</p>
                      </div>
                    )}
                    {selected.merchant && (
                      <div className="flex items-center justify-between rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
                        <p className="text-[12px] font-semibold text-ink-soft">{h.merchantLabel}</p>
                        <p className="text-ink-soft">{selected.merchant}</p>
                      </div>
                    )}
                    {selected.description && (
                      <div className="flex items-center justify-between rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
                        <p className="text-[12px] font-semibold text-ink-soft">{h.description}</p>
                        <p className="text-ink-soft">{selected.description}</p>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center rounded-[16px] border border-dashed border-ink/[0.1] bg-cream/30">
                  <p className="text-[14px] leading-relaxed text-ink-soft">{h.detailsEmpty}</p>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

type DemoDecision = ReturnType<typeof buildDemoDecision>;

export function DemoAiPage() {
  const { t } = useTranslation();
  const locale = useLocale();
  const o = t.overview;
  const ai = t.ai;
  const state = useDemoState();

  const overview = useMemo(() => buildDemoOverview(state), [state]);
  const [amount, setAmount] = useState(() =>
    Math.min(state.available, Math.max(0, overview.comfortableWithdrawal)),
  );
  const [decision, setDecision] = useState<DemoDecision | null>(null);

  const fmt = (value: number) => formatDemoAmount(value, locale);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-4 text-[13px] font-semibold text-ink-soft">{ai.advisorEyebrow}</p>
          <h1 className="text-balance text-[38px] font-extrabold leading-[1] tracking-[-0.04em] sm:text-[54px]">{ai.title}</h1>
          <p className="mt-3 max-w-[560px] text-[15px] leading-relaxed text-ink-soft">
            {ai.personalAdviceBody}
          </p>
        </div>
      </div>

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
            {t.demo.planUpcomingBills}: {fmt(overview.upcomingBillsTotal)} - {t.demo.planReserveTarget}:{" "}
            {fmt(overview.reserveTarget)}
          </>
        }
        whyHref="/demo/ai"
        getMoneyHref="/demo/get-money"
        whatIfHref="/demo/what-if"
      />

      <section className={panel}>
        <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{ai.keyFactsTitle}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
            <p className="text-[12px] font-semibold text-ink-soft">{ai.factAvailable}</p>
            <p className="mt-1 font-bold numbers text-ink">{fmt(state.available)}</p>
          </div>
          <div className="rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
            <p className="text-[12px] font-semibold text-ink-soft">{ai.factMaxRequestable}</p>
            <p className="mt-1 font-bold numbers text-ink">{fmt(state.available)}</p>
          </div>
          <div className="rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
            <p className="text-[12px] font-semibold text-ink-soft">{t.demo.upcomingBills}</p>
            <p className="mt-1 font-bold numbers text-ink">{fmt(overview.upcomingBillsTotal)}</p>
          </div>
        </div>
        <p className="mt-4 text-[13px] leading-relaxed text-ink-soft">
          {ai.educativeNote}
        </p>
      </section>
    </div>
  );
}

export function DemoWhatIfPage() {
  const { t } = useTranslation();
  const locale = useLocale();
  const w = t.whatIfPage;
  const d = t.demo;
  const state = useDemoState();

  const [amount, setAmount] = useState(() => Math.min(state.available, demoRecommendedAmount(state)));
  const scenario = evaluateDemoScenario(state, amount);
  const savings = computeDemoSavings(state);
  const upcomingTotal = computeUpcomingTotal();
  const bills = upcomingBills(locale);
  const fmt = (value: number) => formatDemoAmount(value, locale);

  const statusLabel =
    scenario.status === "comfortable" ? d.comfortable : scenario.status === "caution" ? d.caution : d.highRisk;
  const statusTone =
    scenario.status === "comfortable" ? "bg-green-100 text-green-700" : scenario.status === "caution" ? "bg-orange-soft text-orange-dark" : "bg-red-100 text-red-600";

  const presets = [30000, 50000, 60000, 100000].filter((value) => value <= state.available);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-4 text-[13px] font-semibold text-ink-soft">{w.eyebrow}</p>
          <h1 className="text-balance text-[38px] font-extrabold leading-[1] tracking-[-0.04em] sm:text-[54px]">{w.title}</h1>
          <p className="mt-3 max-w-[560px] text-[15px] leading-relaxed text-ink-soft">{w.subtitle}</p>
        </div>
      </div>

      <section className={panel}>
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <label className="text-[13px] font-semibold text-ink-soft">{w.selectorTitle}</label>
            <span className="text-[13px] font-bold numbers text-ink">{fmt(amount)}</span>
          </div>
          <input
            type="range"
            min="0"
            max={state.available}
            value={amount}
            step={5000}
            onChange={(event) => setAmount(Number(event.target.value))}
            aria-label={w.sliderAria}
            className="w-full h-2 bg-ink/10 rounded-lg appearance-none cursor-pointer accent-orange"
          />
          <div className="flex justify-between text-[12px] text-ink-soft">
            <span>0</span>
            <span>{fmt(state.available)}</span>
          </div>
        </div>
      </section>

      <section className={panel}>
        <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{w.selectedTitle}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
            <p className="text-[12px] font-semibold text-ink-soft">{w.availableNow}</p>
            <p className="mt-1 font-bold numbers text-ink">{fmt(state.available)}</p>
          </div>
          <div className="rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
            <p className="text-[12px] font-semibold text-ink-soft">{w.remainingAvailable}</p>
            <p className="mt-1 font-bold numbers text-ink">{fmt(scenario.availableAfter)}</p>
          </div>
          <div className="rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
            <p className="text-[12px] font-semibold text-ink-soft">{w.shareOfEarned}</p>
            <p className="mt-1 font-bold numbers text-ink">
              {(scenario.shareOfEarned * 100).toFixed(0)}%
            </p>
          </div>
          <div className="rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
            <p className="text-[12px] font-semibold text-ink-soft">{w.slotsLeft}</p>
            <p className="mt-1 font-bold numbers text-ink">?</p>
          </div>
        </div>

        <div className="mt-6 rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-bold ${statusTone}`}>
              {statusLabel}
            </span>
            <span className="text-[12px] font-bold text-ink">{fmt(scenario.bufferAfter)}</span>
          </div>
          <p className="text-[13px] leading-relaxed text-ink-soft">{w.scenarioNote}</p>
        </div>
      </section>

      <section className={panel}>
        <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{w.comparisonTitle}</h2>
        <div className="mt-4 space-y-3">
          {presets.map((value) => {
            const s = evaluateDemoScenario(state, value);
            const isSelected = value === amount;
            const st =
              s.status === "comfortable" ? d.comfortable : s.status === "caution" ? d.caution : d.highRisk;
            return (
              <div
                key={value}
                className={`flex items-center justify-between border border-ink/[0.06] rounded-[12px] p-3 transition-colors ${
                  isSelected ? "bg-orange-soft border-orange/30" : "hover:bg-cream-soft"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={`font-bold numbers ${isSelected ? "text-orange" : "text-ink"}`}>{fmt(value)}</span>
                  <span className="text-[12px] text-ink-soft">{w.remainingAvailable}</span>
                </div>
                <div className="text-right">
                  <p className="font-bold numbers text-ink">{fmt(s.availableAfter)}</p>
                  <span className={`text-[11px] font-bold ${statusTone}`}>{st}</span>
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-4 text-[13px] leading-relaxed text-ink-soft">{w.honestyNote}</p>
      </section>

      <section className={panel}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-[16px] font-extrabold tracking-[-0.02em]">{d.whatIf}</h2>
            <p className="mt-1 text-[13px] text-ink-soft">{d.whatIfHint}</p>
          </div>
          <Link
            href="/demo/get-money"
            className="inline-flex items-center gap-1.5 rounded-full border border-orange/40 px-4 py-2 text-[12px] font-bold text-orange-dark transition-colors hover:border-orange hover:bg-white/50"
          >
            Get money: <ArrowRight size={13} />
          </Link>
        </div>
      </section>
    </div>
  );
}

export function DemoGetMoneyPage() {
  const { t } = useTranslation();
  const locale = useLocale();
  const d = t.demo;
  const w = t.withdraw;
  const state = useDemoState();

  const [amount, setAmount] = useState(() => Math.min(state.available, demoRecommendedAmount(state)));
  const [flowStep, setFlowStep] = useState<string>("amount");
  const scenario = evaluateDemoScenario(state, amount);
  const savings = computeDemoSavings(state);
  const upcomingTotal = computeUpcomingTotal();
  const fmt = (value: number) => formatDemoAmount(value, locale);

  const presets = [10000, 30000, 50000, 60000, 100000].filter((value) => value <= state.available);
  const requestable = amount > 0 && amount <= state.available && scenario.bufferAfter >= 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-4 text-[13px] font-semibold text-ink-soft">{d.earnings}</p>
          <h1 className="text-balance text-[38px] font-extrabold leading-[1] tracking[-0.04em] sm:text-[54px]">{d.title}</h1>
          <p className="mt-3 max-w-[560px] text-[15px] leading-relaxed text-ink-soft">
            {d.subtitle}
          </p>
        </div>
      </div>

      <section className={panel}>
        <div className="grid gap-px bg-ink/[0.07] sm:grid-cols-2 lg:grid-cols-4">
          <div className="bg-white p-5">
            <p className="text-[13px] font-semibold text-ink-soft">{d.available}</p>
            <p className="mt-3 text-[30px] font-extrabold leading-none tracking[-0.03em] text-ink numbers">{fmt(state.available)}</p>
          </div>
          <div className="bg-white p-5">
            <p className="text-[13px] font-semibold text-ink-soft">{d.earnedThisPeriod}</p>
            <p className="mt-3 text-[30px] font-extrabold leading-none tracking[-0.03em] text-ink numbers">{fmt(state.earned)}</p>
          </div>
          <div className="bg-white p-5">
            <p className="text-[13px] font-semibold text-ink-soft">{d.salary}</p>
            <p className="mt-3 text-[30px] font-extrabold leading-none tracking[-0.03em] text-ink numbers">{fmt(state.salary)}</p>
          </div>
          <div className="bg-white p-5">
            <p className="text-[13px] font-semibold text-ink-soft">{d.reserve}</p>
            <p className="mt-3 text-[30px] font-extrabold leading-none tracking[-0.03em] text-ink numbers">{fmt(state.reserveTarget)}</p>
          </div>
        </div>
      </section>

      {flowStep === "amount" ? (
        <section className={panel}>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <label className="text-[13px] font-semibold text-ink-soft">{d.amount}</label>
              <span className="text-[13px] font-bold numbers text-ink">{fmt(amount)}</span>
            </div>
            {amount <= 0 && (
              <div className="flex items-center gap-2 rounded-[12px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
                <AlertCircle size={16} /> {w.errorZeroOrNegative}
              </div>
            )}
            <input
              type="range"
              min="0"
              max={state.available}
              value={amount}
              step={5000}
              onChange={(event) => setAmount(Number(event.target.value))}
              aria-label={d.scenarioAmount}
              disabled={flowStep !== "amount"}
              className="w-full h-2 bg-ink/10 rounded-lg appearance-none cursor-pointer accent-orange"
            />
            <div className="flex justify-between text-[12px] text-ink-soft">
              <span>0</span>
              <span>{fmt(state.available)}</span>
            </div>
            <div className="mt-3 flex gap-2 flex-wrap">
              {presets.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setAmount(value)}
                  className={`rounded-full px-3 py-1.5 text-[12px] font-bold transition-colors ${
                    amount === value ? "bg-orange-soft text-orange" : "text-ink-soft hover:bg-cream-soft hover:text-ink"
                  }`}
                >
                  {fmt(value)}
                </button>
              ))}
            </div>
            <div className="mt-4 rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold text-ink-soft">{d.upcomingBills}</span>
                <span className="text-[12px] text-ink-soft">-{fmt(upcomingTotal)}</span>
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[12px] font-semibold text-ink-soft">{d.reserve}</span>
                <span className="text-[12px] text-ink-soft">-{fmt(savings.target)}</span>
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className={`text-[12px] font-bold ${requestable ? "text-green-600" : "text-red-600"}`}>
                  {requestable ? d.upTo.replace("{amount}", fmt(scenario.availableAfter)) : d.caution}
                </span>
              </div>
            </div>
            <div className="mt-6">
              <button
                type="button"
                disabled={!requestable}
                onClick={() => setFlowStep("confirm")}
                className={`w-full rounded-[12px] px-4 py-3 text-[14px] font-bold transition-colors ${
                  requestable
                    ? "bg-orange text-white hover:bg-orange/90"
                    : "bg-ink/[0.05] text-ink-soft cursor-not-allowed"
                }`}
              >
                {requestable ? `Confirm withdrawal of ${fmt(amount)}` : d.amount}
              </button>
            </div>
          </div>
        </section>
      ) : (
        <section className={panel}>
          <div className="space-y-4">
            <h2 className="text-[16px] font-extrabold tracking[-0.02em]">Confirm withdrawal</h2>
            <p className="text-[14px] text-ink-soft">
              You will receive <span className="font-bold numbers">{fmt(amount)}</span> directly to your card.
            </p>
            <div className="rounded-[12px] border border-ink/[0.08] bg-white/50 p-4">
              <div className="flex items-center justify-between text-[13px]">
                <span className="text-ink-soft">Withdrawal amount</span>
                <span className="font-bold numbers text-ink">{fmt(amount)}</span>
              </div>
              <div className="flex items-center justify-between text-[13px]">
                <span className="text-ink-soft">Available after withdrawal</span>
                <span className="font-bold numbers text-ink">{fmt(scenario.availableAfter)}</span>
              </div>
              <div className="flex items-center justify-between text-[13px]">
                <span className="text-ink-soft">Buffer after upcoming bills</span>
                <span className={`font-bold numbers ${scenario.bufferAfter >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {fmt(scenario.bufferAfter)}
                </span>
              </div>
            </div>
            <p className="text-[13px] leading-relaxed text-ink-soft">
              This is a demo action: no real money moves and no request is sent to a server. Use{" "}
              <Link href="/demo/what-if" className="text-orange-dark font-semibold hover:underline">
                What if
              </Link>
              to explore scenarios first.
            </p>
            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => setFlowStep("amount")}
                className="rounded-[12px] px-4 py-3 text-[14px] font-bold text-ink-soft bg-ink/[0.05] hover:bg-ink/[0.1] transition-colors"
              >
                Back
              </button>
              <button
                type="button"
                disabled={!requestable}
                onClick={() => {
                  setFlowStep("amount");
                }}
                className={`w-full rounded-[12px] px-4 py-3 text-[14px] font-bold transition-colors ${
                  requestable
                    ? "bg-orange text-white hover:bg-orange/90"
                    : "bg-ink/[0.05] text-ink-soft cursor-not-allowed"
                }`}
              >
                Confirm demo withdrawal
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
