import { createRef, useRef } from "react";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { spring } from "motion";
import { expressiveTokens, springPreset } from "../../src/motion/tokens";
import {
  MotionProvider,
  MotionButton,
  MotionLink,
  MotionDisclosure,
  MotionDialog,
  MotionState,
  type MotionDialogHandle,
} from "../../src/motion";

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

it.each(Object.keys(expressiveTokens) as (keyof typeof expressiveTokens)[])(
  "matches the Compose unit-mass trajectory for %s",
  (preset) => {
    const token = expressiveTokens[preset];
    const options = springPreset(preset);
    expect(options.mass).toBe(1);
    expect(options.damping).toBeCloseTo(
      2 * token.dampingRatio * Math.sqrt(token.stiffness),
    );
    const trajectory = spring({ ...options, keyframes: [0, 1] });
    const frequency = Math.sqrt(token.stiffness);
    for (const milliseconds of [16, 50, 100]) {
      const t = milliseconds / 1000;
      const z = token.dampingRatio;
      const damped = frequency * Math.sqrt(1 - z * z);
      const expected =
        z === 1
          ? 1 - (1 + frequency * t) * Math.exp(-frequency * t)
          : 1 -
            Math.exp(-z * frequency * t) *
              (Math.cos(damped * t) +
                ((z * frequency) / damped) * Math.sin(damped * t));
      expect(trajectory.next(milliseconds).value).toBeCloseTo(expected, 5);
    }
  },
);

it("preserves button refs, submission type, handlers and disabled behaviour", () => {
  const ref = createRef<HTMLButtonElement>();
  const click = vi.fn();
  render(
    <MotionProvider reducedMotion>
      <MotionButton ref={ref} type="submit" disabled onClick={click}>
        Submit
      </MotionButton>
    </MotionProvider>,
  );
  expect(ref.current).toBe(screen.getByRole("button"));
  expect(ref.current).toHaveAttribute("type", "submit");
  fireEvent.click(ref.current!);
  expect(click).not.toHaveBeenCalled();
});

it("preserves router links and navigation attributes", () => {
  render(
    <MemoryRouter>
      <MotionProvider reducedMotion>
        <MotionLink to="/research/new" target="_blank" className="button">
          Research
        </MotionLink>
      </MotionProvider>
    </MemoryRouter>,
  );
  expect(screen.getByRole("link")).toHaveAttribute("href", "/research/new");
  expect(screen.getByRole("link")).toHaveAttribute("target", "_blank");
});

it("immediately makes collapsed content inert and handles repeated toggles", () => {
  render(
    <MotionProvider reducedMotion>
      <MotionDisclosure summary="Evidence">
        <a href="#source">Source</a>
      </MotionDisclosure>
    </MotionProvider>,
  );
  const trigger = screen.getByRole("button", { name: "Evidence" });
  const panel = document.getElementById(
    trigger.getAttribute("aria-controls")!,
  )!;
  expect(panel).toHaveAttribute("inert");
  fireEvent.click(trigger);
  expect(trigger).toHaveAttribute("aria-expanded", "true");
  expect(panel).not.toHaveAttribute("inert");
  fireEvent.click(trigger);
  expect(panel).toHaveAttribute("inert");
  expect(trigger).toHaveAttribute("aria-expanded", "false");
});

function DialogExample() {
  const ref = useRef<MotionDialogHandle>(null);
  return (
    <>
      <button onClick={() => ref.current?.showModal()}>Open</button>
      <MotionDialog ref={ref} aria-label="Evidence">
        <button onClick={() => ref.current?.close()}>Close</button>
      </MotionDialog>
    </>
  );
}
it("closes immediately with reduced motion and restores the opener", () => {
  render(
    <MotionProvider reducedMotion>
      <DialogExample />
    </MotionProvider>,
  );
  const opener = screen.getByText("Open");
  opener.focus();
  fireEvent.click(opener);
  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveAttribute("open");
  fireEvent.click(screen.getByText("Close"));
  expect(dialog).not.toHaveAttribute("open");
  expect(opener).toHaveFocus();
});

it("cancels an obsolete close when reopened and closes on unmount", async () => {
  const ref = createRef<MotionDialogHandle>();
  const view = render(
    <MotionProvider>
      <MotionDialog ref={ref} aria-label="Evidence">
        Source
      </MotionDialog>
    </MotionProvider>,
  );
  act(() => ref.current!.showModal());
  const dialog = screen.getByRole("dialog");
  act(() => {
    ref.current!.close();
    ref.current!.showModal();
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 900));
  });
  expect(dialog).toHaveAttribute("open");
  view.unmount();
  expect(dialog).not.toHaveAttribute("open");
});

it("responds to an OS reduced-motion change during an exit", async () => {
  let reduced = false;
  const listeners = new Set<() => void>();
  vi.stubGlobal("matchMedia", () => ({
    matches: reduced,
    addEventListener: (_event: string, cb: () => void) => listeners.add(cb),
    removeEventListener: (_event: string, cb: () => void) =>
      listeners.delete(cb),
  }));
  const ref = createRef<MotionDialogHandle>();
  render(
    <MotionProvider>
      <MotionDialog ref={ref} aria-label="Evidence">
        Source
      </MotionDialog>
    </MotionProvider>,
  );
  act(() => ref.current!.showModal());
  const dialog = screen.getByRole("dialog");
  act(() => ref.current!.close());
  act(() => {
    reduced = true;
    listeners.forEach((listener) => listener());
  });
  await waitFor(() => expect(dialog).not.toHaveAttribute("open"));
});

it("retains a single state node and does not animate identical polling states", () => {
  const view = render(
    <MotionProvider reducedMotion>
      <MotionState stateKey="running">
        <p role="status">Running</p>
      </MotionState>
    </MotionProvider>,
  );
  const status = screen.getByRole("status");
  view.rerender(
    <MotionProvider reducedMotion>
      <MotionState stateKey="running">
        <p role="status">Running</p>
      </MotionState>
    </MotionProvider>,
  );
  expect(screen.getByRole("status")).toBe(status);
  view.rerender(
    <MotionProvider reducedMotion>
      <MotionState stateKey="complete">
        <p role="status">Complete</p>
      </MotionState>
    </MotionProvider>,
  );
  expect(screen.getAllByRole("status")).toHaveLength(1);
  expect(screen.getByRole("status")).toBe(status);
});
