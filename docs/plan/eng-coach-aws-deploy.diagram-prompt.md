# Design-agent prompt — Eng-Coach AWS architecture visuals

> **How to use this file.** Hand this entire document to a design/diagramming agent
> (or paste it as a prompt). It is self-contained: every box, edge, label, and
> requirement-ID chip is specified below, so the agent does **not** need to re-read
> the source architecture doc to produce correct visuals. The source of truth, if
> the agent wants context, is
> [`eng-coach-aws-deploy.architecture.md`](eng-coach-aws-deploy.architecture.md);
> the ASCII diagrams there are what these visuals replace.

---

## ROLE

You are a systems-architecture diagram designer. Produce **five publication-quality
diagrams** that replace the ASCII art in an AWS deployment architecture document.
The audience is senior engineers reviewing a production deployment design; the
diagrams must be *precise* (every label matters — they carry requirement IDs) and
*legible* at a glance (the single most important idea in each diagram must be
obvious before anyone reads a label).

## DELIVERABLE FORMAT (hard requirements)

- **Format:** inline **SVG** (preferred) or a single self-contained **HTML file**
  per diagram. No external assets — no CDN scripts, no remote fonts, no external
  images. Inline everything. (These render inside a strict-CSP artifact host.)
- **Theme-aware:** must be legible in **both light and dark** themes. Use CSS
  variables / `prefers-color-scheme`; never hardcode a single background that
  breaks the other theme. Text contrast ≥ WCAG AA on both.
- **Responsive:** no horizontal page scroll on a ~1000px viewport. Wide diagrams
  scale down or scroll *inside their own container*, not the page.
- **Self-describing:** each diagram has a title and a small legend (see visual
  system below). A colorblind-safe palette (don't rely on red/green alone —
  pair color with shape/label/icon).
- **Fidelity:** reproduce **every** labeled box, edge, and requirement-ID chip
  listed per-diagram below. Do not drop, rename, merge, or invent boxes. The
  requirement IDs (`FR-*`, `NFR-*`, `T1`–`T6`) are load-bearing — render them
  verbatim as small monospace chips attached to the element they annotate.
- **File naming:** `arch-1-shared-plane`, `arch-2a-apprunner`,
  `arch-2b-fargate-alb`, `arch-2c-vpc`, `arch-3-dataflows`.

## VISUAL SYSTEM (shared across all five — consistency matters)

1. **Trust/security boundary zones** are the primary visual language. Use nested
   containers with clearly different treatments:
   - **AWS boundary** — a rounded container labeled "AWS — single region (US),
     single-AZ, one VPC". Everything inside is what we operate.
   - **External SaaS** — a *visually distinct, "outside-the-wall"* container
     (dashed border, muted/desaturated fill, an "external / not migrated" tag).
     WorkOS and Langfuse live here. The point the reader must get instantly:
     **these are NOT ours and do NOT migrate.**
   - **Data plane** — a distinct band/zone inside AWS holding the stateful stores.
   - **Compute tier** — a distinct zone inside AWS holding the two app services.
2. **The "shared plane vs. open fork" concept is the spine of the whole set.**
   Diagram 1 is the *shared invariant plane* — everything that is DECIDED. Diagrams
   2A and 2B are two interchangeable *compute variants* that dock onto that same
   plane. Make this visually unmistakable: 2A and 2B should share an identical
   "docks onto the shared plane" edge/port styling, and each should carry a status
   badge — **2A = "PENDING SSE proof" (amber/caution)**, **2B = "no unresolved
   kill-criterion" (green/confident)**. A reader flipping between 2A and 2B must
   see "same everything below, different compute engine on top."
3. **Requirement chips.** Small monospace pills (e.g. `FR-C5`, `NFR-SEC-1`, `T3`)
   attached to the relevant box/edge. Keep them subordinate (small, low-weight) so
   they annotate without cluttering. Group multiples compactly (`FR-D2/D6`).
4. **Edge semantics — distinguish four edge types** by line style + a tiny label:
   - **HTTPS / client ingress** (solid, bold).
   - **Bearer-forward / internal service-to-service** (solid, medium) — label the
     BFF→backend edge "Bearer forward (no cloud creds in BFF)".
   - **Data-plane access** (solid, thin) — backend → Neon/S3/SSM.
   - **External egress** (dashed) — to WorkOS, Langfuse, LLM providers.
5. **AWS service iconography.** You may use simple, recognizable AWS-service glyphs
   (App Runner, Fargate/ECS, ALB, S3, VPC/IGW, ECR, CloudWatch, IAM, SSM) OR clean
   labeled boxes — but be **consistent** across all five. Neon and WorkOS/Langfuse
   are third-party; give them their own non-AWS treatment. Do **not** imply Neon is
   an AWS-native service (it's a SaaS that runs on AWS).
6. **The single-AZ story must read visually.** This is a deliberate cost trade, not
   an oversight — the design should *look* single-AZ (one AZ column, no mirrored
   standby) and where relevant annotate "no Multi-AZ standby — DR = restore from
   backup". Do not draw a phantom HA standby.

---

## DIAGRAM 1 — Shared invariant plane (`arch-1-shared-plane`) — THE HERO DIAGRAM

The one-view system. Everything except the compute *engine* is fixed; this is that
fixed plane. Center a placeholder "COMPUTE TIER (see §2 — App Runner **or**
Fargate+ALB)" box to show the fork slots in here.

**Zones & boxes:**

- **Clients** (left, outside AWS): three stacked client types — `Browser`,
  `Tauri (macOS)`, `Capacitor (iOS)`. One shared HTTPS edge into AWS.
- **External SaaS** (top, dashed "outside-the-wall" zone, tag "unchanged — NOT
  migrated", chip `FR-M8/O10`): `WorkOS (authN)` and `Langfuse Cloud`.
- **AWS boundary** (the big rounded container): label "AWS — single region (US),
  single-AZ, one VPC".
  - **Compute tier** (zone inside AWS):
    - `Frontend BFF (Next.js)` — chips `FR-M4/M9/M10`, tag "WorkOS @ BFF".
    - `Backend-combined` box containing two stacked sub-items:
      `middleware + agent` and `searxng sidecar` — chip `FR-C8` on the box,
      tag "in-process relay".
    - Edge BFF→Backend labeled **"Bearer forward (no cloud creds in BFF)"** chip `T5`.
    - Placeholder note in/near the compute tier: "(engine chosen in §2)".
  - **Data plane** (a labeled band "DATA PLANE (shared, single-AZ)") — five stores
    the backend connects to, left→right:
    1. `Neon — Postgres + pgvector` chip `T3`, with a call-out below the whole band:
       **"3 loads: checkpointer + thread-store + pgvector (one DATABASE_URL)"**.
    2. `S3 — agent-facts` chips `FR-D2/D6`.
    3. `S3 — trust-traces` chips `FR-D3/D7`.
    4. `SSM Parameter Store (SecureString)` chips `FR-S2 · T2`.
    5. `ephemeral /tmp (offload + blackbox)` chips `FR-C7/D4`, tag **"NO EFS"**.
  - **Cross-cutting footer strip** inside AWS (three compact rows):
    - `IDENTITY: per-service IAM task roles (least privilege)` chip `T5` — with two
      sub-bullets: "frontend role → 2 WorkOS secrets ONLY (`NFR-SEC-1`)" and
      "backend role → DB/LLM/facts/traces; NOT workos-cookie-pw".
    - `OBSERVABILITY: CloudWatch 3 alarms + AWS Budgets` chip `NFR-OBS-1`.
    - `REGISTRY: ECR (digest-pinned deploys)` chip `NFR-DEPLOY-1`.
- **External egress edges** (dashed): Backend → Langfuse (label "trace export,
  in-process relay"); BFF/Backend → WorkOS (label "OIDC / session"). Both cross the
  AWS boundary to the external-SaaS zone.

**The idea this diagram must land:** "Two app services + one sidecar, one Postgres
carrying three loads, BFF holds no cloud creds, external SaaS stays external, no
EFS — and the compute engine is a slot to be filled."

---

## DIAGRAM 2A — Variant A: App Runner (`arch-2a-apprunner`)

Status badge: **amber — "PENDING SSE proof"**. This is the cost-lean compute tier
that docks onto Diagram 1's plane.

**Flow (left→right):**
`Client` —HTTPS→ `App Runner: Frontend BFF (scale-to-zero-ish, WorkOS @ BFF)` →
`App Runner: Backend + searxng (combined service)` → then a `VPC connector (egress)`
node fanning to `Neon / S3 / SSM` (reuse the Diagram-1 data-plane styling, can be a
compact "docks onto shared plane" cluster).

**Callout annotations (as side-notes, not boxes):**
- On the Backend node: **"request timeout posture 3600s — ??"** with a prominent
  **caution marker** — chips `NFR-SCALE-2 · NFR-PARITY-SSE-1`. This is THE open
  question; make the "??" visually the focal risk of the diagram.
- "Sidecar risk: single-container model may not run searxng in-task → 2nd service
  or flip to Fargate" chip `FR-M2`.
- "Scale-in (min=0) hard-kills → in-process relay must drain on shutdown" chips
  `FR-C8/D5`.
- "Cost: lowest floor, no ALB/NAT (~$35–70/mo)".
- Kill-criterion footnote: "SSE < 3600s → fall back to Variant B (keep Neon + whole
  shared plane)".

## DIAGRAM 2B — Variant B: Fargate + ALB (`arch-2b-fargate-alb`)

Status badge: **green — "no unresolved kill-criterion"**. Same shared plane below,
different compute engine on top — draw it deliberately parallel to 2A.

**Flow:**
`Client` —HTTPS→ `ALB (idle ≥ 3601s, TLS @ 443)` → `Fargate svc: Frontend BFF` →
(internal) `ALB (idle ≥ 3601s)` → `Fargate svc: Backend task` containing two
stacked containers: `middleware + agent (app_prod)` and `searxng sidecar` chip
`FR-C5` → `Neon / S3 / SSM` (same docks-onto-shared-plane cluster as 2A).

**Callout annotations:**
- On the ALB nodes: **"idle ≥ 3601s clears the 3600s SSE bar"** chips
  `FR-C1 · NFR-PARITY-SSE-1` — render this as the **confident/green** counterpart to
  2A's amber "??". The visual contrast between 2A and 2B is the whole point.
- On Frontend BFF: "desiredCount ≥ 1 or 0*" with footnote "* `NFR-AVAIL-2` allows
  min-0 (cold-start accepted) to minimize cost; warm floor min-1 = opt-in future
  lever (`T2`)".
- p95-alarm caveat note: "ALB/target p95 alarm MUST exclude `/run/stream` route or
  long streams trip the 5000ms alarm" chip `FR-O5`.
- "Cost: adds ALB hours over 2A (~$75–120/mo). Still single-AZ, still Neon."

> **2A vs 2B pairing note for the designer:** these two should be visually
> *isomorphic* — same layout skeleton, same data-plane cluster, same "docks onto
> shared plane" port — differing only in (a) the compute engine boxes and (b) the
> amber-`??` vs green-`≥3601s` SSE badge. A reader toggling between them should see
> the fork instantly.

---

## DIAGRAM 2C — Minimal single-AZ VPC (`arch-2c-vpc`)

The network topology, whose entire theme is **"avoid the NAT Gateway"** (the silent
budget-killer). This diagram's hero message: minimal cost via public-subnet + IGW,
**no NAT**.

**Boxes/zones:**
- Outer `VPC (single region, single AZ used)`.
- Inside, one `public subnet (one AZ)` containing:
  - `Compute tasks (assignPublicIp = true)` — chip `NFR-COST-1`.
  - `Internet Gateway (IGW)` tag "free".
  - `S3 gateway endpoint` tag "free — keeps S3 traffic off IGW".
- A **prominent crossed-out / struck / red-X** `NAT Gateway` element with label
  **"NO NAT Gateway (~$32/mo avoided)"** — this negative-space element is the point
  of the diagram; make the *absence* explicit and visually loud.
- **Egress edge** (dashed, from compute tasks through IGW): "→ internet: LLM
  providers, WorkOS, Langfuse, Neon control-plane".
- **S3 edge** (solid, through the gateway endpoint, labeled "on AWS backbone").
- Side-note (muted): "PrivateLink to Neon = documented **future** lever, not
  baseline" chip `NFR-SEC-4`. Draw it grayed/dashed to signal "not built yet".
- Footer trade-off note: "Public-subnet tasks get public IPs, but ingress stays
  gated (App Runner/ALB in front; SGs deny direct task ingress except from the LB)
  — same public-ingress + app-layer-auth posture as GCP today (`FR-M9`), not a
  regression."

---

## DIAGRAM 3 — Data-flow walkthroughs (`arch-3-dataflows`)

Two flows, side by side or stacked. These are *sequences*, so a numbered
sequence/flow style (not a static topology) is right.

**Flow 3.1 — the SSE run path `POST /run/stream` (THE load-bearing flow).**
Numbered steps, participants left→right: `Client → BFF → Backend → {Neon, searxng,
LiteLLM/providers, /tmp} → Langfuse`.
1. `Client → BFF`: `POST /run/stream, Authorization: Bearer <token>`.
2. `BFF`: WorkOS validates session; forwards Bearer to backend. Annotate
   **"BFF holds NO db/llm creds"** chips `T5 · NFR-SEC-1`.
3. `Backend (app_prod.py)`: "401 if no Bearer" chip `FR-M9`; else "JWT verify"
   chip `FR-C3`.
4. `Backend`: **"opens ONE long-lived text/event-stream, held ≥ 3600s"** chips
   `FR-C1/C3` — make this the visual centerpiece. It fans out to:
   `checkpointer → Neon`, `pgvector → Neon`, `thread-store → Neon` (bracket these
   three as **"one DATABASE_URL"** chip `T3`); `searxng → sidecar`;
   `LLM/embedding → LiteLLM → provider APIs` chip `FR-M7`;
   `blackbox recs → /tmp (ephemeral)` chip `FR-C7`.
5. `Relay (async)`: `/tmp blackbox → Langfuse Cloud, in-process` chip `FR-C8`.
6. Ingress-hold note spanning both hops: **"BOTH BFF→client AND backend→BFF must
   hold ≥ 3600s"** chip `NFR-PARITY-SSE-1`.
- **Fork-point callout** on step 4: "This 'held ≥ 3600s' is exactly what App Runner
  (2A) has not proven and ALB (2B) provably does. Every other step is variant-
  identical." Tie it visually back to the 2A-amber / 2B-green motif.

**Flow 3.2 — the trust-traces write path (append-only, tamper-evident).**
Single directed flow `Backend runtime → S3 trust-traces bucket` with a stack of
constraint annotations on the edge/target:
- "runtime role: create/append ONLY — no read/list/delete" chip `FR-D3`.
- "AWS realization: unique keys + versioning/Object-Lock, NOT bare PutObject".
- "lifecycle: age 90d → infrequent-access class" chips `FR-D7 · NFR-DR-1`.
- Highlighted takeaway box: **"S3 is multi-AZ + 11-nines at no extra cost — the
  single-AZ decision does NOT reduce object durability; RPO = 0 for written
  objects"** chip `NFR-DR-1 · T1`. (This is the one place single-AZ costs us
  nothing — make that reassuring.)

---

## GLOBAL DO / DON'T

**DO**
- Keep the five diagrams a consistent *set* — shared palette, shared box/edge
  vocabulary, shared chip styling. They will sit in one document.
- Make the ONE key idea of each diagram legible before any label is read (hero
  diagram = the shared plane; 2A/2B = the compute fork; 2C = no-NAT; 3 = the SSE
  hold + the trace write-only boundary).
- Preserve every requirement chip verbatim.
- Reflect the amber-caution (2A, unproven) vs green-confident (2B, proven) split
  everywhere the SSE question appears.

**DON'T**
- Don't invent AWS services not listed (no API Gateway, no Lambda, no EFS/FSx, no
  Kinesis, no Secrets Manager-as-primary, no NAT — several of these are *explicitly
  rejected* in the design; drawing them would be wrong).
- Don't draw a Multi-AZ standby / failover pair — the design is deliberately
  single-AZ.
- Don't imply Neon is AWS-native or that WorkOS/Langfuse are migrated.
- Don't merge the two app services into three, or promote searxng to its own
  service in the baseline (it's a sidecar; only 2A's *fallback* note may show it
  splitting).
- Don't let requirement chips dominate — they annotate, they don't headline.

## ACCEPTANCE CHECK (self-verify before returning)

- [ ] Five files delivered, named as specified, each self-contained + theme-aware.
- [ ] Every box/edge/chip from each diagram's spec is present and verbatim.
- [ ] 2A and 2B are visually isomorphic and carry the amber/green SSE split.
- [ ] The shared-plane-vs-fork relationship reads without prose.
- [ ] No rejected service (API GW, Lambda, EFS, Kinesis, NAT, Multi-AZ standby)
      appears except where explicitly drawn as negated/struck-through (NAT in 2C).
- [ ] Legible in light AND dark; no page-level horizontal scroll at ~1000px.
