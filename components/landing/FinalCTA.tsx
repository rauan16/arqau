"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import Image from "next/image";

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function FinalCTA() {
  return (
    <section id="final-cta" className="relative overflow-hidden bg-green-deep text-cream py-32 lg:py-44">
      <div className="pointer-events-none absolute inset-0">
        <Image
          src="/Kazakhstan1-e1496914203779.jpg"
          alt="Kazakhstan mountain landscape"
          fill
          priority
          sizes="100vw"
          className="absolute inset-0 h-full w-full object-cover object-center opacity-40"
        />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(47,83,56,0.98)_0%,rgba(47,83,56,0.85)_42%,rgba(47,83,56,0.5)_100%)]" />
      </div>

      <div className="container-arqau relative z-10 grid lg:grid-cols-[1.2fr_0.8fr] gap-10 items-end">
        <div>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5, ease: easeOut }}
            className="text-[12px] font-bold tracking-[0.1em] uppercase text-cream/70 mb-6"
          >
            The future of financial wellbeing
          </motion.p>

          <motion.h2
            initial={{ opacity: 0, y: 18 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.6, delay: 0.1, ease: easeOut }}
            className="text-[40px] sm:text-[54px] lg:text-[68px] font-serif font-medium leading-[1.02] tracking-[-0.025em] text-balance"
          >
            Better decisions today.
            <br />
            More freedom tomorrow.
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.5, delay: 0.2, ease: easeOut }}
            className="mt-7 text-[16px] leading-[1.7] text-cream/80 max-w-[380px]"
          >
            Explore the ARQAU concept: earned income visibility, controlled access and financial context in one product experience.
          </motion.p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: 0.3, ease: easeOut }}
          className="flex flex-col sm:flex-row lg:flex-col items-start gap-4"
        >
          <a href="/signup" className="inline-flex items-center gap-2 bg-cream text-ink px-6 py-3.5 rounded-[10px] font-semibold text-[15px] hover:bg-white transition-colors">
            Get started <ArrowRight size={16} />
          </a>
          <a href="#how-it-works" className="inline-flex items-center gap-2 text-cream font-semibold text-[15px] border-b border-cream/40 pb-0.5 hover:border-cream transition-colors">
            See how it works
          </a>
        </motion.div>
      </div>
    </section>
  );
}
