# NEEDLE web UI: design spec

Built with the studio-web skill by William Lu (CC BY 4.0). Owner override for this build: no IBM Carbon styling
(no Plex, no #0f62fe, no square-corner Carbon look); React/Vite + FastAPI, not Streamlit.

**Design read:** an *operate* surface (a triage console) plus one *read* surface (the Finding) for IBM Db2
engineers. The language is precise and technical, with our own tokens.

## The one question
The first screen after a run answers: **which of our services does this advisory hit, and what could this
analyst see?** The strong panel is the **verdict slab**: an ink-black band under the query, holding the
affected count, the longest exposure and the other statuses, with the synthetic-fleet label. Everything else
keeps to the dashboard skeleton: top bar, composer, KPI slab, three ranked lists, exposure table, memo.

## The subject's world (every choice traces back here)
Security advisory, embargo date, TLP sharing label (coloured caps on a black box), analyst clearance,
row permission, `db2exfmt` access plan (RETURN / SORT / FETCH / IXSCAN on VECIDX), package==version pin,
deploy history, haystack and needle.

- **Status labels borrow the TLP label form:** mono caps in a small ink box. AFFECTED is red, UNKNOWN_COVERAGE
  amber, NOT_CONFIRMED grey and PREVIOUSLY_AFFECTED an outline. Every status also carries its word, so colour
  never carries a state alone. No green anywhere, because green would read as "safe".
- **The plan is shown as Db2 prints it:** EXPLAIN text in mono, with the IXSCAN on VECIDX marked.

## Palette (from `palette.mjs --hue 205 --chroma 0.11 --neutral-hue 225 --neutral-chroma 0.005`)
Petrol (hue 205) is the action colour. It is not Carbon blue and not a status colour, and Db2 engineers read it
as "database layer", not "alert".
| Role | Hex | Use |
|---|---|---|
| ground | `#f3f7f9` | page |
| paper | `#fbfcfd` | panels, tables |
| surface | `#e9eef0` | wells, table heads |
| ink | `#101213` | text, verdict slab, TLP boxes |
| mute | `#676a6c` | secondary text (5.1:1) |
| rule | `#c4c8ca` / hair `#dde3e5` | dividers |
| accent | `#009aa6` | focus ring, selection bar, chart line |
| accent-text | `#00757f` | primary button fill, links (5.07:1) |
| affected | `#c4251c` on paper, `#ff5b4f` on ink | AFFECTED |
| amber | `#8a5a00` on paper, `#ffc23d` on ink | UNKNOWN_COVERAGE |

## Type
One family plus its mono: **Red Hat Text** (UI) and **Red Hat Mono** (IDs, SQL, figures). Red Hat is an IBM
company, so the faces fit IBM's design world without being Carbon's Plex. The scale is fixed rem at a 1.2
ratio from 14 px UI text: 12 / 14 / 16.8 / 20.2 / 24.2 / 29 / 34.8. The Finding (a read surface) gets one
larger headline step.

## Motion
150–200 ms state changes only: hover, tab and view fades. No load choreography and nothing pops in.
Skeletons are faint and still.

## Facts list (copy may only use these)
Every number on screen comes from the API (`/api/triage`, `/api/finding`, `/api/explain`) or an evidence file.
None is typed into the UI.

## Must keep (from the handoff)
Real Db2 sign-in by default. The demo switcher appears only with `NEEDLE_DEMO_SWITCHER=1`, labelled "demo
identity switcher — not authentication". Loopback only. Statuses are AFFECTED / NOT_CONFIRMED /
UNKNOWN_COVERAGE, never "safe". The junior identity never sees an embargoed advisory. The router line stays
visible. The synthetic fleet is labelled.

## Landing page (a persuade surface, added after the owner asked for a hero and 3D)
- **Message:** "Find the needle." The literal descriptor follows: what NEEDLE does inside Db2, in one sentence.
- **Hero type:** a product-led dark stage (a lit void, radial gradient, no edges). The subject is the real
  corpus: 26,183 public advisories as points, from nomic-embed-text vectors projected to 3D by PCA
  (`scripts/build_hero_cloud.py`). Embargoed rows are excluded, so the public page cannot leak them.
- **Signature move:** the finding, shown with the data. The question is a needle. Its exact nearest neighbours are
  lit petrol. Under "10% analyst · shared plan" the 21-row first batch shows: rows the permission removes turn red,
  the survivors stay lit, and the readout says "2 of 10". "NEEDLE router" lights the 10 nearest the analyst may
  read. Every number on the stage comes from `cloud.json`.
- **Light (revised after the owner rejected a CSS glow as "just a radius of light"):** the light comes from the scene.
  A bloom pass (UnrealBloomPass, threshold 0.62, strength 0.75, half resolution) lets the dense clusters, the lit
  neighbours, the removed rows and the needle emit light. Depth shading makes far points cooler and dimmer. The
  backdrop is one low key light from the upper right, drawn into the WebGL clear.
- **Animated background tied to the subject:** a faint k-nearest-neighbour graph over a sample of the points.
  Four search pulses walk it greedily toward the question, taking a long edge when they stall, the way a DiskANN
  index search moves. The caption says it is an illustration, not Db2's own graph. "Pause motion" stops the walks,
  the idle turn and the needle pulse.
- **Motion:** one fade-in of the canvas (700 ms) and a slow idle turn. Drag turns it, 1:1 while held, with inertia
  on release. Identity changes fade the points over about 0.7 s. Reduced motion: a still frame, no idle turn, no
  fades, and no Lenis.
- **Scroll:** Lenis 1.3.27, lerp 0.1 on wheel only, native on touch and under reduced motion; inner scrollers
  carry `data-lenis-prevent`.
- **Type:** Red Hat Display for the two display lines (same family as the UI text).
- **Scroll story (desktop, owner request):** the stage pins under the header for four chapters (the corpus, the
  search, the permission, the router). Each chapter switches the scene state the hero already has, and the camera
  eases toward the question (focus 0 / 0.55 / 0.7 / 0.5). One canvas, native scroll position (Lenis), a progress rail
  instead of eyebrow labels, and every number from `cloud.json`. On phones and for screen readers the chapters are
  plain text after the hero. Reduced motion changes chapters without camera travel.
