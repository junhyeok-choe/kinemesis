// Oracle vector generator (test tooling, not engine code). Reads upstream modules only.
// argv: <upstream-root> <upstream-commit>. Writes JSON to stdout.
import {pathToFileURL} from 'node:url';
const [root, commit] = process.argv.slice(2);
const imp = rel => import(pathToFileURL(`${root}/${rel}`).href);
const ke = await imp('src/keyframe-easing.mjs');
const ik = await imp('src/ik.mjs');
const demo = await imp('src/demo.mjs');
const geo = await imp('src/pivot/geometry.mjs');
const PI = Math.PI;
let seed = 12345;                       // deterministic LCG, no Math.random
const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
const seg = (id, parent, length, angle, bend = 0) => ({
  segment_id: id, parent_id: parent, length, angle_rad: angle, thickness: 8, bend_rad: bend,
  primitive_code: 0, aux_code: 0, flags: 0, segment_type: 'line', segment_kind: 'line',
  color_rgb: [0, 0, 0], transparency: 0, visible: true, z_order: id});
const fig = (id, segments) => ({figure_type_id: id, name: 'T' + id, segment_count: segments.length, segments,
  polyfills: [], image_assets: [], text_assets: []});
const jointsOf = (report, frame, slot) => {
  const g = geo.buildGeometry(report, frame), o = g.objects.get ? g.objects.get(slot) : g.objects[slot];
  return Object.fromEntries([...o.joints.entries()].map(([k, v]) => [k, [v.x, v.y]]));
};
const out = {meta: {upstream: 'https://github.com/filippocalippo/StykAnimate-App', commit, node: process.version,
  generator: 'oracle/gen_vectors.mjs', note: 'JSON.stringify drops the sign of -0. Numbers are shortest round-trip doubles.'}};

// 1. Easing scalar functions ------------------------------------------------
const grid = [0, 1e-9, 0.01, 0.1, 0.25, 0.333333333333, 0.5, 0.75, 0.9, 0.99, 1 - 1e-9, 1];
const curves = {'default': ke.DEFAULT_BEZIER, 'ease-in': [0.42, 0, 1, 1], 'ease-out': [0, 0, 0.58, 1],
  'steep': [0.9, 0, 0.1, 1], 'flat-start': [0, 0.9, 0.9, 0], 'linearish': [0.33, 0.33, 0.66, 0.66], 'corner': [0, 0, 0, 1]};
out.bezier = Object.entries(curves).map(([name, pts]) => ({name, points: pts, samples: grid.map(t => [t, ke.cubicBezierProgress(t, pts)])}));
out.modes = ['auto', 'bezier', 'ease-in', 'ease-out', 'linear', 'constant'].map(m => ({mode: m,
  samples: grid.map(t => [t, ke.easedProgress({interpolation: m}, t)])}));
const autoCases = [
  {a: 0, b: 10, duration: 4, prev: null, next: null},
  {a: 0, b: 10, duration: 4, prev: {value: -5, duration: 4}, next: {value: 20, duration: 2}},
  {a: 0, b: 10, duration: 4, prev: {value: 5, duration: 4}, next: {value: 5, duration: 4}},
  {a: 3, b: 3, duration: 4, prev: null, next: null}];
out.autoValue = autoCases.map(c => ({...c, samples: [0, 0.25, 0.5, 0.75, 1].map(t => {
  try { return [t, ke.autoValue(c.a, c.b, t, c.duration, c.prev, c.next)]; } catch (e) { return [t, 'error: ' + e.message]; }})}));
out.shortest = [0, 1, -1, PI - 1e-12, PI, -PI, PI + 1e-12, 2 * PI, -2 * PI, 3 * PI, -3 * PI, 7, -7, 100].map(a => [a, geo.shortest(a)]);

// 2. IK two-bone point solver (bendDirection ±1 only; Both mode needs bendReference) ----------
const ikCase = (name, lengths, target, dir) => {
  const pts = [{x: 0, y: 0}]; lengths.forEach((l, i) => pts.push({x: pts[i].x + l, y: pts[i].y}));
  const r = ik.solveIKPoints(pts, lengths, target, dir);
  return {name, lengths, target, bendDirection: dir, start_points: [[0, 0], ...lengths.map((_, i) => [lengths.slice(0, i + 1).reduce((a, b) => a + b, 0), 0])],
    points: pts.map(p => [p.x, p.y]), result: {iterations: r.iterations, error: r.error}};
};
out.ik = [];
for (const dir of [1, -1]) {
  out.ik.push(ikCase('reach-mid', [50, 40], {x: 60, y: 30}, dir));
  out.ik.push(ikCase('reach-near-fold', [50, 40], {x: 12, y: 3}, dir));
  out.ik.push(ikCase('unreachable', [50, 40], {x: 200, y: 50}, dir));
  out.ik.push(ikCase('exact-reach', [50, 40], {x: 90, y: 0}, dir));
  out.ik.push(ikCase('equal-lengths', [45, 45], {x: 70, y: -40}, dir));
  out.ik.push(ikCase('three-bone', [40, 30, 20], {x: 55, y: 35}, dir));
  out.ik.push(ikCase('four-bone-unreach', [30, 30, 30, 30], {x: 150, y: 100}, dir));
}

// 3. FK on native documents -------------------------------------------------
const doc = (figs, keyframes) => { const r = demo.emptyDocument(); r.figure_types = figs; r.keyframes = keyframes; return r; };
const obj = (figure, uid, x, y, angles, extra = {}) => demo.createObject(figure, uid, x, y, {angles, ...extra});
out.fk = [];
const fkCase = (name, figure, x, y, angles, extra) => {
  const o = obj(figure, 1, x, y, angles, extra), report = doc([figure], [demo.createFrame([o], 1)]);
  const frame = geo.evaluatedFrame(report, 0, 0, 0);
  out.fk.push({name, root: [x, y], scale: o.scale, segments: figure.segments.map(s => ({id: s.segment_id, parent: s.parent_id, length: s.length, bend: s.bend_rad})),
    angles, bends: o.bends, joints: jointsOf(report, frame, 0)});
};
{ // chains of various depth, deterministic angles
  for (const depth of [1, 2, 5, 10, 20]) {
    const segs = Array.from({length: depth}, (_, i) => seg(i + 1, i, 20 + 37.3 * rnd(), 0));
    const angles = segs.map(() => (rnd() * 2 - 1) * PI);
    fkCase(`chain-${depth}`, fig(1, segs), 450.123, 292.456, angles);
  }
  // branching tree with unordered segment array
  const tree = [seg(5, 2, 33, 0), seg(1, 0, 60, 0), seg(3, 1, 25, 0), seg(2, 1, 40, 0), seg(4, 3, 18, 0)];
  fkCase('tree-unordered', fig(1, tree), 100, 200, tree.map(() => (rnd() * 2 - 1) * PI));
  // scale variants
  const sc = [seg(1, 0, 50, 0), seg(2, 1, 40, 0), seg(3, 2, 30, 0)];
  for (const s of [0.5, 2, -1]) fkCase(`scale-${s}`, fig(1, sc), 300, 300, [0.3, -0.8, 1.9], {scale: s});
  // curved (bend) segments
  const bs = [seg(1, 0, 60, 0, 0.8), seg(2, 1, 40, 0, -1.2), seg(3, 2, 30, 0, 1e-8)];
  fkCase('bend', fig(1, bs), 120, 80, [0.4, 1.1, -0.7], {bend_flag: 1, bends: [0.8, -1.2, 1e-8]});
  // large coordinates for float32 quantization
  fkCase('large-coords', fig(1, sc), 98765.4321, -54321.1234, [0.3, -0.8, 1.9]);
}

// 4. Native tween sampling through evaluatedFrame ----------------------------
out.tween = [];
const tweenCase = (name, easings, angleSets, durations, xs) => {
  const figure = fig(1, [seg(1, 0, 60, 0), seg(2, 1, 40, 0), seg(3, 2, 30, 0)]);
  const frames = angleSets.map((angles, i) => {
    const f = demo.createFrame([obj(figure, 1, xs[i], 100, angles)], durations[i]);
    if (easings[i]) f._styk = {easing: easings[i]};
    return f;
  });
  const report = doc([figure], frames);
  const starts = []; let acc = 0; durations.forEach(d => { starts.push(acc); acc += d; });
  const samples = [];
  for (let tick = 0; tick < acc; tick++) {
    let idx = 0; while (idx + 1 < starts.length && starts[idx + 1] <= tick) idx++;
    const n = durations[idx], t = n > 1 ? (tick - starts[idx]) / n : 0;
    try {
      const frame = geo.evaluatedFrame(report, idx, t, tick);
      const o = frame.objects[0];
      samples.push({tick, index: idx, t, root: [o.root_x, o.root_y], angles: [...o.angles], joints: jointsOf(report, frame, 0)});
    } catch (e) { samples.push({tick, error: e.message}); }
  }
  out.tween.push({name, durations, easings, keyframe_angles: angleSets, keyframe_root_x: xs, samples});
};
const A = [[0, 0.5, 1.0], [2.0, -0.5, 0.2], [0.7, 1.5, -1.0]];
for (const mode of ['linear', 'constant', 'ease-in', 'ease-out', 'auto'])
  tweenCase(`mode-${mode}`, [{interpolation: mode}, {interpolation: mode}, {interpolation: 'linear'}], A, [8, 8, 1], [100, 200, 150]);
tweenCase('mode-bezier', [{interpolation: 'bezier', bezier: [0.9, 0, 0.1, 1]}, {interpolation: 'linear'}, {interpolation: 'linear'}], A, [8, 8, 1], [100, 200, 150]);
// shortest-arc wrap: 170deg -> -170deg and 3 / -3 rad
tweenCase('wrap-170', [{interpolation: 'linear'}, {interpolation: 'linear'}], [[170 * PI / 180, 0, 0], [-170 * PI / 180, 0, 0]], [10, 1], [100, 100]);
tweenCase('wrap-exact-pi', [{interpolation: 'linear'}, {interpolation: 'linear'}], [[0, 0, 0], [PI, 0, 0]], [10, 1], [100, 100]);
tweenCase('wrap-minus-pi', [{interpolation: 'linear'}, {interpolation: 'linear'}], [[PI / 2, 0, 0], [-PI / 2, 0, 0]], [10, 1], [100, 100]);
tweenCase('wrap-3pi', [{interpolation: 'linear'}, {interpolation: 'linear'}], [[0, 0, 0], [3 * PI, 0, 0]], [10, 1], [100, 100]);
tweenCase('duration-1', [{interpolation: 'linear'}, {interpolation: 'linear'}], [[0, 0, 0], [1, 1, 1]], [1, 1], [0, 50]);
tweenCase('duration-zero-mid', [{interpolation: 'linear'}, {interpolation: 'linear'}, {interpolation: 'linear'}], A, [4, 0, 1], [100, 200, 150]);
console.log(JSON.stringify(out));
