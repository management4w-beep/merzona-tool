#!/usr/bin/env python3
"""تتبّع المقاطع من رسومات الكتالوج (PDF فيكتور) لأجسام ثري دي حقيقية — كل الأبعاد بالملم.
spec (JSON):
  pdf, page, crop:[x0,y0,x1,y1] (pt)
  al:[sw..]                       طبقة الألمنيوم (تحليل زوجية: خلفية/معدن/حجرة)
  al_box:[pt]                     (اختياري) بس القطع يلي بتلمس هالصندوق
  calib:{mm, axis:'x'|'y'}        عرض أكبر قطعة ألمنيوم بالملم (معايرة)
  items:[{kind, sw:[..], mode:'parity'|'blob'|'seed', box:[pt], close:pt, seeds:[[x,y] pt], bound:[sw..], min:mm², sub:true, solid, eps}]
  glass:{sw:[..], dir:'h'|'v', box:[pt]}     وجوه الزجاج + حافته
  screw:{sw:[..], box:[pt]}                  البرغي
"""
import re, sys, json, subprocess, os, tempfile
from collections import deque, Counter
import numpy as np, cv2

PX = 12.0  # بكسل لكل pt

class Page:
    def __init__(self, S):
        tmp = tempfile.mktemp()
        subprocess.run(['pdftocairo', '-svg', '-f', str(S['page']), '-l', str(S['page']), S['pdf'], tmp + '.svg'], check=True)
        t = open(tmp + '.svg').read(); os.remove(tmp + '.svg')
        self.head = t[:t.index('</defs>') + 7]; body = t[t.index('</defs>') + 7:]
        self.paths = [(m.group(0), dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(0)))) for m in re.finditer(r'<path ([^>]*?)/>', body, re.S)]
        self.crop = S['crop']
        x0, y0, x1, y1 = self.crop; self.W, self.H = int((x1 - x0) * PX), int((y1 - y0) * PX)

    def render(self, sws, widen=1.3, dashed=False):
        x0, y0, x1, y1 = self.crop; sel = []
        for p, a in self.paths:
            if a.get('fill', 'none') != 'none':
                if 'fill' in sws:
                    sel.append(re.sub(r'fill="rgb\([^"]*\)"', 'fill="black"', p))
                continue
            if a.get('stroke-width') not in sws or (('stroke-dasharray' in p) != dashed): continue
            q = p.replace('stroke-width="%s"' % a.get('stroke-width', ''), 'stroke-width="%g"' % (float(a.get('stroke-width', 1)) * widen))
            q = re.sub(r'stroke="rgb\([^"]*\)"', 'stroke="black"', q); sel.append(q)
        svg = re.sub(r'<svg [^>]*>', '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" viewBox="%g %g %g %g">' % (self.W, self.H, x0, y0, x1 - x0, y1 - y0), self.head, count=1)
        svg += '\n'.join(sel) + '</svg>'
        fd, fn = tempfile.mkstemp(suffix='.svg'); os.write(fd, svg.encode()); os.close(fd)
        subprocess.run(['rsvg-convert', '-b', 'white', '-w', str(self.W), '-h', str(self.H), fn, '-o', fn + '.png'], check=True)
        im = cv2.imread(fn + '.png', cv2.IMREAD_GRAYSCALE); os.remove(fn); os.remove(fn + '.png')
        return (im < 160).astype(np.uint8)

    def boxmask(self, box):
        m = np.zeros((self.H, self.W), np.uint8)
        if not box: m[:] = 1; return m
        x0, y0 = self.crop[:2]; bx0, by0, bx1, by1 = box
        m[max(0, int((by0 - y0) * PX)):max(0, int((by1 - y0) * PX)), max(0, int((bx0 - x0) * PX)):max(0, int((bx1 - x0) * PX))] = 1
        return m

    def pt2px(self, x, y): return int((x - self.crop[0]) * PX), int((y - self.crop[1]) * PX)

class RasterPage:
    """رسمة كصورة (كتالوج ممسوح/مصدّر كصورة): العتبة ← خطوط، والمناطق السودا المصمتة (بولي أميد، أسهم) منفصلة."""
    UP = 3
    def __init__(self, S):
        im = cv2.imread(S['raster'], cv2.IMREAD_GRAYSCALE)
        x0, y0, x1, y1 = S['crop']; im = im[y0:y1, x0:x1]
        im = cv2.resize(im, None, fx=self.UP, fy=self.UP, interpolation=cv2.INTER_CUBIC)
        self.crop = S['crop']; self.H, self.W = im.shape
        self.lines = (im < S.get('thr', 150)).astype(np.uint8)
        self.ink = (im < S.get('ink_thr', 235)).astype(np.uint8)
        self.black = (im < S.get('black_thr', 90)).astype(np.uint8)
        lw = S.get('line_px', 3) * self.UP
        self.solid = cv2.morphologyEx(self.lines, cv2.MORPH_OPEN, K(int(lw * 2.2) | 1))
    def render(self, sws, widen=1.0, dashed=False):
        if sws == ['solid']: return self.solid.copy()
        if sws == ['ink']: return self.ink.copy()
        return self.lines.copy()
    def boxmask(self, box):
        m = np.zeros((self.H, self.W), np.uint8)
        if not box: m[:] = 1; return m
        x0, y0 = self.crop[:2]; bx0, by0, bx1, by1 = box; U = self.UP
        m[max(0, int((by0 - y0) * U)):max(0, int((by1 - y0) * U)), max(0, int((bx0 - x0) * U)):max(0, int((bx1 - x0) * U))] = 1
        return m
    def pt2px(self, x, y): return int((x - self.crop[0]) * self.UP), int((y - self.crop[1]) * self.UP)

def parity(lines):
    white = (1 - lines).astype(np.uint8)
    n, lab = cv2.connectedComponents(white, connectivity=4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    adj = {i: set() for i in range(1, n)}
    ys, xs = np.nonzero(lines); r = 11
    lp = np.pad(lab, r)
    if len(xs):
        Sm = np.stack([lp[ys + r + dy, xs + r + dx] for dy in (-r, 0, r) for dx in (-r, 0, r)], 1)
        for row in np.unique(Sm, axis=0):
            u = [v for v in set(row.tolist()) if v]
            for a in u:
                for b in u:
                    if a != b: adj[a].add(b)
    depth = {b: 0 for b in border}; q = deque(border)
    while q:
        a = q.popleft()
        for b in adj[a]:
            if b not in depth: depth[b] = depth[a] + 1; q.append(b)
    m = np.isin(lab, [k for k, d in depth.items() if d % 2 == 1]).astype(np.uint8)
    return cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

def fill_holes(m):
    ff = m.copy(); h, w = m.shape; mk = np.zeros((h + 2, w + 2), np.uint8)
    ff[0, :] = 0; ff[-1, :] = 0; ff[:, 0] = 0; ff[:, -1] = 0
    cv2.floodFill(ff, mk, (0, 0), 1)
    return m | (1 - ff)

K = lambda n: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))

def main(spec, out):
    S = json.load(open(spec)); P = RasterPage(S) if S.get('raster') else Page(S)
    sc = 25.4 / 72 / PX
    taken = np.zeros((P.H, P.W), np.uint8)
    found = []
    if S.get('raster') and S.get('al_mode') == 'solid':  # الألمنيوم مرسوم أسود مصمت
        al = cv2.morphologyEx(P.black, cv2.MORPH_OPEN, K(int(S.get('wall_px', 2.5) * P.UP) | 1)) & P.boxmask(S.get('al_clip'))
        for bx in S.get('al_exclude', []): al = al & (1 - P.boxmask(bx))
    elif S.get('raster'):
        al = parity(P.lines) & P.boxmask(S.get('al_clip'))
        al = al & (1 - cv2.dilate(P.solid, K(5)))
    elif S.get('al_mode') == 'fill':  # الألمنيوم معبّى بالرسمة (متل كتالوج Glide)
        al = P.render(['fill'], widen=0) & P.boxmask(S.get('al_clip'))
        al = cv2.morphologyEx(al, cv2.MORPH_OPEN, K(3))
    else:
        al = parity(P.render(S['al'])) & P.boxmask(S.get('al_clip'))
    nm, mlab = cv2.connectedComponents(al, connectivity=8)
    comps = []
    for i in range(1, nm):
        ys, xs = np.nonzero(mlab == i)
        if len(xs) * (sc ** 2) < 0.3: continue
        comps.append((len(xs), i, xs.min(), xs.max(), ys.min(), ys.max()))
    comps.sort(reverse=True)
    alb0 = P.boxmask(S.get('al_box')) if S.get('al_box') else None
    if alb0 is not None:
        comps = [c for c in comps if ((mlab == c[1]) & alb0).any()]
    comps = [c for c in comps if c[0] >= S.get('al_min_px', 0)]
    big = comps[S.get('calib', {}).get('part', 0)]
    if S.get('calib'):
        c = S['calib']
        if c.get('px_per_mm'):
            span = None; sc = 1.0 / (c['px_per_mm'] * getattr(P, 'UP', PX))
        elif c.get('all'):  # المعايرة على مجموع قطع الألمنيوم (مثلاً فريم بنصّين وعازل)
            big = (0, 0, min(q[2] for q in comps), max(q[3] for q in comps), min(q[4] for q in comps), max(q[5] for q in comps))
        if not c.get('px_per_mm'):
            span = (big[3] - big[2]) if c['axis'] == 'x' else (big[5] - big[4])
            sc = c['mm'] / span
    ox = (big[2] + big[3]) / 2 * sc; oy = (big[4] + big[5]) / 2 * sc
    alb = P.boxmask(S.get('al_box')) if S.get('al_box') else None
    for _, i, *_ in comps:
        m = (mlab == i).astype(np.uint8)
        if alb is not None and not (m & alb).any(): continue
        if m.sum() * sc * sc < S.get('al_min', 0.4): continue
        found.append(('al', m, {})); taken |= m
    for it in S.get('items', []):
        box = P.boxmask(it.get('box')); mode = it.get('mode', 'parity')
        if mode == 'parity':
            m = parity(P.render(it['sw'], dashed=it.get('dashed', False))) & box
        elif mode == 'blob':
            g = P.render(it['sw'], widen=1.2, dashed=it.get('dashed', False)) & box
            k = max(3, int(it.get('close', 1.2) * PX)) | 1
            g = cv2.morphologyEx(g, cv2.MORPH_CLOSE, K(k))
            m = g if it.get('nofill') else fill_holes(g)
            if it.get('open'): m = cv2.morphologyEx(m, cv2.MORPH_OPEN, K(max(3, int(it['open'] * PX)) | 1))
            sm = it.get('smooth', 0.6)
            if sm: kk = int(sm * PX) | 1; m = (cv2.GaussianBlur(m.astype(np.float32), (kk * 2 + 1, kk * 2 + 1), 0) > 0.5).astype(np.uint8)
        elif mode == 'seed':
            lines = P.render(it['bound'], widen=1.0)
            if it.get('close_bound'): lines = cv2.morphologyEx(lines, cv2.MORPH_CLOSE, K(int(it['close_bound'] * PX) | 1))
            if it.get('with_taken', True): lines = lines | taken
            lines = lines | (1 - box)
            m = np.zeros_like(lines)
            for sx, sy in it['seeds']:
                px, py = P.pt2px(sx, sy)
                if lines[py, px]: print('  ⚠️ بذرة على خط', it['kind'], sx, sy); continue
                ff = lines.copy(); mk = np.zeros((P.H + 2, P.W + 2), np.uint8)
                cv2.floodFill(ff, mk, (px, py), 2); m |= (ff == 2).astype(np.uint8)
            m = cv2.dilate(m, K(5))
        if it.get('fit') == 'ellipse':  # حبل الحشو: إهليلج ناعم بدل حواف التهشير
            cs_, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if cs_:
                c_ = max(cs_, key=cv2.contourArea)
                if len(c_) >= 5:
                    e_ = cv2.fitEllipse(c_); m = np.zeros_like(m); cv2.ellipse(m, e_, 1, -1)
        if it.get('merge_al'):  # قطعة مرسومة نصها بطبقة الألمنيوم ونصها بطبقة تانية ← قطعة وحدة
            mb = P.boxmask(it.get('merge_box') or it.get('box'))
            keep = []
            for f in found:
                if f[0] == 'al' and (f[1] & cv2.dilate(m, K(9))).any() and (f[1] & mb).sum() > 0.8 * f[1].sum(): m = m | f[1]
                else: keep.append(f)
            found[:] = keep
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, K(7))
        elif it.get('sub', mode != 'parity'):
            m = m & (1 - cv2.dilate(taken, K(3)))
        found.append((it['kind'], m, it)); taken |= m
    res = {'parts': []}
    def conv(c, eps):
        c = cv2.approxPolyDP(c, eps / sc, True)[:, 0, :]
        return [[round(float(x) * sc - ox, 2), round(-(float(y) * sc - oy), 2)] for x, y in c]
    for kind, m, it in found:
        cs, hier = cv2.findContours(m.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None: continue
        hier = hier[0]; eps = it.get('eps', 0.06 if kind == 'al' else 0.08)
        for i, c in enumerate(cs):
            if hier[i][3] != -1: continue
            a = cv2.contourArea(c) * sc * sc
            if a < it.get('min', 0.4 if kind == 'al' else 2.0): continue
            holes = []
            if not it.get('solid'):
                j = hier[i][2]
                while j != -1:
                    if cv2.contourArea(cs[j]) * sc * sc > it.get('hole_min', 0.15): holes.append(conv(cs[j], eps))
                    j = hier[j][0]
            res['parts'].append({'kind': kind, 'outer': conv(c, eps), 'holes': holes, 'area': round(a, 1), **({'tag': it['tag']} if it.get('tag') else {})})
    GL = S.get('glass'); GL = GL if isinstance(GL, list) else ([GL] if GL else [])
    res['glasses'] = []
    for G in GL:
        g = P.render(G['sw'], widen=1.0) & P.boxmask(G.get('box'))
        horiz = G.get('dir', 'h') == 'h'
        prof = g.sum(1) if horiz else g.sum(0)
        bm = P.boxmask(G.get('box')); bw = bm.sum(1).max() if horiz else bm.sum(0).max()
        Lw = bw * G.get('frac', 0.25)
        rows = np.nonzero(prof > Lw)[0]; faces = []
        for r in rows:
            if faces and r - faces[-1][-1] <= 3: faces[-1].append(r)
            else: faces.append([r])
        if G.get('band'):  # زجاج مرسوم كتهشير خطوط: كل شريط = لوح، وجوهه = أول وآخر خط
            gap_px = int(G.get('band_gap', 1.0) * PX); bands = []
            for r in rows:
                if bands and r - bands[-1][-1] <= gap_px: bands[-1].append(r)
                else: bands.append([r])
            faces = [[b[0]] for b in bands] + [[b[-1]] for b in bands]; faces.sort()
        faces_g = faces; faces = [np.mean(f) for f in faces]; merged = []
        for f in faces:
            if merged and (f - merged[-1][-1]) * sc < G.get('merge', 1.2): merged[-1].append(f)
            else: merged.append([f])
        fpx = [np.mean(m) for m in merged]
        best_rows = [max([r for grp in faces_g for r in grp if any(abs(r - f0) < 0.5 for f0 in m)] or [int(np.mean(m))], key=lambda r: prof[r]) for m in merged]
        cpx = (ox / sc) if horiz else (oy / sc)
        edges = []
        for r in best_rows:
            r = int(r); line = g[r] if horiz else g[:, r]
            # طرف الخط المتصل من حافة القص (الزجاج مقطوع عند الحافة) لحد أول فراغ
            gapmax = int(G.get('gap', 0.8) * PX)
            def run_end(arr):
                last = None; gap = 0
                for i, v in enumerate(arr):
                    if v: last = i; gap = 0
                    else:
                        gap += 1
                        if last is not None and gap > gapmax: break
                        if last is None and i > int(G.get('lead', 15) * PX): break
                return last
            e1 = run_end(line); e2 = run_end(line[::-1])
            edges.append((e1, (len(line) - 1 - e2) if e2 is not None else None))
        X = lambda v: round(float(v * sc - ox), 2); Y = lambda v: round(float(-(v * sc - oy)), 2)
        if horiz:
            gg = {'dir': 'h', 'faces': [Y(f) for f in fpx], 'edgesL': [X(e[0]) if e[0] is not None else None for e in edges], 'edgesR': [X(e[1]) if e[1] is not None else None for e in edges]}
        else:
            gg = {'dir': 'v', 'faces': [X(f) for f in fpx], 'edgesL': [Y(e[1]) if e[1] is not None else None for e in edges], 'edgesR': [Y(e[0]) if e[0] is not None else None for e in edges]}
        gg['edgeL'] = max([e for e in gg['edgesL'] if e is not None], default=None) if horiz else min([e for e in gg['edgesL'] if e is not None], default=None)
        gg['edgeR'] = min([e for e in gg['edgesR'] if e is not None], default=None) if horiz else max([e for e in gg['edgesR'] if e is not None], default=None)
        if G.get('side'): gg['side'] = G['side']
        res['glasses'].append(gg)
    if res['glasses']: res['glass'] = res['glasses'][0]
    SC = S.get('screw')
    if SC:
        g = P.render(SC['sw'], widen=1.0) & P.boxmask(SC.get('box'))
        ys, xs = np.nonzero(g)
        if len(xs):
            res['screw'] = {'x0': round(float(xs.min() * sc - ox), 2), 'x1': round(float(xs.max() * sc - ox), 2), 'y0': round(float(-(ys.max() * sc - oy)), 2), 'y1': round(float(-(ys.min() * sc - oy)), 2)}
    allp = [pt for p in res['parts'] for pt in p['outer']]
    res['bbox'] = [min(x for x, y in allp), min(y for x, y in allp), max(x for x, y in allp), max(y for x, y in allp)]
    res['mm_per_pt'] = round(sc * PX, 5); res['origin_pt'] = [round(P.crop[0] + ox / sc / PX, 2), round(P.crop[1] + oy / sc / PX, 2)]
    json.dump(res, open(out, 'w'))
    print(out, dict(Counter(p['kind'] for p in res['parts'])), 'bbox', [round(v, 1) for v in res['bbox']], 'glass', res.get('glass', {}).get('faces'), res.get('glass', {}).get('edgeL'), res.get('glass', {}).get('edgeR'), 'screw', res.get('screw'), 'mm/pt', res['mm_per_pt'])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
