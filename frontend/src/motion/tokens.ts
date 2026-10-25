/**
 * ExpressiveMotionTokens adapted from AndroidX, Copyright 2024 The Android Open
 * Source Project. Licensed under Apache-2.0; see NOTICE.md and LICENSE.txt.
 * Upstream revision: 53bc2d6eef5ae5438d07f0071dc6f698428df978 (v0_14_0).
 */
export const expressiveTokens = {
  fastSpatial: { stiffness: 800, dampingRatio: 0.6 },
  defaultSpatial: { stiffness: 380, dampingRatio: 0.8 },
  slowSpatial: { stiffness: 200, dampingRatio: 0.8 },
  fastEffects: { stiffness: 3800, dampingRatio: 1 },
  defaultEffects: { stiffness: 1600, dampingRatio: 1 },
  slowEffects: { stiffness: 800, dampingRatio: 1 },
} as const;
export type MotionPreset = keyof typeof expressiveTokens;

/** Convert Compose's unit-mass damping ratio into a damping coefficient. */
export function springPreset(preset: MotionPreset) {
  const { stiffness, dampingRatio } = expressiveTokens[preset];
  return {
    type: "spring" as const,
    mass: 1,
    stiffness,
    damping: 2 * dampingRatio * Math.sqrt(stiffness),
    restDelta: 0.001,
    restSpeed: 0.01,
  };
}
export const motionGeometry = {
  pressedScale: 0.97,
  panelOffset: 24,
  pageOffset: 16,
  surfaceLift: -3,
  surfaceScale: 1.006,
} as const;
