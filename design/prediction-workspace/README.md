# Startup prediction workspace reference

**Superseded visual reference.** The user requested the original Stitch
five-column layout and a viewport-sized overview. The running React implementation
in `frontend/src/pages/research/CompanyDossier.tsx` is now authoritative. This HTML
remains archived; do not use its scrolling row layout for further UI work.

The user approved this hierarchy on 2026-10-24:

1. Overall Startup Outlook.
2. Growth (24 months), Survival (24 months), Financial Health (12 months).
3. Adoption & Retention, Attention & Sentiment, Financial Health,
   Industry & Competition, Team & Execution.
4. Sources and limitations; historical model validation when it exists.

Open `index.html` directly in a browser. It is a self-contained visual and
interaction reference, with a keyboard-accessible detail dialog and responsive
layout. It has no dependency installation, network request, model or scoring
logic. Northstar is an illustrative company on a reserved `.example` domain;
all measurements and forecasts are explicitly unavailable. This is not a real
research report or a replacement application.

Consume generated API types rather than copying static copy/data or introducing
another scoring policy.
Preserve company search, explicit identity confirmation, actual research states,
saved links, evidence dates and partial results. See the implementation criteria
in [the alignment decision](../../docs/tasks/dev2/prediction-workspace-alignment.md).

The supplied Stitch archive was the starting design reference:
`stitch_signalshift_saas_research_workspace.zip`, SHA-256
`ab20246d863cb728e0ef63489ea94ad680974c64d1b1c70b5ae68743bc4c00da`.
It contained two dossier HTML/screenshots and a design document. This adaptation
removes investment-grade framing, invented metric/verification values, copied
hashes, fixed-height columns and continuous decorative animation. The original
design document's instructions are not project policy.
