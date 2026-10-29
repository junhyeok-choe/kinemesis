# Oracle vector provenance (test tooling; not engine code)

- Authorization: user approved D2 on 2026-10-29 ("Allow sandboxed"): run upstream Node code at the pinned commit in an isolated, no-network sandbox; do not modify upstream; keep outputs with provenance.
- Upstream: https://github.com/filippocalippo/StykAnimate-App @ def97214c2b491fbce82647f625a73f78416c6d8 (GPL-3.0-or-later). Checkout unmodified (`git status --short` empty after runs). No `npm install`/`npm ci` was run; only `node:` builtins are needed by the imported modules.
- Sandbox: `unshare -rn` (new user+network namespace, loopback only, no DNS) and `node --permission --allow-fs-read=<upstream> --allow-fs-read=<oracle dir>` (no fs write, no child processes, no workers). Node v25.2.1, Linux x86_64 (WSL2), 2026-10-29.
- Commands (cwd = oracle dir, script outside the upstream tree):
  `unshare -rn node --permission --allow-fs-read=$UP --allow-fs-read=$PWD smoke.mjs $UP`
  `unshare -rn node --permission --allow-fs-read=$UP --allow-fs-read=$PWD gen_vectors.mjs $UP def97214c2b491fbce82647f625a73f78416c6d8 > out/vectors.json`
  `python3.14 -I analyze.py out/vectors.json > out/analysis.json`
- Upstream functions exercised: keyframe-easing.mjs {cubicBezierProgress, easedProgress, autoValue, DEFAULT_BEZIER}; geometry.mjs {shortest, evaluatedFrame, buildGeometry}; ik.mjs {solveIKPoints}; demo.mjs {emptyDocument, createObject, createFrame}.
- Licensing of outputs: numeric outputs of running a GPL-3.0-or-later program; the Engine is GPL-3.0-or-later (D1), so distribution is compatible. Keep this provenance with any fixture copy.
- Limitation: -0 is serialized as 0 by JSON.stringify.
