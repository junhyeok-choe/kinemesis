# Independent Python 2D Animation Engine — Architecture Investigation and Proposal

Status: **DRAFT FOR INDEPENDENT REVIEW. Nothing here is an approved project decision, except those listed under "Approved decisions" below.**

Approved decisions (recorded from the user's own messages):
- **D1 — Licence: GPL-3.0-or-later** for the Engine (approved by the user, 2026-10-29). **D4 — project name: CLOSED, `kinemesis`** (see naming note below; the following sentence is the superseded earlier state): D4 in §8 was **mostly decided**: the user chose the plain name **`theia`** (2026-10-29: "just theia") — i.e. the user rejected the proposed `theia-anim`/`theia_anim` suffix names. Treat as: project = `theia`, import package = `theia`, CLI = `theia`. **Open consequence:** the PyPI *distribution* name `theia` is held by an unrelated 2018 log-aggregator package (2 releases, 2018-05-21 and 2018-06-18) [V]; options: (1) request the name via PEP 541 (abandoned-project process; outcome not guaranteed, nothing requested), (2) publish under a different distribution name while keeping import/CLI `theia`, (3) distribute from source until resolved. Repo location still unconfirmed (proposal: `/home/ubuntu/junhyeok-choe/gsel/theia`). The project's vision statement is to be written in Greek (see "Vision" below). Everywhere in this document, "the Engine" / `animcore` placeholder = theia.

**Vision (Greek, draft — user to review):**
> Θεία — μια ανεξάρτητη μηχανή 2D κίνησης για αρθρωτές φιγούρες: καθαρή, ντετερμινιστική και ελεύθερη, ώστε κάθε στιγμή της κίνησης να μπορεί να υπολογιστεί, να ελεγχθεί και να αναπαραχθεί.
>
> (English gloss: *Theia — an independent 2D animation engine for articulated figures: clean, deterministic and free, so that every instant of motion can be computed, verified and reproduced.*)
- **D5 — Python versions:** develop and test primarily on **3.14**; keep the **core** (`model`, `io`, `eval`, `kinematics`, `scene`, SVG render, `api`, `cli`) compatible with **3.12**; the upstream container importer may require 3.14 (stdlib `compression.zstd`) (approved by the user, 2026-10-29).
- **D3 — Compatibility scope:** upstream-equivalence claims target **native keyframe FK and tween only** for M1–M2; upstream container import (`.styk/.stkz`) at M3; upstream extensions (Both-mode IK/`bendReference`, Auto easing, rigs, layer sheet, etc.) are **deferred** (approved by the user, 2026-10-29).
- **D2 — Run upstream Node code in an isolated, no-network sandbox to generate oracle vectors** (approved by the user, 2026-10-29; executed — see §10).
Date: 2026-10-29. Scope: investigation and planning only; no engine code was written.
Working name used below: **"the Engine"** (package placeholder `animcore`; the real name is an open decision, see §8).

> **Naming note (2026-10-29, later than the rest of this document):** the project name is **kinemesis** (confirmed by the user; kinema + mimesis). Intended: distribution/import/CLI `kinemesis`; repository `junhyeok-choe/kinemesis` (private); local directory `kinemesis`. Wherever this document says `theia`, `animcore` or `kinema`, read "kinemesis" — those were earlier candidates/placeholders. Checked 2026-10-29: `kinemesis` is free on PyPI, npm, crates.io and as a GitHub user/exact repo name (`kinemesis.com` has DNS). Empty placeholder packages are not an acceptable way to claim a PyPI name (PEP 541 treats them as name squatting); the name is claimed by the first real release. The PEP 541 request for `theia` is **no longer needed**.

## 0. How to read this document

Every statement carries one of these tags. Reviewers should challenge the tagged level, not just the claim.

| Tag | Meaning |
| --- | --- |
| **[V]** | Verified by the lead reading upstream source or by running a command in this session. |
| **[V-agent]** | Reported with `file:line` by a read-only subagent; **not** re-read line by line by the lead. Spot-checked items are listed in §1.3. |
| **[D]** | Stated in upstream documentation only; code not confirmed. |
| **[I]** | Inference. May be wrong. |
| **[P]** | Proposal by the model. **Not approved.** |
| **[?]** | Unknown / not investigated. |

Supporting evidence files (raw subagent audits, tagged per claim, with `file:line`):
`audit-A-model.md` (document model, serialization), `audit-B-kinematics.md` (FK/IK/constraints), `audit-C-timeline.md` (time, easing, evaluation), all in the same scratchpad directory as this file.

Context from the user's uploaded chat log (`StykAnimate…pdf`): the user's stated intent is a Python-ported engine **kept separate from Manim, made Manim-compatible only**, leaving combined use to the end user; they also asked whether GPL forces source disclosure on distribution. [V — read from the PDF]

---

## 1. Upstream Source Audit

### 1.1 Identity and provenance

| Item | Finding |
| --- | --- |
| Repository | `https://github.com/filippocalippo/StykAnimate-App` [V] |
| **Commit investigated** | **`def97214c2b491fbce82647f625a73f78416c6d8`** (2026-10-19, "Require the maintainer's review for every change"), `main` at clone time, 525 commits [V] |
| First commit | 2026-09-09 → project is ~6 weeks old; high churn expected [V] |
| Size | ≈450k lines JS/Python in repo; `src/` ≈300 modules, `tests/` ≈850 files [V] |
| Package | `stykanimate-webapp` 1.2.5, `"license": "GPL-3.0-or-later"` [V] |
| Authorship | 512+2+1 commits from one maintainer identity; 10 commits from a `devin-ai-integration[bot]` identity [V]. `AGENTS.md` describes agent-assisted development [V]. |
| Runtime | Electron/browser app (WebGPU renderer) + Python "codec sidecar" (`backend/`, `codecs/`) [V] |
| Checked-in sample projects | **None.** No `.styk/.stkz/.stykmov/.piv/.stk` file exists in the repo [V-agent, grep]. |

### 1.2 Subsystem map

"Upstream core claim": upstream calls its evaluation semantics those of **Pivot Animator** (a separate proprietary program) and says Pivot compatibility is *not* fully signed off (`docs/PIVOT_PARITY.md`: T04 "interpolate pose/length/bend/color/opacity/camera/background" and T05 "auto-easing, wrapping, tick-to-fraction" are unchecked) [D/V-agent]. **Therefore upstream is a reference for "what StykAnimate does", not proof of "what Pivot does".**

| Subsystem | Where (upstream) | Verified behavior (summary) | Unknown / caveat |
| --- | --- | --- | --- |
| **Document model** | `src/pivot/model.mjs`, `src/demo.mjs` (builders), `src/pivot/structure.mjs` | "Native document" **is the Pivot decoder's JSON** (`version` 2–5, `figure_types[]`, `keyframes[]`, `backgrounds[]`) plus an extension namespace `_styk`, per-object `_stykIK`, per-segment `_stykRig`, `_stykAnimationOrigin`. No separate StykAnimate schema. [V-agent] | **No machine-readable schema exists**; validation is hand-written JS (`validateScene`, authoritative) and weaker Python (`codecs/codec_bridge.py:243`). [V-agent] |
| **Figure/joint topology** | `figure_types[i].segments[]` | Segment = `segment_id` (handle), `parent_id` (parent handle; 0 = figure origin), `length`, `angle_rad`, `bend_rad`, thickness, `primitive_code` 0..6, `aux_code`/`flags` bitfields… Tree; cycles/missing parents rejected by validation, but silently dropped/defaulted to root at geometry time. Joins between figures: `object.join = {target_object_slot, target_handle_id}`, position-only inheritance. [V-agent] | Pivot bitfields (`primitive_code`, `field28`, `color_override_raw`, `duration_raw`) are first-class fields. |
| **Instances & pose** | `keyframes[k].objects[j]` | Pose = instance arrays `angles[]`, `lengths[]` (if `len_flag`), `bends[]` (if `bend_flag`) parallel to the definition's segment array, + `root_x`, `root_y`, uniform `scale`. [V-agent] | |
| **FK** | `src/pivot/geometry.mjs` `segmentAt` ≈:662–712 (`buildGeometrySteps` :596) | **Angles are absolute world radians**; child angle does not inherit parent angle. Direction = (cos a, sin a); **y-down** screen space (torso −π/2 = up in default figure; no y-flip anywhere) [I]. Endpoint `= start + L·scale·(cos a, sin a)`, each coordinate rounded with **`Math.fround`** (float32) and that rounding **compounds down the chain**; root and IK internals stay float64. `bend_rad` = total arc sweep; straight if `|bend|<1e-7`; arc tessellated with `steps=max(8,min(160,ceil(|bend|·16),ceil(|L|/4)))`. Scale multiplies lengths only (not bend); negative scale = 180° point reflection, not a mirror. [V (spot-checked: arc, fround, 1e-7); rest V-agent] | Whether Pivot itself uses float32 rounding: [?]. |
| **IK** | `src/ik.mjs` (386 lines), `ik-evaluation.mjs`, `ik-joined.mjs`, `ik-rig.mjs` | Exports `solveIKPoints`, `solveObjectIK`, `ikBendReference`, `interpolateIK`, … IK is a **StykAnimate extension** (not Pivot) [D: `docs/RIG-CONSTRAINTS.md` cites Stick Nodes as model]. Two-bone: analytic law-of-cosines (`along=(a²−b²+d²)/2d`, `height=√(a²−along²)`). n>2 or zero-length bone: **FABRIK**, ≤32 passes, tol 1e-5, collinear seed `sin(πi/n)·total·0.05`. Bend direction ∈ {−1 Left, 0 Both, +1 Right}. "Both" has hysteresis (gates 0.02 / 0.04 / 0.002 of chain length) driven by a **stored `bendReference`** written by the editor at gesture time, never during evaluation. `EPS=1e-10`, `MAX_IK_CHAIN=256`. [V (EPS, MAX_IK_CHAIN, defaults); rest V-agent] | Output depends on **(interpolated pose, stored bendReference)**; a faithful oracle input must include the stored reference and, for n>2, pre-IK angles/`shape`. |
| **Joint constraints** | `src/rig-constraints.mjs`, `rig-weighted.mjs`, `rig-spatial.mjs` | **No angle limits for ordinary joints or IK** (grep + `docs/inverse-kinematics.md:34`). Exist: connectors, weighted joints (≤16 anchors), Smart Stretch (ratio min/max), angle lock (world/figure/parent), spatial joints with `motion{min,max}`. [V-agent / D] | These are StykAnimate-specific rig features; out of reach for early milestones. |
| **Transform composition** | `geometry.mjs:630–643`, `:296–306` | Joined child inherits parent joint **position only** (no rotation/scale). Tweening is done on **relative** angles `angle − (parent.angle + parent.bend)` with shortest-arc, then re-accumulated to absolute. [V-agent] | |
| **Time & evaluation** | `geometry.mjs:534 evaluatedFrame(report,index,t,absoluteTick,…)`, `:325 evaluatedNativeFrame` (pairwise keyframe interpolator), `layer-sheet.mjs:125 sampleLayerSheet`, `animation-pose.mjs`, `animation-channels.mjs` | Time unit = integer **tick** (=output frame). Key start = cumulative sum of `duration_raw` (0..65535); native tick k of an n-tick span uses `t = k/n` (**t never reaches 1 inside the span**). fps integer 1..1000 and **not** used in interpolation. Evaluation is pure in (document, tick) except WeakMap/LRU caches validated by identity. App-opened docs go through the **layer-sheet** path; bare native docs through `evaluatedNativeFrame`. [V-agent; entry point :534 and signature V] | `tick→(index,t)` mapping is duplicated in callers (`playback-worker.mjs:69`, `export-frame-worker.mjs:39`). |
| **Easing** | `src/keyframe-easing.mjs` (105 lines) | Modes: `auto, bezier, ease-in, ease-out, linear, constant` (`hold` alias). Cubic-bezier = **pure bisection** on x(u), ≤40 iterations, `|x−t|<1e-10`; presets (0.42,0,1,1), (0,0,0.58,1), default (0.42,0,0.58,1); control coords must be in [0,1]. Auto = monotone cubic Hermite with duration-weighted harmonic-mean tangents, clamped to endpoint range (isolated pair ⇒ smoothstep). A key owns its **outgoing** interval. Native manual modes apply timing curve once to t, then lerp all fields; Auto passes raw t per property. [V (solver code read verbatim); rest V-agent] | Legacy Pivot `auto_easing` = PCHIP over "runs" (distinct code path) — separate from StykAnimate Auto. |
| **Angular interpolation** | `geometry.mjs:50 shortest(a)=atan2(sin a,cos a)` ∈ (−π,π]; `native-property-curve.mjs:2` `((x+π)%2π+2π)%2π−π` ∈ [−π,π) | **Two different wrap functions with different tie behavior at exactly ±π.** Scalar `rotation` keys without `nativeRotation` keep full turns. [V (shortest, ik.mjs `wrap` line); rest V-agent] | |
| **Geometry generation / rendering** | `geometry.mjs` (1499 lines) → `renderer*.mjs` WebGPU WGSL; `src/playback-worker.mjs`; `resvg` WASM for SVG→raster | Renderer is WebGPU; **no software renderer path to compare against**. Export frames via `export-frame-worker.mjs`. [V-agent/D] | Visual output equivalence needs an independent rasterizer. |
| **Native serialization** | `src/native-container.mjs` (JS), `backend/native_format.py` (Python) | `.styk/.stkz/.stykmov` = 56-byte header (magic, version 1|2, codec, SHA-256) + compressed JSON; v2 adds sections with `S2B/S2S/S2D/S2E` markers. Generic JSON container, knows nothing about scene shape. Unknown fields preserved by object spread; tests assert it incl. `__proto__`. Embeds original PIV bytes (`_stykSource`). Python reference implementation exists. [V-agent/D] | |
| **Validation / errors** | `model.mjs validateScene`; `localized-error.mjs` | Plain `Error` with `.messageKey/.messageParams` (27 locale packs); some container errors carry `.code`; Python raises `ValueError`/`PivError`/`ApiError(status, code)`. **No JSON-path in errors, no error taxonomy.** [V-agent] | |

### 1.3 What the lead verified directly vs. delegated

Directly read/ran by lead: README, AGENTS.md, THIRD_PARTY_NOTICES, LICENSE head, CONTRIBUTING, ARCHITECTURE.md, native-file-format.md, inverse-kinematics.md, keyframe-easing.md, animation-modes.md, property-channels.md, IMPLEMENTATION.md, head of RIG-CONSTRAINTS/PIVOT_PARITY; `keyframe-easing.mjs` (bezier solver, modes), `geometry.mjs` (`arc()`, `fround` endpoint, `shortest`, `evaluatedFrame` signature, segment start/angle/length lines), `ik.mjs` (EPS, MAX_IK_CHAIN, solver defaults, `wrap`), `demo.mjs` default figure. All of these matched the subagent reports. The remaining `file:line` claims are single-source ([V-agent]).

### 1.4 Reference-oracle executability

- Static analysis [V-agent]: `ik.mjs` and `keyframe-easing.mjs` import no DOM; the evaluator closure of `pivot/geometry.mjs` is ≈76–78 non-locale modules with DOM use only inside draw/offscreen paths; upstream's own `node --test` suite imports `geometry.mjs` under plain Node. `src/demo.mjs` (`emptyDocument`, `createObject`, `createFrame`) builds synthetic documents.
- **Executed after user approval of D2 (see §10).** Initially the permission classifier denied running upstream JS and I did not circumvent it; the user then authorized sandboxed execution. Result: `keyframe-easing.mjs`, `ik.mjs`, `demo.mjs` and `pivot/geometry.mjs` import and run under plain Node v25.2.1 with **no `npm ci`** (only `node:` builtins are imported). [V]
- **An oracle proves "equals StykAnimate @ def97214", not "equals Pivot".** [V-agent: PIVOT_PARITY unchecked items]
- Fixture availability: upstream tests that exercise real Pivot behavior need an **undistributed corpus** (`../Pivot Animator v5/Animations/*.piv`, Akane projects) and skip when absent. Self-contained synthetic tests exist (`tests/native-tween-sampling.test.mjs` carries its own PCHIP reference sampler; `keyframe-easing.test.mjs` has exact bezier values 0.3153568125725393 / 0.6846431874274608 / 0.1291619310473198). [V-agent]

---

## 2. Technical Feasibility Assessment

### 2.1 Key finding

**A "port of StykAnimate's engine" is really three different things with very different porting costs.**

| Layer | What it is | Origin | Port cost / risk |
| --- | --- | --- | --- |
| **L-A Pivot-semantic core** | Absolute-angle FK, tick/duration timeline, per-interval easing, shortest-arc, bezier, PCHIP auto-easing, colour/opacity byte tweening, camera, join | Reimplementation of proprietary Pivot behavior [D] | Moderate. Small math, many quirks (float32 compounding, trunc vs round, bitfields). Evidence of Pivot-faithfulness is outside this repo. |
| **L-B StykAnimate extensions** | IK (2-bone, FABRIK, Both-hysteresis, bendReference), Auto monotone easing, layer sheet, authored channels, rigs (connector, Smart Stretch, angle lock, weighted, spatial/3D skinning), animation-origin, movieclips, camera follow, VFX | Upstream-original design | High. Large, intertwined (`geometry.mjs` imports rig, IK, movieclip, VFX, origin modules). Highest licence exposure (original expression). |
| **L-C Application** | Editor, commands/undo, WebGPU renderer, workers, UI, Electron, import/export workers | Upstream-original | Irrelevant to an engine; do not port. |

Consequences:
1. The document model **cannot be ported as a data model**: it is Pivot's binary-decoded JSON with raw bitfields, 16/32-bit limits and version-gated semantics, plus an unregistered `_styk` namespace; no schema exists. [V-agent] An independent, clean, versioned model with an *importer* is the viable path.
2. The **L-A core can be specified from observable behavior** (small closed-form math). L-B must be consciously scoped, not "ported".
3. Determinism is achievable: evaluation is pure given (document, tick) except for the stored IK `bendReference`, which must become **explicit document data** in the Engine. [V-agent]

### 2.2 Verified facts that drive design

- Angle convention upstream: absolute world radians, y-down, 0 = +x. [V-agent; y-down I]
- Float32 rounding at every joint end (`Math.fround`) → upstream coordinates are quantized; a Python float64 FK will differ by up to ~1 float32 ulp per joint, compounding down chains. [V (line spot-checked)]
- Bisection bezier tolerance 1e-10 on x: an independent solver (e.g., Newton) will differ from upstream by ≤ ~1e-10·|dy/dx|. [derived from V]
- `shortest()` and the scalar wrap disagree at exactly ±π (one returns +π for +π, other −π). [V-agent re-derived numbers]
- fps is not used in interpolation; time is ticks; native sampling never reaches t=1 within a span. [V-agent]
- Python 3.14 stdlib has `compression.zstd` (PEP 784) — verified by running `import compression.zstd` on 3.14.2. Together with `zlib`, `hashlib`, `json`, `struct`, an upstream **container v1/v2 reader needs no dependencies** on 3.14. [V]
- Library resolution on Python 3.14 (uv dry-run, Linux x86_64, this machine) [V]: numpy 2.5.4, Pillow 13.0.0, pydantic 2.14.1, typer 0.27.3, skia-python 144.1, aggdraw, jsonschema, pytest, hypothesis all resolve with **binary wheels**. **`pycairo` and `manimpango` have no binary wheel here** (build from source; `pkg-config cairo` absent), so **`manim` 0.22.1 failed to install** in my probe venv (Manim declares `Requires-Python >=3.11`). Therefore Manim integration must be a separately-installable, CI-isolated optional component that is never imported by the core.
- PyPI licence metadata [V]: manim MIT; manimpango MIT; pycairo LGPL-2.1-only OR MPL-1.1; Pillow MIT-CMU; numpy BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0; pydantic MIT; typer MIT. skia-python metadata field blank (**[?]**, verify before use).

### 2.3 Unknowns

1. ~~Whether upstream evaluator runs under plain Node without `npm ci`~~ — **resolved [V]: yes** (§10).
2. Whether Pivot Animator itself matches upstream numerically (no Pivot binary/corpus available to us).
3. True behavior of "Both" IK bend and FABRIK for n>2 beyond what the code states (requires oracle vectors incl. `bendReference`).
4. y-axis convention is inferred, not documented.
5. Upstream stability: 6 weeks old, rapid change; semantics may shift under us.
6. Copyright status of agent-generated upstream portions (see §4).

### 2.4 Risks

| Risk | Severity | Mitigation [P] |
| --- | --- | --- |
| Claiming "compatibility" with Pivot/StykAnimate without evidence | High | Four-level compat vocabulary (§5.1); a claim is allowed only with an executed fixture suite. |
| Licence contamination via translating code | High | Decision D1; provenance log; restrict early milestones to behavior-specified leaf math. |
| Scope explosion (rigs, spatial, movieclips, VFX) | High | Explicit non-goals through M3. |
| Float32 + libm differences make byte-exact goldens impossible | Medium | Derived tolerances (§5.3), not byte equality. |
| Oracle not runnable / upstream changes | Medium | Pin commit; check in generated vectors with provenance; regeneration is a documented, gated task. |
| Manim not installable in CI | Medium | Separate distribution + CI job with system libs; adapter tested against a minimal Mobject surface. |
| Time semantic mismatch (tick/integer vs seconds/rational) | Medium | Define canonical time model now (§3.3) and test frame-rate independence. |

---

## 3. Architecture Proposal  **[P — all of §3 is proposal]**

### 3.1 Evaluation of alternatives

| | **A. Faithful port of the upstream evaluator** | **B. Behavior-preserving reimplementation (specified from observable behavior)** | **C. Reuse established Python libs** | **D. Compatibility layer around upstream (as validation baseline only)** |
| --- | --- | --- | --- | --- |
| Behavioral fidelity | Highest on L-A/L-B incl. quirks | High on specified subset; quirks only where deliberately specified | Not applicable to semantics; strong for rasterization/vector output | Exact by construction (it *is* upstream) |
| Complexity | Very high: ≈76-module closure, Pivot bitfields, rig/VFX/origin entanglement | Moderate, bounded by scope | Low for I/O + drawing; no library provides IK + Pivot-style timeline [I: not exhaustively surveyed] | Low to build; but needs Node + checkout |
| Runtime/render perf | Python ≪ upstream WebGPU/worker architecture either way | Pure-Python FK is fine at figure scale (tens–hundreds of joints) [I]; numpy optional later | Skia/Pillow/cairo fast | Not shippable |
| **Licensing** | **Derivative work ⇒ GPL-3.0-or-later obligations** for the Engine | Independent expression; but author exposure to upstream source taints "clean-room" claims (§4) | Library licences vary (§4) | Use only as a *test oracle*, not distributed as part of Engine |
| Maintainability | Tracks a fast-moving upstream; inherits its entanglement | Own design, own schema | Dependence on third-party API churn | Fragile (Node, upstream churn) |
| Testing needs | Full equivalence suites | Equivalence on specified subset + property tests | Library-behavior tests | None as product; **required as oracle** |
| Extensibility | Limited by Pivot-shaped model | Best: schema designed for rigs + motion graphics | Good for backends | None |

**Recommendation [P]:** **B as the architecture, D as a gated test oracle only, C only for rendering/IO leaves (SVG writer from stdlib; optional raster backend; optional Manim adapter).** Do **not** do A: it imports Pivot's binary-format semantics and 76-module entanglement, offers no model improvement, and maximizes licence exposure. Evidence: §2.1 (three-layer finding), §1.2 (no schema, bitfields, entanglement), §1.4 (oracle valid only as StykAnimate-equivalence).
Exception allowed under B: leaf algorithms that are textbook/public (CSS-style cubic-bezier, smoothstep, shortest-arc, two-bone law-of-cosines IK, FABRIK paper, Fritsch–Carlson/PCHIP) are implemented **from the public references**, then validated against oracle vectors.

### 3.2 Component boundaries and dependency direction

Dependencies point **downward only**; each layer imports nothing from layers above. Enforce with an import-linter contract in CI.

```
  adapters (separate distributions)   gui / mcp (not in scope; boundary only)
        manim-adapter                       │
              │                             │
              ▼                             ▼
        ┌──────────── api (Python facade) ────────────┐   cli (thin, calls api only)
        └───────────────────────┬─────────────────────┘
                                ▼
   render backends ◄── scene (evaluated, immutable) ◄── eval ◄── kinematics
   (svg | raster)                                         │          │
                                                          ▼          ▼
                                       io (serialize/validate/migrate/import) ──► model (plain data)
```

| Component | Responsibility | May depend on | Dependencies (external) |
| --- | --- | --- | --- |
| `model` | Versioned project data: `Project`, `Rig`/`Joint`, `Pose`, `Track`/`Keyframe`, `Timeline`, style. Pure data + invariants. **No behavior beyond validation.** | stdlib | none |
| `io` | Canonical JSON (de)serialization, schema versioning, migration, unknown-field policy, errors with JSON path; importers (later: upstream `.styk` container) | model | none (3.14 stdlib zstd/zlib) |
| `eval` | Time semantics, easing, interpolation, `evaluate(project, t) → EvaluatedScene`; **pure function** | model, kinematics | none |
| `kinematics` | FK, later IK solvers and constraints; pure functions on arrays of lengths/angles | (none; model-agnostic numerics) | none (numpy optional later) |
| `scene` | `EvaluatedScene`: immutable, backend-neutral drawables (polyline/arc/circle/polygon, style, z, transform) | — | none |
| `render` | Backend protocol `render(scene, camera, size) → output`; `svg` (stdlib), `raster` (optional extra) | scene | Pillow or skia-python **[?: choose in M1]** |
| `api` | Stable Python facade: `load`, `evaluate`, `render_frame`, `render_sequence`, `validate` | all above | — |
| `cli` | `validate`, `evaluate`, `render`, `schema`, `convert` — thin wrapper over `api` | api | stdlib `argparse` (avoid dependency; revisit Typer if justified) |
| `manim-adapter` (separate dist) | Map `EvaluatedScene` → Manim Mobjects; drive via updater/`ValueTracker` by calling `evaluate` | api, manim | manim (MIT) |
| gui/mcp | **Not built.** Reserved boundary: they call `api` and operate on `model` with the same validation | — | — |

Data ownership:
- **Project (model)** = the single mutable source of truth (authoring data), owned by `model`.
- **EvaluatedScene** = derived, immutable, never persisted; recomputable.
- **Caches** (if any, later) live inside `eval`/`render` keyed by a project revision hash; they must never alter results (tested by cache-on/off equality).
- Future GUI/agent interfaces mutate a `Project` only through validated operations that the `api` exposes; the *command/patch format* is **reserved but undesigned** (open item for review, not implemented in M1).

Separation of the user's stated capabilities:
- **Character animation/kinematics** = `kinematics` + `model.Rig` + pose tracks.
- **General motion graphics** (paths, text, masks, compositions) = new `model` node kinds + new `scene` drawables; the **scene graph node has a `kind` discriminator** from day one, but only `rig_figure` and `shape` kinds exist in M1. [P]
- **Rendering independent of Manim** = `render` backends consume only `scene`.

### 3.3 Semantics that must be defined before coding (proposed definitions)

| Topic | Proposed definition [P] | Rationale / upstream contrast |
| --- | --- | --- |
| Time | Canonical project time = **exact rational seconds**? ⇒ keys stored as integers in project `timebase` (ticks/second, e.g. 24000 or fps-multiple); sampling frame *i* at `i/fps` as an exact fraction; evaluation API takes `Fraction | float` seconds | Frame-rate independence required. Upstream: integer ticks, fps ignored by interpolation [V-agent]. Importer maps ticks→time. |
| Frame vs timestamp | Frame *i* ⇔ timestamp `i/fps`; a frame samples the scene at its start instant | Define once; upstream's `t=k/n` mapping becomes an *importer rule* |
| Before first key / after last key | Before: track contributes nothing / rig uses rest pose (explicit per channel type). After: hold last | Matches upstream scalar/hold behavior [V-agent] |
| Interval ownership | Easing belongs to the **outgoing** keyframe | Same as upstream [V-agent] |
| Interpolation | `constant`, `linear`, `cubic-bezier(x1,y1,x2,y2)` with x∈[0,1] (presets ease-in/out), `smoothstep`; later `monotone-auto` | Public CSS spec for bezier; mirrors upstream modes [V-agent] |
| Angles | Joint pose is **local** (relative-to-parent) angle in **radians**, float64. Channel kind `angle` = shortest-arc with **specified tie rule at exactly ±π** (rule to be chosen in review); channel kind `scalar` = no wrap | Upstream tweens relative angles with shortest-arc then re-accumulates → local-angle shortest-arc is equivalent [V-agent]; two upstream wrap functions disagree at ±π, so the Engine must choose and test |
| Coordinates | Internal: **y-up, counter-clockwise positive** (math/Manim convention). The upstream importer applies `(x, y, θ, bend) → (x, −y, −θ, −bend)`; conversion has dedicated tests | Upstream is y-down [I]. Alternative (keep y-down) is a reviewer question |
| Transform composition | World = parent world ∘ local, 2D affine (translate, rotate, uniform scale first; non-uniform later). FK computes `end = start + L·(cos a_world, sin a_world)` where `a_world = Σ local`. | Upstream stores absolute angles; importer converts absolute→local via parent chain |
| Numerics | float64 throughout. Upstream's per-joint float32 rounding is **not** part of Engine semantics; it is a **named import/compat profile** (`pivot32`) used only to compare with oracle vectors | Keeps rendering/cache design from changing semantics |
| Determinism | `evaluate(project, t)` pure; no global state, no RNG, no wall-clock; dict iteration order never affects output (sort by id) | JS integer-key ordering differs from Python [V-agent] |
| Errors | Typed exceptions with machine code + JSON path (`ValidationError(code, path, message)`) | Upstream has none [V-agent] |
| Unknown fields | Load strict by default (reject unknown *required-version* and unknown keys in known objects); `--lenient` preserves unknown keys in an `extras` mapping and re-emits them; never silently dropped | Prevents silent loss; upstream preserves via spread [V-agent] |
| Versioning | `schema_version` semver-like `major.minor`; reject unknown major; migrations are pure functions with fixtures | Upstream has no schema [V-agent] |

### 3.4 Python and engineering standards [P]

- Python: **3.14 target, 3.12-compatible core** (D5, approved). 3.14-only stdlib `compression.zstd` is used only in the optional upstream importer.
- Packaging: `pyproject.toml` (PEP 621), `src/` layout, `uv`/pip, hatchling-or-setuptools **[?]**, PEP 561 typed package, `mypy --strict` or pyright in CI, `ruff`, `pytest`, `hypothesis` (dev only), `import-linter`.
- Core has **zero runtime dependencies** in M1. Each added dependency requires a written necessity note (e.g., Pillow only if PNG output is required in M1; numpy only if a measured need appears).
- Security: parse JSON with size/depth limits; container reader enforces upstream's published admission limits (256 MiB, section/marker validation) if/when the importer exists; no `eval`/pickle; no network I/O in core; reproducible builds; `pip-audit` in CI.
- Docs: specification of semantics (§3.3) lives in-repo as normative docs; examples tested via doctest/docs tests.

---

## 4. Licensing Assessment  *(not legal advice; obtain counsel before distribution)*

### 4.1 Upstream licence facts [V unless noted]

- `LICENSE` = GNU GPL v3 text; `package.json` `license: GPL-3.0-or-later`; README states "GPL v3 or (at your option) any later version". No per-file copyright/SPDX headers in `src/`/`backend/` (grep found none apart from a single icon file hit) — so licensing is repo-level. Copyright holder is not named in `LICENSE` (FSF template); commit history shows one maintainer identity plus a bot identity.
- `CONTRIBUTING.md`: contributions licensed GPL-3.0-or-later; no CLA, no DCO. A relicensing of upstream is therefore not available by contract.
- Trademarks (README): name and logo identify the official project; forks should use a different name and icon. Pivot Animator / Stick Nodes names are used descriptively only. → The Engine must **not** use "StykAnimate" branding, logo, or imply endorsement.
- Third-party notices (`THIRD_PARTY_NOTICES.md`): resvg (MPL-2.0, vendored WASM), earcut (ISC), opentype.js (MIT), Noto Sans/Inter (OFL-1.1), zstd-wasm (MIT/BSD-2), sticknodes-rs-adapted logic (MIT, with notice), "Nodes lab" decoder (MIT), FFmpeg via imageio-ffmpeg (GPL-3.0, bundled in desktop releases, run as separate program), Electron/Chromium, Python packages for the sidecar. Of these, only `earcut` (polygon triangulation) is in the evaluator closure; **nothing in the L-A/L-B math is third-party**, i.e. the relevant expression is upstream-original under GPL. [V/V-agent]
- Upstream says it did not distribute the Pivot corpus; Pivot/Stick Nodes formats are read "for interoperability" and the owners are unaffiliated. [V] Pivot-format legality/reverse-engineering position is a **separate** question not assessed here.
- Possible AI-authorship in upstream (bot commits; AGENTS.md). Copyright subsistence in AI-generated portions is legally unsettled; **do not rely on it** to avoid GPL obligations.

### 4.2 Implications

| Path | Consequence |
| --- | --- |
| **Translating upstream code (any language) = adaptation** | Resulting file is a derivative work. Rewriting JS→Python does **not** remove the original copyright. Under GPLv3 the Engine (or at least the combined work conveyed) must be licensed GPLv3(+), keep upstream copyright/licence notices, state modifications with dates (§5a), and provide Corresponding Source to recipients when **conveying** (distributing). Private use or non-distributed internal use does not trigger source disclosure; network-service use does not trigger it under GPLv3 (AGPL differs). Answer to the user's chat question: yes, on distribution recipients must receive source under GPL; there is no obligation for purely private use. |
| **Independent reimplementation from behavior/public algorithms** | Ideas, algorithms, mathematical facts, file-format facts are not protected; specific expression is. Textbook leaf algorithms (CSS cubic-bezier, smoothstep, law-of-cosines IK, FABRIK, PCHIP) can be written from public sources. Design-specific choices in upstream (e.g., "Both" bend hysteresis thresholds 0.02/0.04/0.002, `bendReference` schema, `_styk*` field layouts, Smart Stretch semantics) are the riskiest to reproduce. |
| **Clean-room caveat (important)** | **This investigation session read upstream source.** Anything implemented from this session's context is *not* clean-room. A permissive-licence claim would require a documented clean-room procedure (spec writer who reads code; separate implementer who sees only the behavioral spec and oracle vectors) and ideally counsel. |
| Oracle vectors | Numeric outputs of running upstream are facts about behavior, but they come from executing GPL software on inputs built with its builders; keep them in a separate `fixtures/` tree with provenance (commit, command, date) and treat licensing of generated fixtures conservatively (assume GPL-compatible distribution only until counsel says otherwise). |
| Manim adapter | Manim Community is MIT. A GPL Engine + MIT Manim adapter is permissible; the adapter-plus-engine combination distributed together is under GPL. If the Engine is permissive, the adapter is unconstrained. Keep adapter in a separate distribution either way. |
| Third-party dependencies [V metadata] | Pillow MIT-CMU, numpy BSD-like, pydantic MIT, typer MIT, manimpango MIT, **pycairo LGPL-2.1-only OR MPL-1.1** (dynamic use OK; note if redistributed), skia-python **[?]**. Avoid bundling **FFmpeg (GPL)**; call a user-installed `ffmpeg` binary for video as a separate process, optional. |
| Provenance record | Maintain `PROVENANCE.md`: for each module, source of semantics (public spec / upstream behavior vector / own design) and whether upstream code was consulted. |

### 4.3 Decision D1 — APPROVED: GPL-3.0-or-later
The user approved **GPL-3.0-or-later** for the Engine. Consequences [P unless noted]:
- No clean-room procedure is required; the clean-room caveats in §4.2 become informational. Direct translation of upstream leaf routines is *permitted*, but every such file must carry the upstream copyright/licence notice, a modification notice with date (GPLv3 §5a), and a `PROVENANCE.md` entry naming the upstream file and commit (`def97214…`). Preference remains to implement from public references where equivalent, to keep the codebase small and self-designed.
- Ship the full GPLv3 text as `LICENSE`, set `license = "GPL-3.0-or-later"` (SPDX) in `pyproject.toml`, add `SPDX-License-Identifier: GPL-3.0-or-later` headers to every source file, and add a copyright line for the new project's author(s) (holder name: user to supply).
- Dependencies must be GPLv3-compatible. MIT, BSD, MIT-CMU, ISC, Apache-2.0 are compatible. LGPL-2.1 (pycairo) is compatible for dynamic use. Do not bundle FFmpeg; invoke a user-installed binary.
- The Manim adapter stays a separate distribution. Anyone distributing it together with the Engine distributes under GPL; Manim (MIT) imposes no obstacle.
- Does not by itself approve D2–D5, any compatibility claim, or the use of upstream branding (still prohibited).
- Legal review is still advisable before first public distribution.

---

## 5. Compatibility and Test Plan

### 5.1 Compatibility vocabulary (a claim requires its own executed evidence)

| Level | Definition | Evidence required |
| --- | --- | --- |
| **C0 Structural** | Engine can parse upstream container/JSON and represent its entities without loss of required fields | Round-trip on fixtures; unknown fields preserved/reported |
| **C1 Import/Export** | Engine imports a defined subset to its own model and exports it back (or to the same upstream format) so upstream re-reads it | Upstream-side reopen test (needs oracle execution) |
| **C2 Numerical equivalence** | `evaluate` matches upstream vectors within derived tolerances for a **named** feature subset | Oracle vectors + tolerance table (§5.3) |
| **C3 Visual fidelity** | Rendered frames match upstream renderings within a measured metric | Same drawing parameters; independent rasterizer comparison; **not planned**—upstream has no software reference renderer |

Non-claims: no Pivot Animator compatibility claim at any level without Pivot-produced evidence (none available).

### 5.2 Reference fixtures [P]
1. **Synthetic oracle vectors (preferred, checked in, with provenance)**: generated by an upstream-side script at the pinned commit via `demo.mjs` builders: single/multi-bone figures, curved segments, scale ±, joined figures, two-keyframe and multi-keyframe tweens for each easing mode, wrap-around angles (±π, 3π, 2π multiples), zero-duration spans, last-key hold, version-<5 hold. Format: JSON of inputs (upstream-native doc) + outputs (`joints` per object, scalar tracks).
2. **IK vectors** (M2): 2-bone reachable/unreachable/folded/collinear for Left/Right (Both only with explicit `bendReference`), n>2 FABRIK including stored `shape`.
3. **Container fixtures** (M3): generated v1 and v2 containers via the Python reference `backend/native_format.py` (stdlib-only, runnable without Node) incl. marker edge cases. [V-agent: exists]
4. Corpus-dependent tests: **excluded** (undistributed).

### 5.3 Tolerances (derived, to be confirmed empirically against measured oracle error before freeze)

| Operation | Tolerance | Justification [P] |
| --- | --- | --- |
| FK joint positions, Engine in `pivot32` profile vs oracle | ≤ `(depth+1)·ulp32(|coord|)` per joint | Upstream rounds each end to float32 and compounds; libm sin/cos may flip a rounding by 1 ulp32 per joint |
| FK, float64 profile vs oracle | ≤ `depth · 2⁻²³ · max(1,|coord|)` | Bound by upstream quantization noise |
| Cubic-bezier progress | abs ≤ `1e-10 · max(1, s)` where `s` = max \|dy/dx\| of the curve (upstream solver stops at `\|x−t\|<1e-10`); presets and typical curves therefore ≤ ~2e-10 | **Measured (§10):** vs an exact solver, presets differ by ≤ 1.5e-10, but degenerate curves `[0,0.9,0.9,0]` and `[0,0,0,1]` differ by 4.6e-7 and 1.4e-7 (steep dy/dx), so a flat 1e-8 would have been wrong; the bound must scale with slope. An exact replication of upstream's bisection (≤40 iterations) should match to ~1e-15. |
| smoothstep/linear/constant | exact (≤ 4 ulp64) | closed form |
| Angle shortest-arc | exact except ties at ±π, which are **specified, not toleranced** | Two upstream conventions disagree |
| 2-bone IK | joint positions ≤ 1e-9·chain length | closed form; libm only |
| FABRIK | **property check**: bone lengths preserved ≤ 1e-9·L; end-effector error ≤ upstream tolerance 1e-5·L-ish and ≤ oracle's reported error + 1e-9; joint-position match **only if** algorithm replicated | FABRIK result depends on seed/ordering; do not demand equality for an independently implemented solver |
| Time/frame sampling | exact (Fraction) | Defined semantics |
| Serialization | canonical byte-identity after load→dump→load→dump | |
| SVG renderer | structure exact; numbers parsed and compared ≤ 1e-6 px | formatting at 1e-6 |
| Raster renderer | exact hash on pinned platform+backend; cross-platform bound = **max channel diff measured over the CI matrix**, then pinned and justified in-repo | No arbitrary SSIM threshold |

### 5.4 Verification matrix
- **FK/IK/constraints**: oracle vectors (C2) + property tests (hypothesis): bone length invariants, reachability, idempotence, symmetry under reflection, rotation covariance (rotating root rotates all joints).
- **Transforms & coordinates**: import conversion y-down→y-up round-trip tests; composition associativity tests.
- **Angular interpolation boundaries**: ±π, ±π±ε, 2π multiples, 3π; explicit tie rule tests; scalar-rotation full-turn retention.
- **Keyframe/timestamp semantics**: before-first/after-last, zero-duration spans, coincident keys, key at exactly sampling instant, fractional times.
- **Frame-rate independence**: same project sampled at fps 24/30/60/144 gives identical values at common timestamps (exact).
- **Serialization**: round-trip identity; schema migration fixtures; fuzz (hypothesis/atheris-style) for the container reader; limits.
- **Unsupported fields**: strict mode raises `ValidationError(code="unknown_field", path=…)`; lenient mode round-trips extras.
- **Renderer**: golden SVG; raster comparisons per §5.3.
- **Cross-platform**: CI matrix Linux/macOS/Windows × Python 3.14 (and floor version if D5 ≠ 3.14).
- **Rule:** a Python-only passing suite is *not* evidence of upstream equivalence; only the oracle-vector suites count toward C2.

---

## 6. Milestone Plan

### M0 — Decisions and baseline (no engine code)  [P]
Resolve D1–D5; independent review of this spec; (if authorized) run oracle harness at the pinned commit in an isolated sandbox, generate the FK/easing vectors, measure real float32/libm error to confirm §5.3; freeze semantics doc §3.3; create the project repository (none exists today at the working location) with `PROVENANCE.md`.

### M1 — Minimal vertical slice  [P]
Deliver, nothing more:
1. `model`: `Project` (schema_version, fps, canvas), one `Rig` (joint tree: id, parent, rest length, rest local angle), `Pose` clips as keyframe tracks per joint (angle channel + root x/y), `Timeline`.
2. `eval`: time model; easing = constant/linear/cubic-bezier(+presets)/smoothstep; shortest-arc angle channel; `evaluate(project, t)`.
3. `kinematics`: FK only (straight segments; bend deferred).
4. `render`: **SVG** backend (stdlib) for lines + circle head; PNG only if a raster backend is justified (Pillow vs skia-python decision recorded; both have 3.14 wheels).
5. `io`: canonical JSON v0.1 + validation errors with paths + lenient/strict unknown-field behavior.
6. `api` + `cli` (`validate`, `evaluate`, `render --frame/--time`, `schema`).
7. Tests: unit + hypothesis + golden SVG + serialization round-trip + (if M0 oracle ran) FK/easing oracle vectors via an upstream→Engine **test-only converter**.
Out of scope for M1: IK, bend/curves, joins, GUI, MCP, Manim, motion graphics, upstream container import, video, effects.
Exit criteria: every §5.4 row relevant to M1 has a passing executed test; `import animcore` pulls no third-party modules (checked by test); the SVG output of the demo figure walks across 3 poses reproducibly on 3 OSes.

### M2 — Kinematics depth  [P]
Bend/arc segments (with oracle vectors for bends in tweens and joins — the C2 gaps listed in §10 within the D3 scope); 2-bone analytic IK (Left/Right) + explicit `bend_side` data (no hidden state); n-chain FABRIK; reach/stretch rules; angle limits as *new* Engine feature (upstream has none) only if approved. Per D3, IK is validated by property tests and the §10 sanity vectors; **no upstream IK-compatibility claim**.

### M3 — Interchange  [P]
Upstream `.styk/.stkz` container reader (stdlib), importer for native keyframe documents (L-A subset), conversion profile `pivot32`; export of Engine project JSON. Compat level C0/C1 claims only with executed evidence.

### M4 — Manim adapter (separate distribution)  [P]
`EvaluatedScene`→Mobject mapping; time driven by Manim's updater; Manim-in-CI job with system cairo/pango. Test against Manim's own rendering of simple shapes (scene-graph equality, not pixels).

### M5 — Motion-graphics primitives  [P]
Paths/beziers, text (font handling decision), masks, compositions/precomps, per-node transforms; additional `scene` drawables and render support.

### M6 — Interface boundaries  [P]
Command/patch layer over `Project` (validated operations) as the common substrate for GUI and agent (MCP) front-ends; MCP server and GUI as separate components consuming `api`.

---

## 7. Reviewer focus list (not user decisions)

1. Is the canonical time model (integer timebase + rational sampling) over-engineered relative to "fps integer ticks"? Does it break importer simplicity?
2. y-up internal convention vs y-down native: is the conversion layer worth it for Manim identity mapping?
3. Local-vs-absolute angle storage: any upstream behavior (animation-origin re-rooting, bend interplay: upstream tweens relative to `parent.angle + parent.bend`) that local angles cannot represent? (Audit B notes relative angle is `angle − (parent.angle+parent.bend)`; M2 must decide whether bend is part of the parent frame.)
4. Is deferring "Both"-mode IK hysteresis and `bendReference` reasonable, given it is the observable "feel" of upstream IK?
5. Tie rule at exactly ±π: which convention? Note the two upstream functions disagree.
6. Should `eval` expose both per-time evaluation and an optional *sampled sequence* API for rendering efficiency without altering semantics?
7. Is zero runtime dependencies realistic once raster output and CLI ergonomics are required?
8. Check the claim that no existing Python library covers IK + keyframe timeline + articulated rigs (only informally surveyed).

---

## 8. Open Design Decisions requiring user approval

| ID | Decision | Options | Recommendation [P] |
| --- | --- | --- | --- |
| **D1** | **Licence of the new Engine** | **APPROVED by user: GPL-3.0-or-later** (alternatives considered: permissive with clean-room process) | Closed. See §4.3. |
| **D2** | **Authorize running upstream code (Node, pinned commit, isolated sandbox) to generate oracle vectors** | **APPROVED by user ("Allow sandboxed")** and executed | Closed. See §10. Re-running at a different upstream commit or with new inputs falls under the same authorization only if it keeps the same sandbox constraints. |
| **D3** | **Compatibility scope** | **APPROVED by user:** (i) L-A native keyframe FK/tween equivalence only for M1–M2; (ii) container import (C0/C1) at M3; (iii) StykAnimate extensions deferred | Closed. Consequence: IK built in M2 is an Engine feature validated by properties and sanity vectors, **with no upstream-compatibility claim**; Both-mode IK, Auto easing, rigs, layer sheet remain out of compat scope until a new decision. |
| **D4** | **Project name, repository location and identity** | **Name: `theia` — APPROVED by user.** Remaining: (a) PyPI/import names; (b) repo location. Facts [V, checked 2026-10-29]: PyPI project `theia` already exists (v0.9.2, "a lightweight log aggregator"), so the distribution name `theia` is **unavailable**; `theia-anim` and `theiaanim` returned 404 (free); no GitHub Python+animation repo named like it found. [I] "Eclipse Theia" is a well-known IDE project; not verified here, so avoid confusing search/branding overlap (tagline "theia — 2D rig animation engine"). | (a) distribution `theia-anim`, import package **`theia_anim`** (an import named `theia` would collide with the existing PyPI `theia` package if both are installed); CLI command `theia`. (b) New directory `/home/ubuntu/junhyeok-choe/gsel/theia` (sibling of the other repos there), `git init` only after confirmation. No StykAnimate branding. |
| **D5** | **Python version floor** | **APPROVED by user: 3.14 target, 3.12 core** (alternatives: 3.14 only; 3.11+ for Manim's floor) | Closed. Consequences: `requires-python = ">=3.12"` for the core distribution; CI matrix = 3.12 and 3.14 × Linux/macOS/Windows; no 3.13+/3.14-only syntax or stdlib in core (e.g., no `compression.zstd`, no PEP 649 deferred annotations, no template strings, no `except` without parentheses); the M3 importer declares its 3.14 requirement (or an optional `zstandard` fallback on 3.12 — decide at M3); the Manim adapter is a separate distribution that may use Manim's own ≥3.11 floor intersected with 3.12. |

Not requested of the user: library choices, module names, tolerance values — these are for the independent review.

---

## 9. Execution record

- Investigation actions: cloned upstream into the session scratchpad (read-only use); read docs and key source; dispatched three read-only subagents for the model/serialization, kinematics, and timeline audits; probed Python 3.14 library resolution with `uv` in a scratch venv; verified `compression.zstd`.
- After D2 approval: ran a bounded oracle spike (§10) in a `unshare -rn` + `node --permission` sandbox, writing only to the scratchpad. Upstream checkout stayed clean.
- Not done: no Pivot corpus or `.styk` sample available; no project repository exists, so no planning files were added to the user's workspace. This spec and the three audits remain in the scratchpad.
- Nothing committed, pushed, or published.

---

## 10. Oracle spike results (executed after D2 approval)  — all findings [V] unless noted

Scope: a bounded **verification spike**, not engine code. Artifacts in `scratchpad/oracle/` (`gen_vectors.mjs`, `analyze.py`, `smoke.mjs`, `out/vectors.json`, `out/analysis.json`, `out/SHA256SUMS`, `PROVENANCE.md`). Sandbox: `unshare -rn` (no network) + `node --permission` (read-only fs, no child processes/workers), Node v25.2.1, Linux x86_64 (WSL2). Upstream checkout unmodified (`git status` clean) at `def97214…`. The vectors cover: 7 bezier curves × 12 sample points, 6 easing modes, 4 `autoValue` cases, 14 `shortest` inputs, 14 IK cases (2-bone, 3-bone, 4-bone; bend ±1), 11 FK documents (chains of depth 1–20, unordered tree, scale 0.5/2/−1, curved segments, coordinates ≈1e5), 12 native tween documents (linear/constant/ease-in/ease-out/auto/bezier, wraps at 170°/π/−π/3π, duration 1, zero-duration mid key).
Independent Python reimplementations (written from the formulas, not from upstream code, though IK sign convention and the float32 rounding point were taken from what I had read) were compared with the vectors:

| Question | Result |
| --- | --- |
| Does upstream's evaluator run without `npm ci`? | **Yes**; four modules imported and executed. |
| **FK with float32 rounding emulated at each joint end (`pivot32` profile)** | **Bit-exact (0 error) on all 11 FK cases**, including curved segments, scale 0.5/2/−1, unordered segment arrays, 20-deep chains and coordinates ≈1e5. The profile = float64 root, `end = f32(start + L·scale·(cos a, sin a))` for straight and `f32(start + r(sin(a+b)−sin a), …)` for arcs, children start from the rounded parent. Python `math.sin/cos` matched V8 exactly on these inputs on this machine — **platform-dependence of libm remains unproven** (needs the CI matrix). |
| FK in pure float64 vs oracle | Max error ≤ 0.32 × the proposed bound `(depth+1)·ulp32(coord)` in all cases (largest absolute error 4.7e-3 at coordinates ≈1e5). The §5.3 derived bound **held with margin**. |
| Bezier | Upstream bisection vs exact solver: presets ≤ 1.5e-10; degenerate steep curves up to 4.6e-7. → tolerance must scale with slope (updated §5.3). `auto` (smoothstep), `linear`, `constant` match exactly. |
| Angle wrap | `shortest(a)=atan2(sin a, cos a)` matches to 1.1e-16. The alternative modular formula disagrees at `+π` (returns −π) and at `3π`. Exact ties are decided by the sign of floating rounding error in `sin(a)` (`shortest(−π)=−π`, `shortest(π)=+π`). **Upstream tween direction at an exact 180° difference: 0→π goes positive; π/2→−π/2 goes negative** (vectors `wrap-exact-pi`, `wrap-minus-pi`). The Engine must **specify** a tie rule; it cannot be inferred from math. |
| Native tween semantics | Hypothesis "interpolate **relative** angles (child − parent) by shortest arc after applying the easing progress once, then re-accumulate along the chain" reproduced the oracle within **1e-9** for linear, constant, ease-in, ease-out, custom bezier, three wrap cases, duration-1 and zero-duration-middle-key (ease modes ≤ 4.5e-10 from solver tolerance). Last keyframe holds exactly (`wrap-3pi` last tick = 3π, not wrapped). **Not covered:** bends in tweening (`parent.angle + parent.bend` term), joins, Auto with neighbours (only the endpoint was compared), `auto_easing`/PCHIP legacy path, color/opacity/camera/background. |
| 2-bone IK | Matches an independent law-of-cosines solution to ≤ 2.5e-14 for both bend signs, including unreachable (straight line toward target), exact reach and near-fold. Sign convention taken from code (+1 puts the knee at `+perp·h`). |
| n-bone IK (FABRIK) | Bone lengths preserved ≤ 7e-15; reachable 3-bone case ended with error 2.58e-6 (≤ tolerance 1e-5) after 4 iterations, equal to upstream's reported error; unreachable 4-bone case ends straight with 0 iterations and error = distance−reach. Joint positions for the chain depend on algorithm details; compare via properties, as planned. |
| IK "Both" mode / `bendReference` | **Not exercised** (needs stored reference); remains unverified and deferred. |

Consequences for the plan:
1. **C2 evidence for the FK + native tween subset is now attainable at bit-level** under the `pivot32` profile, and at a derived, empirically-confirmed bound in float64. §5.3's FK rows are confirmed; the bezier row was corrected.
2. The relative-angle shortest-arc reading of upstream tweening (§3.3, "Angles") is **supported by executed evidence** for the covered cases.
3. The ±π tie behavior is a real, observable divergence risk and is promoted to a **review item that M0 must close** (choose: match upstream's sign-of-sin behavior in the `pivot32` profile only, and define a deterministic rule such as "tie → positive" for the native profile).
4. Remaining C2 gaps to fill before any compatibility claim: bends in tweens, joins, Auto with neighbours, legacy PCHIP, color/opacity, camera, IK Both-mode.
5. None of these results establish equivalence with **Pivot Animator**; they establish equivalence with StykAnimate @ `def97214…` for the listed vectors only.

---

## 11. M1 implementation status (2026-10-29, written after implementation; supersedes planning text where they differ)

The user authorized starting implementation immediately after approving D1–D5 and the skeleton commit (the independent architecture review requested in the original brief has **not** happened; M1 is therefore provisional and should be reviewed with this spec).

Implemented in `src/kinemesis/` (zero runtime dependencies; Python 3.12 and 3.14 tested): `model`, `validation`, `serialization` (+ `schema`), `angles`, `easing`, `timeutil`, `kinematics`, `evaluation`, `scene`, `render/svg`, `api`, `cli`, `compat/pivot32`. 85 tests pass on 3.12.3 and 3.14.2, `ruff` and `mypy --strict` clean.

Deviations from the proposal, and decisions made while implementing (all reviewable, none user-approved):
- Module named `evaluation` (not `eval`, which shadows a builtin); `scene` stays separate from `render`.
- Time: keyframes are integer ticks of `Project.timebase` (default 14400 ticks/s: divisible by 24, 25, 30, 48, 50, 60, 72, 90, 100, 120, 144); evaluation takes exact rational seconds; floats mean their shortest decimal (`0.1` = 1/10 s). Frame `i` samples at `i / fps`.
- Easing kinds: `constant`, `linear`, `smoothstep`, `cubic-bezier` (x1, x2 in [0, 1]); owned by the outgoing key. Upstream's neighbour-aware "Auto" is deferred (D3).
- Channels: `x`, `y`, `scale`, `rotation` (scalars; full turns kept) and `angle:<bone>` (local, shortest arc; exact ties turn counter-clockwise). Before a track's first key the figure/rig default applies; after the last key the value holds.
- Coordinates: y-up, origin at canvas center; SVG renderer flips y with a `scale(1 -1)` group. Circle bones: diameter spans the bone. Scale multiplies lengths and stroke widths.
- Strict loader rejects unknown fields (`unknown_field` with JSON-pointer path); lenient keeps them in `extras` and writes them back; duplicate keys, NaN/Infinity, oversize and over-deep documents are rejected with codes.
- Layering is enforced by a test (`tests/test_svg_cli_arch.py`), as is "core imports only the standard library".

Oracle results with the real implementation (`tests/test_oracle.py`):
- FK (10 straight-segment vectors): within the derived bound `(depth+1)·ulp32` in both float64 and `pivot32` profiles; in `pivot32` all 55 of 55 compared joints are bit-identical to the oracle (the test asserts >= 90%; measured 100%); in plain float64 none are identical, as expected from float32 quantization.
- Native tween: 98 samples across linear/constant/ease-in/ease-out/bezier, a 170° wrap and a duration-1 case agree within 1e-9 (root x within 1e-9 × span).
- **Deliberate divergence:** at an *exact* ±π step the engine turns counter-clockwise; upstream's direction depends on rounding. Three vectors (`wrap-exact-pi`, `wrap-minus-pi`, `wrap-3pi`; the tie can occur in a child bone's relative angle) are excluded from equality and tested for determinism instead.
- **Not covered:** bend/arc FK (M2; the `bend` vector is skipped by name), upstream Auto easing and zero-duration keyframes (listed in `UNSUPPORTED`), IK of any kind, joins, colour/opacity/camera/background.
