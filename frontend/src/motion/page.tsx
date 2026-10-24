import { useLayoutEffect, useRef, type ComponentPropsWithoutRef } from "react";
import {
  animate,
  m,
  useMotionValue,
  type AnimationPlaybackControls,
} from "motion/react";
import { useMotionPreference } from "./provider";
import { motionGeometry, springPreset } from "./tokens";

/** Animate route arrivals without retaining old pages, delaying navigation or remounting children. */
export function MotionPage({
  routeKey,
  style,
  ...props
}: Omit<
  ComponentPropsWithoutRef<"main">,
  "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart"
> & { routeKey: string }) {
  const element = useRef<HTMLElement>(null);
  const previous = useRef(routeKey);
  const generation = useRef(0);
  const moving = useRef(false);
  const animations = useRef<AnimationPlaybackControls[]>([]);
  const reduced = useMotionPreference();
  const y = useMotionValue(0);
  const opacity = useMotionValue(1);

  useLayoutEffect(() => {
    const changed = previous.current !== routeKey;
    previous.current = routeKey;
    const version = ++generation.current;
    const settle = () => {
      y.jump(0);
      opacity.jump(1);
      moving.current = false;
    };
    if (changed) {
      element.current?.scrollTo({ top: 0, left: 0, behavior: "instant" });
      element.current?.focus({ preventScroll: true });
    }
    if (reduced) settle();
    else if (changed) {
      // A rapid navigation retargets the moving values instead of jumping back to the start.
      if (!moving.current) {
        y.jump(motionGeometry.pageOffset);
        opacity.jump(0.65);
      }
      moving.current = true;
      const movement = animate(y, 0, springPreset("defaultSpatial"));
      const fade = animate(opacity, 1, springPreset("defaultEffects"));
      animations.current = [movement, fade];
      void Promise.all([movement, fade]).then(() => {
        if (version === generation.current) moving.current = false;
      });
    }
    return () => {
      generation.current++;
      animations.current.forEach((animation) => animation.stop());
    };
  }, [routeKey, reduced, y, opacity]);

  return (
    <m.main
      {...props}
      ref={element}
      style={{ ...style, y, opacity }}
      data-motion-page=""
    />
  );
}
