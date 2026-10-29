# Audit B: Kinematics, constraints, geometry (StykAnimate-App @ def97214)

Paths are relative to the repo root. Static reading only: I did not execute upstream code (the sandbox refused `import()` of it). Tags: V = [VERIFIED-in-code], D = [DOCUMENTED-only], I = [INFERRED]. Every tag below is spelled out in full.

Framing: only the FK core in `src/pivot/geometry.mjs` reimplements Pivot. IK and rig constraints (connector, Smart Stretch, angle lock, weighted, spatial) are StykAnimate extensions modelled on **Stick Nodes**, not Pivot (`docs/RIG-CONSTRAINTS.md:611-621`) [DOCUMENTED-only]. Pivot `.piv` cannot store IK, and export bakes it to plain angles/lengths (`docs/inverse-kinematics.md:32`) [DOCUMENTED-only]. The license is GPL-3.0-or-later (`package.json` license field) [VERIFIED-in-code]. This matters if code is ported rather than re-derived.

## 1. Forward kinematics (pose to world joints)

Entry: `buildGeometrySteps` (`src/pivot/geometry.mjs:596`) -> `objectAt` (`:621`) -> `segmentAt` (`:662`) [VERIFIED-in-code].

- **Traversal.** `geometryDefinition` (`src/pivot/geometry-definition.mjs:189-228`) builds a BFS order. Roots are segments whose `parent_id` is not a known `segment_id`, normally 0. Children are visited in array order. Unreachable cyclic segments are excluded. Duplicate parent:id edges are last-wins (`:213-214`) [VERIFIED-in-code].
- **Start point.** `start = joints.get(parent_id) || root` (`geometry.mjs:674`). `joints` is a Map seeded `{0: root}` (`:655`). `root = (obj.root_x, obj.root_y)` (`:630`) [VERIFIED-in-code].
- **Per-segment inputs** (`:676-689`):
  - `angle = ik?.angles[i] ?? obj.angles[i] ?? runtime_segments[i].angle_rad ?? seg.angle_rad ?? 0`.
  - `bend = obj.bend_flag ? obj.bends[i] : (rt.bend_rad ?? seg.bend_rad ?? 0)`.
  - `length = (ik?.lengths[i] ?? (obj.len_flag ? obj.lengths[i] : seg.length)) * scale`, with `scale = Number(obj.scale ?? 1)` (`:658`).
  - [VERIFIED-in-code]
- **Angles are ABSOLUTE.** They are radians in world frame and do not inherit from the parent or parent bend. The default walker has a torso at -PI/2 and legs at 1.12 and 2.00, all parented to 0 (`src/demo.mjs:11-19`) [VERIFIED-in-code].
  - The relative form exists only for tweening: `readRelativeAngle` computes `angle - (parent.angle + parent.bend)` (`geometry.mjs:298-306`). It is rebuilt as `angles[parent] + bends[parent] + relative` (`:451-460`) [VERIFIED-in-code].
  - The editor adds the bend delta to child angles explicitly when it bends a segment (`tests/editor-rig-bend.test.mjs:41`). FK itself never does [VERIFIED-in-code].
- **Zero direction, handedness, y.**
  - Angle 0 is +x. The direction is `(cos a, sin a)` (`:704`) [VERIFIED-in-code].
  - y is down. Torso -PI/2 is "up" and legs at about +1.1 to +2 rad point down (`demo.mjs:13-18`). I found no y-flip in `geometry.mjs` or `renderer-geometry.mjs` (grep for `scale(...,-1)` came back empty) [INFERRED].
  - So a positive angle is clockwise on screen. This is also the reason IK `bendDirection=+1` places the knee on the +90 degree (`(-uy,ux)`) side, labelled "Right" (`src/ik.mjs:222-223`, `src/ik-view.mjs:273`) [INFERRED].
- **Straight segment** (|bend| < 1e-7, `geometry.mjs:701`): `end = (sx + L cos a, sy + L sin a)`, rounded with `Math.fround` per coordinate (`:704`) [VERIFIED-in-code].
- **Curved segment** (`arc`, `:75-98`):
  - `bend` is the TOTAL signed sweep (radians) over the segment. The tangent turns from `a` to `a+bend`, and the arc length is `length`.
  - Radius is `r = L / bend`. Point `i/steps` is `(sx + r(sin(a + bend i/steps) - sin a), sy + r(cos a - cos(a + bend i/steps)))`.
  - `steps = max(8, min(160, ceil(|bend|*16), ceil(|L|/4)))`.
  - Non-finite input returns `[]`. The final point is `fround`ed and replaces the last arc sample (`:707-711`).
  - [VERIFIED-in-code]
  - The chord used by IK is `L * 2 sin(b/2)/b` in direction `a + b/2` (`ik.mjs:264-268`). This is algebraically identical to the arc end [INFERRED].
- **Joint registration.** `joints.set(segment_id, handle)`, where handle is the `fround`ed end (`:712-715`). The `fround` is applied per joint, so errors compound down a chain. The root is NOT rounded [VERIFIED-in-code].
- **Scale and flip.**
  - There is no separate figure rotation or flip in FK. Whole-figure rotation is just changed absolute angles. `animationRotation = angles[0] - segments[0].angle_rad` is used only by rig/spatial code (`src/animation-origin.mjs:49-55`) [VERIFIED-in-code].
  - Scale multiplies lengths only (`:689`), and bends are not scaled. A negative scale gives a negative length, so the figure is a 180 degree point reflection, not a mirror. Thickness is multiplied by `|scale|` (`:773`) [VERIFIED-in-code].
  - `image_text_flags` mirrors only image/text drawing and the spatial rig (`src/renderer-geometry.mjs:278`, `src/rig-spatial.mjs`) [VERIFIED-in-code].
- **Joined figures.** The child root is `parent.joints.get(target_handle_id ?? 0)`, copied (`:631-643`). Only position is inherited, with no parent scale or rotation. An unresolved join emits a warning and keeps the object's own root. Join order is topological, with cycle detection [VERIFIED-in-code].
- **Polygons** (`:807-860`): vertices come from the first handle's joint, then, per edge, either the end joint or the edge's arc points (reversed if traversed backwards, first point dropped). Curved edges use `|bend| > 1e-7`. A duplicate closing point is popped (`:832-837`). Drawables are sorted by `z` with a stable `Array.sort` (`:963`), in the order polys, mesh, segments [VERIFIED-in-code].
- **Time sampling** (`evaluatedNativeFrame`, `:325-509`):
  - Default is linear (`:201`), with shortest-arc blending for angles via `atan2(sin,cos)`.
  - Legacy `auto_easing` documents use PCHIP over runs (`:202-223`, `src/keyframe-easing.mjs:70`).
  - Per-key Auto/Bezier modes go through `easedProgress` and `autoValue`.
  - Tweening happens on relative angles. `root_x`, `root_y`, `scale`, `lengths` and `bends` are interpolated per channel.
  - This is the real "evaluate at t" path, and it must be ported before FK.
  - [VERIFIED-in-code]

## 2. Inverse kinematics (`src/ik.mjs`, 386 lines)

**Exports** [VERIFIED-in-code]:

| Export | Line | Notes |
|---|---|---|
| `MAX_IK_CHAIN=256` | 10 | |
| `hasPinnedIK(obj)` | 14 | |
| `translateIKTargets`, `remapIKFollowers` | 17, 32 | editor helpers |
| `ikLayout(figure)` | 42 | `{ids, children, order}`, BFS |
| `ikChain(figure, handle, length, layout)` | 54 | chain bone indices, root to tip; stops at derived joints |
| `ikConstruction(seg)` | 63 | |
| `ikFollowerIndices`, `ikFollowers`, `ikAttachments` | 70, 97, 112 | |
| `validateIK(obj)` | 125 | |
| `ikBendReference(points, lengths, previous)` | 158 | |
| `solveIKPoints(points, lengths, target, bendDirection=1, {iterations=32, tolerance=1e-5, bendReference})` | 174 | mutates `points`; returns `{iterations, error, bendReference?}` |
| `solveObjectIK(figure, object, root, layout, controllers, {includePoints, rigPlan, followTargetOrientation})` | 274 | returns `null` or `{angles, lengths?, results: Map, points}` |
| `interpolateIK(a, b, t, sample)` | 365 | |

**Controller schema** (`validateIK`, `:125-155`): table keyed by the end bone's `segment_id`, valued `{enabled, pinned, chainLength, bendDirection, allowStretch?, target:{x,y,rotation}, followers, bendReference?, ...}`. `bendDirection` is -1 (Left), 0 (Both/automatic) or 1 (Right) (`src/ik-view.mjs:273`). Only `enabled && pinned` controllers are evaluated (`:275`). Unpinned controllers are editor-gesture only [VERIFIED-in-code].

**Output is a preprocessing step.** IK emits replacement absolute angles, plus stretched lengths if stretch is on. FK (section 1) then runs unchanged on them (`geometry.mjs:676-689`). Its internal FK uses unrounded doubles (`ik.mjs:279-282`), so it differs from the final `fround`ed joints by float32 noise [VERIFIED-in-code].

**Solve order in `solveObjectIK`:**
- Forward-pose all bones from the pre-IK angles (`:286`).
- Sort the active controllers by ancestor rank and then handle id (`:288-291`).
- Controllers sharing a bone are skipped with `{conflict:true}` (`:294`).
- Per controller:
  1. Base is the parent joint of `chain[0]`.
  2. Chords are curve-aware (`:298`).
  3. Stretch factor is `max(1, dist/reach)`, uniform over the chain (`:299-305`).
  4. Run `solveIKPoints`.
  5. Convert the solved points to angles: `atan2(...) - bend/2 - (chord<0 ? PI : 0)`, wrapped via `wrap(a - old)` (`:311-317`).
  6. Propagate. Bones off the chain get the parent's angle delta (rigid carry). The first articulated child group is forced to `target.rotation + followers[id]` (`:334-347`).
  7. Re-run FK on the affected subtree (`:345`).
- A later controller therefore sees earlier solutions. This ordering is deterministic and unique.

**Two-bone analytic solve** (`:195-224`), taken when `n===2` and both lengths are greater than EPS:
- `d = clamp(dist, |a-b|, a+b)`.
- `along = (a^2 - b^2 + d^2) / (2d)`.
- `height = sqrt(max(0, a^2 - along^2)) * bendDirection`.
- Knee = `base + u*along + perp*height`, with `perp = (-uy, ux)`.
- End = `base + u*d`.
- If `dist >= total - EPS` or `n===1`, the chain is laid out straight along the target direction (`:193`, checked first).

**FABRIK** (`:225-258`), used for n>2 or a zero-length bone:
- Cap is 32 passes. Tolerance is 1e-5 on end-to-target distance (`:174`, `:257`).
- Each pass runs backward then forward and then tests. Early-out if already within tolerance and on the requested side (`:232`).
- Seed: a collinear chain gets a deterministic bend offset `sin(PI i/n) * total * .05 * bendDirection` (`:243-246`).
- If the chain is on the wrong side, it is reflected once across the base-target axis (`:236-239`).
- The result can be left with residual error at the cap. This is documented at `docs/inverse-kinematics.md:22`.

**State and determinism** [VERIFIED-in-code]:
- `solveObjectIK` mutates nothing outside its own scratch copies. It uses no module-level state, only per-call locals.
- `evaluateIKPose` (`src/ik-evaluation.mjs:28-48`) is a value-keyed memo in a WeakMap per document. It cannot change results. Its inputs are root, scale, angles, effective lengths, bends, ids and `JSON.stringify(_stykIK)`.
- The "hysteresis" state is the stored `controller.bendReference` `{side, angle, axis, ratio, shape?}`.
  - It is written ONLY by the editor at gesture time (`src/editor-ik.mjs:32,66,94,169-177,225,274,290`; `src/editor-motion-path.mjs:153-203,296-303`).
  - It is never written during geometry build. It travels in the pose and in saves.
  - `interpolateIK` copies it from the left key, interpolating only `shape` (`ik.mjs:377-379`).
  - If it is absent (Both mode), it is inferred from the pre-IK FK pose by `ikBendReference` (`ik.mjs:177`). That is a pure function of the pose.
- Conclusion: evaluation at arbitrary t is a PURE function of (interpolated pose, stored bendReference). It does not depend on previous frames or seek order. `tests/ik.test.mjs:106-121` asserts exactly this, rebuilding forward and backward and comparing [VERIFIED-in-code].
- Caveat on state: FABRIK for n>2 starts from the pre-IK angles (or `bendReference.shape`). Those are pose data, but they must be carried faithfully. The editor "materializes displayed angles" on FK edits (`docs/inverse-kinematics.md:26`) [DOCUMENTED-only]. Faithful reproduction needs the stored angles and `bendReference`, not just targets [INFERRED].
- **Both mode** (`bendDirection===0`, `:177-221`):
  - It adopts `reference.side` (`:191`).
  - It considers the opposite branch only if `magnitude < total*.02` (near extension) or `throughFold` (`:205-206`).
  - A flip happens only when `improvement = -4*magnitude/a*bendDirection*(-uy*poleX + ux*poleY) > 0.002` (`:210-211`).
  - Exact fold (`dist <= foldTolerance` and `|a-b| < EPS`) places the knee at `axis + side*PI/2` when `ratio > 1e-6`, else at `reference.angle` (`:213-220`).
  - `foldTolerance = max(1e-10, total*1e-6)` in Both mode, and `EPS` otherwise (`:180`).

## 3. Joint constraints

**Angle limits.** NOT FOUND for ordinary joints or IK. Grep for `limit|minAngle|maxAngle` in `ik*.mjs` and `editor-ik.mjs` hit only a comment. This agrees with `docs/inverse-kinematics.md:34` ("does not add joint limits") [VERIFIED-in-code]. Limits that DO exist:
- Spatial mechanical joints: `motion {min,max}` clamp, in radians for hinges (`src/rig-spatial.mjs:31-34,53-56`).
- Smart Stretch ratio `[min,max]`.
- Connector slide `t` in [0,1].

**Connectors** (`src/rig-constraints.mjs:208-220`):
- Start and end anchors are joint ids, where 0 is the root.
- `distance = |end - start|`. The angle is `atan2(dy,dx) - bend/2`, with bend clamped to +-1.99*PI. The length is `distance / (2 sin(bend/2)/bend)`.
- The segment length channel is the slide fraction `t = clamp(len, 0, 1)`. The handle is `start + (end-start)*t`, or the arc point at `sweep = bend*t`.
- The restLength must be at least 1e-8 (`:81`).
- The connector's angle and length are fully derived, so it is a derived joint. IK is blocked on derived joints (`ik.mjs:57`, `rig-constraints.mjs:163`).

**Weighted joints** (`src/rig-weighted.mjs:291-304`):
- Position is `origin + sum(weight_k * (anchor_k - origin))`. There are 1 to 16 anchors, with |weight| at most 100.
- Angle is `atan2(dy,dx)`, or the input angle if the offset is below 1e-8. Length is the offset magnitude.

**Smart Stretch** (`src/rig-constraints.mjs:231-243`, `221-230`):
- A driver segment's `ratio = clamp(|length| / (|scale| * restLength), min, max)` (`:232-238`). Its length is rescaled by `ratio/actual`.
- Width response is `keep`, `inverse` (`1/max(.01, ratio)`) or `scale`.
- Followers inherit the impulse through the plan's `inputs/outputs` (`:132-145`). The amount is `clamp(1 + (incoming-1)*multiplier, -100, 100)`. The follower's vector is stretched anisotropically along `followAxis`: `x = cos(rel)*amount`, `y = sin(rel)`, then `angle = axis + atan2(y,x)` and `length *= hypot` (`:221-230`).
- Modes: `stretch`, `rigid`, `stop`.

**Angle lock** (`:195-205`, `244-249`):
- Modes are `world`, `figure` and `parent`. Space is `rendered` or `authored`.
- `locked = lock.angle + figureDelta + multiplier * wrap(refAngle - restAngle - figureDelta)`, plus an optional secondary term.
- "Authored" space applies the lock before stretch. The default applies it after.

## 4. Numerical constants

| Value | Where | Guards |
|---|---|---|
| `EPS=1e-10` | `ik.mjs:11` | zero length, reach and fold tests, chord bend |
| `iterations=32`, `tolerance=1e-5` | `ik.mjs:174` | FABRIK |
| `foldTolerance=max(1e-10, total*1e-6)` | `:180` | Both mode, folded endpoint noise |
| `total*.02`, `total*.04`, `improvement>.002` | `:206,205,211` | Both-mode flip gates |
| `ratio>1e-6` | `:216` | exact-fold limit |
| `total*1e-7` | `:166,236,242` | bend side, reflect, collinear tests |
| `.05` | `:244` | singularity seed bend |
| `MAX_IK_CHAIN=256`, handle <= 65535 | `:10,131` | chain length, id range |
| quaternion/unit-vector norm 1e-5 | `:146,149` | validation |
| construction anchor `|len|<=.001` | `:79` | follower grouping |
| `1e-8`, `1e-7` | `ik.mjs:313,323` | rig branch tests |
| rig refine: 40 iterations, tol 1e-4, step 1e-4, damping 1e-5, det 1e-14, delta clamp +-.35, backtracking [1,.5,.25,.125], null-space step .18 | `src/ik-rig.mjs:88-122` | projected-rig solver |
| spatial knee `|a-b|+1e-8`; normalize 1e-10, 1e-6 | `src/ik-spatial.mjs:6,33,35` | 3D IK |
| rig `EPS=1e-8`; bend clamp +-1.99*PI; `number()` ranges (restLength 1e-8..1e6; min 0..100; influence -4..4; multiplier -10..10; angles +-1e6) | `rig-constraints.mjs:14,212,81-119` | connector, stretch, lock |
| straight/curved threshold `1e-7` | `geometry.mjs:701,789,824` | FK |
| arc steps 8..160 | `geometry.mjs:83` | tessellation |
| `Math.fround` on every joint | `geometry.mjs:700-712` | native float32 emulation |
| angle-path keys 2..64 | `rig-angle-path.mjs` | validation |
| cache limits 1024 entries, 250000 bones | `ik-evaluation.mjs:8` | memo only |

All of these are [VERIFIED-in-code].

## 5. Purity and import graph

- `src/ik.mjs` imports exactly: `localized-error.mjs`, `ik-spatial.mjs`, `rig-constraints.mjs`, `rig-spatial.mjs`, `ik-rig.mjs` (`:1-9`) [VERIFIED-in-code].
- Transitive closure outside the locale tables, in 13 files: `message-error-core`, `ik-spatial`, `animation-origin`, `animation-origin-support`, `rig-spatial`, `validation-labels`, `spatial-projection`, `rig-constraints`, `rig-angle-path`, `rig-weighted`, `ik-rig`, `localized-error`, plus `ik.mjs`. `localized-error` pulls `locales/en*.mjs` (string dictionaries only). No DOM, editor or renderer globals [VERIFIED-in-code]. `ik.mjs` is Node-callable.
- `src/ik-evaluation.mjs` imports `ik.mjs` and `rig-constraints.mjs` only. `src/ik-joined.mjs` adds `animation-style.mjs`. `ik-topology.mjs` and `ik-view.mjs` are editor and UI, not for use as an oracle [VERIFIED-in-code].
- `src/pivot/geometry.mjs` has about 31 import statements, with a closure of about 78 files (excluding locales). That includes VFX, canvas, WebGPU-adjacent code (`vfx-webgpu`, `vfx-gpu`, `vfx-canvas`), the movie clip modules, the Stick Nodes decoder, `paint.mjs`, `drawing-*` and `vendor/earcut.mjs` (via `renderer-geometry.mjs`). Direct imports are listed at `geometry.mjs:1-34` [VERIFIED-in-code].
- The DOM is touched only inside draw and offscreen paths: `geometry.mjs:1093-1095`, `paint.mjs:71,105`. Module load is not DOM-dependent. `tests/ik.test.mjs:1-8`, `tests/geometry-pose.test.mjs:1-6` and the `package.json` test script (`node --test tests/*.test.mjs`) import it under plain Node [VERIFIED-in-code].
- To call it as an oracle:
  - Build a `report` with `emptyDocument`, `createObject`, `createFrame` (`src/demo.mjs:24-44`).
  - Call `evaluatedFrame(report, index, t)` then `buildGeometry(report, frame)`.
  - Read `.objects.get(slot).joints` (Map: segment_id -> `{x,y}`, key 0 = root) and `.segments[i].points`/`.polys[i].points`.
  - [INFERRED] from test usage (`tests/ik.test.mjs:15-28,106-121`).
  - The `Editor` class is not needed except as a convenience.

## 6. Porting risks

1. **Float32 emulation.**
   - `Math.fround` is applied to each joint end (`geometry.mjs:700-712`), but the root and IK internals are float64. Port with `struct`/`numpy.float32` at exactly those points.
   - Skipping it gives drift of about 1e-6 relative, and it can flip threshold decisions like "Both" fold handling (`tests/ik.test.mjs:134`).
2. **Transcendentals.** V8 `Math.sin/cos/atan2/hypot/pow` are not guaranteed bit-identical to glibc or Python's `math`. Use tolerances, not equality. Source angles and lengths from files are float32-derived (`src/pivot/model.mjs:37-39`, `:200`).
3. **`wrap` vs `shortest`.**
   - `wrap(a) = ((a+PI) % TAU + TAU) % TAU - PI` (`ik.mjs:12`) maps +PI to -PI.
   - `shortest = atan2(sin,cos)` (`geometry.mjs:50`) keeps +PI.
   - JS `%` truncates toward zero. Python `%` floors, so use `math.fmod` to mirror it.
4. **Object key order.** Integer-like keys iterate ascending in JS regardless of insertion. This affects `Object.entries(_stykIK)` (`ik.mjs:275`) and `followers`/`spatialFollowers` tables. Python dicts keep insertion order. Sort numerically (the controller sort at `:290` is already total).
5. **Sort stability.** `Array.sort` is stable in modern V8 and Python `sorted` is too. Drawable z ties (`geometry.mjs:963`) rely on insertion order: polys, mesh, then segments in array order (not BFS).
6. **NaN and -0.**
   - `Math.max/min` propagate NaN. Python `max/min` do not. This applies to `clamp` (`ik.mjs:13`) and `clampRig`.
   - `Math.sign(-0)` returns -0. `Number(null)=0`, `Number(undefined)=NaN`, and `??` vs `||` differ at `geometry.mjs:674-689`.
   - `Object.is` is used in cache compares.
   - Several guards rely on `Number.isFinite` returning early with `[]` (`:76`).
7. **Rounding.** `Math.round` is half toward +infinity; Python `round` is banker's. `roundEven` exists at `src/pivot/model.mjs:24`. `Math.trunc` is used for colors and field28 (`geometry.mjs:321,394`).
8. **Duplicate or cyclic ids.** Duplicate `segment_id` or edges are last-wins. Cyclic segments are silently dropped, and `joints.get(pid) || root` falls back to the root for unknown parents.
9. **Curved segments.** Tessellation `steps` depends on `|L|` and `|bend|`. Polygon vertices therefore depend on `ceil` of floats, so matching needs exact `ceil` semantics. A negative scale makes `L` negative, hence `|L|`.
10. **Evaluation breadth.** Pose channels, `_stykAnimationOrigin`, layer sheets, movie clips, camera and VFX are layered on top (`geometry.mjs:534-585`). A bare FK oracle should use native keyframe documents only.
11. **IK seed dependence.** For chains longer than 2, results depend on the stored pre-IK angles and `bendReference.shape` (see section 2). Reproduce the stored pose, not just the targets.

## Not found
- Joint angle limits for ordinary joints or IK: not found. Searched `ik*.mjs`, `rig-constraints.mjs`, `geometry.mjs`.
- A y-up or y-flip transform in geometry: not found. Searched `geometry.mjs` and `renderer-geometry.mjs`.
- A figure-level rotation or flip parameter inside FK: not found. Rotation lives in the angles, and mirroring is the image/text flag only.
