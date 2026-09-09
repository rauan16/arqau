"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, ChevronRight, CircleDollarSign, History, Home, Menu, MessageCircle, Settings, Users, BriefcaseBusiness, ChartNoAxesCombined, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/language-context";
import LanguageSwitcher from "@/components/app/LanguageSwitcher";

const employeeNav = [
  { labelKey: "navOverview", href: "/dashboard", icon: Home },
  { labelKey: "navEarnings", href: "/dashboard/finance", icon: BarChart3 },
  { labelKey: "navWithdraw", href: "/dashboard/get-money", icon: CircleDollarSign },
  { labelKey: "navAI", href: "/dashboard/ai", icon: MessageCircle },
  { labelKey: "navExpenses", href: "/dashboard/history", icon: History },
  { labelKey: "navProfile", href: "/dashboard/settings", icon: Settings },
];

const employerNav = [
  { labelKey: "navBusinessOverview", href: "/business", icon: Home },
  { labelKey: "navBusinessEmployees", href: "/business/employees", icon: Users },
  { labelKey: "navBusinessPayroll", href: "/business/payroll", icon: BriefcaseBusiness },
  { labelKey: "navBusinessEWA", href: "/business/requests", icon: CircleDollarSign },
  { labelKey: "navBusinessWellbeing", href: "/business/analytics", icon: ChartNoAxesCombined },
  { labelKey: "navBusinessSettings", href: "/business/settings", icon: Settings },
];

function isEmployerRoute(pathname: string) {
  return pathname.startsWith("/business");
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const displayName = user?.name || user?.email?.split("@")[0] || "Guest";
  const initial = displayName.slice(0, 1).toUpperCase();
  const employer = isEmployerRoute(pathname);
  const nav = employer ? employerNav : employeeNav;

  return (
    <div className="min-h-screen bg-cream text-ink lg:grid lg:grid-cols-[248px_1fr]">
      <aside className={`${open ? "translate-x-0" : "-translate-x-full"} fixed inset-y-0 left-0 z-50 w-[248px] border-r border-ink/[0.08] bg-cream-soft px-5 py-6 transition-transform lg:static lg:translate-x-0`}>
        <div className="flex items-center justify-between mb-12">
          <Link href="/" className="text-[20px] font-extrabold tracking-[0.08em]">ARQAU</Link>
          <button className="lg:hidden focus-ring" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={20} /></button>
        </div>
        <p className="mb-4 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft/60">{employer ? "Business workspace" : "Your workspace"}</p>
        <nav className="space-y-1">
          {nav.map(({ labelKey, href, icon: Icon }) => {
            const active = href === "/business" || href === "/dashboard" ? pathname === href : pathname.startsWith(href);
            return <Link key={href} href={href} onClick={() => setOpen(false)} className={`flex items-center gap-3 rounded-[10px] px-3 py-3 text-[14px] font-semibold transition-colors ${active ? "bg-orange text-cream" : "text-ink-soft hover:bg-orange-soft hover:text-orange"}`}><Icon size={17} strokeWidth={1.8} />{t[labelKey as keyof typeof t] as string}</Link>;
          })}
        </nav>
        <div className="mt-12 border-t border-ink/[0.08] pt-5">
          {employer ? (
            <Link href="/business/register" className="flex items-center justify-between rounded-[14px] border border-orange/25 bg-orange-soft p-3 text-[13px] font-semibold text-orange-dark">Update business <ChevronRight size={16} /></Link>
          ) : (
            <Link href="/business/register" className="flex items-center justify-between rounded-[14px] border border-orange/25 bg-orange-soft p-3 text-[13px] font-semibold text-orange-dark">Register business <ChevronRight size={16} /></Link>
          )}
        </div>
        <div className="absolute bottom-6 left-5 right-5 flex items-center gap-3 border-t border-ink/[0.08] pt-5"><div className="flex h-9 w-9 items-center justify-center rounded-full bg-orange text-[13px] font-bold text-cream">{initial}</div><div><p className="text-[13px] font-bold">{displayName}</p><p className="text-[11px] text-ink-soft">{user?.email || "User account"}</p></div></div>
      </aside>
      {open && <button className="fixed inset-0 z-40 bg-ink/20 lg:hidden" aria-label="Close navigation overlay" onClick={() => setOpen(false)} />}
      <main className="min-w-0">
        <header className="sticky top-0 z-30 flex h-[76px] items-center justify-between border-b border-ink/[0.08] bg-cream/90 px-5 backdrop-blur-md sm:px-8 lg:px-12">
          <button className="lg:hidden focus-ring" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={22} /></button>
          <div className="hidden text-[13px] text-ink-soft sm:block">{employer ? "Business" : "Personal finance"} / <span className="font-semibold text-ink">{pathname.split("/").pop() === "dashboard" ? "Overview" : pathname.split("/").pop()}</span></div>
          <Link href="/" className="text-[17px] font-extrabold tracking-[0.08em] lg:hidden">ARQAU</Link>
          <div className="ml-auto flex items-center gap-3"><span className="hidden text-[12px] text-ink-soft md:block">{employer ? "Business account" : "Personal account"}</span><LanguageSwitcher /><Link href={employer ? "/business/settings" : "/dashboard/settings"} className="flex h-9 w-9 items-center justify-center rounded-full bg-orange text-[13px] font-bold text-cream focus-ring">{initial}</Link></div>
        </header>
        <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 lg:px-12 lg:py-12">{children}</div>
      </main>
    </div>
  );
}