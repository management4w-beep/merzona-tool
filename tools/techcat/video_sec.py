#!/usr/bin/env python3
"""مقاطع X300S و X500 من فيديوهات العيّنات (حمدي 2026-11-23): أشكال مرسومة بالملم من صور المقطع المكشوف بالفيديو
(تقريبية — بتتبدّل برسومات المصنّع لما توصل). كل بروفايل = اتحاد أشكال بسيطة ← قطعة وحدة متصلة بحجراتها.
الإخراج: video_sections.json بنفس صيغة techcat-sec.js"""
import json, math, cv2, numpy as np

R = 20.0  # بكسل لكل ملم

class Prof:
    def __init__(s, mat, name, z=None):
        s.mat, s.name, s.z = mat, name, z; s.add = []; s.sub = []
    def rect(s, x0, y0, x1, y1, r=0, sub=False): (s.sub if sub else s.add).append(('r', x0, y0, x1, y1, r)); return s
    def circ(s, cx, cy, rr, sub=False): (s.sub if sub else s.add).append(('c', cx, cy, rr)); return s
    def poly(s, pts, sub=False): (s.sub if sub else s.add).append(('p', pts)); return s
    def box(s, x0, y0, x1, y1, t=1.4, r=0, rin=None):
        """صندوق مجوّف بجدار t (حجرة)"""
        s.rect(x0, y0, x1, y1, r); s.rect(x0 + t, y0 + t, x1 - t, y1 - t, max(0, (r - t) if rin is None else rin), sub=True); return s
    def build(s):
        xs, ys = [], []
        for sh in s.add:
            if sh[0] == 'r': xs += [sh[1], sh[3]]; ys += [sh[2], sh[4]]
            elif sh[0] == 'c': xs += [sh[1] - sh[3], sh[1] + sh[3]]; ys += [sh[2] - sh[3], sh[2] + sh[3]]
            else: xs += [p[0] for p in sh[1]]; ys += [p[1] for p in sh[1]]
        X0, Y0 = min(xs) - 2, min(ys) - 2; W = int((max(xs) - X0 + 2) * R); H = int((max(ys) - Y0 + 2) * R)
        m = np.zeros((H, W), np.uint8)
        P = lambda x, y: (int(round((x - X0) * R)), int(round(H - (y - Y0) * R)))
        def draw(sh, v):
            if sh[0] == 'r':
                _, x0, y0, x1, y1, r = sh
                if r <= 0: cv2.rectangle(m, P(x0, y1), P(x1, y0), v, -1); return
                rr = int(r * R)
                a, b = P(x0, y1), P(x1, y0)
                cv2.rectangle(m, (a[0] + rr, a[1]), (b[0] - rr, b[1]), v, -1); cv2.rectangle(m, (a[0], a[1] + rr), (b[0], b[1] - rr), v, -1)
                for cx, cy in ((a[0] + rr, a[1] + rr), (b[0] - rr, a[1] + rr), (a[0] + rr, b[1] - rr), (b[0] - rr, b[1] - rr)): cv2.circle(m, (cx, cy), rr, v, -1)
            elif sh[0] == 'c': cv2.circle(m, P(sh[1], sh[2]), int(sh[3] * R), v, -1)
            else: cv2.fillPoly(m, [np.array([P(x, y) for x, y in sh[1]], np.int32)], v)
        for sh in s.add: draw(sh, 1)
        for sh in s.sub: draw(sh, 0)
        cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        out = []
        conv = lambda c: [[round(float(px) / R + X0, 2), round(float(H - py) / R + Y0, 2)] for px, py in cv2.approxPolyDP(c, 0.05 * R, True)[:, 0, :]]
        for i, c in enumerate(cs):
            if hier[0][i][3] != -1: continue
            holes = []; j = hier[0][i][2]
            while j != -1: holes.append(conv(cs[j])); j = hier[0][j][0]
            q = {'mat': s.mat, 'pts': conv(c), 'holes': holes}
            if s.name: q['name'] = s.name
            if s.z: q['z'] = s.z
            out.append(q)
        return out

def glass(x0, y0, x1, y1, name='زجاج'):
    return {'mat': 'gl', 'pts': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], 'holes': [], 'name': name}

def interlock(W=46, H=28, P=14, gl=6, gap=6, off=8, hookx=None, pad='gk', sys='X300S'):
    """مقطع أفقي عند التقاء الدرفتين: درفة فوق (زجاجها لليسار) ودرفة تحت (زجاجها لليمين) بمسارين، بخطافات التقاء وفرش."""
    parts = []
    t = 1.4
    # الدرفة الداخلية (فوق)
    a = Prof('al', sys + ' — درفة (مقطع الالتقاء)')
    a.box(P, 0, P + W, H, t, r=5)
    a.rect(0, H - t, P, H).rect(0, H - 4, t, H)                 # شفة الجيب العليا + حاجز
    a.rect(2, 0, P, t).rect(2, 0, 2 + t, 3.5)                   # الشفة السفلى
    hx = hookx if hookx is not None else P + W * 0.42
    # خطاف لتحت بيلفّ لليمين (متل نقشة الفيرزاتشي) — بيتعشّق بخطاف الدرفة التانية
    yb_ = -gap - 2
    a.rect(hx, yb_ + 1.6, hx + t, 0).rect(hx, yb_ + 1.6, hx + 7, yb_ + 1.6 + t).rect(hx + 7 - t, yb_ + 1.6, hx + 7, yb_ + 4.4)
    a.rect(P + W - 8, -3.2, P + W, 0).rect(P + W - 8, -3.2, P + W - 8 + t, 0)  # مجرى فرشاية
    parts += a.build()
    # الدرفة الخارجية (تحت)
    b = Prof('al', sys + ' — درفة تانية (مقطع الالتقاء)')
    y1 = -gap - 2; y0 = y1 - (H + 4)
    b.box(off - 4, y0, off - 4 + W, y1, t, r=6)
    bx = off - 4 + W
    b.rect(bx, y1 - t, bx + P, y1).rect(bx + P - t, y1 - 4, bx + P, y1)
    b.rect(bx, y0, bx + P - 2, y0 + t).rect(bx + P - 2 - t, y0, bx + P - 2, y0 + 3.5)
    b.rect(off - 2, y1, off - 2 + t, y1 + 3.6).rect(off - 2, y1 + 3.6 - t, off + 8, y1 + 3.6)   # شفة لفوق للفرشاية
    # خطاف لفوق بيلفّ لليسار، راسه فوق رجل خطاف الدرفة الأولى ورجله جوّا قناتها — متعشّقين بفراغ 0.6 ملم
    b.rect(hx + 10 - t, y1, hx + 10, -1.6).rect(hx + 3, -3, hx + 10, -1.6).rect(hx + 3, -4.4, hx + 3 + t, -1.6)
    parts += b.build()
    # فرش وإحكام
    for (x0, yy0, x1, yy1) in ((P + W - 7, -3, P + W - 1, 0.2), (off - 1, y1 + 3.6, off + 7, y1 + 3.6 + 3.2), (hx + 4.6, -1.5, hx + 8.4, -0.15)):
        g = Prof(pad, 'فرشاية إحكام (Pile weather strip)' if pad == 'gk' else 'قطعة إحكام الالتقاء'); g.rect(x0, yy0, x1, yy1, 0.6); parts += g.build()
    # الزجاج والغاسكيت
    gy = H / 2
    parts.append(glass(-90, gy - gl / 2, P - 1, gy + gl / 2))
    for yy in (gy + gl / 2, gy - gl / 2 - 2.2):
        g = Prof('gk', 'غاسكيت تزجيج'); g.rect(t + 0.2, yy, P - 3, yy + 2.2, 0.6); parts += g.build()
    gy2 = (y0 + y1) / 2
    parts.append(glass(bx + 1, gy2 - gl / 2, bx + 90, gy2 + gl / 2))
    for yy in (gy2 + gl / 2, gy2 - gl / 2 - 2.2):
        g = Prof('gk', 'غاسكيت تزجيج'); g.rect(bx + 3, yy, bx + P - t - 0.2, yy + 2.2, 0.6); parts += g.build()
    return parts

def sill(SW=32, GH=26, gl=6, rail_x=1.5, frameW=68, deep=34, wheel=4.6, sys='X500'):
    """مقطع رأسي عند العتبة: الدرفة بعربايتها وعجلها راكبة على السكة، فرش حوالين السكة، وفريم العتبة بحجراته."""
    parts = []; t = 1.4; L2 = 70
    hs = SW / 2
    # الدرفة السفلية
    s = Prof('al', sys + ' — درفة (البروفايل السفلي)')
    s.rect(-hs, 0, -hs + t, 33 + GH).rect(hs - t, 0, hs, 33 + GH)                 # الجانبين
    s.rect(-hs, 32.3, hs, 33.7)                                                 # الجسر
    s.rect(-hs, 0, -hs + 4, t).rect(hs - 4, 0, hs, t)                           # أقدام
    s.rect(-hs, 33 + GH - t, -hs + 5.5, 33 + GH).rect(hs - 5.5, 33 + GH - t, hs, 33 + GH)  # شفاف جيب الزجاج
    s.rect(-3.2, 26.5, 3.2, 32.3).rect(-1.8, 27.9, 1.8, 32.3, sub=True).rect(-0.9, 26.5, 0.9, 28, sub=True)  # مجرى البرغي
    s.rect(-hs + t, 17, -hs + 3.2, 18.4).rect(hs - 3.2, 17, hs - t, 18.4)        # بروزات تثبيت العربانة
    parts += s.build()
    # العربانة + العجل + برغي المعايرة (بطول محدود على الطول)
    c = Prof('al', 'عربانة العجل (Roller carriage)', z=[-0.42, -0.1]); c.rect(-11, 9, 11, 25).rect(-9.6, 9, 9.6, 23.6, sub=True); c.rect(-11, 9, -9.6, 25); parts += c.build()
    c2 = Prof('al', 'عربانة العجل (Roller carriage)', z=[0.1, 0.42]); c2.rect(-11, 9, 11, 25).rect(-9.6, 9, 9.6, 23.6, sub=True); parts += c2.build()
    for z in ([-0.4, -0.12], [0.12, 0.4]):
        # العجل قرص محوره عرضي (بيمشي على طول السكة): بالمقطع مستطيل، وبالـ 3D أسطوانة
        cy = 6 + wheel + 0.2; ww = 5.0
        parts.append({'mat': 'rl', 'name': 'عجل نايلون على بلي (Roller)', 'pts': [[rail_x - ww / 2, cy - wheel], [rail_x + ww / 2, cy - wheel], [rail_x + ww / 2, cy + wheel], [rail_x - ww / 2, cy + wheel]], 'holes': [],
                      'wheel': {'cx': rail_x, 'cy': cy, 'r': wheel, 'w': ww, 'zc': (z[0] + z[1]) / 2}})
        blk = Prof('pv', 'بلوك العجل', z=z); blk.rect(-9.4, 15.5, 9.4, 23.4, 1); parts += blk.build()
    # الفرش حوالين السكة
    for x0 in (-hs + 2, rail_x + 4.5):
        g = Prof('gk', 'فرشاية إحكام (Pile weather strip)'); g.rect(x0, 0.2, x0 + 6.5, 8, 0.8); parts += g.build()
    # فريم العتبة
    f = Prof('al', sys + ' — فريم العتبة (Sill)')
    X0 = -frameW * 0.45; X1 = X0 + frameW; yb = -10
    f.rect(X0, yb - t, X1, yb)                                                   # السطح
    f.rect(rail_x - 0.7, yb, rail_x + 0.7, 5).rect(rail_x - 3.4, 4.2, rail_x + 3.4, 5.6, 1)   # السكة (رأس عريض)
    f.rect(X0, yb - t, X0 + t, 6).circ(X0 + 0.7, 6.2, 1.3)                       # جدار + حبّة
    f.rect(X1 - t, yb - t, X1, 9).rect(X1 - 6, 9 - t, X1, 9)                    # جدار خارجي + شفة
    f.box(X0, yb - 6.5, X1, yb - t + 0.01, t)                                    # حجرة مسطّحة
    f.rect(X0 + frameW * 0.55, yb - 6.5, X0 + frameW * 0.55 + t, yb)
    f.box(X0, yb - 6.5 - deep, X1, yb - 6.5 + t, t)                              # الصندوق السفلي
    parts += f.build()
    # الزجاج (رأسي) + غاسكيت
    parts.append({'mat': 'gl', 'pts': [[-gl / 2, 36], [gl / 2, 36], [gl / 2, 36 + L2], [-gl / 2, 36 + L2]], 'holes': [], 'name': 'زجاج'})
    for xx in (-gl / 2 - 2.4, gl / 2):
        g = Prof('gk', 'غاسكيت تزجيج'); g.rect(xx, 33 + GH - 7, xx + 2.4, 33 + GH + 0.6, 0.7); parts += g.build()
    # البرغي: محوره على طول البروفايل (منمثّله رأس دائري قصير)
    sc = Prof('sc', 'برغي معايرة ارتفاع العجل', z=[0.43, 0.47]); sc.circ(0, 19.5, 3.2); parts += sc.build()
    return parts

def arc_band(cx, cy, rx, ry, a0, a1, t=1.6, n=40):
    """شريط منحني (وجه ديكور مقعّر/محدّب) بسماكة t"""
    o = [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    inn = [(cx + (rx - t) * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + (ry - t) * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n, -1, -1)]
    return o + inn

def gida_sill():
    parts = sill(SW=32, GH=26, gl=6, frameW=66, deep=30, wheel=4.6, sys='جيدا')
    # غطا ديكور منحني على وجه فريم العتبة (برونز) — بينكبس عالفريم
    X1 = -66 * 0.45 + 66; yb = -10
    d = Prof('al', 'جيدا — غطاء ديكور منحني للفريم (Decorative cover)')
    d.poly(arc_band(X1, yb - 6.5 - 30, 22, 30 + 6.5 + 12, 0, 90, t=1.6))
    d.rect(X1 - 1.4, 8.4, X1 + 1, 10).rect(X1 - 3, yb - 6.5 - 30, X1 + 22, yb - 6.5 - 30 + 1.6)
    parts += d.build()
    # وجه ديكور منحني على الدرفة
    e = Prof('al', 'جيدا — وجه ديكور منحني للدرفة')
    e.poly(arc_band(16, 2, 9, 54, 0, 90, t=1.4)).rect(14.6, 54.5, 16.6, 56).rect(14.6, 2, 25, 3.4)
    parts += e.build()
    return parts

def gida_ilk():
    parts = interlock(W=48, H=30, P=14, gl=6, gap=6, off=8, sys='جيدا')
    # وجوه ديكور منحنية على الوجه الخارجي لكل درفة
    # ملزوقة على وجه الدرفة (رجليها جوّا الجدار) — مش طايرة
    e = Prof('al', 'جيدا — وجه ديكور منحني للدرفة'); e.poly(arc_band(14 + 48 / 2, 29, 19, 9, 0, 180, t=1.5)).rect(18.2, 28.6, 20.4, 30.4).rect(55.6, 28.6, 57.8, 30.4); parts += e.build()
    f = Prof('al', 'جيدا — وجه ديكور منحني للدرفة'); f.poly(arc_band(4 + 48 / 2, -41, 19, 9, 180, 360, t=1.5)).rect(8.2, -42.4, 10.4, -40.6).rect(45.6, -42.4, 47.8, -40.6); parts += f.build()
    return parts

def sash_parts(cx, SW, GH, gl, wheel, rail_top, sys, role, name_sfx):
    """درفة سفلية متمركزة على السكة (cx) — البروفايل + العربانة + العجل + الفرش + الزجاج"""
    t = 1.4; hs = SW / 2; P = []
    s = Prof('al', sys + ' — درفة ' + name_sfx)
    s.rect(cx - hs, 0, cx - hs + t, 33 + GH).rect(cx + hs - t, 0, cx + hs, 33 + GH)
    s.rect(cx - hs, 32.3, cx + hs, 33.7)
    s.rect(cx - hs, 0, cx - hs + 3.6, t).rect(cx + hs - 3.6, 0, cx + hs, t)
    s.rect(cx - hs, 33 + GH - t, cx - hs + 5.5, 33 + GH).rect(cx + hs - 5.5, 33 + GH - t, cx + hs, 33 + GH)
    s.rect(cx - 3.2, 26.5, cx + 3.2, 32.3).rect(cx - 1.8, 27.9, cx + 1.8, 32.3, sub=True).rect(cx - 0.9, 26.5, cx + 0.9, 28, sub=True)
    s.rect(cx - hs + t, 17, cx - hs + 3.2, 18.4).rect(cx + hs - 3.2, 17, cx + hs - t, 18.4)
    P += s.build()
    cy = rail_top + wheel; ww = 5.0
    for z in ([-0.4, -0.14], [0.14, 0.4]):
        c = Prof('al', 'عربانة العجل (Roller carriage)', z=z); c.rect(cx - hs + 3.4, 9, cx + hs - 3.4, cy + wheel + 6).rect(cx - hs + 4.8, 9, cx + hs - 4.8, cy + wheel + 4.6, sub=True); P += c.build()
        P.append({'mat': 'rl', 'name': 'عجل نايلون على بلي (Roller)', 'pts': [[cx - ww / 2, cy - wheel], [cx + ww / 2, cy - wheel], [cx + ww / 2, cy + wheel], [cx - ww / 2, cy + wheel]], 'holes': [],
                  'wheel': {'cx': cx, 'cy': cy, 'r': wheel, 'w': ww, 'zc': (z[0] + z[1]) / 2}})
    for x0 in (cx - hs + 1.6, cx + 3.6):
        g = Prof('gk', 'فرشاية إحكام (Pile weather strip)'); g.rect(x0, 0.2, x0 + min(6, hs - 5.4), rail_top + 1.2, 0.8); P += g.build()
    P.append({'mat': 'gl', 'pts': [[cx - gl / 2, 36], [cx + gl / 2, 36], [cx + gl / 2, 110], [cx - gl / 2, 110]], 'holes': [], 'name': 'زجاج'})
    for xx in (cx - gl / 2 - 2.4, cx + gl / 2):
        g = Prof('gk', 'غاسكيت تزجيج'); g.rect(xx, 33 + GH - 7, xx + 2.4, 33 + GH + 0.6, 0.7); P += g.build()
    for q in P: q['role'] = role
    return P

def bulge_band(x0, y0, y1, b, t=1.4, n=24):
    """جدار منفوخ لبرّا (قوس) من y0 لـ y1 على x0، انتفاخه b"""
    o = [(x0 + b * math.sin(math.pi * i / n), y0 + (y1 - y0) * i / n) for i in range(n + 1)]
    inn = [(x0 - t + b * math.sin(math.pi * i / n), y0 + (y1 - y0) * i / n) for i in range(n, -1, -1)]
    return o + inn

def window_sill(SW=32, GH=26, gl=6, wheel=4.6, gapT=8, deep=26, sys='X500', deco=False, bulge=0):
    """مقطع العتبة لشباك سحّاب بمسارين: فريم متناظر، سكتين، وكل درفة بنص سكّتها بالظبط (متل العيّنة)"""
    t = 1.4; pitch = SW + gapT; half = pitch / 2 + SW / 2 + 5.5; yb = -10; rail_top = 5.2
    f = Prof('al', sys + ' — فريم (عتبة / راس / جوانب)')
    f.rect(-half, yb - t, half, yb)
    for rx in (-pitch / 2, pitch / 2):
        f.rect(rx - 0.7, yb, rx + 0.7, rail_top - 1.2).rect(rx - 2.6, rail_top - 1.4, rx + 2.6, rail_top, 0.6)
    f.rect(-half, yb - t, -half + t, 16).rect(-half, 16 - t, -half + 6, 16)        # جدار داخلي + شفة
    if bulge:  # X300S: الجدار الخارجي منفوخ لبرّا (قوسين: قصير فوق الرف وطويل تحته) + شفة ملفوفة للفرشاية + كبّاس تحت
        f.poly(bulge_band(half, yb, 16, bulge * 0.55)).poly(bulge_band(half, yb - deep, yb, bulge))
        f.rect(half - 6, yb - t, half, yb)
        f.circ(half - 1.2, 16.2, 2.4).circ(half - 1.2, 16.2, 1.1, sub=True).rect(half - 2.4, 15, half - 1.2, 16.4, sub=True)   # شفة ملفوفة
        f.rect(half - 3.4, yb - deep + 1.6, half - t + 0.01, yb - deep + 3).rect(half - 3.4, yb - deep + 1.6, half - 2, yb - deep + 4.2)  # كبّاس
    else:
        f.rect(half - t, yb - t, half, 16).rect(half - 6, 16 - t, half, 16)            # جدار خارجي + شفة
    f.rect(-0.7, yb, 0.7, 2)                                                        # فاصل المسارين
    if bulge: f.rect(-half, yb - deep, -half + t, yb).rect(-half, yb - deep, half, yb - deep + t)   # الحجرة السفلية (الجدار الخارجي قوس)
    else: f.box(-half, yb - deep, half, yb + 0.01, t)                                     # الحجرة السفلية
    f.rect(-pitch / 2 - 0.7, yb - deep, -pitch / 2 + 0.7, yb).rect(pitch / 2 - 0.7, yb - deep, pitch / 2 + 0.7, yb)
    parts = f.build()
    for q in parts: q['role'] = 'frame'
    if bulge:  # فرشاية بالشفة الملفوفة
        g = Prof('gk', 'فرشاية إحكام (Pile weather strip)'); g.rect(half - 6.6, 14.2, half - 2.2, 19.5, 0.8)
        for q in g.build(): q['role'] = 'frame'; parts.append(q)
    parts += sash_parts(-pitch / 2, SW, GH, gl, wheel, rail_top, sys, 'A', 'داخلية')
    parts += sash_parts(pitch / 2, SW, GH, gl, wheel, rail_top, sys, 'B', 'خارجية')
    if deco:  # جيدا: وجوه ديكور منحنية عالفريم والدرف
        d = Prof('al', 'جيدا — غطاء ديكور منحني للفريم'); d.poly(arc_band(half, yb - deep, 18, deep + 26, 0, 90, t=1.6)).rect(half - 1.4, 14.6, half + 1, 16).rect(half - 2, yb - deep, half + 18, yb - deep + 1.6)
        for q in d.build(): q['role'] = 'frame'; parts.append(q)
    win = {'W': 640, 'H': 520, 'frameY0': yb - deep, 'sashY0': 0, 'glassIn': 36, 'overlap': 26, 'pitch': pitch, 'sw': SW, 'yTop': yb, 'midTop': 2}
    return parts, win

def to_sec(parts, src, normal='y', motion=None, view=None):
    def cen(p):
        xs = [q[0] for q in p['pts']]; ys = [q[1] for q in p['pts']]; return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    mo = None
    if motion:
        mo = dict(motion); box = mo.pop('box', None)
        if box: mo['parts'] = [i for i, p in enumerate(parts) if box[0] <= cen(p)[0] <= box[2] and box[1] <= cen(p)[1] <= box[3]]
        if mo.pop('sash_names', None): mo['parts'] = [i for i, p in enumerate(parts) if not (p.get('name') or '').count('فريم')]
    d = {'parts': parts, 'src': src, 'normal': normal, 'motion': mo, 'labels': [], 'dims': [], 'view': view, 'video': True}
    return d

def to_win(pw, src):
    parts, win = pw
    return {'parts': parts, 'src': src, 'normal': 'x', 'motion': None, 'labels': [], 'dims': [], 'view': 'flat', 'video': True, 'win': win}

SRC300 = 'مرسوم من عيّنة X300S بفيديو ميرزونا (تقريبي — بيتحدّث برسومات المصنّع)'
SRC500 = 'مرسوم من عيّنة X500 بفيديو ميرزونا (تقريبي — بيتحدّث برسومات المصنّع)'
out = {
    'x300_ilk': to_sec(interlock(W=44, H=28, P=13, gl=6, sys='X300S'), SRC300, motion={'type': 'slide', 'dx': -130, 'box': [-200, -200, 200, -5]}),
    'x300_sill': to_win(window_sill(SW=28, GH=24, gl=6, wheel=4.2, gapT=7, deep=22, sys='X300S', bulge=5), SRC300),
    'x500_ilk': to_sec(interlock(W=52, H=34, P=15, gl=8, gap=7, off=10, pad='pd', sys='X500'), SRC500, motion={'type': 'slide', 'dx': -150, 'box': [-200, -200, 200, -6]}),
    'x500_sill': to_win(window_sill(SW=34, GH=28, gl=8, wheel=4.8, gapT=9, deep=30, sys='X500'), SRC500),
    'gida_ilk': to_sec(gida_ilk(), 'مرسوم من عيّنة جيدا بفيديو ميرزونا (تقريبي — بيتحدّث برسومات المصنّع)', motion={'type': 'slide', 'dx': -140, 'box': [-200, -200, 200, -5]}),
    'gida_sill': to_win(window_sill(SW=32, GH=26, gl=6, wheel=4.6, gapT=8, deep=26, sys='جيدا', deco=True), 'مرسوم من عيّنة جيدا بفيديو ميرزونا (تقريبي — بيتحدّث برسومات المصنّع)'),
    'hummer_ilk': to_sec(interlock(W=46, H=30, P=14, gl=6, gap=6, off=8, sys='همر'), 'مرسوم تقريبي من شكل شباك همر المركّب بفيديو ميرزونا (المقطع مش مكشوف — بيتحدّث برسومات المصنّع)', motion={'type': 'slide', 'dx': -140, 'box': [-200, -200, 200, -5]}),
    'hummer_sill': to_win(window_sill(SW=32, GH=26, gl=6, wheel=4.6, gapT=8, deep=26, sys='همر'), 'مرسوم تقريبي من شكل شباك همر المركّب بفيديو ميرزونا (المقطع مش مكشوف — بيتحدّث برسومات المصنّع)'),
    'thummer_ilk': to_sec(interlock(W=38, H=26, P=12, gl=6, gap=5, off=7, sys='تيكنال همر'), 'مرسوم تقريبي من شكل شباك تيكنال همر المركّب بفيديو ميرزونا (المقطع مش مكشوف — بيتحدّث برسومات المصنّع)', motion={'type': 'slide', 'dx': -130, 'box': [-200, -200, 200, -4]}),
    'thummer_sill': to_win(window_sill(SW=28, GH=24, gl=6, wheel=4.2, gapT=7, deep=22, sys='تيكنال همر'), 'مرسوم تقريبي من شكل شباك تيكنال همر المركّب بفيديو ميرزونا (المقطع مش مكشوف — بيتحدّث برسومات المصنّع)'),
}
json.dump(out, open('/home/claude/cat/video_sections.json', 'w'), ensure_ascii=False)
for k, v in out.items(): print(k, len(v['parts']), 'motion parts', len((v['motion'] or {}).get('parts', [])))
