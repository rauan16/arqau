import {
  ArrowRight,
  ArrowDownLeft,
  ArrowUpRight,
  Bell,
  Briefcase,
  CalendarDays,
  Home,
  LineChart,
  Search,
  Sparkles,
  Wallet,
} from "lucide-react";
import { scenario, formatTenge } from "@/lib/demoData";
import { useTranslation } from "@/lib/language-context";
import BrandLogo from "@/components/ui/BrandLogo";

const activityIcons = [ArrowUpRight, ArrowDownLeft, Sparkles];

export default function HeroScreen() {
  const { t } = useTranslation();
  const p = t.landingHero.phone;

  const activity = [
    { title: p.payout, date: p.date1, amount: formatTenge(-50000), meta: p.done, tone: "negative" },
    { title: p.payroll, date: p.date2, amount: `+${formatTenge(scenario.earned)}`, meta: p.received, tone: "positive" },
    { title: p.aiRec, date: p.date3, amount: "", meta: p.view, tone: "muted" },
  ];

  const tabs = [
    { icon: Home, label: p.tabHome },
    { icon: LineChart, label: p.tabAnalytics },
    { icon: Wallet, label: p.tabAccounts },
    { icon: CalendarDays, label: p.tabProfile },
  ];

  return (
    <div className="flex h-full flex-col bg-white px-5 pb-4 pt-12">
      {/* status bar */}
      <div className="mb-4 flex items-center justify-between text-[11px] font-semibold text-ink">
        <span className="numbers">9:41</span>
        <span className="flex items-center gap-1.5">
          <span className="flex items-end gap-[2px]">
            <span className="h-[4px] w-[3px] rounded-sm bg-ink" />
            <span className="h-[6px] w-[3px] rounded-sm bg-ink" />
            <span className="h-[8px] w-[3px] rounded-sm bg-ink" />
            <span className="h-[10px] w-[3px] rounded-sm bg-ink/30" />
          </span>
          <span className="h-[9px] w-[13px] rounded-[3px] border border-ink">
            <span className="mt-[1.5px] ml-[1.5px] block h-[4px] w-[7px] rounded-[1px] bg-ink" />
          </span>
        </span>
      </div>

      {/* app header */}
      <div className="mb-5 flex items-center justify-between">
        <span className="flex items-center gap-2 text-[13px] font-extrabold tracking-[0.06em] text-ink">
          <BrandLogo size={24} />
          ARQAU
        </span>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-orange/30 px-2 py-1 text-[8px] font-bold uppercase text-orange-dark">
            {t.landing.productDemoTag}
          </span>
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-cream text-ink-soft">
            <Search size={14} strokeWidth={2.2} />
          </span>
        </div>
      </div>

      {/* greeting */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <p className="text-[16px] font-extrabold leading-tight text-ink">{p.greeting}</p>
          <p className="mt-0.5 text-[11.5px] text-ink-soft">{p.role}</p>
        </div>
        <Bell size={16} className="mt-1 text-ink-soft" strokeWidth={1.8} />
      </div>

      {/* earned */}
      <div className="mb-2.5 rounded-[18px] border border-ink/[0.07] bg-cream/60 p-4">
        <p className="mb-1 text-[11px] text-ink-soft">{p.earned}</p>
        <div className="flex items-center justify-between">
          <p className="numbers text-[26px] font-extrabold leading-none tracking-tight text-ink">
            {formatTenge(scenario.earned)}
          </p>
          <span className="flex h-7 w-7 items-center justify-center rounded-full border border-ink/10 text-ink">
            <ArrowRight size={13} />
          </span>
        </div>
      </div>

      {/* available */}
      <div className="mb-2.5 flex items-center justify-between rounded-[18px] border border-ink/[0.07] bg-cream/60 px-4 py-3">
        <p className="text-[11px] text-ink-soft">{p.available}</p>
        <p className="numbers text-[16px] font-extrabold text-ink">{formatTenge(scenario.available)}</p>
        <span className="text-[10px] text-ink-soft/60">Illustrative demo value only.</span>
      </div>

      {/* recommended */}
      <div className="mb-3 flex items-center justify-between rounded-[18px] bg-orange-soft p-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-orange text-white">
            <Briefcase size={14} strokeWidth={2} />
          </span>
          <div>
            <p className="text-[10.5px] text-ink-soft">{p.recommended}</p>
            <p className="numbers text-[15px] font-extrabold text-ink">{formatTenge(scenario.recommended)}</p>
          </div>
        </div>
        <ArrowRight size={14} className="text-ink" />
      </div>

      {/* primary action */}
      <button type="button" className="mb-4 w-full rounded-full bg-orange py-3 text-[13.5px] font-bold text-white shadow-[0_14px_26px_-14px_rgba(242,103,34,0.8)]">
        {p.getMoney}
      </button>

      {/* activity */}
      <div className="flex-1">
        <p className="mb-2 text-[11.5px] font-bold text-ink">{p.activity}</p>
        <div className="space-y-1.5">
          {activity.map((item, i) => {
            const Icon = activityIcons[i];
            return (
              <div key={item.title} className="flex items-center gap-2.5 rounded-[14px] border border-ink/[0.06] bg-white px-3 py-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-orange-soft text-orange-dark">
                  <Icon size={12} strokeWidth={2.2} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[11px] font-semibold text-ink">{item.title}</p>
                  <p className="text-[9.5px] text-ink-muted">{item.date}</p>
                </div>
                <div className="text-right">
                  {item.amount && (
                    <p
                      className={`numbers text-[11px] font-bold ${
                        item.tone === "positive" ? "text-ink" : item.tone === "negative" ? "text-ink" : ""
                      }`}
                    >
                      {item.amount}
                    </p>
                  )}
                  <p className="text-[9px] text-ink-muted">{item.meta}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* tab bar */}
      <div className="mt-3 flex items-center justify-between border-t border-ink/[0.07] pt-3">
        {tabs.map(({ icon: Icon, label }, i) => (
          <div key={label} className={`flex flex-col items-center gap-1 ${i === 0 ? "text-orange" : "text-ink-muted"}`}>
            <Icon size={17} strokeWidth={2} />
            <span className="text-[8.5px] font-semibold">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
