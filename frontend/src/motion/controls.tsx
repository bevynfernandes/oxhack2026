import {
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ComponentPropsWithRef,
  type Ref,
} from "react";
import { useMotionValueEvent, useSpring } from "motion/react";
import {
  Link,
  NavLink,
  type LinkProps,
  type NavLinkProps,
} from "react-router-dom";
import { useMotionPreference } from "./provider";
import { motionGeometry, springPreset } from "./tokens";

/** Keep native events/semantics and update style through motion values, not React frames. */
function useControlMotion<T extends HTMLElement>(
  ref: Ref<T> | undefined,
  disabled = false,
  spatial = true,
) {
  const element = useRef<T>(null);
  useImperativeHandle(ref, () => element.current!);
  const reduced = useMotionPreference();
  const [pressed, setPressed] = useState(false);
  const [hovered, setHovered] = useState(false);
  const scale = useSpring(1, springPreset("fastSpatial"));
  const shade = useSpring(0, springPreset("fastEffects"));
  useMotionValueEvent(scale, "change", (value) => {
    if (element.current) element.current.style.scale = String(value);
  });
  useMotionValueEvent(shade, "change", (value) => {
    element.current?.style.setProperty("--motion-state-opacity", String(value));
  });
  useEffect(() => {
    const node = element.current;
    if (!node) return;
    const down = (event: PointerEvent) => {
      if (event.button === 0) setPressed(true);
    };
    const up = () => setPressed(false);
    const enter = (event: PointerEvent) => {
      if (event.pointerType !== "touch") setHovered(true);
    };
    const leave = () => {
      setHovered(false);
      setPressed(false);
    };
    const keyDown = (event: KeyboardEvent) => {
      if (
        event.key === "Enter" ||
        (event.key === " " && node.tagName === "BUTTON")
      )
        setPressed(true);
    };
    node.addEventListener("pointerdown", down);
    node.addEventListener("pointerenter", enter);
    node.addEventListener("pointerleave", leave);
    node.addEventListener("keydown", keyDown);
    node.addEventListener("blur", up);
    return () => {
      node.removeEventListener("pointerdown", down);
      node.removeEventListener("pointerenter", enter);
      node.removeEventListener("pointerleave", leave);
      node.removeEventListener("keydown", keyDown);
      node.removeEventListener("blur", up);
    };
  }, []);
  useEffect(() => {
    if (!pressed) return;
    const release = () => setPressed(false);
    window.addEventListener("pointerup", release);
    window.addEventListener("pointercancel", release);
    window.addEventListener("keyup", release);
    window.addEventListener("blur", release);
    return () => {
      window.removeEventListener("pointerup", release);
      window.removeEventListener("pointercancel", release);
      window.removeEventListener("keyup", release);
      window.removeEventListener("blur", release);
    };
  }, [pressed]);
  useEffect(() => {
    const nextScale =
      !disabled && spatial && pressed ? motionGeometry.pressedScale : 1;
    const nextShade = disabled ? 0 : pressed ? 0.1 : hovered ? 0.05 : 0;
    if (reduced || disabled) {
      scale.jump(nextScale);
      shade.jump(nextShade);
    } else {
      scale.set(nextScale);
      shade.set(nextShade);
    }
  }, [disabled, spatial, pressed, hovered, reduced, scale, shade]);
  return element;
}

const stateLayer =
  "linear-gradient(rgb(0 0 0 / var(--motion-state-opacity, 0)), rgb(0 0 0 / var(--motion-state-opacity, 0)))";

/** Native button with shared press and state-layer feedback. */
export function MotionButton({
  ref,
  ...props
}: ComponentPropsWithRef<"button">) {
  const element = useControlMotion(ref, props.disabled);
  return (
    <button
      {...props}
      ref={element}
      style={{ backgroundImage: stateLayer, ...props.style }}
      data-motion-control=""
    />
  );
}
/** Router link; only button-style links receive press scaling. */
export function MotionLink({
  ref,
  ...props
}: LinkProps & { ref?: Ref<HTMLAnchorElement> }) {
  const element = useControlMotion(
    ref,
    props["aria-disabled"] === true,
    Boolean(props.className?.split(" ").includes("button")),
  );
  return (
    <Link
      {...props}
      ref={element}
      style={{ backgroundImage: stateLayer, ...props.style }}
      data-motion-control=""
    />
  );
}
/** Router navigation with effects feedback and unchanged active-state semantics. */
export function MotionNavLink({
  ref,
  ...props
}: NavLinkProps & { ref?: Ref<HTMLAnchorElement> }) {
  const element = useControlMotion(ref, false, false);
  return (
    <NavLink
      {...props}
      ref={element}
      style={{ backgroundImage: stateLayer, ...props.style }}
      data-motion-control=""
    />
  );
}
/** Native input: effects only, with no replacement of the browser's editing UI. */
export function MotionInput({ ref, ...props }: ComponentPropsWithRef<"input">) {
  const element = useControlMotion(ref, props.disabled, false);
  return (
    <input
      {...props}
      ref={element}
      style={{ backgroundImage: stateLayer, ...props.style }}
      data-motion-control=""
    />
  );
}
/** Native select: effects only, preserving platform keyboard and popup behaviour. */
export function MotionSelect({
  ref,
  ...props
}: ComponentPropsWithRef<"select">) {
  const element = useControlMotion(ref, props.disabled, false);
  return (
    <select
      {...props}
      ref={element}
      style={{ backgroundImage: stateLayer, ...props.style }}
      data-motion-control=""
    />
  );
}
