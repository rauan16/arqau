"use client";

import Link from "next/link";
import { ArrowUpRight, BriefcaseBusiness, ChartNoAxesCombined, Users } from "lucide-react";
import { employerDemo, formatTenge } from "@/lib/demoData";
import AppShell from "@/components/app/AppShell";
import { useTranslation } from "@/lib/language-context";

export default function BusinessPage() {
  const { t } = useTranslation();
  return (
    <AppShell>
      <div>
        <div className="mb-10">
          <p className="eyebrow mb-4">Business workspace</p>
          <h1 className="text-[48px] font-extrabold leading-none tracking-[-0.04em]">{t.employer.title}</h1>
          <p className="mt-4 max-w-[560px] text-[16px] leading-relaxed text-ink-soft">{t.employer.subtitle}</p>
        </div>

        <div className="grid gap-5 md:grid-cols-3">
          {[
            [t.employer.employees, employerDemo.employees.toLocaleString("en-US"), Users],
            [t.employer.earnedPayroll, formatTenge(employerDemo.earnedPayroll), BriefcaseBusiness],
            [t.employer.activeThisMonth, employerDemo.activeThisMonth.toLocaleString("en-US"), ChartNoAxesCombined],
          ].map(([label, value, Icon]) => (
            <section key={label as string} className="rounded-[16px] border border-ink/[0.07] bg-white/70 p-5">
              <Icon size={19} className="text-orange" />
              <p className="mt-5 text-[12px] uppercase tracking-[0.1em] text-ink-soft">{label as string}</p>
              <p className="mt-2 text-[30px] font-extrabold numbers">{value as string}</p>
            </section>
          ))}
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            [t.business.employees, "/business/employees"],
            [t.business.payroll, "/business/payroll"],
            [t.business.ewa, "/business/requests"],
            [t.business.wellbeing, "/business/analytics"],
          ].map(([item, href]) => (
            <Link key={item} href={href} className="flex items-center justify-between rounded-[16px] border border-ink/[0.08] bg-orange-soft p-5 text-[15px] font-bold text-orange hover:bg-orange hover:text-cream transition-colors">
              {item} <ArrowUpRight size={17} />
            </Link>
          ))}
        </div>
      </div>
    </AppShell>
  );
}