/** Motion preference helper. Kept out of components so it can be tested with a fake `matchMedia`. */

/**
 * True when the visitor asked the OS/browser to reduce motion. When `matchMedia` is not
 * available we cannot tell, so we choose the safe answer: no motion.
 */
export function prefersReducedMotion(win: { matchMedia?: (query: string) => { matches: boolean } } = window): boolean {
  if (typeof win.matchMedia !== 'function') return true
  return win.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export interface ControlsConfig {
  autoRotate: boolean
  autoRotateSpeed: number
  /** Smoothed (inertial) orbit controls. Off under reduced motion so the view stops when the user does. */
  enableDamping: boolean
  /** 'demand' redraws only when something changes, so a still view does not keep the GPU busy. */
  frameloop: 'always' | 'demand'
}

/** Orbit-control and render-loop settings for the 3D view. Reduced motion means: nothing moves on its own. */
export function controlsConfig(reducedMotion: boolean): ControlsConfig {
  return reducedMotion
    ? { autoRotate: false, autoRotateSpeed: 0, enableDamping: false, frameloop: 'demand' }
    : { autoRotate: true, autoRotateSpeed: 0.6, enableDamping: true, frameloop: 'always' }
}
