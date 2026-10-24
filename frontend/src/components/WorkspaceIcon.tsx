const paths = {
  activity:
    "M3 17h4l4-10 4 7 3-5h3M17 17l4 4m-4-4a4 4 0 1 0-8 0 4 4 0 0 0 8 0Z",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  chart: "M4 19V5m0 14h16M8 14l4-5 4 2 4-6",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6",
  globe:
    "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z",
  people:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.9M13 3.1a4 4 0 0 1 0 7.8M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  finance: "M3 21h18M5 21V10m5 11V10m4 11V10m5 11V10M2 7l10-5 10 5v3H2V7Z",
  file: "M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 13h8m-8 4h8",
  search: "m21 21-5-5m2-6a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z",
  close: "m6 6 12 12M6 18 18 6",
} as const;

/** Draw the compact line icons used throughout the research terminal. */
export default function WorkspaceIcon({ name }: { name: keyof typeof paths }) {
  return (
    <svg
      aria-hidden="true"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name]} />
    </svg>
  );
}
