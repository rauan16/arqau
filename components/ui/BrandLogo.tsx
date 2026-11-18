import Image from "next/image";

export type BrandLogoProps = {
  /**
   * Rendered square box size in pixels. The mark itself occupies ~41% of the
   * logo canvas, so this value is the full image box, not the glyph height.
   */
  size?: number;
  /** Extra classes for the wrapper span. */
  className?: string;
};

/**
 * The ARQAU brand mark.
 *
 * Single source of truth for the logo so the header, footer, auth screens and
 * in-app chrome never drift apart. The artwork is served from `/logo.png`
 * unchanged: `object-contain` keeps the original square proportions and never
 * clips the top or bottom of the letterform, and width/height are always equal
 * so the image is never stretched.
 */
export default function BrandLogo({ size = 52, className = "" }: BrandLogoProps) {
  return (
    <Image
      src="/logo.png"
      alt="ARQAU"
      width={size}
      height={size}
      sizes={`${size}px`}
      priority
      className={`shrink-0 object-contain ${className}`}
    />
  );
}
