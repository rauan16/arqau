import { ReactNode } from "react";

export default function PhoneFrame({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`relative aspect-[159/323] w-full max-w-[var(--hero-device-width)] rounded-[15%] bg-near-black p-[3.1%] shadow-[0_40px_72px_-34px_rgba(20,15,10,0.38)] ${className}`}
    >
      <div className="relative h-full w-full overflow-hidden rounded-[13.5%] border border-black/40 bg-cream">
        {/* dynamic island */}
        <div className="absolute left-1/2 top-[1.6%] z-20 h-[3.4%] w-[27%] -translate-x-1/2 rounded-full bg-near-black" />
        <div className="h-full w-full overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
