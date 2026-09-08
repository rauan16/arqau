"use client";

import { motion } from "framer-motion";

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function BrandStatement() {
  return (
    <section className="py-28 lg:py-40 bg-cream">
      <div className="container-arqau">
        <div className="statement-frame max-w-[1100px]">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.7, ease: easeOut }}
          className="text-[38px] sm:text-[52px] lg:text-[68px] leading-[1.04] font-medium tracking-[-0.03em] max-w-[940px] text-balance"
        >
          Getting paid earlier is only half the story.{" "}
          <span className="font-serif italic text-orange">Knowing what to do with it is the other half.</span>
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, delay: 0.2, ease: easeOut }}
          className="mt-8 text-[17px] leading-[1.7] text-ink-soft max-w-[480px]"
        >
          ARQAU is building the financial intelligence layer between earned income and everyday decisions.
        </motion.p>
        </div>
      </div>
    </section>
  );
}
