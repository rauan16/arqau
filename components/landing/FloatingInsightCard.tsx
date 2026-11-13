import { ReactNode } from "react";

export default function FloatingInsightCard({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-[12px] border border-ink/[0.1] bg-white/95 p-3 shadow-[0_18px_32px_-22px_rgba(20,15,10,0.45)] sm:p-3.5 ${className}`}
    >
      {children}
    </div>
  );
}
