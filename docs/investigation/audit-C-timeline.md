# Audit C: keyframe interpolation, easing, timeline, pose evaluation (StykAnimate-App @ def97214)

Paths are repo-relative. Tags: V = [VERIFIED-in-code], D = [DOCUMENTED-only], I = [INFERRED]. The sandbox refused to execute repo code. Numbers marked "re-derived" come from running the same one-line formula in an independent scratch script.

## 0. Evaluator entry points (time -> scene)
- `evaluatedFrame(report, index, t = 0, absoluteTick, {tweenCache, skipMovieclips, skipMovieclipPatches} = {})` at src/pivot/geometry.mjs:534. This is the single top-level evaluator. Renderer, playback worker, export worker, thumbnails and Pivot materialization all call it (playback-worker.mjs:159, export-frame-worker.mjs:52, pivot-export-materialize.mjs:109). V
  - Pipeline: layer-sheet branch (`sampleLayerSheet`, :536-545), else `evaluatedNativeFrame` (:547), movieclip crop (:548-566), `composePoseChannels` then `composeAnimationChannels` (:569-575), movieclips, `applyLayerOrder`, camera/VFX time stamp (:577-584). V
- `evaluatedNativeFrame(report, index, t = 0, tweenCache, requestedUids)` at geometry.mjs:325. This is the pairwise keyframe[index] -> [index+1] interpolator. V
- `sampleLayerSheet(report, tick, {sampleLegacy, sampleNative, resolveGeometry, skipMovieclipPatches})` at src/layer-sheet.mjs:125. This path serves every app-opened document (docs/animation-modes.md:3 D).
- `composePoseChannels(report, baseFrame, tick, options)` at src/animation-pose.mjs:140; `samplePoseTrack` :103; `buildVirtualPoseTrack` :72.
- `composeAnimationChannels(report, frame, tick, {resolveGeometry})` at src/animation-channels.mjs:268; `sampleAnimationChannel(channel, tick)` :175.
- The caller supplies both `(index, t)` and `absoluteTick`. Native uses (index, t); channels and sheets use absoluteTick. Inconsistent pairs would mix results. I
- Tick to (index, t) mapping is duplicated in callers (`playbackLocation`, playback-worker.mjs:69; `tickFrame`, export-frame-worker.mjs:39). Each does a binary search for the last row with `start <= tick`, then `t = count > 1 ? (tick-start)/count : 0`. V

## 1. Time model
- Tick = one output frame, a 0-based integer index. A stored keyframe is `report.keyframes[i]`; the two are distinct (docs/TIMELINE.md:197-201 D). The UI shows tick+1 (docs/camera-motion.md:228 D).
- `nativeTimeline` (geometry.mjs:105) gives each keyframe `{start, count}`. `count = max(0, duration_raw)` (`frameTicks`, :100). For version >= 5 the last frame's count is `min(1, n)`. V
  - `duration_raw` is an integer 0..65535 (pivot/model.mjs:233-237 V). 0 means hidden (model.mjs:422 V). Output frames = sum of counts (:418 V).
- `timeline(report)` (geometry.mjs:118) extends the last row to cover `animationEndTick` and camera/VFX clip ends; a layerSheet clamps to `sheet.duration`. V
- Native tick k of an n-tick frame has t = k/n, so t never reaches 1 inside the interval. Test: tick 0..9 gives x = 100*t (keyframe-easing.test.mjs:58-59 V).
- fps: integer 1..1000 (model.mjs:158-162 V). For version < 5, `fps = roundEven(1000/frame_delay_ms)` (:410-411 V). `duration_seconds = total/fps` (:419 V). It is NOT used in pose/scalar interpolation. It is used by camera-motion noise (camera-motion.mjs:56,82 V), the movieclip clock (movieclips.mjs:115 V), audio and export. Interpolation is purely in ticks.
- Integer vs fractional:
  - Export requires integer ticks (export-frame-worker.mjs:40 V). The editor and playback pass integers.
  - The math is continuous in fractional ticks (animation-channels.mjs:175-184 V). Tests sample 1.25, 9.999 (keyframe-easing.test.mjs:48,109 V).
  - Authored keys are integers 0..10,000,000 (animation-channels.mjs:129 V). Sheet keys are integers < `track.end` <= duration <= 10,000,000 (layer-sheet.mjs:15,34-40 V).
- At or after the last key:
  - Scalar holds `a.value` (animation-channels.mjs:183 V).
  - Native returns the last frame (geometry.mjs:328 V).
  - A pose track's last key has `duration_raw = 1`, fraction 0 (animation-pose.mjs:88 V).
  - Sheet layers vanish at `tick >= track.end`; scene and camera hold (layer-sheet.mjs:134 V).
- Before the first key:
  - Scalar returns `undefined`, so the channel contributes nothing (animation-channels.mjs:177 V).
  - Pose returns null, which becomes `blankPoseFrame` (figures absent) (animation-pose.mjs:105,167 V).
- Version < 5 with no `_styk.easing` holds with no tween (geometry.mjs:328 V; keyframe-easing.test.mjs:174-179 V).
- With coincident (zero-duration) rows the last wins (`ceil` midpoint, `start <= tick`). V

## 2. Data structures
- Native frame: `{duration_raw, objects[], object_draw_order, background_id, background_id_b, background_mix, camera:{is_default,x,y,scale,angle_rad}, _styk:{frameId, easing}}` (demo.mjs:31-37 V). Object fields include `unique_id, figure_type_id, root_x, root_y, scale, angles[], bends[]/bend_flag, lengths[]/len_flag, field28, color_override_raw, join, _stykZIndex` (geometry.mjs:340-470 V). Doc: `version, fps, auto_easing, keyframes, figure_types`.
- Authored: `_styk.animation = {version:1, nextKeyId, channels[]}` (animation-channels.mjs:95-96 V).
  - Channel: `{id, target:{kind,uid|id,handleId,polygonId,figureTypeId}, property, keys[], nativeProperties?, maskedRanges?, useBasePose?, orderAnchor?, movieclipCurve?, clipEnd?}`.
  - Key: `{id, tick, value, interpolation, bezier?, hidden?, passthrough?, nativeCurve?:'pchip', nativeRotation?, nativeValueMode?}` (:121-135 V). Pose value is `{frameId}` or `{frameId:null}` (blank).
- Sheet: `_styk.layerSheet = {version:1, duration, nextId, tracks:{[id|'scene'|'camera']:{end, keys[]}}}`. Key: `{id, tick, value|sourceTick, interpolation, bezier?, movieclipPatches?, patchOnly?}` (layer-sheet.mjs:26-56 V).
- Property vocabulary: animation-properties.mjs:4-11 V.

## 3. Easing (src/keyframe-easing.mjs)
- Modes (:7-14 V): `auto`, `bezier`, `ease-in`, `ease-out`, `linear`, `constant`. `hold` is an input alias for `constant`; an absent mode means `linear` (:16 V).
- Sample functions:
  - auto progress is smoothstep `t*t*(3-2t)` (:8).
  - bezier uses `key.bezier ?? [0.42,0,0.58,1]` (:5).
  - ease-in `[0.42,0,1,1]`, ease-out `[0,0,0.58,1]` (:6).
  - constant `t<1 ? 0 : 1`; linear `t`.
  - `easedProgress` clamps the fraction to [0,1] (:64-69).
- Cubic bezier solver (:49-63 V): P0=(0,0), P3=(1,1), coordinate `3(1-t)^2 t a + 3(1-t) t^2 b + t^3`. Pure bisection on x(u): `low=0, high=1, u0=t`, at most 40 iterations, break when `|x-t| < 1e-10`; `t<=0` gives 0 and `t>=1` gives 1. No Newton step. Then y(u). Validation requires four finite numbers in [0,1] and mode `bezier` (:19-21), which keeps x monotone. Test values: ease-in(.5)=0.3153568125725393, ease-out(.5)=0.6846431874274608, default bezier(.25)=0.1291619310473198 (keyframe-easing.test.mjs:29-31 V).
- Auto = `autoValue(a, b, fraction, duration, previous, following)` (:80-96 V):
  - Returns `a` if `fraction<=0`, `!(duration>0)` or `a===b`; returns `b` if `fraction>=1`.
  - `slope = (b-a)/duration`. Neighbour secant d = `(a-prev.value)/prev.duration` before, `(next.value-b)/next.duration` after.
  - Tangent is 0 if the neighbour is missing, non-finite, d is 0, or `sign(d) != sign(slope)`. Otherwise with h = current duration and hn = neighbour duration: `w1 = 2h+hn`, `w2 = h+2hn`, `m = (w1+w2)/(w1/d + w2/slope)` (duration-weighted harmonic mean).
  - Hermite: `a + (b-a)(3t^2-2t^3) + duration*((t^3-2t^2+t) m0 + (t^3-t^2) m1)`, clamped to [min(a,b), max(a,b)]. An isolated pair has m0 = m1 = 0, which is smoothstep.
  - Neighbours count only if their own mode is `auto`: previous key's mode for m0, key b's mode for m1 (animation-channels.mjs:187-193; geometry.mjs:188-193 V). Passthrough keys and null values are excluded.
- Ownership: a key owns its OUTGOING interval. Code: `easedProgress(a,...)` at animation-channels.mjs:185 V; native `a._styk.easing` at geometry.mjs:331 V; docs/keyframe-easing.md:1-2 D. Auto's shape also depends on adjacent keys' modes. `inheritedKeyEasing` (:41-48 V) copies the previous visible key, else `hold`. Discrete properties must be `constant` (:22-25 V).
- Native manual modes apply the timing curve ONCE to t before interpolating all pose/camera/background fields (geometry.mjs:331 V). Auto passes raw t to `autoValue` per parameter and uses smoothstep only for the background (:506 V). `_stykSpatial` and `_stykVfx` interpolate on the raw t even in Auto (:367-368,507 V).

## 4. Angular interpolation
Two different wrap helpers exist:
- geometry.mjs:50 `shortest(a) = atan2(sin a, cos a)`, range (-pi, pi]. Re-derived: +pi -> +pi, -pi -> -pi (sign of sin decides the tie), 2*pi -> -2.4e-16 (not exactly 0), 3*pi -> 3.1415926535897927. Used for native pose relative angles, camera `angle_rad` (geometry.mjs:495-500), Auto angular neighbours and the legacy pchip unwrap. V formula, re-derived numbers.
- native-property-curve.mjs:2 `shortestPropertyAngle(x) = ((x+pi)%2pi + 2pi)%2pi - pi`, range [-pi, pi). Re-derived: +pi -> -pi, -pi -> -pi, 2*pi -> exactly 0. Used for scalar curves flagged `nativeRotation` and the `pchip` branch (animation-channels.mjs:186,218-225 V).
- Exact 180 degrees: the helpers choose opposite directions for a +pi difference. Exact ties are rare in floats, but an oracle must pick one. I
- Native pose angles are interpolated relative to the parent (`readRelativeAngle`, geometry.mjs:298-306), unwrapped as `a + shortest(b-a)`, then re-accumulated down the parent chain (:450-458 V). With `animationOrigin`, the pre-Set-Origin physical chain is used (docs/animation-origin.md:23-25 D; geometry.mjs:416-436 V).
- Explicit scalar `rotation` keys without `nativeRotation` interpolate numerically and keep full turns: 0 to 4*pi at tick 5 gives 2*pi (keyframe-easing.test.mjs ~line 270 V). The `nativeRotation` flag is validated as `true` only on `rotation` (animation-channels.mjs:133 V).
- Camera angle with Auto across 170 to -170 degrees is continuous (keyframe-easing.test.mjs:262-270 V).

## 5. Non-numeric and discrete channels
- Discrete channels return `a.value` (hold): `backgroundId`, `zIndex`, `paint`, discrete VFX (animation-properties.mjs:20; animation-channels.mjs:183 V). Document validation forces `constant` only for `zIndex` (:139 V); legacy `linear` labels on backgrounds are tolerated (comment :137-138).
- Pose channels hold the source frame; interpolation happens inside the virtual native report (animation-channels.mjs:183 V).
- Figure presence:
  - Native emits only objects in `a`. An object absent from `b` keeps `a`'s state until b starts (geometry.mjs:363 V). New objects appear at b's start. Draw order is a's until t >= 1.
  - Authored: blank before the first pose key; sheet layers vanish at `track.end`.
- Z-order: `_stykZIndex` is a held scalar, and `applyLayerOrder` stable-sorts within each layer (layers.mjs:68-89 V).
- Scalar colour ARGB (animation-channels.mjs:195-212 V):
  - A null value returns `a.value` (it hands control back to the scene track).
  - Native mode: the top byte is the mix. If both are 0, return `a`. Otherwise for RGB: if mixA = 0 then av = bv; if mixB = 0 then bv = av; `av + trunc((bv-av)*t)` per byte.
  - Otherwise each byte is `round(lerp or autoValue)`, then `>>>0`.
  - Native-frame `colorTween` (geometry.mjs:307-324) uses the same trunc rule; Auto uses `Math.round(parameter(...))` per byte (:471-491). VFX colour is RGB only, round and clamp (vfx-paint.mjs:4).
- Native opacity byte `field28`: `o + trunc((n-o)*t)` (geometry.mjs:392-394 V).
- Background `tweenBackground` (background.mjs:217-266 V): integer mix 0..255 with `trunc`/`floor`, snaps `j` to an integer within 1e-9, collapses `m >= 254`.

## 6. Purity and caches
Evaluation is a pure function of (document, tick) given correct invalidation. I
- animation-pose.mjs:8-9 `tracks`/`sourceIndices` WeakMaps. The track cache is validated only by `cached.keys === channel.keys`; cleared by `invalidatePoseCache` (:47). V
- geometry.mjs:34-45 `authoredTimelines` (cached `timeline(report)`) plus an `evaluationGenerations` counter, cleared by `invalidateEvaluationCaches`. In-place edits to `duration_raw` or keys without calling it would go stale. V
- layer-sheet.mjs:10,128-130 `cache` WeakMap keyed on the `layerSheet` state identity; `samples` cleared each call. animation-channels.mjs:67 `channelIndices`.
- `PlaybackTweenCache` (src/playback-tween-cache.mjs:215-226 V): worker-only, 1024-entry LRU, keyed on object/next/figure identity. Caches only when endpoints are deep-equal and `!legacyEasing`, and stores the computed result. A test asserts `deepEqual` with the uncached output (tests/playback-tween-cache.test.mjs:12-24 V).
- Module scratch arrays `runTimes`/`runValues` (geometry.mjs:248) are used synchronously. Benign.
- Movieclip presence index and camera-follow (a forward spring pass, lazily extended, keyed by evaluationGeneration; camera-follow.mjs:245) are derived caches, outside a Pivot oracle's scope.
- Outputs alias input objects ("unchanged frames retain identity"), so callers must not mutate them. editor-ranges.mjs:122 clones. I

## 7. Pivot-compat `auto_easing`
- `usesLegacyNativeEasing = report.auto_easing && !keyframes[index]._styk?.easing` (keyframe-easing.mjs:70-72 V).
- Per parameter (geometry.mjs:181-225, 251-296 V):
  1. An explicit `auto` runs `autoValue`.
  2. If not legacy, linear on the already-eased t (angular uses `shortest`).
  3. If legacy, native PCHIP over a "run": extend left/right while `frameTicks(neighbour) > 1` and the object has the value. Times are cumulative frame ticks and angles are cumulatively unwrapped. Endpoint slope is the 3-point formula with a `3*d0` clamp; interior slope is the weighted harmonic mean with `w = (2h0+h1)/(3(h0+h1))` (`pchipAt`, :160-180).
- Any explicit `_styk.easing` object, even `linear`, disables the fallback for that interval (docs/keyframe-easing.md:38-41 D; code :70-72 V). `legacyEasing` forces `len_flag/bend_flag` arrays (geometry.mjs:399 V).
- Virtual pose tracks copy `...report`, so `auto_easing` still applies to keys whose source has no easing (animation-pose.mjs:87,94 V). The authored equivalent is `nativeCurve:'pchip'` (native-property-curve.mjs:3-25; native-property-projection.mjs:47 V).
- On sheet conversion, keys get `version<5 ? 'constant' : auto_easing ? 'auto' : 'linear'` (editor-layer-sheet.mjs:34 V). A sheet's `auto` is therefore StykAnimate's monotone cubic, NOT Pivot PCHIP. Unedited imported spans still evaluate through the `sampleLegacy` baseline (native PCHIP) (layer-sheet.mjs:136-141 V). Export bakes explicit easing and sets `auto_easing:false` (pivot-export-materialize.mjs:129,166 V).
- A Pivot oracle should use `evaluatedNativeFrame` on a plain native doc (no layerSheet, no channels). Auto and the sheet are StykAnimate extensions.

## 8. Constants
- Bezier: 40 iterations, 1e-10 tolerance; presets in section 3. `PlaybackTweenCache.maxEntries` 1024.
- Join rotation delta threshold 1e-12 (animation-pose.mjs:244). Background snap 1e-9, collapse at 254 (background.mjs:232,263).
- Limits:
  - duration_raw 0..65535; fps 1..1000; frame_delay_ms 1..65535.
  - key ticks <= 10,000,000; channels <= 100,000; keys <= 1,000,000.
  - camera scale >= 1e-6; scale and width <= 1e6; opacity in [0,1].
- Camera-motion log-zoom clamp +-8 (camera-motion.mjs:69); follow limit 100,000 frames.
- `trunc` for native bytes, `round` for authored/Auto bytes. `Math.sign` treats 0 as "different sign". Hidden keys sort first at equal tick (animation-pose.mjs:77).

## 9. DOM-free modules and import graph
- keyframe-easing.mjs imports (V, from import lines):
  - src/localized-error.mjs, which imports src/locales/en.mjs (an aggregate of data-only locale modules) and src/message-error-core.mjs.
  - src/locales/en-features/keyframeEasing.mjs.
  - src/animation-properties.mjs, which imports localized-error and src/vfx.mjs. vfx.mjs imports localized-error, vfx-registry, vfx-paint; vfx-paint imports paint; paint imports localized-error.
  - No DOM at import. `paint.mjs:71,105` touch `document`/`OffscreenCanvas` lazily inside functions.
  - `cubicBezierProgress`, `easedProgress`, `autoValue` and `easingMode` read only their arguments. To use them standalone, copy lines 5-16 and 49-96 (no imports needed).
- Core evaluator: the closure of pivot/geometry.mjs, animation-channels.mjs, animation-pose.mjs and layer-sheet.mjs is about 76 non-locale modules. Examples: animation-origin(-support), animation-style, camera-motion/follow, layers, layer-parallax, movieclip-*, ik*, rig-*, spatial-*, vfx*, drawing-raster, surface-raster, paint, pivot/{background,surfaces,geometry-*,structure}, sticknodes/*, vendor/earcut.mjs. Importable under plain Node: tests/animation-pose.test.mjs:4 imports geometry.mjs under `node --test` V; geometry.mjs:12 comment says scene evaluation is independent of the DOM D. DOM use is inside draw functions only (geometry.mjs:1095, background.mjs:130,163).
- DOM-bound (unusable as an oracle): src/layer-timeline.mjs (`document.createElement` at :42), timeline-*, keyframe-easing-popover/view, *.browser.mjs.
- Synthetic-doc builders: src/demo.mjs (`emptyDocument`, `createFrame`, `createObject`; imports only animation-origin.mjs). `emptyDocument` has fps 24, version 5, `auto_easing:false`, first-frame easing `hold` (demo.mjs:39-44 V). `Editor` is also Node-importable.

## 10. Test inventory
Inline and synthetic (reusable as golden fixtures; built with demo.mjs, no external files):
- tests/keyframe-easing.test.mjs (287 lines): bezier values, per-mode scalar vs native vs playback packet vs export, Auto properties, wrapped angles, version<5 holds. Uses `Editor`, so it is not pure-evaluator.
- tests/native-tween-sampling.test.mjs (104 lines): carries its own reference PCHIP sampler and compares with `Object.is` against `evaluatedFrame`. It is the most oracle-like test and imports only geometry.mjs.
- tests/animation-pose.test.mjs, animation-pose-review.test.mjs, animation-pose-support.test.mjs, animation-empty-pose.test.mjs, animation-channels.test.mjs, playback-tween-cache.test.mjs, stored-frame-playback.test.mjs (Worker + Editor), keyframe-defaults.test.mjs, geometry-pose.test.mjs, timeline-channels.test.mjs, tweener.test.mjs, editor-inbetween*.test.mjs.
- tests/export-sampling.test.mjs covers pixel-smoothing sizes only (EXPORT_SMOOTHING), not time sampling. docs/export-sampling.md is likewise about smoothing. Tick-to-frame sampling lives in export-frame-worker.mjs:39.
Undistributed Pivot corpus (skipped when absent via tests/helpers/local-fixtures.mjs `missingFixture`; `STYK_REQUIRE_FIXTURES=1` forces them):
- `../Pivot Animator v5/Animations/tween_camera.piv` (tests/editor-animation-origin.test.mjs:148).
- `../Pivot Animator v5/Animations/Legacy/walking.piv` (tests/pivot-export-materialize.test.mjs:138).
- `../docs/piv_corpus_manifest.json` (tests/import-wire.test.mjs:32).
- Akane and other `.piv` samples via tests/support/corpus.mjs (`STYK_CORPUS_DIR`) in akane-*.mjs and *.browser.mjs.
- docs/PIVOT_PARITY.md:262-266 D: T04 (interpolate pose/length/bend/color/opacity/camera/background) and T05 (auto-easing, wrapping, tick-to-fraction mapping) are unchecked. The project itself does not claim Pivot parity for these.
- Not found: any committed numeric table of Pivot-evaluated outputs. Searched tests/fixtures (autopose JSON and UI chrome only), tests/helpers, tests/support.
