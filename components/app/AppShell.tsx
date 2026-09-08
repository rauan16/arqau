"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, ChevronRight, CircleDollarSign, History, Home, Menu, MessageCircle, Settings, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";

const nav = [
  { label: "Home", href: "/dashboard", icon: Home },
  { label: "AI assistant", href: "/dashboard/ai", icon: MessageCircle },
  { label: "Finance", href: "/dashboard/finance", icon: BarChart3 },
  { label: "Get money", href: "/dashboard/get-money", icon: CircleDollarSign },
  { label: "History", href: "/dashboard/history", icon: History },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  const displayName = user?.name || user?.email?.split("@")[0] || "Guest";
  const initial = displayName.slice(0, 1).toUpperCase();

  return (
    <div className="min-h-screen bg-cream text-ink lg:grid lg:grid-cols-[248px_1fr]">
      <aside className={`${open ? "translate-x-0" : "-translate-x-full"} fixed inset-y-0 left-0 z-50 w-[248px] border-r border-ink/[0.08] bg-cream-soft px-5 py-6 transition-transform lg:static lg:translate-x-0`}>
        <div className="flex items-center justify-between mb-12">
          <Link href="/" className="text-[20px] font-extrabold tracking-[0.08em]">ARQAU</Link>
          <button className="lg:hidden focus-ring" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={20} /></button>
        </div>
        <p className="mb-4 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft/60">Your workspace</p>
        <nav className="space-y-1">
          {nav.map(({ label, href, icon: Icon }) => {
            const active = href === "/dashboard" ? pathname === href : pathname.startsWith(href);
            return <Link key={href} href={href} onClick={() => setOpen(false)} className={`flex items-center gap-3 rounded-[10px] px-3 py-3 text-[14px] font-semibold transition-colors ${active ? "bg-ink text-cream" : "text-ink-soft hover:bg-cream hover:text-ink"}`}><Icon size={17} strokeWidth={1.8} />{label}</Link>;
          })}
        </nav>
        <div className="mt-12 border-t border-ink/[0.08] pt-5">
          <Link href="/business/register" className="flex items-center justify-between rounded-[14px] border border-orange/25 bg-cream-orange p-3 text-[13px] font-semibold text-orange-dark">Register business <ChevronRight size={16} /></Link>
        </div>
        <div className="absolute bottom-6 left-5 right-5 flex items-center gap-3 border-t border-ink/[0.08] pt-5"><div className="flex h-9 w-9 items-center justify-center rounded-full bg-orange text-[13px] font-bold text-cream">{initial}</div><div><p className="text-[13px] font-bold">{displayName}</p><p className="text-[11px] text-ink-soft">{user?.email || "User account"}</p></div></div>
      </aside>
      {open && <button className="fixed inset-0 z-40 bg-ink/20 lg:hidden" aria-label="Close navigation overlay" onClick={() => setOpen(false)} />}
      <main className="min-w-0">
        <header className="sticky top-0 z-30 flex h-[76px] items-center justify-between border-b border-ink/[0.08] bg-cream/90 px-5 backdrop-blur-md sm:px-8 lg:px-12">
          <button className="lg:hidden focus-ring" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={22} /></button>
          <div className="hidden text-[13px] text-ink-soft sm:block">Personal finance / <span className="font-semibold text-ink">{pathname.split("/").pop() === "dashboard" ? "Overview" : pathname.split("/").pop()}</span></div>
          <Link href="/" className="text-[17px] font-extrabold tracking-[0.08em] lg:hidden">ARQAU</Link>
          <div className="ml-auto flex items-center gap-3"><span className="hidden text-[12px] text-ink-soft md:block">Personal account</span><Link href="/dashboard/settings" className="flex h-9 w-9 items-center justify-center rounded-full bg-orange text-[13px] font-bold text-cream focus-ring">{initial}</Link></div>
        </header>
        <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 lg:px-12 lg:py-12">{children}</div>
      </main>
    </div>
  );
}
