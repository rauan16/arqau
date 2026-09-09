import { ArrowRight, Home, LineChart, Wallet, Sparkles, CalendarDays, CircleUserRound } from "lucide-react";
import { scenario, weeklyEarnings, formatTenge } from "@/lib/demoData";

export default function HeroScreen() {
  const max = Math.max(...weeklyEarnings);

  return (
    <div className="flex flex-col h-full pt-[42px] px-5 pb-4 font-sans bg-[#fbf7f1]">
      <div className="flex items-center justify-between mb-6">
        <span className="text-[11px] font-extrabold tracking-[0.1em] text-ink-soft">ARQAU</span>
        <CircleUserRound size={21} className="text-ink-soft" strokeWidth={1.7} />
      </div>

      <p className="text-[13px] text-ink-soft mb-1">Good morning, {scenario.employeeName} <span className="text-green-deep">✦</span></p>
      <div className="flex items-center justify-between mb-4">
        <p className="text-[12px] text-ink-soft">Earned this month</p>
        <span className="text-[10px] text-ink-soft/70">This month →</span>
      </div>

      <p className="text-[34px] font-extrabold leading-none tracking-tight mb-5 numbers">
        {formatTenge(scenario.earned)}
      </p>

      <div className="grid grid-cols-2 gap-2.5 mb-3">
        <div className="rounded-[18px] bg-green-deep text-cream p-3.5">
          <p className="text-[10.5px] opacity-85 mb-1">Available</p>
          <p className="text-[19px] font-bold leading-tight numbers">{formatTenge(scenario.available)}</p>
        </div>
        <div className="rounded-[18px] bg-white border border-ink/[0.07] p-3.5">
          <p className="text-[10.5px] text-ink-soft mb-1">Recommended</p>
          <p className="text-[19px] font-bold leading-tight numbers">{formatTenge(scenario.recommended)}</p>
        </div>
      </div>

      <div className="rounded-[18px] bg-white border border-ink/[0.07] p-3.5 mb-3 flex items-center justify-between">
        <div>
          <p className="text-[10.5px] text-ink-soft mb-0.5 flex items-center gap-1"><CalendarDays size={11} /> Next payday</p>
          <p className="text-[14px] font-bold">{scenario.nextPaydayDays} days</p>
        </div>
        <div className="flex items-end gap-[3px] h-8">
          {weeklyEarnings.map((v, i) => (
            <div
              key={i}
              className="w-[6px] rounded-full bg-green-bright/70"
              style={{ height: `${(v / max) * 100}%` }}
            />
          ))}
        </div>
      </div>

      <div className="rounded-[18px] bg-ink text-cream p-4 mt-auto mb-4">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Sparkles size={13} className="text-green-bright" />
          <p className="text-[10.5px] font-semibold text-green-bright">ARQAU recommends</p>
        </div>
        <p className="text-[19px] font-bold mb-1.5 numbers">{formatTenge(scenario.recommended)}</p>
        <p className="text-[11.5px] text-cream/70 leading-snug mb-3">
          Keeps your upcoming expenses covered while protecting your reserve target.
        </p>
        <div className="flex items-center gap-1 text-[12px] font-semibold text-green-bright">
          View recommendation <ArrowRight size={13} />
        </div>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-ink/[0.07]">
        {[
          { icon: Home, label: "Home" },
          { icon: LineChart, label: "Earnings" },
          { icon: Wallet, label: "Expenses" },
          { icon: Sparkles, label: "AI" },
        ].map(({ icon: Icon, label }, i) => (
          <div key={label} className={`flex flex-col items-center gap-1 ${i === 0 ? "text-ink" : "text-ink-soft/60"}`}>
            <Icon size={17} strokeWidth={2} />
            <span className="text-[9px]">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
