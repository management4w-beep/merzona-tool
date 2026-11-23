#!/usr/bin/env python3
"""يبني techcat-sec.js من رسومات الكتالوجات (trace.py) — كل مقطع = أجزاء حقيقية بالملم + أسماء + فكّ/حركة."""
import json, subprocess, sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
SPECS = json.load(open(os.path.join(HERE, 'sections.json')))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'techcat-sec.js')

def pip(pt, poly):
    x, y = pt; c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1: c = not c
    return c

def inside_part(pt, p):
    return pip(pt, p['outer']) and not any(pip(pt, h) for h in p['holes'])

def cen(poly):
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]; return [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2]

res = {}
for sid, S in SPECS.items():
    tj = os.path.join(HERE, 'out', sid + '.json'); os.makedirs(os.path.dirname(tj), exist_ok=True)
    spec = dict(S['trace'])
    if spec.get('pdf'): spec['pdf'] = os.path.join(HERE, spec['pdf'])
    sp = tj + '.spec'; json.dump(spec, open(sp, 'w'))
    r = subprocess.run(['python3', os.path.join(HERE, 'trace.py'), sp, tj], capture_output=True, text=True)
    if r.returncode: print(r.stderr); sys.exit(1)
    print(sid, r.stdout.strip().splitlines()[-1])
    T = json.load(open(tj))
    parts = []
    drop = S.get('drop', [])
    for i, p in enumerate(T['parts']):
        if i in drop: continue
        mat = S.get('mat', {}).get(str(i), p['kind'])
        q = {'mat': mat, 'pts': p['outer'], 'holes': p['holes']}
        nm = S.get('name_idx', {}).get(str(i))
        if nm: q['name'] = nm
        parts.append(q)
    # الزجاج: ألواح من الوجوه (أزواج: لوح، فراغ، لوح...) + فاصل + سيليكون خارجي
    glass = S.get('glass', {})
    for G in (S.get('glass_manual') or T.get('glasses') or ([T['glass']] if T.get('glass') else [])):
      if G and G.get('faces') and not glass.get('off'):
          f = sorted(G['faces'], reverse=(G['dir'] == 'h'))
          ext = glass.get('ext', 75)
          sides = [G['side']] if G.get('side') else glass.get('sides', ['L', 'R'])
          for side in sides:
              e = G['edge' + side] if glass.get('edge' + side) is None else glass['edge' + side]
              if e is None: continue
              sg = -1 if side == 'L' else 1
              a, b = (e, e + sg * ext)
              lo, hi = min(a, b), max(a, b)
              for k in range(0, len(f) - 1, 2):
                  y0, y1 = sorted([f[k], f[k + 1]])
                  pts = [[lo, y0], [hi, y0], [hi, y1], [lo, y1]] if G['dir'] == 'h' else [[y0, lo], [y1, lo], [y1, hi], [y0, hi]]
                  parts.append({'mat': 'gl', 'pts': pts, 'holes': [], 'name': 'زجاج'})
              # فاصل الزجاج المزدوج + سيليكون ثانوي
              for k in (range(1, len(f) - 2, 2) if glass.get('spacer', True) else []):
                  y0, y1 = sorted([f[k], f[k + 1]])
                  s0, s1 = e + sg * 0.5, e + sg * 5
                  t0, t1 = e + sg * 5, e + sg * 14
                  for (u0, u1, m, nm) in ((s0, s1, 'gk', 'سيليكون ثانوي'), (t0, t1, 'sp', 'فاصل ألمنيوم + مادة مجففة')):
                      lo2, hi2 = min(u0, u1), max(u0, u1)
                      pts = [[lo2, y0], [hi2, y0], [hi2, y1], [lo2, y1]] if G['dir'] == 'h' else [[y0, lo2], [y1, lo2], [y1, hi2], [y0, hi2]]
                      parts.append({'mat': m, 'pts': pts, 'holes': [], 'name': nm})
    sc = T.get('screw') if not S.get('screw_off') else None
    if S.get('screw'): sc = S['screw']
    screw = None
    if sc:
        d = S.get('screw_d', 5.5)
        if abs(sc['y1'] - sc['y0']) >= abs(sc['x1'] - sc['x0']):
            cx = S.get('screw_x', 0.0); screw = {'axis': 'y', 'c': cx, 'a': sc['y0'], 'b': sc['y1'], 'd': d, 'head': S.get('screw_head', 'a')}
            parts.append({'mat': 'sc', 'pts': [[cx - d / 2, sc['y0']], [cx + d / 2, sc['y0']], [cx + d / 2, sc['y1']], [cx - d / 2, sc['y1']]], 'holes': [], 'screw': screw, 'name': S.get('screw_name', 'برغي ستانلس ستيل')})
    # الأسماء: نقطة داخل الجزء
    for nm in S.get('names', []):
        x, y, label = nm
        for p in parts:
            if p.get('screw'): continue
            if pip([x, y], p['pts']) and not any(pip([x, y], h) for h in p['holes']):
                p['name'] = label; p['at'] = [x, y]; break
        else:
            print('  ⚠️ ما لقيت جزء للاسم', label, x, y)
    # نقطة داخلية لكل جزء مسمّى (أبعد نقطة عن الحواف) — لتأشير الاسم
    def seg_d(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy or 1e-9
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L)); return math.hypot(px - ax - t * dx, py - ay - t * dy)
    for p in parts:
        if not p.get('name') or p.get('at'): continue
        if p.get('screw'): sc_ = p['screw']; p['at'] = [sc_['c'], (sc_['a'] + sc_['b']) / 2]; continue
        xs = [q[0] for q in p['pts']]; ys = [q[1] for q in p['pts']]
        best = None; N = 40
        for i in range(N + 1):
            for j in range(N + 1):
                x = min(xs) + (max(xs) - min(xs)) * i / N; y = min(ys) + (max(ys) - min(ys)) * j / N
                if not inside_part([x, y], {'outer': p['pts'], 'holes': p['holes']}): continue
                d = min(seg_d(x, y, *poly[k - 1], *poly[k]) for poly in [p['pts']] + p['holes'] for k in range(len(poly)))
                if best is None or d > best[0]: best = (d, x, y)
        if best: p['at'] = [round(best[1], 2), round(best[2], 2)]
    for p in parts:
        p['pts'] = [[round(a, 2), round(b, 2)] for a, b in p['pts']]
        p['holes'] = [[[round(a, 2), round(b, 2)] for a, b in h] for h in p['holes']]
    mo = S.get('motion')
    if mo and mo.get('box'):
        bx0, by0, bx1, by1 = mo['box']
        mo = dict(mo); mo['parts'] = [i for i, p in enumerate(parts) if bx0 <= cen(p['pts'])[0] <= bx1 and by0 <= cen(p['pts'])[1] <= by1]
        mo.pop('box')
    S = dict(S); S['motion'] = mo
    sec = {'parts': parts, 'src': S['src'], 'normal': S.get('normal', 'y'), 'motion': S.get('motion'), 'labels': S.get('labels', []), 'dims': S.get('dims', []), 'view': S.get('view')}
    res[sid] = sec
# مقاطع مرسومة من فيديوهات العيّنات (video_sec.py)
try:
    res.update(json.load(open(os.path.join(HERE, 'video_sections.json'))))
except FileNotFoundError: pass
js = '/* مقاطع الكتالوج الفني: متتبّعة من رسومات المصنّعين الأصلية (فيكتور) بالملم. مولّد بـ tools/techcat/build_sec.py — لا تعدّل يدوياً */\nwindow.TCSEC = ' + json.dumps(res, ensure_ascii=False, separators=(',', ':')) + ';\n'
open(OUT, 'w').write(js)
print('→', OUT, len(js) // 1024, 'KB')
