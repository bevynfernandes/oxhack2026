import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";
import { animate, LayoutGroup, m, useMotionValue } from "motion/react";
import { MotionButton } from "./controls";
import { useMotionPreference, useMotionTransition } from "./provider";
import { motionGeometry } from "./tokens";

/** Give grouped interactive content shared spring feedback without changing its semantics. */
export function MotionSurface({
  children,
  onPointerEnter,
  onPointerLeave,
  onFocusCapture,
  onBlurCapture,
  ...props
}: Omit<
  ComponentPropsWithoutRef<"div">,
  "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart"
> & { children: ReactNode }) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const reduced = useMotionPreference();
  const transition = useMotionTransition("defaultSpatial");
  const active = !reduced && (hovered || focused);
  return (
    <m.div
      {...props}
      data-motion-surface=""
      initial={false}
      animate={{
        y: active ? motionGeometry.surfaceLift : 0,
        scale: active ? motionGeometry.surfaceScale : 1,
      }}
      transition={transition}
      onPointerEnter={(event) => {
        if (event.pointerType !== "touch") setHovered(true);
        onPointerEnter?.(event);
      }}
      onPointerLeave={(event) => {
        setHovered(false);
        onPointerLeave?.(event);
      }}
      onFocusCapture={(event) => {
        setFocused(true);
        onFocusCapture?.(event);
      }}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
          setFocused(false);
        onBlurCapture?.(event);
      }}
    >
      {children}
    </m.div>
  );
}

/** Group indicator identities without adding a layout wrapper. */
export function MotionSelection({ children }: { children: ReactNode }) {
  const id = useId();
  return <LayoutGroup id={id}>{children}</LayoutGroup>;
}
/** Place inside the active control; the group supplies shared spring geometry. */
export function MotionIndicator() {
  return (
    <m.span
      aria-hidden="true"
      className="motion-indicator"
      layoutId="selection"
      transition={useMotionTransition("fastSpatial")}
    />
  );
}

/** Animate an actual state change without remounting content or duplicating announcements. */
export function MotionState({
  stateKey,
  children,
  ...props
}: ComponentPropsWithoutRef<"div"> & {
  stateKey: string;
  children: ReactNode;
}) {
  const opacity = useMotionValue(1);
  const previous = useRef(stateKey);
  const transition = useMotionTransition("defaultEffects");
  const reduced = useMotionPreference();
  useEffect(() => {
    if (previous.current === stateKey) return;
    previous.current = stateKey;
    if (reduced) {
      opacity.jump(1);
      return;
    }
    opacity.jump(0.65);
    const animation = animate(opacity, 1, transition);
    return () => {
      animation.stop();
      opacity.jump(1);
    };
  }, [stateKey, reduced, opacity, transition]);
  return (
    <div {...props}>
      <m.div style={{ opacity }}>{children}</m.div>
    </div>
  );
}

/** Accessible disclosure with measured, interruptible height and immediate inertness on close. */
export function MotionDisclosure({
  summary,
  children,
  defaultOpen = false,
  className = "",
  ...props
}: Omit<ComponentPropsWithoutRef<"div">, "onToggle"> & {
  summary: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [height, setHeight] = useState(0);
  const content = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const transition = useMotionTransition("defaultSpatial");
  const chevron = useMotionTransition("fastSpatial");
  useLayoutEffect(() => {
    const node = content.current;
    if (!node) return;
    const measure = () => setHeight(node.getBoundingClientRect().height);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const toggle = () => {
    if (open && content.current?.contains(document.activeElement))
      trigger.current?.focus();
    setOpen(!open);
  };
  return (
    <div {...props} className={`motion-disclosure ${className}`}>
      <MotionButton
        type="button"
        className="motion-disclosure-trigger"
        ref={trigger}
        aria-expanded={open}
        aria-controls={id}
        onClick={toggle}
      >
        <m.span
          aria-hidden="true"
          className="motion-chevron"
          animate={{ rotate: open ? 90 : 0 }}
          transition={chevron}
        >
          ›
        </m.span>
        <span>{summary}</span>
      </MotionButton>
      <m.div
        id={id}
        className="motion-disclosure-clip"
        initial={false}
        animate={{ height: open ? height : 0 }}
        transition={transition}
        inert={!open}
        aria-hidden={!open}
      >
        <div ref={content} className="motion-disclosure-content">
          {children}
        </div>
      </m.div>
    </div>
  );
}
