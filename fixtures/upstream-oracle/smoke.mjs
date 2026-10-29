// Read-only import smoke test. argv[2] = upstream repo root.
import {pathToFileURL} from 'node:url';
const root = process.argv[2];
const load = async (rel) => {
  try { const m = await import(pathToFileURL(`${root}/${rel}`).href); return {ok: true, exports: Object.keys(m)}; }
  catch (e) { return {ok: false, error: String(e && e.message || e).slice(0, 300)}; }
};
const out = {};
for (const rel of ['src/keyframe-easing.mjs', 'src/ik.mjs', 'src/demo.mjs', 'src/pivot/geometry.mjs'])
  out[rel] = await load(rel);
console.log(JSON.stringify(out, null, 1));
