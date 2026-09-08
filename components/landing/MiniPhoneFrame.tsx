import { ReactNode } from "react";

export default function MiniPhoneFrame({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`relative w-[208px] h-[426px] shrink-0 rounded-[32px] bg-near-black p-[7px] shadow-[0_34px_70px_-25px_rgba(20,15,10,0.44)] ${className}`}
    >
      <div className="relative w-full h-full rounded-[26px] overflow-hidden bg-cream border border-black/40">
        <div className="absolute top-[7px] left-1/2 -translate-x-1/2 w-[56px] h-[14px] bg-near-black rounded-full z-20" />
        {children}
      </div>
    </div>
  );
}
