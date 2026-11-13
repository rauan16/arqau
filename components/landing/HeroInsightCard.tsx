import { ReactNode } from "react";

export default function HeroInsightCard({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-[22px] border border-white/70 bg-white/[0.94] p-4 shadow-[0_24px_52px_-28px_rgba(17,14,12,0.62)] sm:p-[18px]">
      {children}
    </div>
  );
}
