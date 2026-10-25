import {
  useEffect,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";
import { animate, m, useMotionValue } from "motion/react";
import { useMotionPreference } from "./provider";

type AmbientMode = "drift" | "counter-drift" | "orbit" | "flyby";

/** Run slow decorative motion centrally while reduced-motion users stay still. */
export function MotionAmbient({
  mode,
  children,
  ...props
}: Omit<
  ComponentPropsWithoutRef<"div">,
  "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart"
> & {
  mode: AmbientMode;
  children: ReactNode;
}) {
  const reduced = useMotionPreference();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useMotionValue(0);
  useEffect(() => {
    x.jump(0);
    y.jump(0);
    rotate.jump(0);
    if (reduced) return;
    const animations =
      mode === "orbit"
        ? [
            animate(x, [0, 7, 0, -7, 0], {
              duration: 22,
              ease: "linear",
              repeat: Infinity,
            }),
            animate(y, [0, -7, 0, 7, 0], {
              duration: 22,
              ease: "linear",
              repeat: Infinity,
            }),
            animate(rotate, [0, 2, 0, -2, 0], {
              duration: 28,
              ease: "linear",
              repeat: Infinity,
            }),
          ]
        : mode === "flyby"
          ? [
              animate(x, [-100, -48, 30, 94, 42, -42, -100], {
                duration: 14,
                ease: "linear",
                repeat: Infinity,
              }),
              animate(y, [34, -34, -58, -18, 40, 64, 34], {
                duration: 14,
                ease: "linear",
                repeat: Infinity,
              }),
              animate(rotate, [-35, -8, 22, 72, 132, 218, 325], {
                duration: 14,
                ease: "linear",
                repeat: Infinity,
              }),
            ]
          : [
              animate(x, mode === "drift" ? [0, 42, -30, 0] : [0, -38, 34, 0], {
                duration: mode === "drift" ? 18 : 22,
                ease: "linear",
                repeat: Infinity,
              }),
              animate(y, mode === "drift" ? [0, -26, 18, 0] : [0, 24, -20, 0], {
                duration: mode === "drift" ? 20 : 24,
                ease: "linear",
                repeat: Infinity,
              }),
              animate(
                rotate,
                mode === "drift" ? [0, 1.5, -1, 0] : [0, -1, 1.25, 0],
                {
                  duration: mode === "drift" ? 26 : 30,
                  ease: "linear",
                  repeat: Infinity,
                },
              ),
            ];
    return () => {
      animations.forEach((animation) => animation.stop());
      x.jump(0);
      y.jump(0);
      rotate.jump(0);
    };
  }, [mode, reduced, rotate, x, y]);
  return (
    <m.div
      {...props}
      aria-hidden="true"
      data-motion-ambient={mode}
      style={{ ...props.style, x, y, rotate }}
    >
      {children}
    </m.div>
  );
}
