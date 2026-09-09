import { ArrowRight, MessageCircle } from "lucide-react";
import { scenario, upcomingExpenses, weeklyEarnings, formatTenge, evaluateWithdrawal } from "@/lib/demoData";

const base = "flex flex-col h-full pt-9 px-4 pb-4 font-sans text-ink";

export function EarningsScreen() {
  const max = Math.max(...weeklyEarnings);
  return (
    <div className={base}>
      <p className="text-[11px] font-bold text-ink-soft mb-0.5">Earnings</p>
      <p className="text-[10px] text-ink-soft/70 mb-4">{scenario.month}</p>
      <p className="text-[27px] font-extrabold leading-none mb-1 numbers">{formatTenge(scenario.earned)}</p>
      <p className="text-[10.5px] text-ink-soft mb-4">Earned so far</p>
      <div className="flex items-end gap-[3px] h-12 mb-4">
        {weeklyEarnings.map((v, i) => (
          <div key={i} className="w-[7px] rounded-full bg-green-bright/70" style={{ height: `${(v / max) * 100}%` }} />
        ))}
      </div>
      <div className="space-y-2 mt-auto">
        <div className="flex justify-between text-[11px]">
          <span className="text-ink-soft">Already received</span>
          <span className="font-semibold numbers">{formatTenge(scenario.alreadyReceived)}</span>
        </div>
        <div className="flex justify-between text-[11px] pt-2 border-t border-ink/[0.07]">
          <span className="text-ink-soft">Available</span>
          <span className="font-semibold text-orange numbers">{formatTenge(scenario.available)}</span>
        </div>
      </div>
    </div>
  );
}

export function ExpensesScreen() {
  return (
    <div className={base}>
      <p className="text-[11px] font-bold text-ink-soft mb-3">Upcoming expenses</p>
      <p className="text-[27px] font-extrabold leading-none mb-4 numbers">{formatTenge(scenario.upcomingExpensesTotal)}</p>
      <div className="space-y-2.5 mb-4">
        {upcomingExpenses.map((e) => (
          <div key={e.label} className="flex justify-between text-[11.5px]">
            <span className="text-ink-soft">{e.label}</span>
            <span className="font-semibold numbers">{formatTenge(e.amount)}</span>
          </div>
        ))}
      </div>
      <div className="mt-auto rounded-xl bg-orange-soft p-3">
        <p className="text-[10.5px] text-orange font-medium leading-snug">
          Your planned expenses are covered.
        </p>
      </div>
    </div>
  );
}

export function RecommendationScreen() {
  return (
    <div className={base}>
      <p className="text-[11px] font-bold text-ink-soft mb-3">ARQAU recommendation</p>
      <p className="text-[10.5px] text-ink-soft mb-1">Take</p>
      <p className="text-[29px] font-extrabold leading-none mb-4 numbers">{formatTenge(scenario.recommended)}</p>
      <p className="text-[11px] text-ink-soft leading-snug mb-4">
        This amount keeps your upcoming expenses covered while maintaining a {formatTenge(scenario.reserveTarget)} reserve.
      </p>
      <span className="inline-block w-fit text-[10px] font-semibold text-orange bg-orange-soft px-2.5 py-1 rounded-full mb-4">
        Recommended
      </span>
      <div className="mt-auto flex items-center gap-1 text-[11.5px] font-semibold text-orange">
        See why <ArrowRight size={13} />
      </div>
    </div>
  );
}

export function WhatIfScreen() {
  const result = evaluateWithdrawal(80000);
  return (
    <div className={base}>
      <p className="text-[11px] font-bold text-ink-soft mb-3">What if?</p>
      <p className="text-[11px] text-ink-soft mb-3">How much would you like to withdraw?</p>
      <div className="mb-3">
        <div className="h-1.5 rounded-full bg-ink/[0.08] relative">
          <div className="h-1.5 rounded-full bg-orange" style={{ width: "67%" }} />
          <div className="absolute -top-1 w-3.5 h-3.5 rounded-full bg-orange border-2 border-white shadow" style={{ left: "63%" }} />
        </div>
        <div className="flex justify-between text-[9px] text-ink-soft/60 mt-1">
          <span>0 ₸</span>
          <span>120,000 ₸</span>
        </div>
      </div>
      <p className="text-[23px] font-extrabold leading-none mb-2 numbers">{formatTenge(result.amount)}</p>
      <span className="inline-block w-fit text-[10px] font-semibold text-orange-dark bg-orange-soft px-2.5 py-1 rounded-full mb-3">
        {result.label}
      </span>
      <p className="text-[10.5px] text-ink-soft leading-snug mb-4">{result.note}</p>
      <div className="mt-auto flex items-center gap-1 text-[11.5px] font-semibold text-orange">
        Compare scenarios <ArrowRight size={13} />
      </div>
    </div>
  );
}

export function AIScreen() {
  return (
    <div className={base}>
      <div className="flex items-center gap-1.5 mb-3">
        <MessageCircle size={13} className="text-orange" />
        <p className="text-[11px] font-bold text-ink-soft">AI Assistant</p>
      </div>
      <div className="space-y-2.5 text-[10.5px] leading-snug">
        <div className="ml-auto max-w-[85%] bg-ink text-cream rounded-xl rounded-tr-sm px-3 py-2">
          What happens if I withdraw 80,000 ₸?
        </div>
        <div className="mr-auto max-w-[90%] bg-orange-soft rounded-xl rounded-tl-sm px-3 py-2">
          You can, but your reserve would fall below the recommended level.
        </div>
        <div className="ml-auto max-w-[85%] bg-ink text-cream rounded-xl rounded-tr-sm px-3 py-2">
          What amount would be safer?
        </div>
        <div className="mr-auto max-w-[90%] bg-orange-soft rounded-xl rounded-tl-sm px-3 py-2">
          50,000 ₸ keeps expenses covered and your reserve intact.
        </div>
      </div>
    </div>
  );
}
