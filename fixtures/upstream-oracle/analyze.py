"""Throwaway analysis: independent float64 reimplementations vs upstream oracle vectors. Not engine code."""
import json, math, struct, sys
d = json.load(open(sys.argv[1]))
f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
def ulp32(x):
    x = abs(x); return 2.0 ** (math.frexp(x)[1] - 24) if x else 2.0 ** -149
res = {}

# --- bezier: independent high-precision solver (bisection to machine precision)
def bez(t, p):
    x1, y1, x2, y2 = p
    c = lambda u, a, b: 3*(1-u)**2*u*a + 3*(1-u)*u*u*b + u**3
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        u = (lo + hi) / 2
        if c(u, x1, x2) < t: lo = u
        else: hi = u
    return c((lo + hi) / 2, y1, y2)
worst = {}
for c in d['bezier']:
    e = max(abs(v - bez(t, c['points'])) for t, v in c['samples'])
    worst[c['name']] = e
res['bezier_max_abs_err_vs_exact_solver'] = worst
modes = {'linear': lambda t: t, 'constant': lambda t: 0.0 if t < 1 else 1.0, 'auto': lambda t: t*t*(3-2*t),
         'ease-in': lambda t: bez(t, [0.42, 0, 1, 1]), 'ease-out': lambda t: bez(t, [0, 0, 0.58, 1]), 'bezier': lambda t: bez(t, [0.42, 0, 0.58, 1])}
res['modes_max_abs_err'] = {m['mode']: max(abs(v - modes[m['mode']](t)) for t, v in m['samples']) for m in d['modes']}

# --- shortest: two candidate conventions
S1 = lambda a: math.atan2(math.sin(a), math.cos(a))
S2 = lambda a: ((a + math.pi) % (2*math.pi) + 2*math.pi) % (2*math.pi) - math.pi
res['shortest_vs_atan2form_max'] = max(abs(v - S1(a)) for a, v in d['shortest'])
res['shortest_vs_modform_disagree_at'] = [[a, v, S2(a)] for a, v in d['shortest'] if abs(v - S2(a)) > 1e-9]

# --- IK two-bone closed form, independent derivation (law of cosines)
def ik2(a, b, tx, ty, dirn):
    dist = math.hypot(tx, ty); tot = a + b
    ux, uy = (tx/dist, ty/dist) if dist else (1.0, 0.0)
    if dist >= tot: return [(0,0),(ux*a,uy*a),(ux*tot,uy*tot)]
    dd = min(max(dist, abs(a-b)), tot)
    along = (a*a - b*b + dd*dd)/(2*dd); h = math.sqrt(max(0, a*a - along*along))*dirn
    return [(0,0),(ux*along - uy*h, uy*along + ux*h),(ux*dd, uy*dd)]
ik_err = {}
for c in d['ik']:
    if len(c['lengths']) != 2: continue
    mine = ik2(*c['lengths'], c['target']['x'], c['target']['y'], c['bendDirection'])
    ik_err[f"{c['name']}/{c['bendDirection']}"] = max(max(abs(p[0]-q[0]), abs(p[1]-q[1])) for p, q in zip(c['points'], mine))
res['ik_two_bone_max_abs_err'] = ik_err
# n>2: property checks (bone lengths, reach error)
prop = {}
for c in d['ik']:
    if len(c['lengths']) <= 2: continue
    P = c['points']; L = [math.dist(P[i], P[i+1]) for i in range(len(P)-1)]
    prop[f"{c['name']}/{c['bendDirection']}"] = {'max_len_err': max(abs(a-b) for a, b in zip(L, c['lengths'])),
        'end_err': math.dist(P[-1], (c['target']['x'], c['target']['y'])), 'reported_err': c['result']['error'], 'iters': c['result']['iterations']}
res['ik_chain_properties'] = prop

# --- FK
def fk(segs, angles, root, scale, bends=None, f32mode=False):
    j = {0: root}; order = []
    # parents may be unordered: resolve by repeated passes
    by = {s['id']: (s, a, (bends[i] if bends else 0.0)) for i, (s, a) in enumerate(zip(segs, angles))}
    def pos(i):
        if i in j: return j[i]
        s, a, b = by[i]; st = pos(s['parent']); L = s['length']*scale
        if abs(b) < 1e-7: x, y = st[0] + L*math.cos(a), st[1] + L*math.sin(a)
        else:
            r = L/b; x = st[0] + r*(math.sin(a+b) - math.sin(a)); y = st[1] + r*(math.cos(a) - math.cos(a+b))
        j[i] = (f32(x), f32(y)) if f32mode else (x, y); return j[i]
    for i in by: pos(i)
    return j
def depth(segs, i):
    par = {s['id']: s['parent'] for s in segs}; n = 0
    while i != 0: i = par[i]; n += 1
    return n
fkres = {}
for c in d['fk']:
    segs = c['segments']; ang = c['angles']; bends = c['bends'] if c['bends'] else None
    r = {}
    for label, f in (('float64', False), ('pivot32', True)):
        mine = fk(segs, ang, tuple(c['root']), c['scale'], bends if c['bends'] else None, f)
        worst = 0; ratio = 0
        for k, (x, y) in c['joints'].items():
            k = int(k)
            if k == 0: continue
            ex, ey = abs(mine[k][0]-x), abs(mine[k][1]-y)
            worst = max(worst, ex, ey)
            bound = (depth(segs, k)+1) * max(ulp32(x), ulp32(y))
            ratio = max(ratio, max(ex, ey)/bound)
        r[label] = {'max_abs_err': worst, 'max_err_over_bound': ratio}
    fkres[c['name']] = r
res['fk'] = fkres

# --- tween: relative-angle shortest-arc reconstruction (semantic hypothesis)
def tween_expected(c, s):
    kf = c['keyframe_angles']; idx = s['index']; t = s['t']; e = c['easings'][idx]
    a, b = kf[idx], kf[min(idx+1, len(kf)-1)]
    mode = e['interpolation']
    if mode == 'auto': return None
    p = bez(t, e.get('bezier', [0.42,0,0.58,1])) if mode == 'bezier' else modes[mode](t)
    if idx == len(kf)-1: return list(a)
    def rel(v): return [v[0]] + [v[i] - v[i-1] for i in range(1, len(v))]   # bend 0, parent chain 1<-2<-3
    ra, rb = rel(a), rel(b)
    rr = [x + S1(y - x)*p for x, y in zip(ra, rb)]
    out = []; acc = 0.0
    for v in rr: acc += v; out.append(acc)
    return out
tw = {}
for c in d['tween']:
    worst = 0; n = 0; mism = []
    for s in c['samples']:
        if 'error' in s: mism.append(('error', s['tick'], s['error'])); continue
        ex = tween_expected(c, s)
        if ex is None: continue
        e = max(abs(u-v) for u, v in zip(ex, s['angles'])); worst = max(worst, e); n += 1
        if e > 1e-9: mism.append((s['tick'], [round(v, 6) for v in s['angles']], [round(v, 6) for v in ex]))
    tw[c['name']] = {'compared': n, 'max_abs_err': worst, 'mismatches': mism[:3]}
res['tween_vs_relative_shortest_hypothesis'] = tw
print(json.dumps(res, indent=1, default=str))
