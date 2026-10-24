# Shared Expressive motion

Use `MotionProvider` once at the root. Import UI primitives from `src/motion`;
keep Motion engine imports and numeric animation settings inside this directory.
The dependency is pinned; updates must run motion lifecycle and browser tests.

- `MotionButton` preserves native button props/ref and form behaviour.
- `MotionLink` preserves Router link props; `.button` links get press feedback.
- `MotionNavLink`, `MotionInput`, `MotionSelect` keep native semantics and use effects.
- `MotionDisclosure summary={...}` owns measured height, chevron and inert content.
- `MotionDialog` exposes `showModal()`/`close()` through `MotionDialogHandle`.
  It retains native modality during exit, cancels obsolete exits on reopen, and
  restores focus after close. Escape and navigation cleanup share this lifecycle.
- `MotionSelection` groups related active controls. Render `MotionIndicator`
  inside the active control only; it moves between selected controls in that group.
- `MotionState stateKey={status}` preserves its child DOM and live region. Keys
  represent actual state changes, never poll timestamps or response object identity.

```tsx
<MotionSelection>
  {tabs.map((tab) => (
    <MotionButton
      key={tab.id}
      role="tab"
      aria-selected={selected === tab.id}
      onClick={() => setSelected(tab.id)}
    >
      {tab.name}
      {selected === tab.id && <MotionIndicator />}
    </MotionButton>
  ))}
</MotionSelection>
```

Fast spatial springs serve small controls; default spatial serves panels and
content expansion; slow spatial is reserved for larger future surfaces. Effects
springs are critically damped and serve opacity/state colour. The six parameter
pairs match the pinned AndroidX source; rendering and stop tolerances differ
between browser and Compose, so this is not a claim of pixel-identical rendering.

OS reduced motion takes effect live and makes transitions immediate. Do not
animate chart values, table rows, search ordering, polling timestamps or static
cards. Animation never delays a backend write or replaces status text.

See NOTICE.md and LICENSE.txt for upstream attribution. Tests compare analytical
unit-mass spring trajectories, native semantics and interruptible modal behaviour.
