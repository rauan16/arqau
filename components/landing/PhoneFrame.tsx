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
      className={`relative w-[318px] h-[646px] rounded-[48px] bg-near-black p-[10px] shadow-[0_56px_100px_-28px_rgba(20,15,10,0.5)] ${className}`}
    >
      <div className="relative w-full h-full rounded-[40px] overflow-hidden bg-cream border border-black/40">
        {/* dynamic island */}
        <div className="absolute top-[10px] left-1/2 -translate-x-1/2 w-[86px] h-[22px] bg-near-black rounded-full z-20" />
        <div className="w-full h-full overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
