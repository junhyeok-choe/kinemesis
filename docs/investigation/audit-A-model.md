# Audit A: StykAnimate-App document model, native serialization, validation

Repo: /tmp/claude-1000/-home-ubuntu-junhyeok-choe-gsel/92c3e784-38e3-4bbc-a193-90307707caf6/scratchpad/upstream/StykAnimate-App @ def97214. Paths below are relative to it. Tags: V = [VERIFIED-in-code], D = [DOCUMENTED-only], I = [INFERRED].

## 0. Headline findings
- The "native document" is an in-memory JSON object that is the Pivot decoder's schema (`version` 2-5, `figure_types`, `keyframes`, `backgrounds`) plus a `_styk` extension namespace. There is no separate StykAnimate schema. [V] src/pivot/model.mjs:145-170; src/demo.mjs:39-44
- No machine-readable schema exists. Validation is hand-written imperative code in two places: JS (src/pivot/model.mjs, authoritative) and Python (codecs/codec_bridge.py, weaker). See section 6.
- `.styk` and `.stkz` are generic JSON carried in a binary container. The container has no knowledge of the scene shape. [V] src/native-container.mjs
- Pivot concepts are not wrapped. `*_raw` fields, `aux_code`/`primitive_code` bitfields, `field28` and `color_override_raw` are first-class native fields, and version-gated semantics are in the model. [V] src/pivot/model.mjs:61-63, 364-435

## 1. In-memory document shape

**Document root** [V] src/demo.mjs:39-44 (`emptyDocument`) and src/pivot/model.mjs:134-170:
- Fields: `version` (2|3|4|5), `canvas_width`/`canvas_height` (int 1..100000), `fps` (int 1..1000), optional `frame_delay_ms` (int 1..65535, used when version<5), `auto_easing`, `auto_easing_disabled_raw`, `auto_easing_source`, `figure_types[]`, `keyframes[]`, `backgrounds[]`, `_styk{}`.
- Limits: at most 65535 figure types, 100000 keyframes, 30000 segments per figure, 1,000,000 total segments, 2,000,000 total objects. [V] model.mjs:164-186, 241

**Figure definition** (`figure_types[i]`). The code calls it "figure type"; the id is `figure_type_id`. [V] src/demo.mjs:12-17
- Fields: `figure_type_id` (int, unique), `name`, `segment_count` (derived by `syncDerived`, model.mjs:369), `segments[]`, `polyfills[]`, `image_assets[]`, `text_assets[]`, optional `segment_decode.global_style` ({outline_thickness, u28, rgb, u30}, model.mjs:300-317), optional `_styk{}` (movieclip, animationOrigin, colorMode, spatialMesh).

**Segment** (inside a definition) [V] demo.mjs:4-9; model.mjs:188-203:
- `segment_id` (handle, int 1..65535, unique per figure), `parent_id` (handle of the parent, 0 = figure origin), `length`, `angle_rad`, `thickness`, `bend_rad`, `primitive_code` (0..6), `aux_code` (0..255, bit 0 = static), `flags` (= primitive_code | aux_code<<8), `color_rgb`, `transparency` (0..255), `secondary` (gradient), `z_order`, plus derived `segment_kind`, `segment_type`, `visible`, `is_static`, `flag_bits`.
- Extension fields: `paint`, `_sticknodes`, `_stykRig`.

**Instance** (`keyframes[k].objects[j]`) [V] demo.mjs:19-24; model.mjs:50-70:
- Fields: `object_slot`, `unique_id` (int 0..0xffffffff, the persistent identity), `figure_type_id`, `root_x`, `root_y`, `scale` (float32, >=0), `color_override_raw`, `field28` (transparency byte), `angles[]`, `len_flag`+`lengths[]`, `bend_flag`+`bends[]`, `join`.
- Derived: `color_override_rgb`, `color_override_mix`, `transparency`, `opacity` (syncDerived, model.mjs:424-433).
- Extension fields: `_stykIK`, `_stykAnimationOrigin`, `_stykZIndex`, `_stykMovieclip`, `_sticknodesShapes`, `_sticknodesSprite`, `_styk{}` (e.g. `{locked:true}`, demo.mjs:61).

**Pose.** There is no separate pose object. A pose is the per-instance arrays `angles`/`lengths`/`bends` (always one entry per definition segment, in segment-array order) plus `root_x/root_y/scale`. `angles` is mandatory. `lengths` and `bends` count only when `len_flag`/`bend_flag` is truthy, otherwise the definition's value is used. [V] model.mjs:65-69; geometry.mjs:674-690

**Frame** (`keyframes[k]`) [V] demo.mjs:31-37:
- Fields: `duration_raw` (int 0..65535), `background_id`, `background_id_b`, `background_mix`, `camera`, `objects[]`, `object_draw_order` (permutation of object indices), `object_draw_order_unique_ids`, optional `_styk{}` (`frameId`, `easing`).
- Derived: `inbetweens` (= duration_raw-1 when version>=5), `hidden`, `duration_frames` (version<5). [V] model.mjs:420-423
- Timeline: tick start = cumulative sum of `duration_raw`. In version>=5 the last key counts at most 1 tick. [V] geometry.mjs:105-117

**Camera / scene.** `keyframes[k].camera = {is_default, x, y, scale, angle_rad}`, validated only when `!is_default`; scale must be > 0. [V] model.mjs:289-297. "Scene" is a layer-sheet track id, not a data object. [V] layer-sheet.mjs:27-31. Camera coordinates are offsets from the animation centre, angle in radians, and a smaller scale zooms in. [D] docs/CAMERA-EDITING.md:3-6

**Layers** (`_styk.layers`) [V] src/layers.mjs:10-15, 20-48:
- Shape: `{version:1, nextId, order:['layer-N'...], byId:{id:{name,visible,locked,parallax?,drawing?,color?}}, assignments:{<uid>:layerId}, defaultLayerId, activeId, fixed:{scene,camera}, ...folders}`.
- Layer order is separate from object slots. [V] layers.mjs:5

**Layer sheet** (`_styk.layerSheet`) [V] layer-sheet.mjs:24-90; [D] docs/layer-timeline.md:60:
- Shape: `{version:1, duration, nextId, tracks:{<'scene'|'camera'|layerId>:{end, keys:[{id:'cell-N', tick, value:{frameId|null}, sourceTick?, patchOnly?, movieclipPatches?, easing...}]}}}`.
- Must have a track for scene, camera and every layer. Key ticks are strictly increasing and below `track.end`.
- The doc states that `unique_id`, layer id, cell id and pose-source id are four different identities. [D] docs/layer-timeline.md:60, docs/timeline-identity.md:3
- When `layerSheet` exists, `timeline()` is re-clamped to `sheet.duration` and extended by camera and vfx clips. [V] geometry.mjs:118-123

**Authored animation** (`_styk.animation`) [V] animation-channels.mjs:93-130:
- Shape: `{version:1, nextKeyId, channels:[{id, target:{kind:figure|segment|polygon|layer|camera|scene,...}, property, keys:[{id,tick,value,interpolation,hidden?}]}]}`.
- The channel id is derived: `kind:uri(identity):property`.
- Pose keys point at `_styk.frameSources[frameId]`, which are retained native keyframes. [V] layer-sheet.mjs:33-39

**Other `_styk` keys found** (no registry): `name`, `format`, `format_version`, `palette`, `drawing`, `audio`, `cameraMotion`, `vfxClips`, `simpleFrameDraft`, `frameSources`, `movieclipSource`, `libraryKind`, `sticknodes`. [V] grep of `report._styk.*` in src/; docs/native-file-format.md:157-171

## 2. Topology, geometry conventions

**Parent links.** Each segment stores `parent_id`, the parent's `segment_id`, not an array index. 0 is the origin. This is a tree. The validator rejects missing parents and cycles. [V] model.mjs:188-219. `segments[]` order is arbitrary; geometry resolves parents lazily via `segmentAt`. [V] geometry.mjs:662-674. A "joint" is the end point of a segment, keyed by its `segment_id` (handle). Handle 0 is the figure root. [V] geometry.mjs:655

**Inter-figure joins.**
- `object.join = {target_object_slot, target_unique_id?, target_handle_id}` attaches the child's root to the parent's joint position at `target_handle_id`. [V] geometry.mjs:630-643; structure.mjs:123-137
- Joins address object slots, not UIDs. The code comment says "Joins address object slots, never UIDs or segment-array indices". [V] structure.mjs:167
- `normalizeFrame` rebuilds `target_unique_id` and `target_object_slot`. [V] structure.mjs:123-137
- Validation checks the target slot exists, the handle is in the target's type, and there are no cycles. [V] model.mjs:252-277
- An unresolvable join only produces a geometry warning ("Unresolved join"). [V] geometry.mjs:643

**Units and angle semantics.**
- Angles are radians and absolute: `angles[i]` is the world direction of segment i, not relative to its parent. Endpoint = start + length*(cos a, sin a). [V] geometry.mjs:75-82, 704; ik.mjs:3 ("absolute-angle skeletons")
- Relative angles are derived only for tweening: child angle minus (parent angle + parent bend). [V] geometry.mjs:298-306
- `bend_rad` is the total arc angle swept over the segment. Radius = length/bend; a straight line is used when |bend|<1e-7. [V] geometry.mjs:75-92
- `object.scale` multiplies each segment's `length` and the rendered `thickness` (times |scale|). Scale is uniform; there is no per-axis scale. [V] geometry.mjs:658-660, 773. Scale is applied at geometry time, not baked into `lengths[]`.
- Float32 rounding of endpoints (`Math.fround`) is part of the native semantics. [V] geometry.mjs:704

**Coordinates.**
- No doc states the y direction.
- Evidence suggests y-down screen coordinates with the origin at the canvas top-left. The default torso has angle -PI/2, a ground object sits at y=423, and the walker at y=292 is above it. [I] demo.mjs:13, 57-62
- The reference mirror and rotate code uses a plain `(x cos - y sin, x sin + y cos)` rotation. [V] animation-origin.mjs:72

**Animation origin** (docs/animation-origin.md, src/animation-origin*.mjs):
- Re-rooting metadata `figure._styk.animationOrigin = {handleId, rotationHandleId, reversed, support?}` plus per-instance `_stykAnimationOrigin = {x, y, offsetX?, offsetY?, ghosts?}`. [V] animation-origin.mjs:10-28, 68-81; [D] animation-origin.md:7-17
- Effective root = pivot - path vector. Offsets are in rotation-property space. [V] animation-origin.mjs:68-75, 106-117
- PIV export removes this metadata after sampling. [D] animation-origin.md:35-39

**Rig and IK.**
- `_stykIK` is per-instance, keyed by segment handle string. Each entry has `enabled`, `pinned`, `chainLength` (1..256), `bendDirection` (1, 0 or -1), `target{x,y,rotation}`, `followers`, optional `allowStretch`, `attachmentOffsets` and spatial fields. [V] src/ik.mjs:125-150
- `_stykRig` is per-segment (`connector`, `stretch`, `follow`, `orientation`, `response`, `weighted`, `spatial`). [V] rig-constraints.mjs:19, 33-38; geometry.mjs:688. Docs: [D] docs/RIG-CONSTRAINTS.md.
- IK validation requires the driven segment to be non-derived. [V] model.mjs:54

## 3. Native JSON schema and round-tripping
- `.styk` is the whole document. `.stkz` is a stripped document produced by `nativeFigureDocument`: 1 keyframe, `backgrounds:[]`, `_styk:{format:'StykAnimate', format_version:1, name, libraryKind?}`. [V] native-figure.mjs:59-83
- `.stkz` handling: object slots are renumbered, a join leaving the set is detached with root_x/root_y and angles frozen from the solved geometry, runtime caches are deleted, `_stykSource` is dropped from nested movieclip documents, and `unique_id` is reassigned on import. [V] native-figure.mjs:10-28, 39-57; [D] docs/native-file-format.md:15-16
- `.stykmov` is a third kind (magic `STMV`) not mentioned in the main doc intro. [V] native-container.mjs:28; backend/native_format.py:41
- Unknown-field preservation is by construction: the container is generic JSON and the editor spreads objects (`{...source}`). The container never mentions scene fields. Tests assert it. [V] tests/native-container.test.mjs:74-80, 213-242; tests/native-figure.test.mjs:52-75 (custom figure field, `_stykStyle`, `futureMetadata`, opaque `_stykSource`-named fields kept)
- Load normalisation removes only `editable_paths`, `_codec`, `_stykWeb`. [V] native-container.mjs:697-699; backend/server.py:626-629
- Legacy wrapper `{format:'stykanimate', version:1, document}` is unwrapped. Plain JSON `.styk` is accepted (BOM tolerant). [V] native-container.mjs:193-198, 688-693
- `_stykSource = {kind, version, source_base64, sha256, document_sha256, document_digest_version}` embeds the original PIV/STK bytes for byte-exact re-export; the sha256 is verified on load. [V] native-container.mjs:672-684; tests/native-figure.test.mjs:34-37; [D] backend/README.md:94-102
- Version/format gate: Python checks `_styk.format=='StykAnimate'` and `format_version==1` (codecs/codec_bridge.py:247-249). No such check was found in src/*.mjs; grep for `format_version` shows only writers. Not found in the JS loader.

## 4. Container format
Header (56 bytes, little endian) [V] native-container.mjs:171-183; backend/native_format.py:36:
- bytes 0-3: magic `STYK`, `STKZ` or `STMV`
- byte 4: version 1 or 2
- byte 5: codec (v1 must be 1 = zlib; v2 allows 0 stored, 1 zlib, 2 zstd)
- bytes 6-7: flags, must be 0
- bytes 8-15: raw (uncompressed) length of the JSON; bytes 16-23: stored length; bytes 24-55: SHA-256 of the raw JSON bytes

Version 2 [V] native-container.mjs:208-250; [D] docs/native-file-format.md:24-89:
- After the header: u32 section count (max 64), compressed JSON skeleton, then N x 64-byte section records, then section payloads.
- Section record: kind (1 = numeric arrays, 2 = binary blobs), codec, reserved fields (must be 0), raw length, stored length, SHA-256, 8 bytes padding.
- Big values in the skeleton become marker strings: `S2B:type:section:offset:count` (arrays of >=32 finite numbers; u8/u16/u32/i32/f32/f64 chosen as smallest exact type), `S2S:` (base64 field values in `source_base64`/`data_base64`), `S2D:` (data URLs of >=64 KiB in `data_url`/`styk_tiles`), `S2E:` (escape for literal strings that start like markers). [V] native-container.mjs:29-40, 456-495
- Identical array markers resolve to the same JS array instance, so pose-sequence sharing survives a save/load. [V] native-container.mjs:19-20, 337-344
- Limits: 256 MiB per file and per section, 384 MiB skeleton, 1 GiB materialisation budget (MAX_BYTES*4). [V] native-container.mjs:23-27
- Writers prefer zstd with a vendored WASM codec, falling back to zlib. [V] native-container.mjs:134-146

Version 1 is the 56-byte header followed by zlib-compressed JSON.

Hashing is SHA-256 over uncompressed bytes for the skeleton and every section. A mismatch gives "damaged (checksum mismatch)". [V] native-container.mjs:204, 237, 242

Implementations:
- JS (worker side): src/native-container.mjs (`decodeDocument`, `liftDocument`, `buildContainerV1/V2`, `normalizeDecodedDocument`, `validateNativeFigure`, `verifyEmbeddedSource`).
- Python: backend/native_format.py. `encode` (v1, constant `VERSION=1`), `encode_v2`, `decode` (returns JSON bytes, v1/v2/plain JSON), `_lift`, `_materialize`. Used from backend/server.py:42, 613, 736, 785.
- Small spec drift: the JS header comment writes the S2D marker as `<n> <p>` with a space, while the regex and the doc use a colon. [V] native-container.mjs:11 vs 39

## 5. Validation and error reporting

**JS** [V]:
- `messageError(new Error(''), "<errors.group.key>", {params})` builds a plain `Error` with `.messageKey` and `.messageParams`. The English diagnostic message is interpolated from `src/locales/en-features/errors.mjs`. [V] localized-error.mjs:1-8; message-error-core.mjs
- There are no custom exception classes and no numeric error codes.
- Some container and figure errors also set `.code`: `codec_unavailable`, `document_too_large`, `invalid_native_figure`, `invalid_movieclip`, `invalid_native_version`, `invalid_document`. [V] native-container.mjs:163, 548, 654-667, 691, 695
- Parameter labels pass through a label table (`validationLabel`) so field names are localised on failure only. [V] validation-labels.mjs; model.mjs:20-23
- Localisation: 27 locale packs in src/locales/packs/*.json. [V] ls
- Entry points:
  - `validateScene`, a synchronous wrapper over the cooperative generator `validateSceneSteps` (yields progress). [V] model.mjs:134-141
  - `validateObjectChanges` (incremental, for gestures). [V] model.mjs:76-119
  - `validateLayerState`, `validateLayerSheet`, `validateAnimationDocument(Steps)`, `validateOriginSupportSteps`, `validateSticknodes*`, `validateIK`.
  - Load orchestration: `prepareEditorLoadSteps` in src/editor-load.mjs:30-75. Order: movieclip graph, scene, drawings, audio, layers, animation, layerSheet, frame identities, retained sources.
- Typical checks (model.mjs:134-362):
  - Integer ranges: canvas, fps, `duration_raw`, ids.
  - float32 range: `float32` rejects values that overflow `Math.fround`.
  - rgb triplets, uniqueness of figure ids / handles / uids.
  - Parent cycles, join targets and cycles, draw-order permutation, camera, backgrounds.
- No path (JSON pointer) is reported with an error, only a label.

**Python:**
- Container errors are `ValueError` with fixed English strings; there is no code. [V] backend/native_format.py:68-109, 392-461
- The service wraps them in `ApiError(status, code, message)`, giving JSON `{ok:false,error,code}`. Codes seen: `invalid_native_figure` (422), `invalid_movieclip` (422), `invalid_native_version` (422), `invalid_document` (400), `source_expired` (410), `document_too_large` (413), `cache_limit` (413), `backend_closed` (503). [V] backend/server.py:122-127, 185-206, 619-640, 685; [D] backend/README.md:29
- Scene validation on the Python side is `validate_document`, which raises `PivError` with English messages. [V] codecs/codec_bridge.py:243-340

## 6. Machine-readable schema
**Not found.**
- Searched: `*.schema.json`, `*.d.ts` (only vendor/resvg/index.d.ts), `tsconfig*`, `@typedef` in src/. Found only layout and telemetry schemas (src/shell/layout-schema.mjs, src/telemetry-schema.mjs), which are unrelated.
- The schema exists only as the validators above and as prose in docs/native-file-format.md, which covers the container and a few `_styk` records (palette, drawing), not the scene.
- The Python validator, JS validator, and the Pivot codec in codecs/ (piv_document.py etc.) are three non-generated definitions of the shape.

## 7. What is inseparable (port must drop or redefine)

**Tied to the Pivot binary:**
- `version` 2..5 semantics: fps from `frame_delay_ms` (v<5), duration_frames vs inbetweens, color_override signed vs unsigned handling, last-frame count. [V] model.mjs:410-433; geometry.mjs:105-117
- Raw bit fields: `primitive_code` 0..6, `aux_code`/`flags` (bit 0 = static, `flags = prim | aux<<8`), `field28`, `color_override_raw` (low 24 bits RGB, high 8 bits mix), `duration_raw`, `auto_easing_disabled_raw`, `segment_decode.global_style.u28/u30`. [V] model.mjs:61-63, 364-433
- Handle limits (65535), `unique_id` limited to 32-bit, 16-bit counts. Join as (object slot, handle id) with slot order = object array order. [V] model.mjs:171-198; structure.mjs
- `_stykSource` embeds original PIV/STK bytes for byte-exact re-export. [V] native-container.mjs:672
- Python codecs/ (PIV/STK reader and writer) and "parent tools" that are referenced but not in the repo (`tools/` does not exist). [V] ls; backend/README.md:10

**UI/editor concerns inside the document:**
- Layers, layerSheet (exposure sheet), simpleFrameDraft, frameSources, animation channels, cameraMotion, vfxClips, audio, drawing/raster layers, movieclips, palette. All are under `_styk` and are tied to the editor.
- Per-object `_styk.locked`, layer `visible`/`locked`/`color`.
- A reimplementation of the Pivot semantic subset (figure_types, segments, instances, frames, joins, camera, backgrounds) can be cleanly separated from everything under `_styk` and `_stykIK`/`_stykRig`/`_stykAnimationOrigin`. Evidence: `validateScene` reads `_styk` only for `animationOrigin`/`spatialMesh`/`colorMode`/`movieclip` hooks (model.mjs:222-224, 365).
- Still, the geometry evaluator itself (src/pivot/geometry.mjs, 1499 lines) imports rig, IK, movieclip, VFX and origin modules and cannot run without them. [V] geometry.mjs:596-720

## Tests and fixtures
Unit tests relevant to the scope:
- Container: tests/native-container.test.mjs (322 lines, 22 tests); backend/test_native_format.py (246 lines); tests/native-files.browser.mjs (browser).
- Figure: tests/native-figure.test.mjs (168 lines, 6 tests).
- Validation: tests/model-incremental.test.mjs, tests/animation-origin-validation.test.mjs, tests/animation-validation-steps.test.mjs, tests/editor-load.test.mjs, tests/timeline-identity.test.mjs, tests/range-figure-operations.test.mjs, tests/editor-origin-support.test.mjs, backend/test_stk_topology.py, backend/test_native_layout.py, backend/test_server.py.

Golden inputs:
- **Not checked in as files:** no `.styk`, `.stkz`, `.stykmov`, `.piv` or `.stk` file exists in the repo (find over the tree).
- Most tests build documents in code (`createDemo()`, `new Editor()`, inline literals), so these are self-contained goldens.
- Corpus tests need an undistributed corpus. Browser tests reference `../Pivot Animator v5/Animations/*.piv` and `Figures/Legacy/man.stk` outside the repo. Audit scripts use `corpusPath('Downloads/16 Akane vs Akato Segundo round (3).piv')`, documented as "not in the repository". [V] tests/support/corpus.mjs:1-4; tests/app.browser.mjs:43, 49. The "37 original PIV fixtures" in docs/PIVOT_PARITY.md:72 are also not in the repo. [D]
- Checked-in JSON fixtures that exist: tests/sticknodes-synthetic.json (a Stick Nodes binary as base64, synthetic, importer only); tests/geometry-cooperative-baseline.json (geometry baseline with `objects[...]` including root and joints); tests/fixtures/autopose-*.json (autopose, not the scene). [V] heads inspected.
- Useful helper: scripts/read-native-document.mjs reads a native container into JSON (dev tool).
