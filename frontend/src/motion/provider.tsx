import {
  createContext,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { LazyMotion, domMax, MotionConfig } from "motion/react";
import { springPreset, type MotionPreset } from "./tokens";

const query = "(prefers-reduced-motion: reduce)";
function subscribe(listener: () => void) {
  const media = window.matchMedia?.(query);
  media?.addEventListener("change", listener);
  return () => media?.removeEventListener("change", listener);
}
function ignoreSubscription() {
  return () => {};
}
function snapshot() {
  return window.matchMedia?.(query).matches ?? false;
}
const ReducedMotion = createContext<boolean | null>(null);

/** Subscribe to OS changes; the server defaults to immediate rendering. */
export function useMotionPreference() {
  const inherited = useContext(ReducedMotion);
  const system = useSyncExternalStore(
    inherited === null ? subscribe : ignoreSubscription,
    snapshot,
    () => true,
  );
  return inherited ?? system;
}

/** Supply the shared engine once, preserving instant reduced-motion feedback. */
export function MotionProvider({
  children,
  reducedMotion,
}: {
  children: ReactNode;
  reducedMotion?: boolean;
}) {
  const system = useMotionPreference();
  const reduced = reducedMotion ?? system;
  return (
    <ReducedMotion.Provider value={reduced}>
      <LazyMotion features={domMax} strict>
        <MotionConfig reducedMotion={reduced ? "always" : "never"}>
          {children}
        </MotionConfig>
      </LazyMotion>
    </ReducedMotion.Provider>
  );
}

/** Get one named physical transition, or an immediate reduced-motion update. */
export function useMotionTransition(preset: MotionPreset) {
  const reduced = useMotionPreference();
  return useMemo(
    () => (reduced ? { duration: 0 } : springPreset(preset)),
    [reduced, preset],
  );
}
