"use client";

import Link from "next/link";
import { ArrowLeft, ArrowUpRight, Building2, ChartNoAxesCombined, Users, Wallet } from "lucide-react";
import { employerDemo, formatTenge } from "@/lib/demoData";
import { useTranslation } from "@/lib/language-context";

export default function BusinessPlaceholder({ title, description }: { title: string; description: string }) {
  const { t } = useTranslation();
  const metrics = [
    { label: t.employer.employees, value: employerDemo.employees.toLocaleString("en-US"), icon: Users },
    { label: t.employer.earnedPayroll, value: formatTenge(employerDemo.earnedPayroll), icon: Wallet },
    { label: t.employer.activeThisMonth, value: employerDemo.activeThisMonth.toLocaleString("en-US"), icon: ChartNoAxesCombined },
  ];

  return (
    <div>
      <Link href="/business" className="inline-flex items-center gap-2 text-[13px] font-semibold text-ink-soft hover:text-orange"><ArrowLeft size={15} />{t.employer.navEmployees}</Link>
      <p className="eyebrow mt-10 mb-4">Business workspace</p>
      <h1 className="text-[48px] font-extrabold leading-none tracking-[-0.04em]">{title}</h1>
      <p className="mt-5 max-w-[560px] text-[16px] leading-relaxed text-ink-soft">{description}</p>

      <div className="mt-10 grid gap-5 sm:grid-cols-3">
        {metrics.map(({ label, value, icon: Icon }) => (
          <section key={label} className="rounded-[16px] border border-ink/[0.07] bg-white/70 p-5">
            <Icon size={19} className="text-orange" />
            <p className="mt-5 text-[12px] uppercase tracking-[0.1em] text-ink-soft">{label}</p>
            <p className="mt-2 text-[30px] font-extrabold numbers">{value}</p>
          </section>
        ))}
      </div>

      <div className="mt-8 rounded-[20px] border border-ink/[0.08] bg-white/70 p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[13px] font-semibold">Foundation ready</p>
            <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">This workspace shares the same navigation, tokens and business registration flow as ARQAU. Connect payroll and eligibility data to unlock the full employer view.</p>
          </div>
          <Building2 size={28} className="text-orange shrink-0" />
        </div>
        <Link href="/business/register" className="mt-5 inline-flex items-center gap-2 text-[13px] font-bold text-orange">
          {t.employer.updateCta} <ArrowUpRight size={15} />
        </Link>
      </div>
    </div>
  );
}
