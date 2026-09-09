"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, CircleDollarSign, Plus, Search, Send, Sparkles, TrendingDown, TrendingUp, AlertCircle, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, Transaction, FinanceSummary, EarnedWages, WageAccessRequest, WithdrawalAnalysis } from "@/lib/api";

const panel = "rounded-[16px] border border-ink/[0.07] bg-white/70 p-5 shadow-[0_18px_38px_-32px_rgba(22,20,18,0.5)]";

function formatTenge(value: number) {
  return value.toLocaleString("en-US");
}

function PageFrame({ eyebrow, title, copy, children }: { eyebrow: string; title: string; copy: string; children: React.ReactNode }) {
  return <div>
    <div className="mb-10 max-w-[680px]">
      <p className="eyebrow mb-4">{eyebrow}</p>
      <h1 className="text-balance text-[40px] font-extrabold leading-[1] tracking-[-0.04em] sm:text-[58px]">{title}</h1>
      <p className="mt-4 text-[16px] leading-relaxed text-ink-soft">{copy}</p>
    </div>
    {children}
  </div>;
}

function Metric({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return <div className={panel}>
    <div className="flex items-center justify-between text-green-deep">
      <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-ink-soft">{label}</p>
      {icon}
    </div>
    <p className="mt-5 text-[28px] font-extrabold tracking-tight numbers">{value}</p>
  </div>;
}

function EmptyState({ title, description, actionLabel, actionHref, onAction }: { title: string; description: string; actionLabel?: string; actionHref?: string; onAction?: () => void; }) {
  return (
    <div className={`${panel} flex flex-col items-start justify-between gap-4`}>
      <div>
        <h2 className="text-[18px] font-bold">{title}</h2>
        <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">{description}</p>
      </div>
      {actionLabel && (actionHref || onAction) && (
        actionHref ? (
          <Link href={actionHref} className="inline-flex items-center gap-2 text-[13px] font-bold text-orange-dark">
            <Plus size={15} /> {actionLabel}
          </Link>
        ) : (
          <button onClick={onAction} className="inline-flex items-center gap-2 text-[13px] font-bold text-orange-dark">
            <Plus size={15} /> {actionLabel}
          </button>
        )
      )}
    </div>
  );
}

export function FinancePage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [txType, setTxType] = useState<"income" | "expense">("expense");
  const [txAmount, setTxAmount] = useState("");
  const [txCategory, setTxCategory] = useState("");
  const [txMerchant, setTxMerchant] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    try {
      const [txns, summaryData] = await Promise.all([
        api.finance.getTransactions(),
        api.finance.getSummary().catch(() => null),
      ]);
      setTransactions(txns);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load financial data. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleAddTransaction() {
    const amount = Number(txAmount);
    if (!amount || amount <= 0) return;
    setSaving(true);
    setError(null);
    try {
      await api.finance.createTransaction({
        type: txType,
        amount_minor: amount,
        category: txCategory || undefined,
        merchant: txMerchant || undefined,
      });
      setTxAmount("");
      setTxCategory("");
      setTxMerchant("");
      setShowAdd(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save transaction. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const income = summary?.total_income_minor || 0;
  const expense = summary?.total_expense_minor || 0;

  if (loading) {
    return <PageFrame eyebrow="Finance" title="See the money in context." copy="Loading your financial data...">
      <div className="flex h-40 items-center justify-center"><Loader2 className="animate-spin text-green-deep" size={24} /></div>
    </PageFrame>;
  }

  return <PageFrame eyebrow="Finance" title="See the money in context." copy="Track income, expenses and net balance in one place.">
    {error && <div className="mb-4 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700 flex items-center gap-2"><AlertCircle size={16} />{error}</div>}
    <div className="grid gap-5 md:grid-cols-3">
      <Metric label="Income" value={income ? `${formatTenge(income)} ₸` : "—"} icon={<TrendingUp />} />
      <Metric label="Expenses" value={expense ? `${formatTenge(expense)} ₸` : "—"} icon={<TrendingDown />} />
      <Metric label="Net Balance" value={summary ? `${formatTenge(summary.net_balance_minor)} ₸` : "—"} icon={<CircleDollarSign />} />
    </div>

    <div className="mt-5 grid gap-5 lg:grid-cols-1">
      <section className={panel}>
        <div className="flex items-center justify-between">
          <h2 className="text-[18px] font-bold">Transactions</h2>
          <button onClick={() => setShowAdd(!showAdd)} className="btn-primary px-3 py-2 text-[12px]">
            <Plus size={14} /> Add
          </button>
        </div>
        {showAdd && (
          <div className="mt-4 space-y-3">
            <div className="flex gap-2">
              <button onClick={() => setTxType("income")} className={`flex-1 rounded-[10px] border px-3 py-2 text-[13px] font-semibold transition-colors ${txType === "income" ? "border-green bg-green-soft text-green-deep" : "border-ink/10 hover:border-green/30"}`}>Income</button>
              <button onClick={() => setTxType("expense")} className={`flex-1 rounded-[10px] border px-3 py-2 text-[13px] font-semibold transition-colors ${txType === "expense" ? "border-orange bg-orange-soft text-orange-dark" : "border-ink/10 hover:border-orange/30"}`}>Expense</button>
            </div>
            <input type="number" value={txAmount} onChange={(e) => setTxAmount(e.target.value)} placeholder="Amount (₸)" aria-label="Amount" className="w-full rounded-[10px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-green-deep numbers" />
            <input value={txCategory} onChange={(e) => setTxCategory(e.target.value)} placeholder="Category (optional)" aria-label="Category" className="w-full rounded-[10px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-green-deep" />
            <input value={txMerchant} onChange={(e) => setTxMerchant(e.target.value)} placeholder="Description (optional)" aria-label="Description" className="w-full rounded-[10px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-green-deep" />
            <button onClick={handleAddTransaction} disabled={saving || !txAmount} className="btn-primary w-full justify-center disabled:opacity-50">
              {saving ? "Saving..." : "Save transaction"}
            </button>
          </div>
        )}
        {transactions.length === 0 ? (
          <p className="mt-6 text-[14px] text-ink-soft">No transactions yet. Add your first income or expense above.</p>
        ) : (
          <div className="mt-6 space-y-3">
            {transactions.slice(0, 20).map((item) => (
              <div key={item.id} className="flex items-center justify-between border-b border-ink/[0.06] pb-3 text-[13px] last:border-0">
                <div>
                  <p className="font-semibold">{item.merchant || item.category || item.type}</p>
                  <p className="text-ink-soft">{item.date ? new Date(item.date).toLocaleDateString() : ""}</p>
                </div>
                <span className={`font-bold numbers ${item.type === "income" ? "text-green" : "text-orange-dark"}`}>
                  {item.type === "income" ? "+" : "-"}{formatTenge(item.amount_minor)} ₸
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  </PageFrame>;
}

export function AIPage() {
  const [earned, setEarned] = useState<EarnedWages | null>(null);
  const [withdrawalAmount, setWithdrawalAmount] = useState("");
  const [analysis, setAnalysis] = useState<WithdrawalAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [message, setMessage] = useState("");
  const [chatHistory, setChatHistory] = useState<Array<{ from: "you" | "arqau"; text: string }>>([]);
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const [chatDisabled, setChatDisabled] = useState(false);

  async function loadEarned() {
    try {
      const data = await api.ewa.getEarned();
      setEarned(data);
    } catch {
      setEarned(null);
    }
  }

  useEffect(() => {
    loadEarned();
  }, []);

  async function handleAnalyze() {
    const amount = Number(withdrawalAmount);
    if (!amount || amount <= 0) {
      setAnalysisError("Enter a valid amount to analyze.");
      return;
    }
    if (earned && amount > earned.available_amount_minor) {
      setAnalysisError(`Amount exceeds available (${formatTenge(earned.available_amount_minor)} ₸)`);
      return;
    }
    setAnalyzing(true);
    setAnalysisError("");
    try {
      const result = await api.ai.analyzeWithdrawal(amount);
      setAnalysis(result);
    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : "Analysis failed. Please try again.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleChat(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim() || sending) return;
    const userMsg = message.trim();
    setMessage("");
    setChatHistory((h) => [...h, { from: "you", text: userMsg }]);
    setSending(true);
    setChatError("");
    setChatDisabled(true);
    try {
      const result = await api.ai.chat(userMsg);
      setChatHistory((h) => [...h, { from: "arqau", text: result.response }]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Chat failed";
      setChatError(msg);
      setChatHistory((h) => h.slice(0, -1));
    } finally {
      setSending(false);
      setChatDisabled(false);
    }
  }

  async function handleRetryChat() {
    if (!message.trim() || sending) return;
    setChatError("");
    setSending(true);
    setChatDisabled(true);
    try {
      const result = await api.ai.chat(message.trim());
      setChatHistory((h) => [...h, { from: "arqau", text: result.response }]);
      setMessage("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Chat failed";
      setChatError(msg);
    } finally {
      setSending(false);
      setChatDisabled(false);
    }
  }

  const contextualPrompts = useMemo(() => {
    if (!earned || earned.available_amount_minor === 0) {
      return [
        "How much should I take today?",
        "Will my upcoming bills be covered?",
        "How can I build a small reserve?",
        "What if I take a larger amount?",
      ];
    }
    const available = formatTenge(earned.available_amount_minor);
    const half = Math.floor(earned.available_amount_minor / 2);
    return [
      `What happens if I withdraw ${formatTenge(half)}?`,
      `Should I access ${available} now?`,
      "How do I protect my reserve?",
      "What amount covers my bills?",
    ];
  }, [earned]);

  return <PageFrame eyebrow="ARQAU assistant" title="Explore your financial context." copy="Understand your earned income, expenses and withdrawal options with ARQAU analysis.">
    <div className="grid gap-5 lg:grid-cols-[1fr_0.35fr]">
      <section className={`${panel} max-w-[760px]`}>
        <h2 className="mb-4 text-[16px] font-bold">Withdrawal analysis</h2>
        {earned && (
          <div className="mb-4 rounded-[12px] bg-green-soft px-4 py-3 text-[13px] text-ink-soft">
            Available to access: <span className="font-bold text-green-deep numbers">{formatTenge(earned.available_amount_minor)} ₸</span>
          </div>
        )}
        <div className="flex gap-2">
          <input
            type="number"
            value={withdrawalAmount}
            onChange={(e) => { setWithdrawalAmount(e.target.value); setAnalysis(null); setAnalysisError(""); }}
            placeholder="Enter amount to analyze (₸)"
            aria-label="Withdrawal amount"
            className="min-w-0 flex-1 rounded-[10px] border border-ink/[0.1] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-green-deep numbers"
          />
          <button onClick={handleAnalyze} disabled={analyzing} className="btn-primary px-4">
            {analyzing ? <Loader2 className="animate-spin" size={16} /> : "Analyze"}
          </button>
        </div>
        {analyzing && (
          <div className="mt-4 flex items-center gap-2 rounded-[12px] border border-ink/[0.08] bg-cream px-4 py-3 text-[13px] text-ink-soft">
            <Loader2 className="animate-spin text-green-deep" size={16} />
            Analyzing your financial context...
          </div>
        )}
        {analysisError && (
          <div className="mt-3 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {analysisError}
          </div>
        )}
        {analysis && !analyzing && (
          <div className="mt-4 space-y-3 rounded-[12px] border border-ink/[0.08] bg-cream p-4">
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-ink-soft">Risk level</span>
              <span className={`text-[13px] font-bold ${analysis.risk_level === "low" ? "text-green" : analysis.risk_level === "medium" ? "text-yellow-600" : "text-red-600"}`}>
                {analysis.risk_level.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-ink-soft">Recommendation</span>
              <span className="text-[13px] font-bold capitalize">{analysis.recommendation.replace(/_/g, " ")}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-ink-soft">Remaining after withdrawal</span>
              <span className="text-[13px] font-bold numbers">{formatTenge(analysis.remaining_amount)} ₸</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-ink-soft">Reserve status</span>
              <span className="text-[13px] font-bold capitalize">{analysis.reserve_status}</span>
            </div>
            <div className="border-t border-ink/[0.08] pt-3">
              <p className="text-[13px] leading-relaxed text-ink-soft">{analysis.explanation}</p>
            </div>
            <p className="text-[11px] text-ink-soft italic">{analysis.disclaimer}</p>
          </div>
        )}
      </section>
      <aside className="rounded-[20px] border border-green/20 bg-green-soft p-5">
        <div className="flex items-center gap-2 text-green-deep"><Sparkles size={18} /><h2 className="font-bold">Suggested questions</h2></div>
        <p className="mt-2 text-[12px] text-ink-soft">Tap a question to ask ARQAU</p>
        <div className="mt-4 space-y-2">
          {contextualPrompts.map((prompt) => (
            <button key={prompt} onClick={() => { setMessage(prompt); }} className="w-full rounded-[10px] border border-green/20 bg-cream px-3 py-2.5 text-left text-[13px] font-semibold text-green-deep transition-colors hover:bg-green hover:text-cream">
              {prompt}
            </button>
          ))}
        </div>
      </aside>
    </div>
    <section className={`${panel} mt-5 max-w-[760px]`}>
      <h2 className="mb-4 text-[16px] font-bold">Ask about your finances</h2>
      {chatError && (
        <div className="mb-3 rounded-[10px] border border-yellow-200 bg-yellow-50 px-4 py-3 text-[13px] text-yellow-800 flex items-center justify-between gap-3">
          <span>AI assistant is temporarily unavailable. Withdrawal analysis is still available above.</span>
          <button onClick={handleRetryChat} disabled={sending || chatDisabled || !message.trim()} className="shrink-0 rounded-[8px] border border-yellow-300 bg-yellow-100 px-3 py-1.5 text-[12px] font-bold text-yellow-900 transition-colors hover:bg-yellow-200 disabled:opacity-50">
            Retry
          </button>
        </div>
      )}
      <div className="max-h-[320px] space-y-3 overflow-y-auto">
        {chatHistory.length === 0 && !chatDisabled && (
          <p className="text-[13px] text-ink-soft">Ask questions about your financial context...</p>
        )}
        {chatHistory.map((item, i) => (
          <div key={i} className={`max-w-[82%] rounded-[16px] px-4 py-3 text-[14px] leading-relaxed ${item.from === "you" ? "ml-auto bg-ink text-cream" : "bg-green-soft text-ink"}`}>
            {item.text}
          </div>
        ))}
        {chatDisabled && sending && chatHistory.length > 0 && (
          <div className="max-w-[82%] rounded-[16px] bg-green-soft px-4 py-3 text-[14px] leading-relaxed">
            <span className="inline-flex items-center gap-2 text-ink-soft"><Loader2 className="animate-spin" size={14} /> Analyzing your financial context...</span>
          </div>
        )}
      </div>
      <form className="mt-4 flex gap-2 border-t border-ink/[0.08] pt-4" onSubmit={handleChat}>
        <input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask about your finances..." aria-label="Ask about your finances" className="min-w-0 flex-1 rounded-[10px] border border-ink/[0.1] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-green-deep" disabled={sending || chatDisabled} />
        <button className="btn-primary px-4" type="submit" disabled={sending || chatDisabled || !message.trim()}>
          {sending ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />}
        </button>
      </form>
    </section>
  </PageFrame>;
}

export function GetMoneyPage() {
  const [earned, setEarned] = useState<EarnedWages | null>(null);
  const [requests, setRequests] = useState<WageAccessRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    try {
      const [earnedData, requestsData] = await Promise.all([
        api.ewa.getEarned().catch(() => null),
        api.ewa.getRequests().catch(() => []),
      ]);
      setEarned(earnedData);
      setRequests(requestsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load earned wages. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleRequest() {
    const amt = Number(amount);
    if (!amt || amt <= 0) {
      setError("Enter a valid amount to request.");
      return;
    }
    if (earned && amt > earned.available_amount_minor) {
      setError(`Requested amount exceeds available balance of ${formatTenge(earned.available_amount_minor)} ₸.`);
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await api.ewa.createRequest({ amount_minor: amt, reason: reason || undefined });
      setAmount("");
      setReason("");
      setSuccess("Request submitted. You can track its status in History.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <PageFrame eyebrow="Get money" title="Access what you have already earned." copy="Loading your earned wages...">
      <div className="flex h-40 items-center justify-center"><Loader2 className="animate-spin text-green-deep" size={24} /></div>
    </PageFrame>;
  }

  const available = earned?.available_amount_minor || 0;
  const hasEarned = earned && earned.earned_amount_minor > 0;
  const requestedAmount = Number(amount || 0);
  const remaining = Math.max(0, available - requestedAmount);

  return <PageFrame eyebrow="Get money" title="Access what you have already earned." copy="ARQAU calculates your available amount from earned income and withdrawals. Request only what you need.">
    {error && <div className="mb-4 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700 flex items-center gap-2"><AlertCircle size={16} />{error}</div>}
    {success && <div className="mb-4 rounded-[10px] border border-green/20 bg-green-soft px-4 py-3 text-[13px] text-green-deep flex items-center gap-2"><Check size={16} />{success}</div>}

    {hasEarned ? (
      <section className={panel}>
        <h2 className="mb-4 text-[18px] font-bold">Your earned wages</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-[12px] text-ink-soft">Earned</p>
            <p className="mt-1 text-[28px] font-extrabold tracking-tight numbers">{formatTenge(earned.earned_amount_minor)} ₸</p>
          </div>
          <div>
            <p className="text-[12px] text-ink-soft">Accessed</p>
            <p className="mt-1 text-[28px] font-extrabold tracking-tight numbers">{formatTenge(earned.accessed_amount_minor)} ₸</p>
          </div>
          <div>
            <p className="text-[12px] text-ink-soft">Available</p>
            <p className="mt-1 text-[28px] font-extrabold tracking-tight text-green-deep numbers">{formatTenge(available)} ₸</p>
          </div>
        </div>

        <div className="mt-5 border-t border-ink/[0.06] pt-5">
          <h3 className="mb-4 text-[15px] font-bold">Request access</h3>
          <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div className="rounded-[12px] bg-cream px-4 py-3">
              <p className="text-[12px] text-ink-soft">Requesting</p>
              <p className="mt-1 text-[20px] font-extrabold tracking-tight numbers">{formatTenge(requestedAmount)} ₸</p>
            </div>
            <div className="rounded-[12px] bg-cream px-4 py-3">
              <p className="text-[12px] text-ink-soft">Remaining after</p>
              <p className="mt-1 text-[20px] font-extrabold tracking-tight numbers">{formatTenge(remaining)} ₸</p>
            </div>
            <div className="rounded-[12px] bg-cream px-4 py-3 sm:col-span-1 col-span-2">
              <p className="text-[12px] text-ink-soft">Available limit</p>
              <p className="mt-1 text-[20px] font-extrabold tracking-tight numbers">{formatTenge(available)} ₸</p>
            </div>
          </div>
          <div className="space-y-3">
            <input type="number" value={amount} onChange={(e) => { setAmount(e.target.value); setError(null); }} placeholder={`Amount up to ${formatTenge(available)} ₸`} aria-label="Amount to request" className="w-full rounded-[10px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-green-deep numbers" />
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (optional)" aria-label="Reason for request" className="w-full rounded-[10px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-green-deep" />
            <button onClick={handleRequest} disabled={submitting || !amount || Number(amount) <= 0 || Number(amount) > available} className="btn-primary w-full justify-center disabled:opacity-50">
              {submitting ? "Submitting..." : "Submit request"}
            </button>
          </div>
        </div>
      </section>
    ) : (
      <EmptyState
        title="Earned wage access"
        description="Set your earned wages in Finance to see your available balance and request access."
        actionLabel="Set earned wages"
        actionHref="/dashboard/finance"
      />
    )}

    {requests.length > 0 && (
      <section className={`${panel} mt-5`}>
        <h2 className="mb-4 text-[18px] font-bold">Request history</h2>
        <div className="space-y-3">
          {requests.map((req) => (
            <div key={req.id} className="flex items-center justify-between rounded-[12px] border border-ink/[0.08] bg-cream px-4 py-3">
              <div>
                <p className="font-semibold">{formatTenge(req.amount_minor)} ₸</p>
                <p className="text-[12px] text-ink-soft">{new Date(req.created_at).toLocaleDateString()}</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-[11px] font-bold ${
                req.status === "approved" ? "bg-green/20 text-green" :
                req.status === "pending" ? "bg-yellow-100 text-yellow-700" :
                req.status === "rejected" ? "bg-red-100 text-red-600" :
                "bg-ink/10 text-ink-soft"
              }`}>
                {req.status}
              </span>
            </div>
          ))}
        </div>
      </section>
    )}
  </PageFrame>;
}

export function HistoryPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [requests, setRequests] = useState<WageAccessRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  async function loadData() {
    try {
      const [txns, reqs] = await Promise.all([
        api.finance.getTransactions(),
        api.ewa.getRequests().catch(() => []),
      ]);
      setTransactions(txns);
      setRequests(reqs);
    } catch {
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const allItems = useMemo(() => {
    const txItems = transactions.map((t) => ({
      id: t.id,
      merchant: t.merchant || t.category || t.type,
      category: t.category || "Transaction",
      date: t.date ? new Date(t.date).toLocaleDateString() : "",
      status: "Completed" as const,
      amount: t.amount_minor,
      type: t.type as "income" | "expense",
      source: "transaction" as const,
    }));
    const reqItems = requests.map((r) => ({
      id: r.id,
      merchant: "Wage Access Request",
      category: r.status,
      date: new Date(r.created_at).toLocaleDateString(),
      status: r.status as "Completed" | "Pending",
      amount: r.amount_minor,
      type: "expense" as const,
      source: "request" as const,
    }));
    return [...txItems, ...reqItems].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [transactions, requests]);

  const filtered = useMemo(() => {
    if (!query.trim()) return allItems;
    return allItems.filter((item) => `${item.merchant} ${item.category}`.toLowerCase().includes(query.toLowerCase()));
  }, [allItems, query]);

  if (loading) {
    return <PageFrame eyebrow="History" title="Every transaction, in context." copy="Loading...">
      <div className="flex h-40 items-center justify-center"><Loader2 className="animate-spin text-green-deep" size={24} /></div>
    </PageFrame>;
  }

  return <PageFrame eyebrow="History" title="Every transaction, in context." copy="Search and review the activity behind your balance.">
    <section className={panel}>
      {allItems.length === 0 ? (
        <EmptyState
          title="No activity yet"
          description="Add income or expenses to start building your financial history."
          actionLabel="Add financial data"
          actionHref="/dashboard/finance"
        />
      ) : (
        <>
          <div className="relative max-w-[360px]">
            <Search size={16} className="absolute left-3 top-3.5 text-ink-soft" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search activity" aria-label="Search activity" className="w-full rounded-[10px] border border-ink/[0.1] bg-cream py-3 pl-9 pr-3 text-[14px] outline-none transition-colors focus:border-green-deep" />
          </div>
          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-[13px]">
              <thead className="border-b border-ink/[0.08] text-[11px] uppercase tracking-[0.1em] text-ink-soft">
                <tr>
                  <th className="pb-3">Description</th>
                  <th className="pb-3">Category</th>
                  <th className="pb-3">Date</th>
                  <th className="pb-3">Type</th>
                  <th className="pb-3 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className="border-b border-ink/[0.06] last:border-0">
                    <td className="py-4 font-semibold">{item.merchant}</td>
                    <td className="py-4 text-ink-soft">{item.category}</td>
                    <td className="py-4 text-ink-soft">{item.date}</td>
                    <td className="py-4 text-ink-soft capitalize">{item.type}</td>
                    <td className={`py-4 text-right font-bold numbers ${item.type === "income" ? "text-green" : "text-orange-dark"}`}>
                      {item.type === "income" ? "+" : "-"}{formatTenge(item.amount)} ₸
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && <p className="py-10 text-center text-[14px] text-ink-soft">No activity matches your search.</p>}
          </div>
        </>
      )}
    </section>
  </PageFrame>;
}

export function SettingsPage() {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    logout();
    router.push("/login");
  }

  return <PageFrame eyebrow="Settings" title="Your preferences, your pace." copy="Manage the details that shape your ARQAU experience.">
    <div className="grid max-w-[760px] gap-5">
      <section className={`${panel}`}>
        <h2 className="text-[12px] font-bold uppercase tracking-[0.08em] text-ink-soft">Account</h2>
        <div className="mt-4 space-y-4">
          <div className="flex items-center justify-between gap-5">
            <div>
              <p className="text-[13px] font-semibold">{user?.name || "—"}</p>
              <p className="text-[12px] text-ink-soft">{user?.email}</p>
            </div>
            <span className="text-[11px] font-semibold text-ink-soft">Name / Email</span>
          </div>
          <div className="border-t border-ink/[0.06] pt-3 flex items-center justify-between gap-5">
            <div>
              <p className="text-[13px] font-semibold">{user?.is_verified ? "Verified" : "Not verified"}</p>
              <p className="text-[12px] text-ink-soft">Email verification status</p>
            </div>
            <span className={`text-[11px] font-semibold ${user?.is_verified ? "text-green" : "text-orange-dark"}`}>{user?.is_verified ? "Active" : "Pending"}</span>
          </div>
        </div>
      </section>

      <section className={panel}>
        <h2 className="font-bold">Account actions</h2>
        <p className="mt-1 text-[13px] text-ink-soft">Sign out of your ARQAU account.</p>
        <button
          onClick={handleLogout}
          className="mt-4 rounded-[10px] border border-ink/10 bg-cream px-4 py-2.5 text-[13px] font-bold text-ink transition-colors hover:bg-ink hover:text-cream"
        >
          Sign out
        </button>
      </section>
    </div>
  </PageFrame>;
}
