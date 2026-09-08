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
      className={`rounded-[18px] bg-cream/95 backdrop-blur-sm border border-ink/[0.08] shadow-[0_24px_50px_-24px_rgba(30,20,10,0.32)] p-[18px] ${className}`}
    >
      {children}
    </div>
  );
}
