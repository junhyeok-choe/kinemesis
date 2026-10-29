# Provenance log

Purpose: record, per component, where its semantics come from and whether upstream source was consulted (GPL-3.0-or-later project decision D1: translating upstream code is permitted, but each such file must keep the upstream notice, carry a dated modification notice, and be listed here).

Upstream: https://github.com/filippocalippo/StykAnimate-App @ `def97214c2b491fbce82647f625a73f78416c6d8` (GPL-3.0-or-later).

| Component | Status | Source of semantics | Upstream source consulted? | Notes |
| --- | --- | --- | --- | --- |
| `docs/ARCHITECTURE-SPEC.md` | draft | Investigation of upstream docs/source; own proposals | Yes (read) | Text is original; facts about upstream are cited with `file:line`. |
| `docs/investigation/*` | draft | Subagent audits of upstream, spot-checked by the lead | Yes (read) | Tagged VERIFIED / DOCUMENTED / INFERRED per claim. |
| `fixtures/upstream-oracle/out/vectors.json` | generated 2026-10-29 | **Output of running upstream code** (`keyframe-easing.mjs`, `ik.mjs`, `demo.mjs`, `pivot/geometry.mjs`) via `gen_vectors.mjs` | Executed in sandbox | Numeric facts of a GPL-3.0-or-later program's behavior; distributed under this project's GPL-3.0-or-later. Keep `fixtures/upstream-oracle/PROVENANCE.md` with any copy. |
| `fixtures/upstream-oracle/gen_vectors.mjs`, `smoke.mjs`, `analyze.py` | written 2026-10-29 | Own test tooling; imports upstream modules only at run time; builds documents with upstream's `demo.mjs` builders and uses the schema field names it reads | Consulted | Not engine code. Not copied from upstream. |
| `LICENSE` | — | Verbatim GPLv3 text from https://www.gnu.org/licenses/gpl-3.0.txt (identical to the copy in upstream apart from one trailing blank line) | n/a | |
| Engine code (`model`, `io`, `eval`, `kinematics`, `scene`, `render`, `api`, `cli`) | **not started** | — | — | Add one row per module when it exists. |

Rules for new rows: name the semantic source (public spec such as CSS cubic-bezier / Fritsch–Carlson PCHIP / FABRIK paper, own design, or oracle vector), state explicitly if upstream code was read or translated, and link the test that executes the equivalence claim.
