import Link from "next/link";
import { ArrowLeft, ArrowUpRight } from "lucide-react";

export default function BusinessPlaceholder({ title, description }: { title: string; description: string }) {
  return <div className="max-w-[820px]"><Link href="/business" className="inline-flex items-center gap-2 text-[13px] font-semibold text-ink-soft hover:text-orange-dark"><ArrowLeft size={15} />Business overview</Link><p className="eyebrow mt-10 mb-4">Business workspace</p><h1 className="text-[48px] font-extrabold leading-none tracking-[-0.04em]">{title}</h1><p className="mt-5 max-w-[560px] text-[16px] leading-relaxed text-ink-soft">{description}</p><div className="mt-10 rounded-[20px] border border-ink/[0.08] bg-cream-orange p-6"><p className="text-[13px] font-semibold">Foundation ready</p><p className="mt-2 text-[14px] leading-relaxed text-ink-soft">This workspace is ready for the next connected data layer. It shares the same navigation, tokens and business registration flow as ARQAU.</p><Link href="/business/register" className="mt-5 inline-flex items-center gap-2 text-[13px] font-bold text-orange-dark">Update business profile <ArrowUpRight size={15} /></Link></div></div>;
}
