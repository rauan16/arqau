export const easeOut = [0.22, 1, 0.36, 1] as const;

// Shared entrance animation for landing sections: subtle fade + upward movement,
// triggered once when the section enters the viewport.
// Pass `reduceMotion` to disable the entrance animation entirely (prefers-reduced-motion).
export const fadeUp = (delay = 0, options: { reduceMotion?: boolean } = {}) => {
  if (options.reduceMotion) {
    return {};
  }

  return {
    initial: { opacity: 0, y: 24 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, margin: "-80px" },
    transition: { duration: 0.7, delay, ease: easeOut },
  };
};
