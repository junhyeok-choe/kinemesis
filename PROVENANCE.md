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
| `angles.py` | M1, 2026-10-29 | Own design: wrap to (-pi, pi], exact ties turn counter-clockwise (spec 3.3) | Upstream behavior studied (two differing wrap functions); no code translated | Test: `tests/test_angles_easing.py`; divergence at exact ties documented in `tests/test_oracle.py`. |
| `easing.py` | M1 | Public definitions: CSS cubic-bezier, smoothstep; own bisection solver (64 steps) | Upstream solver read for tolerance analysis; no code translated | Equivalence tested against oracle vectors with a solver-tolerance-derived bound. |
| `kinematics.py` | M1 | Textbook forward kinematics; scale multiplies lengths only (as observed upstream) | Behavior studied; no code translated | Oracle: `tests/test_oracle.py::test_fk_*` (derived bound; float32 profile nearly bit-exact). |
| `compat/pivot32.py` | M1 | Observed upstream behavior: float32 rounding of joint ends (`Math.fround`), `atan2(sin, cos)` wrap | Read in upstream; re-implemented via `struct` | Comparison profile only; not engine semantics. |
| `evaluation.py` | M1 | Own design: exact rational time, outgoing-key easing ownership, hold after last key | Behavior studied; no code translated | Oracle: native tween vectors (98 samples) within 1e-9; unsupported vectors listed in the test. |
| `model.py`, `validation.py`, `serialization.py`, `schema.py`, `scene.py`, `errors.py`, `timeutil.py` | M1 | Own design | Upstream document model studied only to define what *not* to copy | No upstream schema exists; the format is new. |
| `render/svg.py`, `api.py`, `cli.py` | M1 | Own design; standard SVG | No | Golden SVG tests in `tests/golden/`. |
| Remaining engine modules (IK, bend/arc, raster, importers, adapters) | **not started** | — | — | Add one row per module when it exists. |

Rules for new rows: name the semantic source (public spec such as CSS cubic-bezier / Fritsch–Carlson PCHIP / FABRIK paper, own design, or oracle vector), state explicitly if upstream code was read or translated, and link the test that executes the equivalence claim.
