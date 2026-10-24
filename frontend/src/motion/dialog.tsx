import {
  useEffect,
  useImperativeHandle,
  useRef,
  type ComponentPropsWithoutRef,
  type Ref,
} from "react";
import {
  animate,
  m,
  useMotionValue,
  type AnimationPlaybackControls,
  type MotionStyle,
} from "motion/react";
import { useMotionPreference } from "./provider";
import { motionGeometry, springPreset } from "./tokens";

export interface MotionDialogHandle {
  showModal(): void;
  close(): void;
}
/** Native modal with cancellable spring exits; focus stays trapped until native close. */
export function MotionDialog({
  ref,
  onCancel,
  onClose,
  children,
  ...props
}: Omit<
  ComponentPropsWithoutRef<"dialog">,
  "open" | "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart"
> & { ref?: Ref<MotionDialogHandle> }) {
  const element = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const generation = useRef(0);
  const phase = useRef<"closed" | "open" | "closing">("closed");
  const animations = useRef<AnimationPlaybackControls[]>([]);
  const reduced = useMotionPreference();
  const x = useMotionValue(motionGeometry.panelOffset as number);
  const opacity = useMotionValue(0);
  const stop = () => {
    generation.current++;
    animations.current.forEach((animation) => animation.stop());
  };
  const close = () => {
    const node = element.current;
    if (!node?.open) return;
    stop();
    phase.current = "closing";
    const version = generation.current;
    if (reduced) {
      x.jump(motionGeometry.panelOffset);
      opacity.jump(0);
      phase.current = "closed";
      node.close();
      return;
    }
    const movement = animate(
      x,
      motionGeometry.panelOffset,
      springPreset("defaultSpatial"),
    );
    const fade = animate(opacity, 0, springPreset("defaultEffects"));
    animations.current = [movement, fade];
    void Promise.all([movement, fade]).then(() => {
      if (version === generation.current && node.open) {
        phase.current = "closed";
        node.close();
      }
    });
  };
  useImperativeHandle(ref, () => ({
    showModal() {
      const node = element.current;
      if (!node) return;
      stop();
      if (!node.open) {
        opener.current =
          document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null;
        x.jump(motionGeometry.panelOffset);
        opacity.jump(0);
        node.showModal();
      }
      phase.current = "open";
      if (reduced) {
        x.jump(0);
        opacity.jump(1);
      } else
        animations.current = [
          animate(x, 0, springPreset("defaultSpatial")),
          animate(opacity, 1, springPreset("defaultEffects")),
        ];
    },
    close,
  }));
  useEffect(() => {
    if (!reduced) return;
    stop();
    if (phase.current === "closing") {
      phase.current = "closed";
      element.current?.close();
    }
    x.jump(phase.current === "open" ? 0 : motionGeometry.panelOffset);
    opacity.jump(phase.current === "open" ? 1 : 0);
  }, [reduced, x, opacity]);
  useEffect(() => {
    const node = element.current;
    return () => {
      stop();
      node?.close();
    };
  }, []);
  return (
    <m.dialog
      {...props}
      ref={element}
      data-motion-dialog=""
      style={
        {
          ...props.style,
          x,
          opacity,
          "--motion-backdrop-opacity": opacity,
        } as MotionStyle
      }
      onCancel={(event) => {
        onCancel?.(event);
        if (!event.defaultPrevented) {
          event.preventDefault();
          close();
        }
      }}
      onClose={(event) => {
        if (element.current?.open) return;
        phase.current = "closed";
        if (opener.current?.isConnected) opener.current.focus();
        onClose?.(event);
      }}
    >
      {children}
    </m.dialog>
  );
}
