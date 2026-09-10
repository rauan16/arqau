"use client";

import { motion } from "framer-motion";
import { employerDemo, formatTenge } from "@/lib/demoData";
import { useTranslation } from "@/lib/language-context";

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function EmployerSection() {
  const { t } = useTranslation();
  const max = Math.max(...employerDemo.weeklyActivity);
  return (
    <section id="employers" className="py-32 lg:py-40 bg-cream-soft">
      <div className="container-arqau">
        <div className="max-w-[560px] mb-14">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, ease: easeOut }}
            className="eyebrow mb-5 reveal-text"
          >
            {t.landing.employerEyebrow}
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, ease: easeOut }}
            className="text-[38px] sm:text-[50px] lg:text-[58px] font-extrabold leading-[1.01] tracking-[-0.03em] mb-7 reveal-text text-balance"
          >
            Give employees more control over earned income.
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.1, ease: easeOut }}
            className="text-[18px] leading-[1.7] text-ink-soft mb-9 max-w-[520px] reveal-text"
          >
            ARQAU gives employers a modern layer for earned wage access, withdrawal controls and employee financial wellbeing.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.2, ease: easeOut }}
          >
            <a href="/business/register" className="btn-primary">{t.landing.employerCta} →</a>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: easeOut }}
          className="card-dark rounded-[30px] p-8 sm:p-12 max-w-[1100px] text-cream shadow-[0_32px_80px_-48px_rgba(21,21,21,0.65)]"
        >
          <div className="flex items-center justify-between mb-8">
            <p className="text-[12px] font-semibold tracking-[0.08em] text-cream/60">ARQAU FOR BUSINESS</p>
            <span className="text-[11px] font-medium text-cream/40 border border-cream/20 rounded-full px-2.5 py-1">
              Illustrative example
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-7 mb-12">
            <div>
              <p className="text-[12px] text-cream/70 mb-1.5">{t.employer.employees}</p>
              <p className="text-[22px] sm:text-[28px] font-bold tracking-tight truncate">{employerDemo.employees.toLocaleString("en-US")}</p>
            </div>
            <div>
              <p className="text-[12px] text-cream/70 mb-1.5">{t.employer.earnedPayroll}</p>
              <p className="text-[22px] sm:text-[28px] font-bold tracking-tight truncate">{formatTenge(employerDemo.earnedPayroll)}</p>
            </div>
            <div>
              <p className="text-[12px] text-cream/70 mb-1.5">{t.employer.activeThisMonth}</p>
              <p className="text-[22px] sm:text-[28px] font-bold tracking-tight truncate">{employerDemo.activeThisMonth.toLocaleString("en-US")}</p>
            </div>
            <div>
              <p className="text-[12px] text-cream/70 mb-1.5">Withdrawals</p>
              <p className="text-[22px] sm:text-[28px] font-bold tracking-tight truncate">{formatTenge(employerDemo.withdrawals)}</p>
            </div>
          </div>

          <div className="flex items-end gap-3 h-28 border-t border-cream/10 pt-7">
            {employerDemo.weeklyActivity.map((v, i) => (
              <div key={i} className="flex-1 rounded-t-md bg-orange-2" style={{ height: `${(v / max) * 100}%` }} />
            ))}
          </div>
          <p className="text-[11.5px] text-cream/40 mt-4">
            {t.landing.employerIllustrative}
          </p>
        </motion.div>
      </div>
    </section>
  );
}
