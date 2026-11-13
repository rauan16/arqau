"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Bell, BriefcaseBusiness, ChartNoAxesCombined, ChevronRight, CircleDollarSign, History, Home, Menu, MessageCircle, Search, Settings, SlidersHorizontal, Users, Wallet, X } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/language-context";
import LanguageSwitcher from "@/components/app/LanguageSwitcher";
import BrandLogo from "@/components/ui/BrandLogo";

const employeeNav = [
  { labelKey: "navHome", href: "/dashboard", icon: Home },
  { labelKey: "navFinance", href: "/dashboard/finance", icon: BarChart3 },
  { labelKey: "navAi", href: "/dashboard/ai", icon: MessageCircle },
  { labelKey: "navWhatIf", href: "/dashboard/what-if", icon: SlidersHorizontal },
  { labelKey: "navGetMoney", href: "/dashboard/get-money", icon: Wallet },
  { labelKey: "navHistory", href: "/dashboard/history", icon: History },
  { labelKey: "navSettings", href: "/dashboard/settings", icon: Settings },
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

function isActiveNavItem(href: string, pathname: string) {
  if (href === "/business" || href === "/dashboard") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * The demo is a public surface, so its destinations stay inside `/demo` instead
 * of sending an anonymous visitor into the authenticated application.
 */
function demoNavHref(href: string) {
  if (href === "/dashboard") return "/demo";
  return `/demo${href.slice("/dashboard".length)}`;
}

export interface AppShellProps {
  children: React.ReactNode;
  /** Optional demo user for demo mode (bypasses auth) */
  demoUser?: { name: string; email: string } | null;
  /** Whether to run in demo mode without authentication */
  isDemo?: boolean;
}

export default function AppShell({ children, demoUser, isDemo = false }: AppShellProps) {
  const pathname = usePathname();
  const { user: authUser } = useAuth();
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const user = isDemo && demoUser ? demoUser : authUser;
  const displayName = user?.name || user?.email?.split("@")[0] || t.navGuest;
  const initial = displayName.slice(0, 1).toUpperCase();
  const employer = isEmployerRoute(pathname);
  const nav = employer ? employerNav : employeeNav;

  return (
    <div className="min-h-screen bg-cream text-ink lg:grid lg:grid-cols-[250px_1fr]">
      <aside className={`${open ? "translate-x-0" : "-translate-x-full"} fixed inset-y-0 left-0 z-50 flex w-[250px] flex-col overflow-y-auto border-r border-ink/[0.08] bg-white px-5 py-6 transition-transform lg:static lg:translate-x-0`}>
        <div className="mb-10 flex items-center justify-between">
          <Link href="/" className="flex items-center"><BrandLogo size={44} /></Link>
          <button className="lg:hidden focus-ring" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={20} /></button>
        </div>
        {employer && (
          <p className="mb-4 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft/60">Business workspace</p>
        )}
        <nav className="space-y-1">
          {nav
            .filter(({ href }) => !(isDemo && !employer && href === "/dashboard/settings"))
            .map(({ labelKey, href, icon: Icon }) => {
            // Demo mode keeps every destination inside the public demo tree.
            const target = isDemo && !employer ? demoNavHref(href) : href;
            const active = isActiveNavItem(target, pathname);
            return (
              <Link
                key={href}
                href={target}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-[12px] px-3 py-3 text-[14px] font-semibold transition-colors ${active ? "bg-cream-orange text-ink" : "text-ink-soft hover:bg-orange-soft hover:text-orange"}`}
              >
                <Icon size={17} strokeWidth={1.8} className={active ? "text-orange" : undefined} />
                {t[labelKey as keyof typeof t] as string}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto pt-8">
          {employer ? (
            <Link href="/business/register" className="flex items-center justify-between rounded-[14px] border border-orange/25 bg-orange-soft p-3 text-[13px] font-semibold text-orange-dark">
              Update business <ChevronRight size={16} />
            </Link>
          ) : (
            <div className="rounded-[14px] bg-cream/60 p-4">
              <p className="text-[12px] font-bold text-ink">{t.navDemoNoticeTitle}</p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-ink-soft">{t.navDemoNoticeBody}</p>
            </div>
          )}
          <div className="mt-5 flex items-center gap-3 border-t border-ink/[0.08] pt-5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-[13px] font-bold text-cream">{initial}</div>
            <div className="min-w-0">
              <p className="truncate text-[13px] font-bold">{displayName}</p>
              <p className="text-[11px] text-ink-soft">{employer ? (user?.email || "User account") : t.navEmployeeRole}</p>
            </div>
          </div>
        </div>
      </aside>
      {open && <button className="fixed inset-0 z-40 bg-ink/20 lg:hidden" aria-label="Close navigation overlay" onClick={() => setOpen(false)} />}
      <main className="min-w-0 overflow-x-hidden">
        <header className="sticky top-0 z-30 flex h-[76px] items-center justify-between gap-3 border-b border-ink/[0.08] bg-cream/90 px-5 backdrop-blur-md sm:px-8 lg:px-12">
          <div className="flex items-center gap-3">
            <button className="lg:hidden focus-ring" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={22} /></button>
            <Link href="/" className="lg:hidden"><BrandLogo size={38} /></Link>
            {employer && (
              <div className="hidden text-[13px] text-ink-soft sm:block">
                Business / <span className="font-semibold text-ink">{pathname.split("/").pop() === "business" ? "Overview" : pathname.split("/").pop()}</span>
              </div>
            )}
          </div>
          <div className="ml-auto flex items-center gap-3">
            {employer && <span className="hidden text-[12px] text-ink-soft md:block">Business account</span>}
            {!employer && (
              <>
                <span aria-hidden="true" className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-cream-orange text-ink-soft"><Search size={17} /></span>
                <span aria-hidden="true" className="flex h-10 w-10 items-center justify-center rounded-[12px] border border-ink/[0.08] bg-white text-ink-soft"><Bell size={17} /></span>
              </>
            )}
            <LanguageSwitcher />
            {employer && (
              <Link href="/business/settings" className="flex h-9 w-9 items-center justify-center rounded-full bg-orange text-[13px] font-bold text-cream focus-ring">{initial}</Link>
            )}
          </div>
        </header>
        <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 lg:px-12 lg:py-12">{children}</div>
      </main>
    </div>
  );
}
