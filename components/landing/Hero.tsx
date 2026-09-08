"use client";

import { motion } from "framer-motion";
import { ArrowRight, Home, Utensils, Car, Lightbulb, SlidersHorizontal, ShieldCheck } from "lucide-react";
import PhoneFrame from "./PhoneFrame";
import HeroScreen from "./HeroScreen";
import FloatingInsightCard from "./FloatingInsightCard";
import { scenario, upcomingExpenses, weeklyEarnings, formatTenge } from "@/lib/demoData";

const easeOut = [0.22, 1, 0.36, 1] as const;
const easeInOut = "easeInOut" as const;

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: (delay = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.75, delay, ease: easeOut },
  }),
};

const floatY = (duration: number, delay: number) => ({
  y: [0, -10, 0],
  transition: {
    duration,
    delay,
    repeat: Infinity,
    ease: easeInOut,
  },
});

export default function Hero() {
  const maxEarn = Math.max(...weeklyEarnings);

  return (
    <section id="top" className="relative min-h-[700px] lg:min-h-[800px] overflow-hidden pt-[120px] pb-20 lg:pt-[140px] lg:pb-28">
      {/* organic orange field */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1.2, ease: "easeOut" }}
        className="pointer-events-none absolute inset-0 -z-10"
      >
        <svg
          className="hidden lg:block absolute -right-[8%] -top-[12%] w-[78%] h-[150%]"
          viewBox="0 0 900 1000"
          fill="none"
          preserveAspectRatio="xMidYMid slice"
        >
          <path
            d="M900 0H320C420 90 300 190 210 260C90 350 20 470 60 620C100 770 260 830 400 900C520 960 700 1000 900 960V0Z"
            fill="url(#heroGradient)"
          />
          <defs>
            <linearGradient id="heroGradient" x1="900" y1="0" x2="200" y2="960" gradientUnits="userSpaceOnUse">
              <stop stopColor="#FF9B68" />
              <stop offset="1" stopColor="#FF7745" />
            </linearGradient>
          </defs>
        </svg>
        <div className="lg:hidden absolute left-[-25%] right-[-25%] top-[48%] bottom-[-10%] rounded-t-[48%] bg-orange-2" />
      </motion.div>

      <div className="relative z-10 max-w-[1480px] mx-auto pl-6 pr-6 lg:pl-[72px] lg:pr-[72px]">
        <div className="grid lg:grid-cols-[minmax(440px,1fr)_minmax(480px,1.1fr)] xl:grid-cols-[1fr_1.1fr] gap-10 lg:gap-12 xl:gap-16 items-start">
          {/* left: copy */}
          <div className="relative z-10 max-w-[520px]">
            <motion.p variants={fadeUp} initial="hidden" animate="show" custom={0} className="eyebrow mb-6">
              Smarter access to earned wages
            </motion.p>

            <motion.h1
              variants={fadeUp}
              initial="hidden"
              animate="show"
              custom={0.1}
              className="text-[44px] sm:text-[60px] lg:text-[76px] xl:text-[84px] font-extrabold leading-[0.94] tracking-[-0.04em] text-ink text-balance"
            >
              Your money.
              <br />
              When you&apos;ve
              <br />
              <span className="font-serif italic font-medium text-orange">earned it.</span>
            </motion.h1>

            <motion.p
              variants={fadeUp}
              initial="hidden"
              animate="show"
              custom={0.22}
              className="mt-8 text-[16px] sm:text-[17px] leading-[1.7] text-ink-soft max-w-[400px]"
            >
              ARQAU helps you access what you&apos;ve already earned, understand your options and make a more confident decision before payday.
            </motion.p>

            <motion.div
              variants={fadeUp}
              initial="hidden"
              animate="show"
              custom={0.32}
              className="mt-10 flex flex-wrap items-center gap-4"
            >
              <a href="/signup" className="btn-primary">
                Get started <ArrowRight size={16} className="btn-arrow" />
              </a>
              <a href="#how-it-works" className="btn-secondary">
                See how it works
              </a>
            </motion.div>

            <motion.div
              variants={fadeUp}
              initial="hidden"
              animate="show"
              custom={0.45}
              className="mt-20 hidden lg:flex items-center gap-3 text-[13px] text-ink-soft/60"
            >
              <span className="text-lg">↓</span> Scroll to explore
            </motion.div>
          </div>

          {/* right: phone + floating cards */}
          <div className="relative w-full min-h-[420px] sm:min-h-[520px] lg:min-h-[1040px] xl:min-h-[760px] flex items-center justify-center">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{
                opacity: { duration: 0.9, delay: 0.2, ease: easeOut },
              }}
              className="phone-float absolute left-1/2 -translate-x-1/2 top-0 z-10"
            >
              <PhoneFrame>
                <HeroScreen />
              </PhoneFrame>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: [0, -10, 0] }}
              transition={{ opacity: { duration: 0.6, delay: 0.55 }, ...floatY(5, 1.3).transition }}
                className="hidden lg:block absolute z-20 left-0 top-[68%] w-[200px] xl:top-[12%] xl:-left-[80px] xl:w-[180px]"
            >
              <FloatingInsightCard>
                <p className="text-[11px] text-ink-soft mb-0.5">Your earnings</p>
                <p className="text-[10px] text-ink-soft/70 mb-2">This month</p>
                <p className="text-[19px] font-bold mb-2.5">{formatTenge(scenario.earned)}</p>
                <div className="flex items-end gap-[3px] h-7">
                  {weeklyEarnings.map((v, i) => (
                    <div key={i} className="w-[7px] rounded-full bg-orange" style={{ height: `${(v / maxEarn) * 100}%` }} />
                  ))}
                </div>
                <p className="mt-1.5 text-[9px] text-ink-soft/50">Illustrative example</p>
              </FloatingInsightCard>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: [0, -9, 0] }}
              transition={{ opacity: { duration: 0.6, delay: 0.7 }, ...floatY(5.8, 1.5).transition }}
                className="hidden lg:block absolute z-20 left-0 top-[84%] w-[220px] xl:top-[51%] xl:-left-[80px] xl:w-[200px]"
            >
              <FloatingInsightCard>
                <p className="text-[11px] text-ink-soft mb-2.5">Upcoming expenses</p>
                <div className="space-y-1.5 mb-2.5">
                  {upcomingExpenses.map((e) => {
                    const Icon = e.label === "Rent" ? Home : e.label === "Food" ? Utensils : Car;
                    return (
                      <div key={e.label} className="flex items-center justify-between text-[11.5px]">
                        <span className="flex items-center gap-1.5 text-ink-soft">
                          <Icon size={12} /> {e.label}
                        </span>
                        <span className="font-semibold">{formatTenge(e.amount)}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="pt-2 border-t border-ink/[0.07] flex items-center justify-between text-[12px]">
                  <span className="text-ink-soft">Total</span>
                  <span className="font-bold">{formatTenge(scenario.upcomingExpensesTotal)}</span>
                </div>
                <p className="mt-1.5 text-[9px] text-ink-soft/50">Illustrative example</p>
              </FloatingInsightCard>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: [0, -7, 0] }}
              transition={{ opacity: { duration: 0.6, delay: 0.85 }, ...floatY(5.2, 1.7).transition }}
                className="hidden lg:block absolute z-20 right-0 top-[68%] w-[230px] xl:top-[16%] xl:-right-[56px] xl:w-[180px]"
            >
              <FloatingInsightCard className="bg-cream-orange border-orange/20">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Lightbulb size={13} className="text-orange-dark" />
                  <p className="text-[11px] font-semibold text-orange-dark">AI recommendation</p>
                </div>
                <p className="text-[12px] leading-snug text-ink-soft mb-2">
                  ARQAU considers your earned income, upcoming expenses and reserve target before suggesting an amount.
                </p>
                <span className="text-[12px] font-semibold">→</span>
              </FloatingInsightCard>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: [0, -8, 0] }}
              transition={{ opacity: { duration: 0.6, delay: 1 }, ...floatY(5.6, 1.9).transition }}
                className="hidden lg:block absolute z-20 right-0 top-[84%] w-[210px] xl:top-[54%] xl:-right-[50px] xl:w-[170px]"
            >
              <FloatingInsightCard>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <SlidersHorizontal size={13} className="text-ink-soft" />
                  <p className="text-[12px] font-semibold">What if?</p>
                </div>
                <p className="text-[11.5px] text-ink-soft leading-snug mb-2.5">
                  Try different scenarios and see how they affect your balance.
                </p>
                <span className="text-[12px] font-semibold text-orange-dark">Open simulator →</span>
              </FloatingInsightCard>
            </motion.div>

<motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: [0, -6, 0] }}
              transition={{ opacity: { duration: 0.6, delay: 1.1 }, ...floatY(4.8, 2.1).transition }}
              className="hidden lg:block absolute z-20 left-1/2 -translate-x-1/2 bottom-0 w-[200px]"
            >
              <FloatingInsightCard>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <ShieldCheck size={13} className="text-green" />
                  <p className="text-[11px] font-semibold">Reserve target</p>
                </div>
                <p className="text-[10.5px] text-ink-soft mb-1">Amount ARQAU recommends keeping</p>
                <p className="text-[18px] font-bold">{formatTenge(scenario.reserveTarget)}</p>
              </FloatingInsightCard>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
