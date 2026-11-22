#!/usr/bin/env python3
"""فحوصات المتصفح الآلية لميرزونا (المصمم، عرض السعر، الكتالوج).
تشغيل:  python3 tests/e2e/run_all.py            ← بيفحص ملفات المستودع الحالية
        python3 tests/e2e/run_all.py --dir beta ← بيفحص نسخة beta/
كل فحص بيفتح الصفحة بمتصفح حقيقي (Playwright/Chromium) مع سيرفر وهمي، وبيعمل: فتح، تعديل، حفظ، إغلاق، إعادة فتح.
لازم كلها تطلع PASS قبل أي تنزيل (tools/release.py بيشغّلها لحاله)."""
import asyncio, json, os, sys, shutil, tempfile, threading, base64, functools, http.server, socketserver
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, sys.argv[sys.argv.index('--dir') + 1]) if '--dir' in sys.argv else ROOT
SRV = 'https://merzona-server-production.up.railway.app'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
results = []

def check(cond, name):
    results.append((bool(cond), name))
    print(('  PASS ' if cond else '  FAIL ') + name)

def serve(dirpath):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Q, directory=dirpath)
    httpd = socketserver.TCPServer(('127.0.0.1', 0), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

def prepare():
    tmp = tempfile.mkdtemp(prefix='mz-e2e-')
    for f in os.listdir(SRC):
        p = os.path.join(SRC, f)
        if os.path.isfile(p) and (f.endswith('.html') or f.endswith('.js') or f.endswith('.json')): shutil.copy(p, tmp)
    img = os.path.join(SRC, 'img') if os.path.isdir(os.path.join(SRC, 'img')) else os.path.join(ROOT, 'img')
    if os.path.isdir(img): shutil.copytree(img, os.path.join(tmp, 'img'))
    tc = os.path.join(SRC, 'catalog-images', 'tc') if os.path.isdir(os.path.join(SRC, 'catalog-images', 'tc')) else os.path.join(ROOT, 'catalog-images', 'tc')
    if os.path.isdir(tc): shutil.copytree(tc, os.path.join(tmp, 'catalog-images', 'tc'))
    if os.environ.get('MZ_OLD_INDEX') and os.path.isfile(os.environ['MZ_OLD_INDEX']): shutil.copy(os.environ['MZ_OLD_INDEX'], os.path.join(tmp, 'index-old.html'))  # مقارنة مع نسخة قديمة
    # منكشف قائمة البنود للفحص بس (ما بيتغير الملف الأصلي)
    ip = os.path.join(tmp, 'index.html'); s = open(ip, encoding='utf8').read()
    a = "window.WD = window.WD || {};\n"
    assert a in s, 'designer anchor missing'
    s = s.replace(a, a + "WD.__t = { items: function(){ return items; }, selId: function(){ return selectedId; }, sel: function(id){ selectItem(id); }, cam: function(){ return { frame: camFrame, item: camItem, n: camOpenings.length }; }, sketch: function(){ return camBuildFacadeSketch('pencil', null); } };\n", 1)
    open(ip, 'w', encoding='utf8').write(s)
    return tmp

async def new_ctx(p, b, mobile=False):
    ctx = await (b.new_context(**p.devices['iPhone 13']) if mobile else b.new_context(viewport={"width": 1400, "height": 900}))
    await ctx.add_init_script("localStorage.setItem('merzona-device-token','dev1');localStorage.setItem('merzona-access-status','approved');localStorage.setItem('merzona-session-token','s1');window.print=function(){window.__printed=(window.__printed||0)+1};")
    async def srv(route):
        u = route.request.url
        if '/public/catalog-image/' in u: return await route.fulfill(status=200, content_type='image/png', body=PNG)
        if u.split('?')[0].endswith('/public/catalogs'):
            return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'catalogs': [{'id': 'c1', 'name': 'Showers', 'count': 3, 'cover': {'id': 'i1', 'v': '1', 'w': 10, 'h': 10}}, {'id': 'c2', 'name': 'pergolas', 'count': 2, 'cover': {'id': 'i4', 'v': '1', 'w': 10, 'h': 10}}]}))
        if '/public/catalogs/c1' in u:
            return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'id': 'c1', 'name': 'Showers', 'items': [{'id': 'i%d' % k, 'v': '1', 'w': 10, 'h': 10} for k in (1, 2, 3)]}))
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else {}
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
    return ctx

ROWS = "Array.from(document.querySelectorAll('#qty-rows tr')).filter(function(tr){return (tr.querySelector('.item-input')||{}).value}).map(function(tr){return tr.querySelector('.w-input').value+'x'+tr.querySelector('.h-input').value})"
ITEMS = "WD.__t.items().map(function(i){return {t:i.shapeType,w:i.width,h:i.height,L:i.showerLeftPanel?i.showerLeftWidth:0,R:i.showerRightPanel?i.showerRightWidth:0,seg:(i.hrSegments||[]).reduce(function(a,s){return a+(s.totalLength||0)},0),hg:i.hrGlassHeight||0,tot:i.hrTotalLength||0,mount:i.pgMount||'',lay:i.layout&&i.layout.kind}})"
ADD = """(function(rows){ function ix(n){return ITEMS.findIndex(function(t){return t.en===n})} rows.forEach(function(r){ addQtyRow(r[0],r[1],1,'',ix(r[2])); }); })(%s)"""

async def open_tool(pg, port, rows):
    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate(ADD % json.dumps(rows))
async def reopen(pg):
    await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(1000)
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1000)

async def t_sliding_ids(p, b, port):
    """🚪 عرض 260223: الكبسة عالدرفة اليمين كانت تغيّر اليسار (معرّفات مكررة)، والباب السحّاب كان يفتح لوفر/لفوق"""
    print('• المصمم: درفات بمعرّفات مكررة + باب سحّاب محفوظ كباب')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[7000, 2800, 'Aluminum Door']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(800)
    # متل البيانات المحفوظة بالعرض: باب اسمو سحّاب، 6 درفات، آخر درفة إلها نفس معرّف الأولى، وإحداهن لوفر
    await pg.evaluate("""(function(){ var ex = window.__getDesignItemsForExport__(); var it = ex.items[0];
      it.label = 'Vetromax Minimal Sliding System concealed'; it.shapeType = 'door';
      var T = ['plain','slide_left','slide_left','slide_right','louver','plain'], ids = ['n2','n3','n4','n5','n6','n2'];
      it.layout = { id:'n1', kind:'split', direction:'row', children: T.map(function(t,k){ return { frac: 100/6, node: { id: ids[k], kind:'leaf', type: t } }; }) };
      window.__applyDesignItemsImport__(JSON.parse(JSON.stringify(ex.items)), 2); })()""")
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    st = await pg.evaluate("(function(){ var it = WD.__t.items()[0]; var ids = it.layout.children.map(function(c){return c.node.id}); return { t: it.shapeType, ids: ids, types: it.layout.children.map(function(c){return c.node.type}), cap: document.querySelector('#card-' + it.id + ' .card-classify').textContent }; })()")
    check(st['t'] == 'slidingDoor' and 'Sliding Door' in st['cap'], 'باب سحّاب محفوظ كباب ← صار باب سحّاب (وبيكتب Sliding Door) ' + str(st))
    check(len(set(st['ids'])) == 6 and st['ids'][0] == 'n2', 'المعرّف المكرّر صار جديد (الأولى بتضل متل ما هي) ' + str(st['ids']))
    check('louver' not in st['types'] and st['types'][4] == 'plain', 'فتحة لوفر بباب سحّاب رجعت ثابت ' + str(st['types']))
    # كبسة عالدرفة اليمين ← بتتغيّر هي بس
    before = st['types']
    cells = pg.locator('#card-' + str(await pg.evaluate("WD.__t.items()[0].id")) + ' rect.cell')
    n = await cells.count()
    seen = set()
    for k in range(4):
        await cells.nth(n - 1).click(force=True); await pg.wait_for_timeout(150)
        tt = await pg.evaluate("WD.__t.items()[0].layout.children.map(function(c){return c.node.type})")
        seen.add(tt[5]); check(tt[:5] == before[:5], 'الكبسة عاليمين ما بتغيّر غير اليمين (' + str(k + 1) + ') ' + str(tt))
        cells = pg.locator('#card-' + str(await pg.evaluate("WD.__t.items()[0].id")) + ' rect.cell'); n = await cells.count()
    check(seen <= {'plain', 'slide_left', 'slide_right', 'frosted'} and 'slide_left' in seen, 'خيارات الباب السحّاب: ثابت/سحب بس (بلا لوفر ولا فتح لفوق) ' + str(seen))
    # تقسيم جديد بعد ما انفتحت الصفحة ما بياخد معرّف موجود
    await pg.evaluate("(function(){ var it = WD.__t.items()[0]; splitLeaf(it.id, it.layout.children[5].node.id, 'col'); })()"); await pg.wait_for_timeout(300)
    allIds = await pg.evaluate("(function(){ var out=[]; (function w(n){ out.push(n.id); if(n.kind==='split') n.children.forEach(function(c){ w(c.node); }); })(WD.__t.items()[0].layout); return out; })()")
    check(len(allIds) == len(set(allIds)), 'التقسيم الجديد بمعرّفات جديدة ' + str(allIds))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_view_version(p, b, port):
    """👁️ سجل النسخ: "شوف" بيفتح نسخة قديمة بتاب جديد للعرض بس (ولا كتابة)، والعرض الأساسي ما بيتغيّر"""
    print('• 👁️ عرض نسخة قديمة من سجل النسخ (للقراءة بس)')
    ctx = await new_ctx(p, b); posts = []
    ctx.on('request', lambda r: posts.append(r.url) if r.method not in ('GET', 'HEAD', 'OPTIONS') else None)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[2000, 1500, 'Hinged Window']])
    await pg.fill('#m-client', 'الزبون الأساس'); await pg.fill('#m-ref', 'M-Q-260223')
    old = await pg.evaluate("(function(){ var d = captureFullQuotationData(); d.fields['m-client'] = 'نسخة قديمة من الزبون'; return d; })()")
    await pg.evaluate("window.downloadDriveJsonFile = async function(){ return %s; }" % json.dumps(old, ensure_ascii=False))
    async with ctx.expect_page() as pinfo:
        await pg.evaluate("viewVersionFromHistory('f1', '١/١١/٢٠٢٦ ١٠:٣٠', 'tok')")
    vp = await pinfo.value; vdialogs = []; verrs = []
    vp.on('dialog', lambda d: (vdialogs.append(d.message), asyncio.ensure_future(d.accept()))); vp.on('pageerror', lambda e: verrs.append(str(e)[:200]))
    await vp.wait_for_load_state('load'); await vp.wait_for_timeout(4500)
    bar = await vp.evaluate("(document.getElementById('mzViewBar')||{}).innerText || ''")
    cl = await vp.evaluate("document.getElementById('m-client').value")
    check('نسخة قديمة' in bar and 'للعرض بس' in bar and 'M-Q-260223' in bar and cl == 'نسخة قديمة من الزبون', 'التاب الجديد فيه النسخة القديمة + شريط "للعرض بس" ' + repr((bar[:80], cl)))
    np = len(posts)
    await vp.evaluate("localStorage.setItem('mz-probe', 'x'); try{ saveToGoogleDrive(); }catch(e){}")
    await vp.wait_for_timeout(600)
    r = await vp.evaluate("fetch('%s/quotes/save', {method:'POST', body:'{}'}).then(function(){return 'sent'}, function(e){return 'blocked'})" % SRV)
    check(r == 'blocked' and len(posts) == np and any('للعرض بس' in m for m in vdialogs), 'بالنسخة القديمة: الحفظ والإرسال مقفولين ' + str((r, posts[np:], vdialogs[-1:])))
    probe = await pg.evaluate("localStorage.getItem('mz-probe')")
    base = await pg.evaluate("document.getElementById('m-client').value")
    check(probe is None and base == 'الزبون الأساس', 'العرض الأساسي ما تغيّر وما انكتب شي بالمتصفح ' + repr((probe, base)))
    # آخر تصميم محفوظ بينفتح لحالو - بلا سؤال
    dl = []; pg.on('dialog', lambda d: dl.append(d.message))
    got = await pg.evaluate("""(async function(){ var ex = window.__getDesignItemsForExport__(); var items = JSON.parse(JSON.stringify(ex.items)); items.forEach(function(i){ i.width = 2222; });
      window.fetchLatestSavedDesignForRef = async function(){ return { schema:'merzona-design-v1', ref:'M-Q-260223', savedAt: Date.now() + 60000, designItems: items, designNextId: ex.nextId }; };
      var r = await offerNewerSavedDesign(); return { r: r, w: window.__getDesignItemsForExport__().items.map(function(i){ return i.width; }) }; })()""")
    await pg.wait_for_timeout(300)
    check(got['r'] is True and got['w'] and all(w == 2222 for w in got['w']) and not [m for m in dl if 'تصميم' in m], 'آخر تصميم محفوظ بينفتح لحالو بلا ما يسأل ' + str((got, dl)))
    check(not errs and not verrs, 'بلا أخطاء ' + str((errs[:2], verrs[:2])))
    await ctx.close()


async def t_shower_wall(p, b, port):
    """🧱 الشاور: المقاسات يلي بتنكتب = الفتحة؛ مقاس القص = −5 مم عند كل جدار (يمين ويسار)"""
    print('• 🧱 الشاور: خصم 5 مم عند الجدار')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[1350, 2200, 'Full Shower With Glass Door'], [800, 2200, 'Glass Door']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1500)
    ids = await pg.evaluate("WD.__t.items().map(function(i){return i.id})")
    line = lambda i: pg.evaluate("(document.querySelector('#card-%d .sh-cut-line')||{}).textContent || ''" % i)
    t0 = await line(ids[0]); t1 = await line(ids[1])
    check('ثابت 545' in t0 and 'باب 795' in t0, 'شاور كامل (ثابت 550 + باب 800): قص الثابت 545 والباب 795 ' + repr(t0))
    check('باب 790' in t1, 'باب لحالو بين جدارين (800): قص 790 ' + repr(t1))
    await pg.evaluate(f"WD.__t.sel({ids[1]})"); await pg.click('#shWallBtns [data-wall="right"]'); await pg.wait_for_timeout(300)
    t1 = await line(ids[1]); act = await pg.evaluate("Array.from(document.querySelectorAll('#shWallBtns [data-wall]')).map(function(b){return b.dataset.wall + ':' + b.classList.contains('active')}).join()")
    check('باب 795' in t1 and act == 'left:true,right:false', 'جهة مش جدار ← ما في خصم منها ' + repr((t1, act)))
    tot = await pg.evaluate(ITEMS)
    check(tot[0]['w'] == 800 and tot[0]['L'] + tot[0]['R'] == 550, 'المقاسات المحفوظة ما تغيّرت (الفتحة)')
    for k in range(2): await reopen(pg)
    t1 = await line(ids[1]); check('باب 795' in t1, 'إعدادات الجدار محفوظة بعد حفظ/فتح ' + repr(t1))
    # 🆕 2026-11-22 (S-Q-260008): مقاسات التصنيع بتطلع مقاس قص كل لوح بعد خصم الجدار
    await pg.evaluate("openMfgSizesOverlay()"); await pg.wait_for_timeout(400)
    o0 = await pg.evaluate(f"document.getElementById('mfgOut-{ids[0]}').textContent")
    check(o0.replace(' ', '') == '545×2200+795×2200mm', 'مقاسات التصنيع: ثابت 545 + باب 795 ' + repr(o0))
    blk = await pg.evaluate(f"document.querySelector('#mfgOut-{ids[0]} + .sh-mfg-cut').textContent")
    check('خصم فراغ 0.5 سم' in blk and 'المجموع 1 سم' in blk and 'ثابت يسار' in blk and 'الباب' in blk, 'شرح الخصم واضح ' + blk[:90])
    if os.environ.get('MZ_SHOT'): await pg.locator(f'#mfgOut-{ids[0]}').locator('xpath=../..').screenshot(path=os.environ['MZ_SHOT'] + '/shower_mfg.png')
    await pg.click(f'#mfgOut-{ids[0]} + .sh-mfg-cut input[data-shwall="right"]'); await pg.wait_for_timeout(300)
    o0 = await pg.evaluate(f"document.getElementById('mfgOut-{ids[0]}').textContent")
    check(o0.replace(' ', '') == '545×2200+800×2200mm', 'شيل جدار يمين من مقاسات التصنيع ← الباب 800 ' + repr(o0))
    check(await pg.evaluate(f"WD.__t.items().find(function(i){{return i.id=={ids[0]}}}).showerWallR") is False, 'الإعداد انحفظ عالبند')
    # 🆕 2026-11-22: الخصم قابل للتعديل (الافتراضي 5 مم كل جدار)
    await pg.evaluate("closeMfgSizesOverlay()"); await pg.evaluate(f"WD.__t.sel({ids[1]})"); await pg.wait_for_timeout(200)
    check(await pg.evaluate("document.getElementById('shWallGap').value") == '5' and await pg.evaluate("!!document.querySelector('.mz-step #shWallGap')"), 'خانة الخصم بلوحة الشاور (افتراضي 5) بأسهم')
    await pg.click('#shWallBtns [data-wall="right"]'); await pg.wait_for_timeout(200)  # رجّع جدار اليمين
    await pg.fill('#shWallGap', '10'); await pg.dispatch_event('#shWallGap', 'change'); await pg.wait_for_timeout(300)
    t1 = await line(ids[1]); check('باب 780' in t1 and '−10' in t1, 'خصم 10 مم كل جدار ← باب 800 بين جدارين = 780 ' + repr(t1))
    check('المجموع 2 سم' in await pg.evaluate("document.getElementById('shWallGapTot').textContent"), 'المجموع مكتوب (2 سم)')
    if os.environ.get('MZ_SHOT'): await pg.locator('#showerDoorBlock').screenshot(path=os.environ['MZ_SHOT'] + '/shower_gap_panel.png')
    await pg.evaluate("openMfgSizesOverlay()"); await pg.wait_for_timeout(300)
    await pg.locator(f'#mfgOut-{ids[1]} + .sh-mfg-cut .mz-step button.mz-step-b').first.click(); await pg.wait_for_timeout(300)
    o1 = await pg.evaluate(f"document.getElementById('mfgOut-{ids[1]}').textContent")
    if os.environ.get('MZ_SHOT'): await pg.locator(f'#mfgOut-{ids[1]}').locator('xpath=..').screenshot(path=os.environ['MZ_SHOT'] + '/shower_gap_mfg.png')
    check(o1.replace(' ', '') == '782×2200mm', 'سهم − بمقاسات التصنيع ← 9 مم كل جدار = 782 ' + repr(o1))
    check(await pg.evaluate(f"WD.__t.items().find(function(i){{return i.id=={ids[0]}}}).showerWallGap") is None, 'البنود التانية ما تأثرت (افتراضي)')
    await reopen(pg)
    check(await pg.evaluate(f"WD.__t.items().find(function(i){{return i.id=={ids[1]}}}).showerWallGap") == 9, 'الخصم انحفظ بعد إعادة الفتح')
    await pg.evaluate("closeMfgSizesOverlay()")
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_camera_quad(p, b, port):
    """📷 الكاميرا: كل زاوية من الإطار الأزرق بتتحرك لحالها (تصوير من اليمين/اليسار) والرسمة بتلحق الزوايا"""
    print('• 📷 الكاميرا: زوايا حرة للإطار (منظور)')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); dl = []
    pg.on('dialog', lambda d: (dl.append(d.message), asyncio.ensure_future(d.accept())))
    await open_tool(pg, port, [[1200, 1400, 'Hinged Window']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1000)
    await pg.evaluate("""navigator.mediaDevices.getUserMedia = async function(){ var c = document.createElement('canvas'); c.width = 640; c.height = 480; var x = c.getContext('2d'); x.fillStyle = '#777'; x.fillRect(0,0,640,480); x.fillStyle = '#ddd'; x.fillRect(200,120,240,240); return c.captureStream(5); }""")
    await pg.evaluate("openCameraOverlay()"); await pg.wait_for_timeout(900)
    F = "(function(){ var f = WD.__t.cam().frame; return { q: f.q || null, x0: f.x0, y0: f.y0, x1: f.x1, y1: f.y1 }; })()"
    async def drag(corner, dx, dy):
        bb = await pg.locator('.cam-handle[data-corner="%s"] .cam-dot' % corner).bounding_box()
        cx, cy = bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2
        await pg.mouse.move(cx, cy); await pg.mouse.down()
        for k in range(1, 6): await pg.mouse.move(cx + dx * k / 5, cy + dy * k / 5)
        await pg.mouse.up(); await pg.wait_for_timeout(150)
    f0 = await pg.evaluate(F)
    await drag('tr', 0, 90)
    f1 = await pg.evaluate(F); q = f1['q']
    vw, vh = 1400, 900
    check(q and abs(q[1][1] - (0.25 + 90 / vh)) < 0.01 and abs(q[1][0] - 0.75) < 0.005, 'الزاوية فوق-يمين نزلت لحالها ' + str(q))
    check(q and q[0] == [0.25, 0.25] and abs(q[2][0] - 0.75) < 1e-6 and abs(q[2][1] - 0.75) < 1e-6 and q[3] == [0.25, 0.75], 'باقي الزوايا ما تحركت ' + str(q))
    pts = await pg.evaluate("document.getElementById('camFrameInner').getAttribute('points')")
    check(len(pts.split()) == 4, 'الإطار مرسوم شكل رباعي ' + pts)
    check(await pg.evaluate("getComputedStyle(document.getElementById('camSquareBtn')).display != 'none'"), 'زر رجّعو زوايا قائمة ظاهر')
    await drag('bl', -60, 40)
    q2 = (await pg.evaluate(F))['q']
    check(abs(q2[3][0] - (0.25 - 60 / vw)) < 0.01 and abs(q2[3][1] - (0.75 + 40 / vh)) < 0.01, 'الزاوية تحت-يسار طلعت لبرّا لحالها ' + str(q2))
    # شكل متقاطع ما بينقبل: سحب فوق-يسار لورا فوق-يمين
    await drag('tl', 900, 0)
    q3 = (await pg.evaluate(F))['q']
    check(q3[0][0] < q3[1][0], 'ما بيقبل شكل متقاطع/مقلوب ' + str(q3))
    # بعد التثبيت: وضع التكبير مستطيل للتقسيم، و"شوفو عالفتحة" بيلوي الرسمة عالزوايا
    await pg.evaluate("cameraConfirmFrame()"); await pg.wait_for_timeout(400)
    check(await pg.evaluate("document.querySelectorAll('#camPerspLayer .cam-persp').length") == 0 and await pg.evaluate("document.querySelectorAll('#cameraOverlaySvg .cam-split-btn').length") > 0, 'وضع التقسيم: مستطيل مستقيم مع أزرار التقسيم')
    await pg.evaluate("cameraToggleZoom()"); await pg.wait_for_timeout(400)
    m = await pg.evaluate("""(function(){ var s = document.querySelector('#camPerspLayer .cam-persp[data-cam-active]'); if(!s) return null;
      var M = new DOMMatrix(getComputedStyle(s).transform), w = +s.getAttribute('width'), h = +s.getAttribute('height');
      var vb = document.getElementById('cameraOverlaySvg').viewBox.baseVal;
      function ap(x, y){ var p = M.transformPoint(new DOMPoint(x, y, 0, 1)); return [p.x / p.w / vb.width, p.y / p.w / vb.height]; }
      return { c: [ap(0,0), ap(w,0), ap(w,h), ap(0,h)], q: WD.__t.cam().frame.q }; })()""")
    if os.environ.get('MZ_SHOT'): await pg.screenshot(path=os.environ['MZ_SHOT'] + '/cam_persp.png')
    ok = m and all(abs(m['c'][i][j] - m['q'][i][j]) < 0.003 for i in range(4) for j in range(2))
    check(ok, 'زوايا الرسمة = زوايا الإطار الأربعة بالضبط ' + str(m))
    # النقر على القسم بالرسمة الملوية بيدوّر شكله
    t0 = await pg.evaluate("JSON.stringify(WD.__t.cam().item.layout)")
    qq = m['q']; cx = sum(x[0] for x in qq) / 4 * vw; cy = sum(x[1] for x in qq) / 4 * vh
    await pg.mouse.click(cx, cy); await pg.wait_for_timeout(300)
    t1 = await pg.evaluate("JSON.stringify(WD.__t.cam().item.layout)")
    check(t0 != t1, 'النقر عالقسم بالرسمة الملوية بيغيّر شكله')
    sk = await pg.evaluate("WD.__t.sketch().then(function(c){ window.__sk = c.toDataURL('image/png'); return { w: c.width, h: c.height }; }, function(e){ return 'ERR ' + e.message; })")
    if os.environ.get('MZ_SHOT'):
        import base64; open(os.environ['MZ_SHOT'] + '/cam_sketch.png', 'wb').write(base64.b64decode((await pg.evaluate('window.__sk')).split(',')[1]))
    check(isinstance(sk, dict) and sk['w'] > 100, 'سكتش الواجهة اشتغل مع الفتحة الملوية ' + str(sk))
    await pg.evaluate("cameraBackToFraming()"); await pg.wait_for_timeout(200)
    await pg.evaluate("cameraSquareFrame()"); await pg.wait_for_timeout(200)
    f4 = await pg.evaluate(F)
    check(f4['q'] is None and abs(f4['x1'] - f1['x1']) < 0.02, 'رجّعو زوايا قائمة: صار مستطيل ' + str(f4))
    await pg.evaluate("closeCameraOverlay()")
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_real3d(p, b, port):
    """✨ ثري دي واقعي: كل شباك/باب بينعرض صورة WebGL واقعية + عارض تفاعلي (لون/زجاج) - وإذا ما في WebGL بتضل الرسمة"""
    print('• ✨ ثري دي واقعي')
    fx = os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'three')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await ctx.route('**/three.min.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'three.min.js'), 'rb').read()))
    await ctx.route('**/OrbitControls.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'OrbitControls.js'), 'rb').read()))
    await open_tool(pg, port, [[3000, 2400, "Aluminum's Sliding Doors"], [1200, 1400, 'Hinged Window'], [1000, 2200, 'Aluminum Casting Gate for Persons'], [1305, 2200, 'Glass Partitions for Showers'], [4000, 1100, 'Handrail (Hidden Glass)']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    check(await pg.evaluate("!!(window.THREE && THREE.WebGLRenderer)"), 'three.js محمّل')
    await pg.evaluate("""(function(){ var its = WD.__t.items(); var w = its[1];
      w.layout = {id:'q1',kind:'split',direction:'row',children:[{frac:50,node:{id:'q2',kind:'leaf',type:'tri_right'}},{frac:50,node:{id:'q3',kind:'leaf',type:'plain'}}]};
      its[0].layout = {id:'s1',kind:'split',direction:'row',children:[{frac:50,node:{id:'s2',kind:'leaf',type:'slide_right'}},{frac:50,node:{id:'s3',kind:'leaf',type:'slide_left'}}]};
      its[2].layout = {id:'d1',kind:'leaf',type:'tri_left'}; })()""")
    await pg.evaluate("open3DPreview()")
    for k in range(40):
        n = await pg.evaluate("document.querySelectorAll('#threeDGrid img.threeD-real').length")
        if n >= 4: break
        await pg.wait_for_timeout(300)
    info = await pg.evaluate("""Array.from(document.querySelectorAll('#threeDGrid .threeD-card')).map(function(c){ var i = c.querySelector('img.threeD-real'); return i ? (i.naturalWidth + 'x' + i.naturalHeight) : (c.querySelector('svg') ? 'svg' : '-'); })""")
    check(info[:4] == ['900x680'] * 4, 'السحاب والشباك والباب والفاصل: صورة واقعية ' + str(info))
    check(info[4] == 'svg', 'الهاندريل: بتضل الرسمة ' + str(info))
    # الصورة مش فاضية: فيها تباين (الحيط + الألمنيوم الغامق)
    var = await pg.evaluate("""new Promise(function(res){ var im = document.querySelector('#threeDGrid img.threeD-real'); var c = document.createElement('canvas'); c.width = 90; c.height = 68; var x = c.getContext('2d'); x.drawImage(im, 0, 0, 90, 68); var d = x.getImageData(0,0,90,68).data, mn = 255, mx = 0; for(var i=0;i<d.length;i+=4){ var v = (d[i]+d[i+1]+d[i+2])/3; if(v<mn) mn=v; if(v>mx) mx=v; } res([mn, mx]); })""")
    check(var[1] - var[0] > 120, 'الصورة مرسومة فعلاً (مش فاضية) ' + str(var))
    if os.environ.get('MZ_SHOT'):
        await pg.screenshot(path=os.environ['MZ_SHOT'] + '/r3d_cards.png', full_page=False)
        for i, nm in enumerate(['slide', 'win', 'door']):
            u = await pg.evaluate("document.querySelectorAll('#threeDGrid img.threeD-real')[%d].src" % i)
            import base64; open(os.environ['MZ_SHOT'] + '/r3d_%s.png' % nm, 'wb').write(base64.b64decode(u.split(',')[1]))
    # زر الرسمة بيرجّع الرسمة
    await pg.click('#threeDGrid .threeD-card >> nth=0 >> [data-r3d="sketch"]'); await pg.wait_for_timeout(200)
    check(await pg.evaluate("(function(){ var c = document.querySelectorAll('#threeDGrid .threeD-card')[0]; return c.querySelector('.threeD-sketch svg') && c.querySelector('img.threeD-real').style.display == 'none'; })()"), 'زر ✏️ الرسمة بيبدّل للرسمة')
    # العارض التفاعلي + لون
    await pg.click('#threeDGrid .threeD-card >> nth=1 >> [data-r3d="view"]'); await pg.wait_for_timeout(800)
    check(await pg.evaluate("!!document.querySelector('#mzR3dOverlay canvas')"), 'العارض التفاعلي انفتح')
    await pg.click('#mzR3dBar button[data-k="color"][data-v="white"]'); await pg.wait_for_timeout(500)
    await pg.click('#mzR3dBar button[data-k="glass"][data-v="tinted"]'); await pg.wait_for_timeout(500)
    if os.environ.get('MZ_SHOT'): await pg.screenshot(path=os.environ['MZ_SHOT'] + '/r3d_viewer.png')
    # سحب للتدوير بلا أخطاء
    await pg.mouse.move(700, 400); await pg.mouse.down(); await pg.mouse.move(560, 360, steps=8); await pg.mouse.up(); await pg.wait_for_timeout(300)
    await pg.click('#mzR3dClose'); await pg.wait_for_timeout(200)
    check(await pg.evaluate("!document.getElementById('mzR3dOverlay')"), 'العارض تسكّر')
    await pg.evaluate("close3DPreview()")
    for k in range(2): await reopen(pg)
    c = await pg.evaluate("(function(){ var w = WD.__t.items()[1]; return [w.r3dColor, w.r3dGlass, w.width, w.height]; })()")
    check(c == ['white', 'tinted', 1200, 1400], 'اللون والزجاج انحفظوا مع البند والمقاس ما تغيّر ' + str(c))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_real3d_pergola(p, b, port):
    """⛱️ البيرغولا بالثري دي (صورة واقعية) + سقف ساندويتش بانل + تغيير السقف من العارض"""
    print('• ⛱️ بيرغولا ثري دي + ساندويتش بانل')
    fx = os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'three')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await ctx.route('**/three.min.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'three.min.js'), 'rb').read()))
    await ctx.route('**/OrbitControls.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'OrbitControls.js'), 'rb').read()))
    await open_tool(pg, port, [[8750, 4800, 'Aluminum Pergola'], [1200, 1400, 'Hinged Window']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    await pg.evaluate("WD.__t.sel(WD.__t.items()[0].id)"); await pg.wait_for_timeout(300)
    await pg.evaluate("setShape('pergola')"); await pg.wait_for_timeout(300)
    await pg.evaluate("pgField('width', 8750); pgField('height', 4800)"); await pg.wait_for_timeout(200)
    t = await pg.evaluate("(function(){ var it = WD.__t.items()[0]; return [it.shapeType, it.width, it.height]; })()")
    check(t == ['pergola', 8750, 4800], 'البند بيرغولا ' + str(t))
    check(await pg.evaluate("!!document.querySelector('#inPgRoof option[value=sandwich]')"), 'خيار سقف ساندويتش بانل موجود بالمصمم')
    await pg.select_option('#inPgRoof', 'sandwich'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("WD.__t.items()[0].pgRoof") == 'sandwich', 'السقف صار ساندويتش')
    check(await pg.evaluate("/ساندويتش بانل/.test(buildPergolaSVG(WD.__t.items()[0], null)) && /مساحة السقف 42.00/.test(buildPergolaSVG(WD.__t.items()[0], null))"), 'الرسمة والمساحة (8.75×4.8=42 م²)')
    await pg.evaluate("open3DPreview()")
    for k in range(40):
        n = await pg.evaluate("document.querySelectorAll('#threeDGrid img.threeD-real').length")
        if n >= 2: break
        await pg.wait_for_timeout(300)
    info = await pg.evaluate("""Array.from(document.querySelectorAll('#threeDGrid .threeD-card')).map(function(c){ var i = c.querySelector('img.threeD-real'); return i ? 'img' : (c.querySelector('svg') ? 'svg' : '-'); })""")
    check(info == ['img', 'img'], 'البيرغولا والشباك بالثري دي ' + str(info))
    if os.environ.get('MZ_SHOT'):
        import base64
        u = await pg.evaluate("document.querySelectorAll('#threeDGrid img.threeD-real')[0].src"); open(os.environ['MZ_SHOT'] + '/pg_sandwich.png', 'wb').write(base64.b64decode(u.split(',')[1]))
    check(await pg.evaluate("/ألوان ونوع السقف/.test(document.querySelectorAll('#threeDGrid .threeD-card')[0].textContent)"), 'زر العارض للبيرغولا')
    await pg.click('#threeDGrid .threeD-card >> nth=0 >> [data-r3d="view"]'); await pg.wait_for_timeout(800)
    check(await pg.evaluate("document.querySelectorAll('#mzR3dBar button[data-k=roof]').length") == 5, '5 أنواع سقف بالعارض')
    for roof in ['louver', 'poly', 'glass', 'slats']:
        await pg.click('#mzR3dBar button[data-k="roof"][data-v="%s"]' % roof); await pg.wait_for_timeout(400)
        if os.environ.get('MZ_SHOT'): await pg.screenshot(path=os.environ['MZ_SHOT'] + '/pg_%s.png' % roof)
    check(await pg.evaluate("WD.__t.items()[0].pgRoof") == 'slats' and await pg.evaluate("document.getElementById('inPgRoof').value") == 'slats', 'تغيير السقف من العارض بيتطبق عالتصميم')
    await pg.click('#mzR3dBar button[data-k="roof"][data-v="sandwich"]'); await pg.wait_for_timeout(300)
    await pg.mouse.move(700, 400); await pg.mouse.down(); await pg.mouse.move(400, 300, steps=8); await pg.mouse.up(); await pg.wait_for_timeout(300)
    if os.environ.get('MZ_SHOT'): await pg.screenshot(path=os.environ['MZ_SHOT'] + '/pg_view.png')
    await pg.click('#mzR3dClose'); await pg.evaluate("close3DPreview()")
    for k in range(2): await reopen(pg)
    check(await pg.evaluate("WD.__t.items()[0].pgRoof") == 'sandwich', 'السقف انحفظ بعد إعادة الفتح')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_pergola_posts(p, b, port):
    """⛱️ تصميم أعمدة البيرغولا: مزدوج + قطع بالنص، الطرفين زاوية، تحكم بالقياسات، وكل عمود لحاله"""
    print('• ⛱️ تصميم أعمدة البيرغولا')
    fx = os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'three')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await ctx.route('**/three.min.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'three.min.js'), 'rb').read()))
    await ctx.route('**/OrbitControls.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'OrbitControls.js'), 'rb').read()))
    await open_tool(pg, port, [[8750, 4800, 'Aluminum Pergola']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    await pg.evaluate("WD.__t.sel(WD.__t.items()[0].id); setShape('pergola')"); await pg.wait_for_timeout(300)
    await pg.evaluate("pgField('width', 8750); pgField('height', 4800); pgField('pgMount', 'wall'); pgField('pgPostsPerRow', 3); pgField('pgRoof', 'sandwich')"); await pg.wait_for_timeout(200)
    L = "(function(){ var ly = pgPostLayout(WD.__t.items()[0]); return { posts: ly.posts.length, rungs: ly.rungs.length, fins: ly.fins.length, ys: ly.ys.length, slots: ly.slots.map(function(x){ return x.style; }), p: ly.posts.map(function(q){ return [Math.round(q.x), Math.round(q.z)]; }) }; })()"
    a = await pg.evaluate(L)
    check(a['posts'] == 3 and a['fins'] == 0 and a['slots'] == ['single'] * 3, 'عادي: 3 أعمدة ' + str(a))
    check(await pg.evaluate("getComputedStyle(document.getElementById('pgDblBlock')).display") == 'none', 'خيارات المزدوج مخفية')
    await pg.click('#pgPostStyleBtns [data-v="double"]'); await pg.wait_for_timeout(300)
    a = await pg.evaluate(L)
    check(a['slots'] == ['corner', 'double', 'corner'] and a['posts'] == 6, 'مزدوج: الطرفين زاوية والوسط عمودين ' + str(a))
    check(a['fins'] == 6 and a['rungs'] == 0 and a['ys'] == 0, 'افتراضي: قطع عمودية (2 بالوسط و2 بكل زاوية) ' + str(a))
    check([4150, 75] in a['p'] and [4600, 75] in a['p'], 'عمود الوسط مزدوج بالمسافة الصح ' + str(a['p']))
    check([325, 75] in a['p'] and [75, 325] in a['p'] and [8425, 75] in a['p'] and [8675, 325] in a['p'], 'الزوايا: ضلع قدام وضلع جنب 400 ' + str(a['p']))
    check(await pg.evaluate("document.querySelector('#pgInfillDirBtns [data-v=v]').classList.contains('active')"), 'زر عمودية مفعّل')
    # أفقية كخيار
    await pg.click('#pgInfillDirBtns [data-v="h"]'); await pg.wait_for_timeout(200)
    a = await pg.evaluate(L)
    check(a['fins'] == 0 and a['rungs'] == 5 and a['ys'] > 0, 'أفقية متل السلّم كخيار ' + str(a))
    await pg.click('#pgInfillDirBtns [data-v="v"]'); await pg.wait_for_timeout(200)
    check(await pg.evaluate("getComputedStyle(document.getElementById('pgDblBlock')).display") == 'block', 'خيارات المزدوج ظاهرة')
    await pg.fill('#inPgDblGap', '500'); await pg.dispatch_event('#inPgDblGap', 'change')
    await pg.fill('#inPgCornerF', '600'); await pg.dispatch_event('#inPgCornerF', 'change')
    await pg.fill('#inPgInfillGap', '80'); await pg.dispatch_event('#inPgInfillGap', 'change')
    await pg.select_option('#inPgInfill', '50x100'); await pg.wait_for_timeout(300)
    a = await pg.evaluate(L)
    check([4050, 75] in a['p'] and [4700, 75] in a['p'] and [525, 75] in a['p'] and a['fins'] == 9, 'القياسات بتتطبق ' + str(a))
    cut = await pg.evaluate("pgCalc(WD.__t.items()[0]).cut.filter(function(c){ return /قطع تصميم/.test(c.name); }).map(function(c){ return [c.size, c.n, c.len]; })")
    check(cut == [['50x100', 9, 2550]], 'القطع العمودية بالتيوبات (طولها لتحت الجسر) ' + str(cut))
    check(await pg.evaluate("pgCalc(WD.__t.items()[0]).cut[0].n") == 6, 'عدد الأعمدة بالتيوبات 6')
    check(await pg.evaluate("document.querySelectorAll('#pgPostCustomBox select').length") == 3 and await pg.evaluate("document.querySelectorAll('#pgPostCustomBox select')[0].querySelector('option[value=corner]') != null && document.querySelectorAll('#pgPostCustomBox select')[1].querySelector('option[value=corner]') == null"), 'اختيار لكل عمود (الزاوية بس للأطراف)')
    await pg.select_option('#pgPostCustomBox select[data-pgpost="1"]', 'single'); await pg.wait_for_timeout(300)
    a = await pg.evaluate(L)
    check(a['slots'] == ['corner', 'single', 'corner'] and a['posts'] == 5 and a['fins'] == 6, 'عمود الوسط صار عادي ' + str(a))
    svg = await pg.evaluate("buildPergolaSVG(WD.__t.items()[0], null)")
    check(svg.count('stroke-width') > 0 and 'ساندويتش' in svg, 'الرسمة')
    if os.environ.get('MZ_SHOT'):
        await pg.evaluate("(function(){ var d = document.createElement('div'); d.id='pgShot'; d.style.cssText='position:fixed;inset:0;background:#fff;z-index:99999;padding:10px'; d.innerHTML = buildPergolaSVG(WD.__t.items()[0], null).replace(/var\(--wd-ink[^)]*\)/g,'#223'); document.body.appendChild(d); })()")
        await pg.screenshot(path=os.environ['MZ_SHOT'] + '/pgp_svg.png'); await pg.evaluate("document.getElementById('pgShot').remove()")
    await pg.evaluate("open3DPreview()")
    for k in range(40):
        if await pg.evaluate("document.querySelectorAll('#threeDGrid img.threeD-real').length") >= 1: break
        await pg.wait_for_timeout(300)
    check(await pg.evaluate("document.querySelectorAll('#threeDGrid img.threeD-real').length") == 1, 'الثري دي مع تصميم الأعمدة')
    if os.environ.get('MZ_SHOT'):
        import base64
        u = await pg.evaluate("document.querySelector('#threeDGrid img.threeD-real').src"); open(os.environ['MZ_SHOT'] + '/pgp_3d.png', 'wb').write(base64.b64decode(u.split(',')[1]))
        await pg.click('#threeDGrid .threeD-card >> nth=0 >> [data-r3d="view"]'); await pg.wait_for_timeout(800)
        await pg.mouse.move(700, 450); await pg.mouse.down(); await pg.mouse.move(860, 420, steps=6); await pg.mouse.up(); await pg.mouse.wheel(0, -900); await pg.wait_for_timeout(500)
        await pg.screenshot(path=os.environ['MZ_SHOT'] + '/pgp_view.png'); await pg.click('#mzR3dClose')
    await pg.evaluate("close3DPreview()")
    for k in range(2): await reopen(pg)
    a = await pg.evaluate(L)
    check(a['slots'] == ['corner', 'single', 'corner'] and await pg.evaluate("WD.__t.items()[0].pgDblGap") == 500, 'انحفظ بعد إعادة الفتح ' + str(a))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_hr_sizes_steppers(p, b, port):
    """🏷️ مسقط الهاندريل: مقاس كل لوح مكتوب (بالمسقط وبالثري دي) + أسهم −/+ للعدد بدل الكتابة + عدد القطع الصغيرة بالبيرغولا"""
    print('• مقاسات ألواح الهاندريل + أسهم العدد')
    fx = os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'three')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await ctx.route('**/three.min.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'three.min.js'), 'rb').read()))
    await ctx.route('**/OrbitControls.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'OrbitControls.js'), 'rb').read()))
    await open_tool(pg, port, [[7230, 1100, 'Glass Handrail for Balcony'], [8750, 4800, 'Aluminum Pergola']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    iid = await pg.evaluate("WD.__t.items()[0].id"); await pg.evaluate(f"WD.__t.sel({iid})"); await pg.wait_for_timeout(300)
    # أسهم عدد الألواح (الهاندريل المسطح)
    st = await pg.evaluate("(function(){ var i = document.getElementById('inHrCount'); var w = i.parentNode; return { wrap: w.classList.contains('mz-step'), btns: w.querySelectorAll('button.mz-step-b').length, v: i.value }; })()")
    check(st['wrap'] and st['btns'] == 2, 'خانة عدد الألواح إلها أسهم − و + ' + str(st))
    v0 = int(st['v'])
    await pg.click('#inHrCount + button.mz-step-b'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("+document.getElementById('inHrCount').value") == v0 + 1, 'سهم + بيزيد العدد')
    await pg.locator('.mz-step:has(#inHrCount) button.mz-step-b').first.click(); await pg.locator('.mz-step:has(#inHrCount) button.mz-step-b').first.click(); await pg.wait_for_timeout(300)
    check(await pg.evaluate("+document.getElementById('inHrCount').value") == v0 - 1, 'سهم − بينقّص العدد')
    check(await pg.evaluate("!!document.querySelector('.mz-step #inHrStandoffPairs')"), 'أزواج الستاند أوف كمان بأسهم')
    # المسقط + الأضلاع
    await pg.click('#btnHrPlanStart'); await pg.wait_for_timeout(400)
    segs = await pg.evaluate("WD.__t.items()[0].hrSegments.map(function(s){return s.id})")
    await pg.evaluate(f"onHrSegField({iid},'{segs[0]}','totalLength',6040); onHrSegField({iid},'{segs[0]}','panelCount',5); onHrSegField({iid},'{segs[1]}','totalLength',1190); onHrSegField({iid},'{segs[1]}','panelCount',1)")
    await pg.wait_for_timeout(400)
    n = await pg.evaluate("document.querySelectorAll('#hrSegmentsList .mz-step').length")
    check(n >= 2, 'عدد ألواح كل ضلع بأسهم ' + str(n))
    await pg.locator('#hrSegmentsList .mz-step >> nth=1 >> button.mz-step-b >> nth=1').click(); await pg.wait_for_timeout(400)
    check(await pg.evaluate("WD.__t.items()[0].hrSegments[1].panelCount") == 2, 'سهم + على الضلع التاني ← لوحين')
    pw = await pg.evaluate(f"Array.from(document.querySelectorAll('#card-{iid} .hr-plan-svg text.hr-pw')).map(function(t){{return t.textContent}})")
    pws = [round(int(x)) for x in pw]
    check(len(pw) == 7 and pws.count(pws[0]) >= 5 and all(450 < x < 1250 for x in pws), 'مقاس كل لوح مكتوب عالمسقط ' + str(pw))
    # ثري دي: لافتات المقاسات + زر إخفاء
    await pg.evaluate(f"WD.__t.sel({iid})"); await pg.click('#btnHr3D'); await pg.wait_for_timeout(900)
    d3 = await pg.evaluate("window.__getHr3DDebugState__()")
    check(d3['open'] and d3['labels'] == 7 + 2 and d3['labelsVisible'] == 9, 'ثري دي: مقاس على كل لوح + طول كل ضلع ' + str(d3))
    if os.environ.get('MZ_SHOT'): await pg.screenshot(path=os.environ['MZ_SHOT'] + '/hr3d_labels.png')
    await pg.click('#hr3DLblBtn'); await pg.wait_for_timeout(200)
    check(await pg.evaluate("window.__getHr3DDebugState__().labelsVisible") == 0, 'زر خبّي المقاسات')
    await pg.click('#hr3DLblBtn'); await pg.wait_for_timeout(200)
    check(await pg.evaluate("window.__getHr3DDebugState__().labelsVisible") == 9, 'زر أظهر المقاسات')
    await pg.evaluate("closeHandrail3D()")
    if os.environ.get('MZ_SHOT'):
        await pg.locator(f'#card-{iid}').screenshot(path=os.environ['MZ_SHOT'] + '/hr_plan_pw.png')
        await pg.locator('#hrSegmentsList').screenshot(path=os.environ['MZ_SHOT'] + '/hr_segs_step.png')
    # البيرغولا: عدد القطع الصغيرة بين العمودين
    pid = await pg.evaluate("WD.__t.items()[1].id"); await pg.evaluate(f"WD.__t.sel({pid}); setShape('pergola')"); await pg.wait_for_timeout(300)
    await pg.evaluate("pgField('width', 8750); pgField('height', 4800); pgField('pgMount', 'wall'); pgField('pgPostsPerRow', 3); pgField('pgPostStyle', 'double')"); await pg.wait_for_timeout(300)
    F = "pgPostLayout(WD.__t.items()[1]).fins.length"
    check(await pg.evaluate(F) == 6, 'تلقائي حسب الفراغ (6)')
    check(await pg.evaluate("!!document.querySelector('.mz-step #inPgInfillCount')"), 'خانة عدد القطع الصغيرة بأسهم')
    for k in range(4): await pg.locator('.mz-step:has(#inPgInfillCount) button.mz-step-b >> nth=1').click()
    await pg.wait_for_timeout(300)
    check(await pg.evaluate("WD.__t.items()[1].pgInfillCount") == 4 and await pg.evaluate(F) == 12, 'عدد ثابت 4 بين كل عمودين (3 مسافات = 12) ' + str(await pg.evaluate(F)))
    cut = await pg.evaluate("pgCalc(WD.__t.items()[1]).cut.filter(function(c){ return /قطع تصميم/.test(c.name); }).map(function(c){ return c.n; })")
    check(cut == [12], 'التيوبات بتحسب العدد الجديد ' + str(cut))
    await pg.click('#pgInfillDirBtns [data-v="h"]'); await pg.wait_for_timeout(200)
    check(await pg.evaluate("pgPostLayout(WD.__t.items()[1]).ys.length") == 4, 'أفقي كمان بيلتزم بالعدد')
    await pg.click('#pgInfillDirBtns [data-v="v"]'); await pg.wait_for_timeout(200)
    await reopen(pg)
    check(await pg.evaluate("WD.__t.items()[1].pgInfillCount") == 4, 'العدد انحفظ بعد إعادة الفتح')
    await pg.evaluate("WD.__t.sel(WD.__t.items()[1].id); pgField('pgInfillCount', 0)"); await pg.wait_for_timeout(200)
    check(await pg.evaluate(F) == 6, 'صفر ← رجع تلقائي')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_survey(p, b, port):
    """📏 الكشف بالموقع (2026-11-22): صوت ← مقاسات، بلا نت ← بينحفظ وبينفهم بعدين، ليزر، ذكاء اصطناعي من صورة، حفظ عالموبايل، وتحويل لعرض سعر"""
    print('• 📏 الكشف بالموقع: صوت + بلا نت + ليزر + صورة + عرض سعر')
    ctx = await new_ctx(p, b, mobile=True); calls = []
    async def sv(route):
        u = route.request.url.split('?')[0]; body = route.request.post_data or ''
        calls.append((u.rsplit('/', 1)[-1] if '/survey/' not in u else u.split('/survey/')[1], len(body)))
        J = lambda o, st=200: route.fulfill(status=st, content_type='application/json', body=json.dumps(o, ensure_ascii=False))
        if u.endswith('/quote-items'): return await J({'items': [{'en': 'Hinged Window', 'ar': 'شباك مفصلي'}, {'en': 'Aluminum Door', 'ar': 'باب ألمنيوم'}]})
        if u.endswith('/survey/status'): return await J({'voice': True, 'ai': True})
        if u.endswith('/survey/stt'):
            n = sum(1 for c in calls if c[0] == 'stt')
            return await J({'heard': 'المطبخ شباك مفصلي ألف وميتين بألف وخمسمية عدد 2', 'w': 1200, 'h': 1500, 'qty': 2, 'room': 'المطبخ', 'item': {'en': 'Hinged Window', 'ar': 'شباك مفصلي'}} if n == 1 else
                           {'heard': 'باب الصالون تسعمية بألفين ومية', 'w': 900, 'h': 2100, 'qty': 1, 'room': 'الصالون', 'item': {'en': 'Aluminum Door', 'ar': 'باب ألمنيوم'}})
        if u.endswith('/survey/parse'): return await J({'heard': '', 'w': None, 'h': None, 'qty': 1, 'room': 'الواجهة', 'item': {'en': 'Hinged Window', 'ar': 'شباك مفصلي'}})
        if u.endswith('/survey/ai-photo'): return await J({'kind': 'plan', 'openings': [{'type': 'شباك مفصلي', 'where': 'الواجهة', 'w': 1450, 'h': None, 'qty': 3, 'note': 'قيس الارتفاع'}, {'type': 'باب', 'where': 'المدخل', 'w': None, 'h': None, 'qty': 1, 'note': ''}], 'notes': ''})
        if u.endswith('/survey/save'): return await J({'ok': True})
        if '/users/status' in u: return await J({})
        return await J({'status': 'approved'} if '/access/status' in u else {})
    await ctx.route(SRV + '/**', sv)
    # مايك وهمي (صوت من مولّد نغمة) - MediaRecorder حقيقي
    await ctx.add_init_script("""navigator.mediaDevices.getUserMedia = function(){ var ac = new AudioContext(); var o = ac.createOscillator(); var d = ac.createMediaStreamDestination(); o.connect(d); o.start(); return Promise.resolve(d.stream); };""")
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/survey.html'); await pg.wait_for_timeout(2500)
    check(await pg.is_visible('#svNew'), 'الصفحة بتفتح (بعد البوابة) وفيها «كشف جديد»')
    check('📝 النوتات' in await pg.inner_text('#svMain') and 'نوت' in await pg.title(), 'اسمها «نوت»')
    await pg.click('#svNew'); await pg.wait_for_timeout(500)
    await pg.fill('#svClient', 'أبو سامر'); await pg.fill('#svLoc', 'المزة')
    # 🎙️ صوت ← السيرفر ← الخانات
    await pg.click('#svMic'); await pg.wait_for_timeout(1500)
    check(await pg.evaluate("document.getElementById('svMic').classList.contains('rec')"), 'عم يسجّل (الزر أحمر)')
    await pg.click('#svMic'); await pg.wait_for_timeout(1500)
    o = await pg.evaluate("SV._state.cur.openings.map(function(o){ return [o.room, o.item && o.item.en, o.w, o.h, o.qty]; })")
    check(o == [['المطبخ', 'Hinged Window', 1200, 1500, 2]], 'الصوت عبّى الفتحة: المطبخ، شباك مفصلي، 1200×1500، عدد 2 ' + str(o))
    stt = [c for c in calls if c[0] == 'stt']
    check(len(stt) == 1 and stt[0][1] > 2000, 'التسجيل انبعت للسيرفر ' + str(stt))
    check('سمعت' in await pg.inner_text('#svMain'), 'بيبيّن شو سمع')
    # 📴 بلا نت ← التسجيل بينحفظ، ولما يرجع النت بينفهم
    await ctx.set_offline(True); await pg.evaluate("window.dispatchEvent(new Event('offline'))"); await pg.wait_for_timeout(200)
    check('بلا نت' in await pg.inner_text('#svNet'), 'شارة «بلا نت»')
    await pg.click('#svMic'); await pg.wait_for_timeout(1300); await pg.click('#svMic'); await pg.wait_for_timeout(1200)
    st = await pg.evaluate("SV._state.cur.openings.map(function(o){ return !!o.pendingAudio; })")
    check(st == [False, True], 'بلا نت: فتحة جديدة والتسجيل محفوظ ' + str(st))
    check('بانتظار' in await pg.inner_text('#svMain') or 'بيتفهم' in await pg.inner_text('#svMain'), 'مكتوب إنو التسجيل بانتظار النت')
    await ctx.set_offline(False); await pg.evaluate("window.dispatchEvent(new Event('online'))"); await pg.wait_for_timeout(2000)
    o = await pg.evaluate("SV._state.cur.openings.map(function(o){ return [o.room, o.w, o.h, !!o.pendingAudio]; })")
    check(o[1] == ['الصالون', 900, 2100, False], 'رجع النت ← التسجيل انفهم لحالو ' + str(o))
    # 📡 ليزر: بعد ما تكبس عالعرض، القياس بينزل فيه وبعدين بالارتفاع
    oid = await pg.evaluate("SV._state.cur.openings[1].id")
    await pg.evaluate(f"SV.focusField(document.querySelector('#op-{oid} input[data-f=w]'))")
    await pg.evaluate("SV._laserValue(915)"); await pg.evaluate("SV._laserValue(2095)")
    o = await pg.evaluate("[SV._state.cur.openings[1].w, SV._state.cur.openings[1].h]")
    check(o == [915, 2095], 'الليزر: العرض وبعدين الارتفاع ' + str(o))
    # − / + للعدد
    await pg.click(f'#op-{oid} .step button >> nth=1'); await pg.click(f'#op-{oid} .step button >> nth=1')
    check(await pg.evaluate("SV._state.cur.openings[1].qty") == 3, 'أسهم العدد')
    # 🤖 صورة/مخطط
    tmpimg = os.path.join(tempfile.gettempdir(), 'mz-plan.png'); open(tmpimg, 'wb').write(PNG)
    await pg.set_input_files('#svAiFile', tmpimg); await pg.wait_for_timeout(1500)
    txt = await pg.inner_text('#svModalBox')
    check('لقيت بالمخطط 2' in txt and '1450' in txt, 'الذكاء الاصطناعي اقترح فتحتين ' + txt[:80])
    await pg.click('#svModalBox [data-ai="1"]'); await pg.click('#svModalBox .btn >> text=ضيفهن'); await pg.wait_for_timeout(1200)
    o = await pg.evaluate("SV._state.cur.openings.slice(2).map(function(o){ return [o.item && o.item.en, o.w, o.h, o.qty, o.room]; })")
    check(o == [['Hinged Window', 1450, None, 3, 'الواجهة']], 'بس المختارة انضافت، مع المقاس المكتوب والعدد ' + str(o))
    if os.environ.get('MZ_SHOT'): await pg.screenshot(path=os.environ['MZ_SHOT'] + '/survey.png', full_page=True)
    # 💾 عالموبايل: بعد إعادة التحميل كل شي موجود
    await pg.wait_for_timeout(600); await pg.reload(); await pg.wait_for_timeout(2500)
    t = await pg.inner_text('#svMain')
    check('أبو سامر' in t and '3 فتحة' in t, 'بعد إعادة التحميل الكشف محفوظ عالموبايل ' + t[:120])
    await pg.click('.sv-list .card'); await pg.wait_for_timeout(600)
    check(await pg.evaluate("SV._state.cur.openings.length") == 3, 'الفتحات رجعت')
    await pg.wait_for_timeout(4500)
    check(any(c[0] == 'save' for c in calls), 'نسخة انرفعت للسيرفر')
    # 📄 حوّل لعرض سعر
    await pg.click('.dock .btn >> text=حوّل لعرض سعر'); await pg.wait_for_timeout(9000)
    check('index.html' in pg.url, 'انفتحت أداة عرض السعر')
    rows = await pg.evaluate(ROWS)
    cl = await pg.evaluate("document.getElementById('m-client').value")
    check(rows[:2] == ['1200x1500', '915x2095'] and rows[2].startswith('1450x') and len(rows) == 3 and cl == 'أبو سامر', 'العرض انعبّى من الكشف ' + str((rows, cl)))
    qty = await pg.evaluate("Array.from(document.querySelectorAll('#qty-rows tr')).filter(function(tr){return (tr.querySelector('.item-input')||{}).value}).map(function(tr){return tr.querySelector('.qty-input').value})")
    check(qty == ['2', '3', '3'], 'الأعداد ' + str(qty))
    check('من النوت' in await pg.evaluate("document.body.innerText"), 'رسالة «من النوت»')
    # 📝 النوت جوّا قسم عروض الأسعار بالداشبورد
    pd = await ctx.new_page(); await pd.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pd.wait_for_timeout(3000)
    await pd.click('#quotationsTabBtn'); await pd.wait_for_timeout(800)
    check(await pd.is_visible('#mzNotePanel') and await pd.get_attribute('#mzNoteNew', 'href') == 'survey.html#new' and await pd.locator('#surveyTabBtn').count() == 0, 'زر «📝 نوت» بقسم عروض الأسعار (مش زر لحالو)')
    await pd.click('#mzNoteNew'); await pd.wait_for_timeout(2800)
    check('survey.html' in pd.url and await pd.evaluate("!!(SV._state.cur && SV._state.cur.openings)"), '«➕ نوت جديدة» بتفتح نوت فاضية مباشرة')
    await pd.close()
    check(not errs, 'بلا أخطاء ' + str(errs[:3]))
    await ctx.close()


async def t_cutplan(p, b, port):
    """✂️ خطة القص والستيكرات (2026-11-22): الزجاج على ألواح المعمل والألمنيوم على القضبان بأقل هدر + ستيكر لكل قطعة"""
    print('• ✂️ خطة القص (زجاج + ألمنيوم) والستيكرات')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    # الخوارزميات
    r = await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
    sh = await pg.evaluate("(function(){ var r = cpPackSheets([{code:'A',name:'x',w:1600,h:1100,qty:6}], {sheetW:3210,sheetH:2250,gap:4,rotate:true}); return [r.sheets.length, r.sheets.map(function(s){return s.used.length}), r.tooBig.length]; })()")
    check(sh == [2, [4, 2], 0], '6 قطع 1600×1100 ← لوحين (4 + 2) ' + str(sh))
    sh = await pg.evaluate("(function(){ var r = cpPackSheets([{code:'A',name:'x',w:2200,h:3000,qty:1},{code:'B',name:'y',w:4000,h:500,qty:1}], {sheetW:3210,sheetH:2250,gap:4,rotate:true}); return [r.sheets.length, r.sheets[0].used[0].rot, r.tooBig.length]; })()")
    check(sh == [1, True, 1], 'قطعة بتندار لتساع، والأكبر من اللوح بتنحكى ' + str(sh))
    ov = await pg.evaluate("(function(){ var r = cpPackSheets([{code:'A',name:'x',w:700,h:900,qty:7},{code:'B',name:'y',w:1300,h:400,qty:5},{code:'C',name:'z',w:500,h:2100,qty:3}], {sheetW:3210,sheetH:2250,gap:4,rotate:true}); return r.sheets.map(function(s){ return s.used.map(function(a){ return [a.x,a.y,a.w,a.h]; }); }); })()")
    bad = []
    for shs in ov:
        for i, a in enumerate(shs):
            if a[0] < 0 or a[1] < 0 or a[0] + a[2] > 3210.01 or a[1] + a[3] > 2250.01: bad.append(('out', a))
            for c in shs[i+1:]:
                sep = max(c[0] - (a[0] + a[2]), a[0] - (c[0] + c[2]), c[1] - (a[1] + a[3]), a[1] - (c[1] + c[3]))
                if sep < 4 - 0.01: bad.append(('near', a, c, sep))
    check(not bad and sum(len(x) for x in ov) == 15, 'ولا قطعة فوق التانية ولا برّا اللوح وبينهن فراغ القص، وكل القطع انحطت ' + str(bad[:2]))
    rnd = await pg.evaluate("(function(){ var bad = 0, lost = 0, seed = 7; function R(n){ seed = (seed * 16807) % 2147483647; return seed % n; } for(var t = 0; t < 40; t++){ var ps = [], tot = 0; for(var k = 0; k < 1 + R(8); k++){ var q = 1 + R(6); tot += q; ps.push({code:'P'+k, name:'x', w: 150 + R(2600), h: 150 + R(2000), qty: q}); } var r = cpPackSheets(ps, {sheetW:3210, sheetH:2250, gap:4, rotate: !!R(2)}); var n = r.tooBig.length; r.sheets.forEach(function(s){ n += s.used.length; s.used.forEach(function(a, i){ if(a.x < 0 || a.y < 0 || a.x + a.w > 3210.01 || a.y + a.h > 2250.01) bad++; s.used.forEach(function(c, j){ if(j <= i) return; var sep = Math.max(c.x - (a.x + a.w), a.x - (c.x + c.w), c.y - (a.y + a.h), a.y - (c.y + c.h)); if(sep < 3.99) bad++; }); }); }); if(n !== tot) lost++; } return [bad, lost]; })()")
    check(rnd == [0, 0], '40 تجربة عشوائية: ولا تداخل ولا قطعة ضايعة ' + str(rnd))
    br = await pg.evaluate("(function(){ var r = cpPackBars([{profile:'P1',name:'a',len:3000,qty:2},{profile:'P1',name:'b',len:2900,qty:1},{profile:'P1',name:'c',len:1000,qty:1},{profile:'P2',name:'d',len:7000,qty:1}], {bar:6000,kerf:4,trim:10}); return r.map(function(g){ return [g.profile, g.bars.length, g.bars.map(function(b){ return b.cuts.map(function(c){return c.len}); }), g.tooLong.length]; }); })()")
    check(br == [['P1', 2, [[3000, 2900], [3000, 1000]], 0], ['P2', 0, [], 1]], 'القضبان: 3000+3000 ما بيساعوا بقضيب (الشفرة والأطراف) ← قضيبين، والأطول من القضيب بينحكى ' + str(br))
    # من التصميم: شاور + هاندريل + بيرغولا
    await pg.evaluate(ADD % json.dumps([[1350, 2200, 'Full Shower With Glass Door'], [6040, 1100, 'Glass Handrail for Balcony'], [4000, 3000, 'Aluminum Pergola']]))
    await pg.fill('#m-ref', 'M-Q-260999'); await pg.fill('#m-client', 'أبو سامر')
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1500)
    ids = await pg.evaluate("WD.__t.items().map(function(i){return i.id})")
    await pg.evaluate(f"WD.__t.sel({ids[2]}); setShape('pergola')"); await pg.wait_for_timeout(300)
    await pg.evaluate("openMfgSizesOverlay()"); await pg.wait_for_timeout(300)
    await pg.click('#mfgSizesOverlay button >> text=خطة القص'); await pg.wait_for_timeout(600)
    g = await pg.evaluate("__CP.glass.map(function(p){ return [p.name, p.w, p.h, p.qty]; })")
    check(['ثابت يسار', 545, 2200, 1] in g and ['الباب', 795, 2200, 1] in g, 'قطع الشاور بعد خصم الجدار ' + str(g))
    hr = [x for x in g if x[0] == 'لوح هاندريل']
    check(hr and sum(x[3] for x in hr) >= 4 and all(x[2] == 1100 for x in hr), 'ألواح الهاندريل ' + str(hr))
    bars = await pg.evaluate("__CP.bars.length")
    check(bars > 0, 'قطع البيرغولا نزلت للقضبان ' + str(bars))
    gs = await pg.inner_text('#cpGlassSum'); bs = await pg.inner_text('#cpBarsSum')
    check(('لوح' in gs or 'ألواح' in gs) and 'الاستفادة' in gs and 'قضيب' in bs and 'الهدر' in bs, 'الملخص: ألواح وقضبان وهدر ' + gs[:80] + ' | ' + bs[:80])
    check(await pg.locator('#cpBody .cp-sheet svg').count() >= 1 and await pg.locator('#cpBody .cp-bar svg').count() >= 1, 'رسمة لكل لوح ولكل قضيب')
    # قطعة يدوية + بتنحفظ لنفس العرض
    await pg.click('#cpBody button >> text=قطعة زجاج'); await pg.wait_for_timeout(300)
    n = await pg.evaluate("__CP.glass.length")
    await pg.fill(f'input[data-cp="glass:{n-1}:w"]', '1450'); await pg.dispatch_event(f'input[data-cp="glass:{n-1}:w"]', 'change'); await pg.wait_for_timeout(300)
    await pg.evaluate("closeCutPlan(); openCutPlan()"); await pg.wait_for_timeout(400)
    check(await pg.evaluate("__CP.glass.filter(function(p){return p.manual && p.w === 1450}).length") == 1, 'القطعة اليدوية انحفظت لهالعرض')
    if os.environ.get('MZ_SHOT'): await pg.screenshot(path=os.environ['MZ_SHOT'] + '/cutplan.png', full_page=False)
    # الستيكرات
    html = await pg.evaluate("cpLabelsHTML()")
    tot = await pg.evaluate("__CP.glass.filter(function(p){return !p.off}).reduce(function(a,p){return a+p.qty},0) + __CP.bars.filter(function(p){return !p.off}).reduce(function(a,p){return a+p.qty},0)")
    check(html.count('class="lb"') == tot and (html.count('<svg') == tot or not await pg.evaluate("typeof qrcode !== 'undefined'")) and 'M-Q-260999' in html and 'أبو سامر' in html and '545 × 2200' in html, 'ستيكر لكل قطعة مع QR ورقم العرض والمقاس (' + str(tot) + ')')
    async with pg.expect_popup() as pinfo:
        await pg.evaluate("window.print = function(){}"); await pg.click('#cpOverlay button >> text=اطبع الستيكرات')
    pop = await pinfo.value
    await pop.wait_for_load_state(); check(await pop.locator('.lb').count() == tot, 'صفحة الطباعة فيها كل الستيكرات')
    await pop.close()
    check(not errs, 'بلا أخطاء ' + str(errs[:3]))
    await ctx.close()


async def t_install_checklist(p, b, port):
    """✅ قوائم التركيب والتسليم (2026-11-22): خطوات + صور + توقيع + تقرير، بلا نت، ومن الكشف مباشرة"""
    print('• ✅ قائمة التركيب والتسليم')
    ctx = await new_ctx(p, b, mobile=True); saved = []
    async def sv(route):
        u = route.request.url.split('?')[0]
        if u.endswith('/survey/save'): saved.append(json.loads(route.request.post_data or '{}'))
        body = {'status': 'approved'} if '/access/status' in u else ({'items': []} if u.endswith('/quote-items') else {})
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', sv)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/survey.html'); await pg.wait_for_timeout(2500)
    # من كشف ← تركيب بنفس بيانات الزبون
    await pg.click('#svNew'); await pg.wait_for_timeout(400); await pg.fill('#svClient', 'أم خالد'); await pg.fill('#svLoc', 'كفرسوسة')
    await pg.click('#svMain button >> text=✅ تركيب'); await pg.wait_for_timeout(700)
    st = await pg.evaluate("[SV._state.cur.type, SV._state.cur.client, SV._state.cur.location, SV._state.cur.steps.length]")
    check(st[0] == 'install' and st[1] == 'أم خالد' and st[2] == 'كفرسوسة' and st[3] >= 8, 'تركيب من الكشف بنفس بيانات الزبون وخطوات جاهزة ' + str(st))
    await pg.set_offline(True) if hasattr(pg, 'set_offline') else await ctx.set_offline(True)
    chks = pg.locator('.st-chk'); await chks.nth(0).check(); await chks.nth(1).check(); await pg.wait_for_timeout(200)
    check('2 من' in await pg.inner_text('#inProgTxt'), 'التقدّم بيتحدّث (بلا نت كمان)')
    # صورة لخطوة
    sid = await pg.evaluate("SV._state.cur.steps[2].id")
    tmpimg = os.path.join(tempfile.gettempdir(), 'mz-step.png'); open(tmpimg, 'wb').write(PNG)
    await pg.evaluate(f"SV.stepPhoto('{sid}')"); await pg.set_input_files('#svFile', tmpimg); await pg.wait_for_timeout(800)
    check(await pg.evaluate("SV._state.cur.steps[2].photos.length") == 1, 'صورة للخطوة')
    await pg.click('#svMain .btn >> text=نوع') if False else None
    # خطوة جديدة
    await pg.click('#svMain button >> text=➕ خطوة'); await pg.wait_for_timeout(300)
    n = await pg.evaluate("SV._state.cur.steps.length"); check(n == st[3] + 1, 'خطوة جديدة')
    # توقيع
    c = pg.locator('#inSig'); bb = await c.bounding_box()
    await pg.mouse.move(bb['x'] + 20, bb['y'] + 40); await pg.mouse.down(); await pg.mouse.move(bb['x'] + 120, bb['y'] + 90, steps=8); await pg.mouse.move(bb['x'] + 200, bb['y'] + 30, steps=8); await pg.mouse.up()
    await pg.click('#svMain button >> text=اعتمد التوقيع'); await pg.wait_for_timeout(400)
    sig = await pg.evaluate("[SV._state.cur.signature.slice(0, 22), !!SV._state.cur.signedAt]")
    check(sig == ['data:image/png;base64,', True] and await pg.is_visible('#inSigImg'), 'التوقيع انحفظ كصورة ' + str(sig))
    if os.environ.get('MZ_SHOT'): await pg.screenshot(path=os.environ['MZ_SHOT'] + '/install.png', full_page=True)
    # بعد إعادة التحميل
    await pg.wait_for_timeout(500); await ctx.set_offline(False); await pg.reload(); await pg.wait_for_timeout(2500)
    t = await pg.inner_text('#svMain')
    check('✅ أم خالد' in t and 'موقّع' in t and '2/' in t, 'بالقائمة: التركيب محفوظ وموقّع ' + t[:160])
    await pg.wait_for_timeout(4500)
    ins = [x['survey'] for x in saved if x.get('survey', {}).get('type') == 'install']
    check(ins and ins[-1]['signature'] and len(ins[-1]['steps'][2]['photos']) == 1, 'نسخة للسيرفر مع الصور والتوقيع')
    # واتس اب
    await pg.click('.sv-list .card >> text=✅ أم خالد'); await pg.wait_for_timeout(500)
    await pg.evaluate("SV.field('phone', '0939 919 670'); window.__opened = []; window.open = function(u){ window.__opened.push(u); }")
    await pg.click('#svMain button >> text=ابعت للزبون')
    await pg.wait_for_function("window.__opened && window.__opened.length > 0", timeout=5000); u = await pg.evaluate("window.__opened.filter(function(x){ return x; })[0] || JSON.stringify(window.__opened)")
    import urllib.parse as _up
    check(u.startswith('https://wa.me/963939919670?text=') and 'أم خالد' in _up.unquote(u) and '✔️' in _up.unquote(u), 'رسالة واتس اب بالخطوات ' + _up.unquote(u)[:100])
    check(not errs, 'بلا أخطاء ' + str(errs[:3]))
    await ctx.close()


async def t_techcat(p, b, port):
    """📘 الكتالوج الفني للمهندسين (2026-11-22): صفحة عامة مرتّبة + كل المقاطع موجودة + بلا ملاحظات داخلية + زر بالداشبورد"""
    print('• 📘 الكتالوج الفني للمهندسين')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    await pg.goto(f'http://127.0.0.1:{port}/techcat.html'); await pg.wait_for_timeout(1500)
    n = await pg.locator('section.sys').count()
    check(n >= 20, 'كل الأنظمة معروضة ' + str(n))
    txt = await pg.inner_text('#doc')
    check('غير محدد' not in txt and '.pdf' not in txt and 'صفحة)' not in txt and 'الكتالوج بيذكر' not in txt, 'بلا ملاحظات داخلية ولا "غير محدد" ولا أسماء ملفات')
    srcs = await pg.evaluate("Array.from(document.querySelectorAll('figure:not(.web) img')).map(function(i){ return i.src; })")
    bad = []
    for u in srcs:
        r = await pg.request.get(u)
        if r.status != 200: bad.append(u.rsplit('/', 1)[-1])
    check(len(srcs) >= 50 and not bad, 'كل صور المقاطع موجودة (' + str(len(srcs)) + ') ' + str(bad[:3]))
    check(await pg.locator('figure svg').count() >= 6, 'مقاطع توضيحية للأنظمة يلي ما إلها رسمة رسمية')
    check(all(await pg.evaluate("Array.from(document.querySelectorAll('section.sys')).map(function(s){ return !!s.querySelector('figure'); })")), 'كل نظام إلو مقطع/رسمة')
    check(await pg.locator('.toc a').count() == n, 'فهرس فيه كل الأنظمة')
    # 🧊 مقاطع ميرزونا: كل رسمة 2D إلها مجسّم 3D من نفس الأشكال
    fx = os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'three')
    await ctx.route('**/three.min.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'three.min.js'), 'rb').read()))
    await ctx.route('**/OrbitControls.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(os.path.join(fx, 'OrbitControls.js'), 'rb').read()))
    nb = await pg.locator('.b3d').count(); check(nb == n, 'كل نظام إلو مقطع ميرزونا مع زر 3D (' + str(nb) + '/' + str(n) + ')')
    for code in ['MZ-SL-01', 'MZ-SL-05', 'MZ-HG-01', 'MZ-HG-03', 'MZ-FD-01', 'MZ-PV-01', 'MZ-CW-03', 'MZ-CW-05', 'MZ-BL-01', 'MZ-VS-01']:
        await pg.click('#' + code + ' .b3d'); await pg.wait_for_timeout(1200)
        v = await pg.evaluate("[window.__v3, !!document.querySelector('#v3c canvas'), getComputedStyle(document.getElementById('v3')).display, TC.SECMAP['%s'].parts.length]" % code)
        check(v[1] and v[2] == 'flex' and v[0]['parts'] == v[3], code + ': المجسّم 3D من نفس أشكال الرسمة (' + str(v[3]) + ' قطعة)')
        await pg.click('#v3 button >> text=➕'); await pg.click('#v3 button >> text=↺ رجّع'); await pg.click('#v3 button >> text=✕'); await pg.wait_for_timeout(150)
    await ctx.close()
    # ⛔ إطفاء/تشغيل الأنظمة
    ctx = await new_ctx(p, b); posted = []; state = {'hidden': ['MZ-SL-01', 'MZ-CW-06']}
    async def tcs(route):
        if route.request.method == 'POST': posted.append(json.loads(route.request.post_data)); state['hidden'] = posted[-1]['hidden']
        await route.fulfill(status=200, content_type='application/json', body=json.dumps({'hidden': state['hidden']}))
    await ctx.route(SRV + '/public/techcat-settings', tcs); await ctx.route(SRV + '/techcat-settings', tcs)
    pg = await ctx.new_page(); await pg.goto(f'http://127.0.0.1:{port}/techcat.html'); await pg.wait_for_timeout(1500)
    check(await pg.locator('section.sys').count() == n - 2 and await pg.locator('#MZ-SL-01').count() == 0 and 'MZ-CW-06' not in await pg.inner_text('.toc'), 'الأنظمة المطفية ما بتطلع للزبون (ولا بالفهرس)')
    await pg.goto(f'http://127.0.0.1:{port}/techcat.html#manage'); await pg.reload(); await pg.wait_for_timeout(1500)
    check(await pg.locator('section.sys').count() == n and await pg.locator('#MZ-SL-01.off').count() == 1 and await pg.locator('.tc-sw').count() == n, 'وضع الإدارة: كل الأنظمة مع مفتاح، والمطفي باهت')
    await pg.click('#MZ-SL-01 .tc-sw input'); await pg.click('#MZ-HG-02 .tc-sw input'); await pg.wait_for_timeout(600)
    check(posted and sorted(posted[-1]['hidden']) == ['MZ-CW-06', 'MZ-HG-02'] and '✅' in await pg.inner_text('#tcMsg'), 'التشغيل والإطفاء بينحفظ عالسيرفر ' + str(posted[-1:]))
    pg2 = await ctx.new_page(); await pg2.goto(f'http://127.0.0.1:{port}/techcat.html'); await pg2.wait_for_timeout(1500)
    check(await pg2.locator('#MZ-SL-01').count() == 1 and await pg2.locator('#MZ-HG-02').count() == 0, 'الزبون بيشوف التعديل فوراً')
    # 📤 رابط لنظام واحد (متل كتالوج الصور)
    p3 = await ctx.new_page(); await p3.goto(f'http://127.0.0.1:{port}/techcat.html?s=MZ-SL-04'); await p3.wait_for_timeout(1500)
    t3 = await p3.inner_text('#doc')
    check(await p3.locator('section.sys').count() == 1 and await p3.locator('#MZ-SL-04 figure').count() >= 2 and 'Montana' in t3 and 'كل الكتالوج' in t3 and 'Montana' in await p3.title(), 'رابط نظام واحد: النظام بمقاطعه + اللوغو + التواصل')
    await p3.goto(f'http://127.0.0.1:{port}/techcat.html?s=MZ-HG-02'); await p3.wait_for_timeout(1200)
    check(await p3.locator('section.sys').count() == 0 and 'مش متوفر' in await p3.inner_text('#doc'), 'النظام المطفي ما بينفتح برابطه')
    await p3.goto(f'http://127.0.0.1:{port}/techcat.html'); await p3.wait_for_timeout(1200)
    await p3.evaluate("navigator.share = function(o){ window.__sh = o; return Promise.resolve(); }")
    await p3.click('#MZ-SL-04 .tc-share'); sh = await p3.evaluate("window.__sh")
    check(sh and sh['url'].endswith('techcat.html?s=MZ-SL-04') and 'Montana' in sh['title'], 'زر «ابعت هالنظام» بيبعت رابط النظام ' + str(sh))
    await ctx.close()
    ctx = await new_ctx(p, b); pd = await ctx.new_page()
    await pd.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pd.wait_for_timeout(3000)
    await pd.click('#catalogsTabBtn'); await pd.wait_for_timeout(800)
    check(await pd.is_visible('#techCatPanel') and await pd.get_attribute('#techCatOpen', 'href') == 'techcat.html' and await pd.get_attribute('#techCatManage', 'href') == 'techcat.html#manage', 'زر الكتالوج الفني بقسم الكتالوجات')
    check(not errs, 'بلا أخطاء ' + str(errs[:3]))
    await ctx.close()


async def t_design_new_item_confirm(p, b, port):
    """🛠️ M-Q-260224: بند انضاف بالمصمم بالغلط (بيرغولا تانية) ما بيصير بند بعرض السعر بلا سؤال، واسمه مش Plan + Front"""
    print('• المصمم: بند جديد بلا صف ← سؤال قبل ما ينضاف لعرض السعر')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    msgs = []; mode = {'accept': False}
    def on_dialog(d):
        msgs.append(d.message)
        asyncio.ensure_future(d.accept() if mode['accept'] else d.dismiss())
    pg.on('dialog', on_dialog)
    await open_tool(pg, port, [[1200, 1400, 'Hinged Window']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    rows0 = await pg.evaluate("document.querySelectorAll('#qty-rows tr[data-row-uid]').length")
    await pg.evaluate("addItem('pergola')"); await pg.wait_for_timeout(300)
    await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(1000)
    check(any('مش موجود بعرض السعر' in m and 'بيرغولا' in m for m in msgs), 'سؤال قبل إضافة البند ' + str(msgs[-1:]))
    check(await pg.evaluate("document.querySelectorAll('#qty-rows tr[data-row-uid]').length") == rows0, 'إلغاء ← ما انضاف صف')
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1000)
    check(await pg.evaluate("WD.__t.items().filter(function(i){ return i.shapeType === 'pergola'; }).length") == 0, 'إلغاء ← البند انشال من التصميم')
    mode['accept'] = True; n0 = len(msgs)
    await pg.evaluate("addItem('pergola')"); await pg.wait_for_timeout(300)
    await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(1200)
    check(len(msgs) > n0 and await pg.evaluate("document.querySelectorAll('#qty-rows tr[data-row-uid]').length") == rows0 + 1, 'موافق ← انضاف صف')
    nm = await pg.evaluate("(function(){ var r = document.querySelectorAll('#qty-rows tr[data-row-uid]'); return r[r.length-1].querySelector('.item-input').value; })()")
    check('Plan + Front' not in nm and 'ergola' in nm, 'اسم البند الجديد من بنود السيستم ' + nm)
    # بلا بنود جديدة ← بلا سؤال
    n1 = len(msgs); await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1000); await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(800)
    check(not any('مش موجود بعرض السعر' in m for m in msgs[n1:]), 'ما في بنود جديدة ← ما في سؤال')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_mobile_delete_item(p, b, port):
    """🗑️ عالموبايل: زر حذف على كل بطاقة وبشريط التعديل (شريط الأسماء مع × مخفي عالموبايل)"""
    print('• المصمم عالموبايل: زر الحذف')
    ctx = await new_ctx(p, b, mobile=True); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    msgs = []; pg.on('dialog', lambda d: (msgs.append(d.message), asyncio.ensure_future(d.accept())))
    await open_tool(pg, port, [[1200, 1400, 'Hinged Window']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    await pg.evaluate("addItem('room')"); await pg.wait_for_timeout(400)
    n0 = await pg.evaluate("WD.__t.items().length")
    rid = await pg.evaluate("WD.__t.items().filter(function(i){ return i.shapeType === 'room'; })[0].id")
    btn = pg.locator('#card-%d .mz-card-del' % rid)
    check(await btn.count() == 1 and await btn.is_visible(), 'زر 🗑️ احذف ظاهر على بطاقة المجلس عالموبايل')
    await btn.click(); await pg.wait_for_timeout(400)
    check(await pg.evaluate("WD.__t.items().length") == n0 - 1 and any('بدك تحذف' in m for m in msgs), 'انحذف بعد التأكيد')
    # شريط التعديل
    await pg.evaluate("addItem('pergola')"); await pg.wait_for_timeout(400)
    check(await pg.locator('#mzEdBar .mz-ed-del').count() == 1, 'زر 🗑️ بشريط التعديل')
    n1 = await pg.evaluate("WD.__t.items().length")
    await pg.evaluate("mzDeleteAsk(WD.__t.selId())"); await pg.wait_for_timeout(300)
    check(await pg.evaluate("WD.__t.items().length") == n1 - 1 and await pg.evaluate("WD.__t.items().every(function(i){ return i.shapeType !== 'pergola'; })"), 'حذف البند المفتوح')
    # البند المربوط بصف: سؤال واحد بس (سؤال الصف)
    m0 = len(msgs); wid = await pg.evaluate("WD.__t.items()[0].id")
    await pg.locator('#card-%d .mz-card-del' % wid).click(); await pg.wait_for_timeout(400)
    check(len(msgs) == m0 + 1 and 'مربوط بصف' in msgs[-1], 'المربوط بصف: سؤال واحد ' + str(msgs[m0:]))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_refresh_restore(p, b, port):
    """🔄 الريفريش بيرجّعك لنفس المكان: نفس العرض المفتوح (والمصمم)، وبالداشبورد نفس القسم - وعرض جديد بالنية بيبلّش فاضي"""
    print('• الريفريش: بتضل وين كنت')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[1200, 1400, 'Hinged Window'], [2000, 2200, 'Aluminum Door']])
    await pg.fill('#m-client', 'زبون الريفريش'); await pg.dispatch_event('#m-client', 'input'); await pg.wait_for_timeout(2500)
    n_before = await pg.evaluate("document.querySelectorAll('#qty-rows tr .item-input').length")
    await pg.reload(); await pg.wait_for_timeout(4000)
    r = await pg.evaluate("({ c: document.getElementById('m-client').value, n: document.querySelectorAll('#qty-rows tr .item-input').length, w: Array.from(document.querySelectorAll('#qty-rows .w-input')).map(function(i){ return i.value; }) })")
    check(r['c'] == 'زبون الريفريش' and r['n'] == n_before and '2000' in r['w'] and '1200' in r['w'], 'بعد الريفريش: نفس العرض ' + str(r))
    # المصمم مفتوح ← بيرجع مفتوح
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(3000)
    await pg.reload(); await pg.wait_for_timeout(5500)
    check(await pg.evaluate("getComputedStyle(document.getElementById('wdOverlay')).display != 'none'"), 'بعد الريفريش: المصمم رجع مفتوح')
    await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(2500)
    # عرض جديد بالنية ← ريفريش بيضل فاضي
    await pg.evaluate("resetAllNoConfirm()"); await pg.wait_for_timeout(2500)
    await pg.reload(); await pg.wait_for_timeout(4000)
    check(await pg.evaluate("document.getElementById('m-client').value") == '', 'عرض جديد ← بعد الريفريش بيضل فاضي')
    # فتحة عادية (مش ريفريش) ← ما في رجوع
    await pg.fill('#m-client', 'زبون تاني'); await pg.dispatch_event('#m-client', 'input'); await pg.wait_for_timeout(2500)
    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(4000)
    check(await pg.evaluate("document.getElementById('m-client').value") == '', 'فتح الصفحة من جديد (مش ريفريش) ← عرض فاضي متل قبل')
    # الداشبورد: القسم المفتوح بيرجع بعد الريفريش
    pd = await ctx.new_page(); pd.on('pageerror', lambda e: errs.append(str(e)[:200])); pd.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pd.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pd.wait_for_timeout(3000)
    await pd.evaluate("showQuotationsView()"); await pd.wait_for_timeout(500)
    await pd.reload(); await pd.wait_for_timeout(3500)
    check(await pd.evaluate("document.getElementById('quotationsView').style.display != 'none' && document.getElementById('dashboardView').style.display == 'none'"), 'الداشبورد: رجع على نفس القسم بعد الريفريش')
    await pd.evaluate("showDashboardView()"); await pd.wait_for_timeout(300); await pd.reload(); await pd.wait_for_timeout(3000)
    check(await pd.evaluate("document.getElementById('dashboardView').style.display != 'none'"), 'الداشبورد: اللوحة الرئيسية بتضل الرئيسية')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_types_and_roundtrip(p, b, port):
    print('• أنواع البنود + حفظ وإعادة فتح')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[16549, 1100, 'Handrail (Hidden Glass)'], [5200, 1100, 'Glass Handrail for Balcony'], [1500, 2200, 'Aluminum Casting Gate for Persons'],
                               [3000, 2400, "Aluminum's Sliding Doors"], [1305, 2200, 'Glass Partitions for Showers'], [1350, 2200, 'Full Shower With Glass Door'],
                               [900, 2200, 'Glass Door'], [6000, 5000, 'Pergola Aluminum (Majlis)'], [1200, 1400, 'Hinged Window']])
    rows0 = await pg.evaluate(ROWS)
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1500)
    it = await pg.evaluate(ITEMS)
    check([x['t'] for x in it] == ['handrail', 'handrail', 'door', 'slidingDoor', 'window', 'showerGlassDoor', 'showerGlassDoor', 'pergola', 'window'], 'أنواع البنود من الأسماء')
    check(it[0]['seg'] == 16549 and it[0]['hg'] == 1100, 'طول وارتفاع الهاندريل من الجدول')
    check(it[5]['w'] == 800 and it[5]['L'] + it[5]['R'] == 550, 'الشاور الكامل: باب 800 + ثابت')
    # partition -> shower door, door 600 => fixed 705
    ids = await pg.evaluate("WD.__t.items().map(function(i){return i.id})")
    await pg.evaluate(f"WD.__t.sel({ids[4]})"); await pg.evaluate("setShape('showerGlassDoor')")
    await pg.fill('#shDoor', '600'); await pg.locator('#shDoor').blur(); await pg.wait_for_timeout(200)
    it = await pg.evaluate(ITEMS); check(it[4]['w'] == 600 and it[4]['L'] + it[4]['R'] == 705, 'الفاصل صار شاور: باب 600 وثابت 705')
    # pergola edits
    await pg.evaluate(f"WD.__t.sel({ids[7]})"); await pg.click('#pgMountBtns [data-v="wall"]'); await pg.fill('#inPgL', '6500'); await pg.locator('#inPgL').blur(); await pg.wait_for_timeout(200)
    for k in range(2): await reopen(pg)
    it = await pg.evaluate(ITEMS); rows = await pg.evaluate(ROWS)
    check(it[4]['w'] == 600 and it[4]['L'] + it[4]['R'] == 705, 'الشاور ثابت بعد حفظ/فتح مرتين')
    check(it[7]['t'] == 'pergola' and it[7]['mount'] == 'wall' and it[7]['w'] == 6500, 'البيرغولا محفوظة بعد إعادة الفتح')
    check(rows[4] == '1305x2200' and rows[7] == '6500x5000' and rows[0] == rows0[0], 'مقاسات الجدول صح')
    # handrail follows table after design
    await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(800)
    await pg.evaluate("(function(){var trs=Array.from(document.querySelectorAll('#qty-rows tr')).filter(function(t){return (t.querySelector('.item-input')||{}).value}); var w=trs[1].querySelector('.w-input'); w.value='6000'; w.dispatchEvent(new Event('input',{bubbles:true})); w.dispatchEvent(new Event('change',{bubbles:true}));})()")
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1000)
    it = await pg.evaluate(ITEMS); check(it[1]['w'] == 6000 and (it[1]['seg'] == 6000 or it[1]['tot'] == 6000), 'الهاندريل لحق الطول الجديد من الجدول')
    # print / 3D / mfg
    await pg.evaluate("preparePrint()"); await pg.wait_for_timeout(1200)
    check(await pg.evaluate("(window.__printed||0)>0"), 'الطباعة اشتغلت')
    e3 = await pg.evaluate("(function(){try{open3DPreview(); close3DPreview(); openMfgSizesOverlay(); return ''}catch(e){return e.message}})()")
    check(e3 == '', 'الثري دي ومقاسات التصنيع بدون أخطاء')
    check(not errs, 'ما في أخطاء جافاسكربت ' + (str(errs[:2]) if errs else ''))
    await ctx.close()

async def t_old_misguessed(p, b, port):
    print('• تصميم قديم: هاندريل انعمل شباك بالغلط')
    ctx = await new_ctx(p, b); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[4000, 1100, 'Handrail (Hidden Glass)'], [5200, 1100, 'Glass Handrail for Balcony']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    await pg.evaluate("(function(){ var its=WD.__t.items(); its[0].shapeType='window'; its[0].layout={id:'nx1',kind:'leaf',type:'plain'}; its[1].shapeType='window'; its[1].layout={id:'nx2',kind:'split',direction:'row',children:[{frac:50,node:{id:'nx3',kind:'leaf',type:'plain'}},{frac:50,node:{id:'nx4',kind:'leaf',type:'plain'}}]}; })()")
    await reopen(pg)
    it = await pg.evaluate(ITEMS)
    check(it[0]['t'] == 'handrail' and it[0]['seg'] == 4000, 'الشباك الفاضي رجع هاندريل')
    check(it[1]['t'] == 'window' and it[1]['lay'] == 'split', 'الشباك يلي فيه تقسيمات ما انلمس')
    check(not errs, 'ما في أخطاء جافاسكربت')
    await ctx.close()

THREE_STUB = """(function(){ if(window.THREE) return; var made={mesh:0,line:0};
function O(){ this.position={x:0,y:0,z:0,set:function(x,y,z){this.x=x;this.y=y;this.z=z;},copy:function(p){this.x=p.x;this.y=p.y;this.z=p.z;}}; this.rotation={x:0,y:0,z:0}; this.children=[]; }
O.prototype.add=function(c){ this.children.push(c); }; O.prototype.traverse=function(f){ f(this); this.children.forEach(function(c){ c.traverse? c.traverse(f): f(c); }); };
function G(){ this.dispose=function(){}; } function Mt(){ this.dispose=function(){}; }
function Mesh(g,m){ O.call(this); this.geometry=g; this.material=m; made.mesh++; } Mesh.prototype=Object.create(O.prototype);
function LS(g,m){ O.call(this); this.geometry=g; this.material=m; made.line++; } LS.prototype=Object.create(O.prototype);
function Scene(){ O.call(this); } Scene.prototype=Object.create(O.prototype);
function Group(){ O.call(this); } Group.prototype=Object.create(O.prototype);
function Light(){ O.call(this); } Light.prototype=Object.create(O.prototype);
function Cam(){ O.call(this); this.lookAt=function(){}; this.updateProjectionMatrix=function(){}; } Cam.prototype=Object.create(O.prototype);
function R(){ this.domElement=document.createElement('canvas'); this.setPixelRatio=function(){}; this.setSize=function(){}; this.render=function(){ window.__hrRendered=(window.__hrRendered||0)+1; }; this.dispose=function(){}; }
function OC(){ this.target={set:function(){}}; this.update=function(){}; this.dispose=function(){}; }
window.THREE={ Scene:Scene, Group:Group, Mesh:Mesh, LineSegments:LS, BoxGeometry:G, CylinderGeometry:G, PlaneGeometry:G, EdgesGeometry:G, MeshStandardMaterial:Mt, LineBasicMaterial:Mt,
  HemisphereLight:Light, DirectionalLight:Light, AmbientLight:Light, PerspectiveCamera:Cam, WebGLRenderer:R, OrbitControls:OC, Color:function(){}, DoubleSide:2, __made:made }; })();"""

async def t_handrail_plan(p, b, port):
    """📐 مسقط الهاندريل بأضلاع وزوايا + طباعة + ثري دي."""
    print('• مسقط الهاندريل والثري دي')
    ctx = await new_ctx(p, b); await ctx.add_init_script(THREE_STUB)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[7230, 1100, 'Glass Handrail for Balcony']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    iid = await pg.evaluate("WD.__t.items()[0].id"); await pg.evaluate(f"WD.__t.sel({iid})"); await pg.wait_for_timeout(300)
    check(await pg.evaluate("getComputedStyle(document.getElementById('hrPlanStartWrap')).display") != 'none', 'زر المسقط ظاهر للهاندريل المسطح')
    await pg.click('#btnHrPlanStart'); await pg.wait_for_timeout(400)
    segs = await pg.evaluate("WD.__t.items()[0].hrSegments.map(function(s){return s.id})")
    # سكتش حمدي: 604 سم (5 ألواح) وبعدين بيلف يمين 119 سم
    await pg.evaluate(f"onHrSegField({iid},'{segs[0]}','totalLength',6040); onHrSegField({iid},'{segs[0]}','panelCount',5); onHrSegField({iid},'{segs[1]}','totalLength',1190); onHrSegField({iid},'{segs[1]}','panelCount',1)")
    await pg.wait_for_timeout(300)
    g = await pg.evaluate("(function(){var it=WD.__t.items()[0]; var g=hrPlanGeometry(it); return {n:g.sides.length,total:g.total,end:[Math.round(g.sides[1].x1),Math.round(g.sides[1].y1)],w:it.width}})()")
    check(g['n'] == 2 and g['total'] == 7230 and g['end'] == [6040, -1190], 'ضلعين: 6040 وبعدين يمين 1190 ' + str(g))
    check(g['w'] == 7230, 'طول البند = مجموع الأضلاع (متل حساب العرض) ' + str(g['w']))
    card = await pg.evaluate(f"(function(){{var c=document.querySelector('#card-{iid} .hr-plan-svg'); return c? {{t:c.textContent, lines:c.querySelectorAll('line').length}} : null}})()")
    check(card and '6040' in card['t'] and '1190' in card['t'] and '7230' in card['t'] and card['lines'] >= 6, 'المسقط مرسوم فوق الواجهة بالأطوال ' + str(card and card['t'][:80]))
    vis = await pg.evaluate(f"(function(){{var c=document.querySelector('#card-{iid} .card-canvas'); var pl=c.querySelector('.hr-plan-svg').getBoundingClientRect(); var el=c.querySelector('svg:not(.hr-plan-svg)').getBoundingClientRect(); return [Math.round(pl.width),Math.round(pl.height),Math.round(el.width),Math.round(el.height),Math.round(el.top-pl.bottom)]}})()")
    check(vis[0] > 150 and vis[2] > 150 and vis[3] > 40 and vis[4] >= 0, 'المسقط والواجهة سوا بنفس المربع (الواجهة تحت المسقط وظاهرة) ' + str(vis))
    check(await pg.evaluate("!!document.querySelector('#hrPlanPreview svg') && document.getElementById('hrPlanTotal').textContent.indexOf('7230')>=0"), 'معاينة المسقط بلوحة التعديل')
    # ضلع تالت بيلف يسار، وزاوية 45 على التاني
    await pg.click('#btnHrAddLanding'); await pg.wait_for_timeout(300)
    segs = await pg.evaluate("WD.__t.items()[0].hrSegments.map(function(s){return s.id})")
    check(len(segs) == 3 and await pg.evaluate("WD.__t.items()[0].hrSegments[1].turnDeg") == -90, 'ضلع جديد بيلف يمين افتراضيًا')
    await pg.click('.hr-turn-row >> nth=1 >> text=يسار'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("WD.__t.items()[0].hrSegments[1].turnDeg") == 90, 'زر يسار')
    await pg.evaluate(f"onHrSegTurn({iid},'{segs[1]}',45)"); await pg.wait_for_timeout(200)
    check('135°' in await pg.evaluate(f"document.querySelector('#card-{iid} .hr-plan-svg').textContent"), 'الزاوية الغير قائمة مكتوبة (135°)')
    await pg.evaluate(f"onHrSegTurn({iid},'{segs[1]}',-90)")
    # حفظ وإعادة فتح
    await reopen(pg)
    st = await pg.evaluate("(function(){var it=WD.__t.items()[0]; return {plan:!!it.hrPlan, turns:it.hrSegments.map(function(s){return s.turnDeg||0}), n:it.hrSegments.length}})()")
    check(st['plan'] and st['n'] == 3 and st['turns'][:2] == [-90, -90], 'المسقط والزوايا محفوظين بعد إعادة الفتح ' + str(st))
    await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(800)
    rows = await pg.evaluate(ROWS); check(rows[0] == '8430x1100', 'جدول العرض = مجموع الأضلاع ' + str(rows))
    # الطباعة: المسقط بصفحة الهاندريل
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1000)
    await pg.evaluate("preparePrint()"); await pg.wait_for_timeout(1200)
    check(await pg.evaluate("!!document.querySelector('.print-item-canvas .hr-plan-svg')"), 'المسقط بالطباعة')
    try:
        await pg.locator('.print-item:has(.hr-plan-svg)').first.screenshot(path=os.path.join(tempfile.gettempdir(), 'hr-plan-print.png'))
    except Exception as e:
        print('   (print shot)', str(e)[:80])
    # ثري دي
    await pg.evaluate(f"WD.__t.sel({iid})"); await pg.click('#btnHr3D'); await pg.wait_for_timeout(600)
    d3 = await pg.evaluate("window.__getHr3DDebugState__()")
    check(d3['open'] and d3['stats']['panels'] == 7 and d3['stats']['sides'] == 3 and d3['stats']['totalMm'] == 8430, 'ثري دي: 3 أضلاع، 7 ألواح ' + str(d3))
    check(await pg.evaluate("(window.__hrRendered||0) > 0 && getComputedStyle(document.getElementById('hr3DOverlay')).display == 'block'"), 'المشهد عم ينرسم')
    await pg.evaluate("closeHandrail3D()")
    check(await pg.evaluate("getComputedStyle(document.getElementById('hr3DOverlay')).display") == 'none', 'سكّر الثري دي')
    try:
        await pg.locator(f'#card-{iid}').screenshot(path=os.path.join(tempfile.gettempdir(), 'hr-plan-card.png'))
        await pg.locator('#hrPlanTools').screenshot(path=os.path.join(tempfile.gettempdir(), 'hr-plan-tools.png'))
        await pg.locator('#hrSegmentsList').screenshot(path=os.path.join(tempfile.gettempdir(), 'hr-plan-segs.png'))
    except Exception:
        pass
    # بدون مسقط: الأضلاع على خط واحد (رجوع)
    await pg.evaluate(f"WD.__t.sel({iid})"); await pg.evaluate("disableHandrailPlan()"); await pg.wait_for_timeout(300)
    check(not await pg.evaluate(f"!!document.querySelector('#card-{iid} .hr-plan-svg')"), 'إلغاء المسقط بيرجع الواجهة لحالها')
    check(not errs, 'ما في أخطاء جافاسكربت ' + str(errs[:2]))
    await ctx.close()

async def t_handrail_draw(p, b, port, mobile):
    """✏️ محرر المسقط: أرقام وأسهم، رسم بالإصبع، صورة الدفتر."""
    print('• محرر مسقط الهاندريل ' + ('(موبايل)' if mobile else '(كمبيوتر)'))
    ctx = await new_ctx(p, b, mobile); await ctx.add_init_script(THREE_STUB)
    sent = []
    async def srv(route):
        u = route.request.url
        if '/ai/read-sketch' in u:
            sent.append(json.loads(route.request.post_data or '{}'))
            return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'runs': [{'title': 'بلكونة صالة', 'sides': [{'len': 6040, 'dir': 0}, {'len': 1190, 'dir': -90}]}, {'title': '', 'sides': [{'len': 850, 'dir': 0}, {'len': 5300, 'dir': -90}]}], 'notes': 'فلقة الرخام 17 سم'}))
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else {}
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[7230, 1100, 'Glass Handrail for Balcony']])
    await pg.evaluate("try{ setMode('%s') }catch(e){}" % ('mobile' if mobile else 'desktop'))
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    iid = await pg.evaluate("WD.__t.items()[0].id"); await pg.evaluate(f"WD.__t.sel({iid})"); await pg.wait_for_timeout(300)
    await pg.evaluate("openHandrailPlanEditor()"); await pg.wait_for_timeout(300)
    check(await pg.evaluate("getComputedStyle(document.getElementById('hpeOverlay')).display") == 'flex', 'المحرر انفتح')
    # (1) أرقام وأسهم متل الدفتر: 604 → ، 119 ↓
    for k in '604': await pg.click(f'#hpeKeys .pad button:text-is("{k}")')
    check('6040' in await pg.evaluate("document.getElementById('hpeBufMm').textContent"), 'الكتابة بالسانتي = 6040 مم')
    await pg.click('#hpeKeys .pad button:text-is("→")')
    for k in '119': await pg.click(f'#hpeKeys .pad button:text-is("{k}")')
    await pg.click('#hpeKeys .pad button:text-is("↓")')
    sd = await pg.evaluate("hpe.sides.map(function(s){return [s.dir,s.len,s.n]})")
    check(sd == [[0, 6040, 6], [-90, 1190, 1]], 'ضلعين بكبستين لكل واحد ' + str(sd))
    check('7230' in (await pg.evaluate("document.getElementById('hpeInfo').textContent")).replace('723', '7230', 0) or '723' in await pg.evaluate("document.getElementById('hpeInfo').textContent"), 'المجموع فوق الرسمة')
    # تعديل ضلع بالكبس عليه
    box = await pg.evaluate("(function(){var l=document.querySelector('#hpeSvg line[data-side=\"0\"]'); var r=l.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]})()")
    await pg.mouse.click(box[0], box[1]); await pg.wait_for_timeout(200)
    check(await pg.evaluate("hpe.sel") == 0 and await pg.evaluate("getComputedStyle(document.getElementById('hpeEdit')).display") == 'flex', 'كبسة على خط بتفتح تعديله')
    await pg.fill('#hpeEdN', '5'); await pg.locator('#hpeEdN').dispatch_event('change'); await pg.wait_for_timeout(100)
    check(await pg.evaluate("hpe.sides[0].n") == 5, 'عدد الألواح تعدّل')
    await pg.click('#hpeKeys .pad button:text-is("↶")') if False else None
    dbg = await pg.evaluate("hpe.undo.map(function(u){return JSON.parse(u).map(function(s){return s.n}).join(',')})")
    await pg.evaluate("hpeUndo()"); check(await pg.evaluate("hpe.sides[0].n") == 6, 'تراجع ' + str(dbg)); await pg.evaluate("hpeRedo()")
    # تحريك الرسمة بإصبع واحد (وضع الأرقام) + قرصة إصبعين (تكبير) + ملاءمة
    v0 = await pg.evaluate("[hpe.view.ox, hpe.view.oy, hpe.view.s]")
    st0 = await pg.evaluate("(function(){var r=document.getElementById('hpeStage').getBoundingClientRect(); return [r.left,r.top,r.width,r.height]})()")
    await pg.mouse.move(st0[0] + st0[2]*0.3, st0[1] + st0[3]*0.85); await pg.mouse.down()
    for i in range(1, 11): await pg.mouse.move(st0[0] + st0[2]*0.3 + i*8, st0[1] + st0[3]*0.85 - i*4)
    await pg.mouse.up(); await pg.wait_for_timeout(100)
    v1 = await pg.evaluate("[hpe.view.ox, hpe.view.oy, hpe.view.s, hpe.sides.length, hpe.sel]")
    check(abs(v1[0] - v0[0] - 80) < 2 and abs(v1[1] - v0[1] + 40) < 2 and v1[3] == 2 and v1[4] == -1, 'إصبع واحد بيحرّك الرسمة (وما بيرسم ولا بيختار) ' + str([v0, v1]))
    await pg.evaluate('''(function(){ var st=document.getElementById('hpeStage'), r=st.getBoundingClientRect(), cx=r.left+r.width/2, cy=r.top+r.height/2;
      function ev(t,id,x,y){ st.dispatchEvent(new PointerEvent(t,{pointerId:id,clientX:x,clientY:y,bubbles:true,pointerType:'touch',isPrimary:id===1})); }
      ev('pointerdown',1,cx-40,cy); ev('pointerdown',2,cx+40,cy);
      for(var i=1;i<=10;i++){ ev('pointermove',1,cx-40-i*6,cy); ev('pointermove',2,cx+40+i*6,cy); }
      ev('pointerup',1,cx-100,cy); ev('pointerup',2,cx+100,cy); })()''')
    v2 = await pg.evaluate("[hpe.view.s, hpe.sides.length]")
    check(v2[0] > v1[2]*2.2 and v2[1] == 2, 'إصبعين (قرصة) بيكبّروا ' + str([v1[2], v2]))
    await pg.evaluate("hpeZoom(1/1.3)"); check(await pg.evaluate("hpe.view.s") < v2[0], 'زر التصغير')
    await pg.evaluate("hpeFit()"); check(abs(await pg.evaluate("hpe.view.s") - v0[2]) < 1e-6, 'زر الملاءمة بيرجّع الرسمة كلها')
    # (2) الإصبع: خط تقريبي معوّج لتحت ← بيصير ضلع لتحت بزاوية 90
    await pg.click('#hpeTabDraw'); await pg.wait_for_timeout(200)
    st = await pg.evaluate("(function(){var r=document.getElementById('hpeStage').getBoundingClientRect(); return [r.left,r.top,r.width,r.height]})()")
    x0, y0 = st[0] + st[2]*0.5, st[1] + st[3]*0.3
    await pg.mouse.move(x0, y0); await pg.mouse.down()
    for i in range(1, 21): await pg.mouse.move(x0 + (3 if i % 2 else -2), y0 + i*6)
    for i in range(1, 21): await pg.mouse.move(x0 - i*7, y0 + 120 + (2 if i % 2 else -3))
    await pg.mouse.up(); await pg.wait_for_timeout(200)
    sd = await pg.evaluate("hpe.sides.map(function(s){return s.dir})")
    check(sd[:2] == [0, -90] and len(sd) == 4 and sd[2] == -90 and sd[3] == 180, 'الرسم بالإصبع: تحت وبعدين يسار (زوايا 90°) ' + str(sd))
    check(await pg.evaluate("hpe.sel") >= 2, 'بعد الرسم: الخط الجديد محدد لتكتب طوله')
    await pg.evaluate("hpe.sel=2"); await pg.evaluate("hpeRender()")
    await pg.fill('#hpeEdLen', '50'); await pg.locator('#hpeEdLen').dispatch_event('change'); await pg.wait_for_timeout(100)
    check(await pg.evaluate("hpe.sides[1].len + hpe.sides[2].len") == 1690, 'كتبت الطول الحقيقي للخط المرسوم (50 سم بيتجمع مع 119 لأنو نفس الاتجاه؟)') if False else check(await pg.evaluate("hpe.sides[2].len") == 500, 'كتبت الطول الحقيقي للخط المرسوم')
    # (4) صورة الدفتر
    await pg.locator('#hpeFile').set_input_files(os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'sufiya-logo.png')); await pg.wait_for_timeout(1500)
    check(sent and sent[0].get('image', '').startswith('data:image/jpeg;base64,'), 'الصورة انبعتت للسيرفر مصغّرة')
    check('بلكونة صالة' in await pg.evaluate("document.getElementById('hpeAi').textContent"), 'بيعرض الرسمات يلي لقاها')
    await pg.click('#hpeAi button:text("استعملها") >> nth=0'); await pg.wait_for_timeout(200)
    sd = await pg.evaluate("hpe.sides.map(function(s){return [s.dir,s.len]})")
    check(sd == [[0, 6040], [-90, 1190]], 'رسمة الدفتر انرسمت ' + str(sd))
    # تم → البند
    await pg.click('#hpeOverlay .tb.ok'); await pg.wait_for_timeout(300)
    it = await pg.evaluate("(function(){var it=WD.__t.items()[0]; return {plan:!!it.hrPlan, segs:it.hrSegments.map(function(s){return [s.totalLength,s.panelCount,s.turnDeg==null?null:s.turnDeg]}), w:it.width}})()")
    check(it['plan'] and it['segs'] == [[6040, 6, -90], [1190, 1, None]] and it['w'] == 7230, 'تم: الرسمة صارت أضلاع البند ' + str(it))
    check(await pg.evaluate(f"!!document.querySelector('#card-{iid} .hr-plan-svg')"), 'المسقط ظاهر بالبطاقة')
    vis = await pg.evaluate(f"(function(){{var c=document.querySelector('#card-{iid} .card-canvas'); var el=c.querySelector('svg:not(.hr-plan-svg)').getBoundingClientRect(); var pl=c.querySelector('.hr-plan-svg').getBoundingClientRect(); return [Math.round(el.width),Math.round(el.height),Math.round(pl.width)]}})()")
    vw = await pg.evaluate(f"(function(){{var c=document.querySelector('#card-{iid}').getBoundingClientRect(); var q=document.querySelectorAll('#card-{iid} .card-canvas svg'); var m=0; q.forEach(function(x){{m=Math.max(m,x.getBoundingClientRect().right)}}); return [Math.round(c.right), Math.round(m), document.documentElement.clientWidth]}})()")
    check(vis[0] > 120 and vis[1] > 30 and vis[2] > 120 and vw[1] <= vw[0] + 1, 'الواجهة (السكتش) ظاهرة تحت المسقط وما في شي طالع برّا المربع ' + str([vis, vw]))
    if mobile:
        await pg.evaluate("try{ mzEdClose && mzEdClose() }catch(e){}")
        await pg.locator(f'#card-{iid}').screenshot(path=os.path.join(tempfile.gettempdir(), 'hr-card-mobile.png'))
    # فتح من جديد: بيحمّل الرسمة
    await pg.evaluate("openHandrailPlanEditor()"); await pg.wait_for_timeout(200)
    check(await pg.evaluate("hpe.sides.map(function(s){return s.dir})") == [0, -90], 'إعادة الفتح بتحمّل الرسمة')
    if mobile:
        ov = await pg.evaluate("(function(){var o=document.getElementById('hpeOverlay'); return [o.scrollWidth, document.documentElement.clientWidth, document.getElementById('hpeStage').getBoundingClientRect().height]})()")
        check(ov[0] <= ov[1] + 1 and ov[2] >= 120, 'موبايل: المحرر ضمن الشاشة ومساحة الرسم كافية ' + str(ov))
        await pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'hpe-mobile.png'))
    await pg.evaluate("hpeClose(false)")
    check(not errs, 'ما في أخطاء جافاسكربت ' + str(errs[:2]))
    await ctx.close()

async def t_acct_ai(p, b, port):
    """💬 المساعد المحاسبي: مسودات بس، الاعتماد بيمر بنفس الحفظ، الملفات، الأخطاء، الحد الشهري."""
    print('• المساعد المحاسبي')
    import subprocess
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_acct.js'), sdir], stdout=subprocess.PIPE, text=True)
    aport = int(proc.stdout.readline().split()[1])
    try:
        ctx = await b.new_context(viewport={"width": 1300, "height": 900})
        await ctx.add_init_script("try{ if(!localStorage.getItem('merzona-device-token')) localStorage.setItem('merzona-device-token','OWNERDEV'); localStorage.setItem('merzona-acct-book','syria'); }catch(e){}")
        async def fwd(route):
            u = route.request.url
            if '/access/status' in u: return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'status': 'approved', 'isOwner': True}))
            if '/acct/' in u or '/ai/' in u:
                resp = await route.fetch(url=u.replace(SRV, f'http://127.0.0.1:{aport}'))
                return await route.fulfill(response=resp)
            await route.fulfill(status=200, content_type='application/json', body='{}')
        await ctx.route(SRV + '/**', fwd)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/accounting.html'); await pg.wait_for_timeout(2500)
        check(await pg.evaluate("!!(__acctT.S().book && __acctT.S().book.base==='USD')"), 'دفتر سوريا انفتح')
        await pg.click('#aiBtn'); await pg.wait_for_timeout(500)
        check(await pg.evaluate("getComputedStyle(document.getElementById('aiPanel')).display") == 'flex', 'التشات انفتح')
        # 0) ما في مفتاح: الرسالة الأولى بتفتح خانة اللصق، مفتاح غلط بينرفض بسبب واضح، والصح بينحفظ (والمفتاح بيلزق مع فراغات)
        await pg.fill('#aiIn', 'مرحبا'); await pg.click('#aiSend'); await pg.wait_for_timeout(1200)
        check(await pg.evaluate("!!document.getElementById('aiKeyIn')"), 'بدون مفتاح: خانة لصق المفتاح انفتحت لحالها')
        await pg.fill('#aiKeyIn', 'sk-ant-api03-' + 'b'*40); await pg.click('#aiKeySave'); await pg.wait_for_timeout(800)
        check('رفض' in await pg.evaluate("document.getElementById('aiKeyErr').textContent"), 'مفتاح مرفوض: السبب واضح')
        await pg.fill('#aiKeyIn', ' sk-ant-api03-good' + 'g'*40 + ' '); await pg.click('#aiKeySave'); await pg.wait_for_timeout(1200)
        check('من حد 2$' in await pg.evaluate("document.getElementById('aiUse').innerText"), 'المفتاح الصح انحفظ والمساعد صار جاهز')
        await pg.evaluate("localStorage.removeItem('mz-acct-ai-syria')"); await pg.click('#aiClear'); await pg.wait_for_timeout(300)
        # 1) كلام عادي → سند قبض + زبون جديد
        await pg.fill('#aiIn', 'قبضت من أبو أحمد 2000$ كاش دفعة على فيلا الخويش'); await pg.click('#aiSend'); await pg.wait_for_timeout(1500)
        card = await pg.evaluate("(function(){var c=document.querySelectorAll('#aiLog .act'); var a=c[c.length-1]; return a? {t:a.innerText, dis:a.querySelector('[data-ok]').disabled} : null})()")
        check(card and 'سند قبض' in card['t'] and 'زبون جديد' in card['t'] and 'أبو أحمد' in card['t'] and not card['dis'], 'مسودة سند قبض مع زبون جديد ' + str(card and card['t'][:120]))
        check(await pg.evaluate("Object.keys(__acctT.S().book.docs).length") == 0, 'ما انسجّل شي قبل الموافقة')
        await pg.click('#aiLog .act [data-ok]'); await pg.wait_for_timeout(2000)
        d = await pg.evaluate("(function(){var ds=Object.values(__acctT.S().book.docs); var r=ds.find(function(x){return x.type==='receipt'}); if(!r) return null; return {amt:r.amount, party:__acctT.S().book.parties[r.partyId]&&__acctT.S().book.parties[r.partyId].name, acct:r.acct, notes:r.notes, project:r.project, no:r.no}})()")
        check(d and d['amt'] == 2000 and d['party'] == 'أبو أحمد' and d['acct'] == '1000' and 'من المساعد' in d['notes'] and d['project'] == 'فيلا الخويش', 'اعتمد: الزبون انضاف والسند انحفظ ' + str(d))
        check('انعتمدت' in await pg.evaluate("document.querySelector('#aiLog .act').innerText"), 'البطاقة صارت معتمدة')
        # 2) صورة فاتورة → فاتورة مورد، بالتعديل
        await pg.locator('#aiFile').set_input_files(os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'sufiya-logo.png')); await pg.wait_for_timeout(600)
        check('sufiya-logo.png' in await pg.evaluate("document.getElementById('aiFiles').innerText"), 'الملف مرفق')
        await pg.click('#aiSend'); await pg.wait_for_timeout(1500)
        asked = json.loads(await pg.evaluate(f"fetch('http://127.0.0.1:{aport}/__asked').then(function(r){{return r.text()}})"))
        check(asked['last']['model'] == 'claude-haiku-5-5' and 'image' in asked['last']['types'], 'الصورة انبعتت للنموذج الرخيص ' + str(asked['last']))
        await pg.click('#aiLog .act:last-of-type [data-ed]'); await pg.wait_for_timeout(1200)
        mf = await pg.evaluate("(function(){var m=document.querySelector('.modal-bg'); return m? {ref:(m.querySelector('#fRef')||{}).value, txt:m.innerText.slice(0,300)} : null})()")
        check(mf and mf['ref'] == '125', 'عدّل: النموذج العادي انفتح معبّى ' + str(mf and mf['ref']))
        await pg.click('.modal-bg .mf .pri'); await pg.wait_for_timeout(2500)
        bill = await pg.evaluate("(function(){var r=Object.values(__acctT.S().book.docs).find(function(x){return x.type==='bill'}); return r? {party:__acctT.S().book.parties[r.partyId].name, total:AcctCore.docTotals(r,__acctT.S().book).total, ref:r.ref} : null})()")
        check(bill and bill['party'] == 'مؤسسة النور' and bill['total'] == 1190 and bill['ref'] == '125', 'فاتورة المورد انحفظت من النموذج ' + str(bill))
        await pg.wait_for_timeout(1000)
        check('انعتمدت' in await pg.evaluate("Array.from(document.querySelectorAll('#aiLog .act')).pop().innerText"), 'بطاقة الفاتورة صارت معتمدة بعد الحفظ من النموذج')
        # 3) مسودة ناقصة → زر الاعتماد موقّف وبيقول شو ناقص
        await pg.fill('#aiIn', 'سجّل مازوت 50 غلط'); await pg.click('#aiSend'); await pg.wait_for_timeout(1500)
        c3 = await pg.evaluate("(function(){var a=Array.from(document.querySelectorAll('#aiLog .act')).pop(); return {t:a.innerText, dis:a.querySelector('[data-ok]').disabled}})()")
        check(c3['dis'] and 'حساب الدفع' in c3['t'], 'مسودة ناقصة ما بتنعتمد وبتقول شو ناقص ' + c3['t'][:160])
        await pg.click('#aiLog .act:last-of-type [data-no]'); await pg.wait_for_timeout(200)
        check('انلغت' in await pg.evaluate("Array.from(document.querySelectorAll('#aiLog .act')).pop().innerText"), 'إلغاء المسودة')
        u = await pg.evaluate("document.getElementById('aiUse').innerText")
        check('من حد 2$' in u and 'رسالة' in u, 'الكلفة والحد ظاهرين ' + u)
        # 4) بعد التحديث المحادثة باقية
        await pg.reload(); await pg.wait_for_timeout(2500); await pg.click('#aiBtn'); await pg.wait_for_timeout(500)
        check(await pg.evaluate("document.querySelectorAll('#aiLog .act').length") == 3, 'المحادثة محفوظة على الجهاز')
        await pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'acct-ai.png'))
        check(not errs, 'ما في أخطاء جافاسكربت ' + str(errs[:2]))
        await ctx.close()
    finally:
        proc.kill()

async def t_edit_panel(p, b, port, mobile):
    print('• لوحة التعديل ' + ('(موبايل)' if mobile else '(كمبيوتر)'))
    ctx = await new_ctx(p, b, mobile); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[1200, 1400, 'Hinged Window'], [4000, 1100, 'Glass Handrail for Balcony'], [1500, 1500, 'Hinged Window']])
    await pg.evaluate("try{ setMode('%s') }catch(e){}" % ('mobile' if mobile else 'desktop'))
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    ids = await pg.evaluate("WD.__t.items().map(function(i){return i.id})")
    await pg.click(f'#card-{ids[1]} .mz-edit-btn'); await pg.wait_for_timeout(500)
    st = await pg.evaluate("({sel:WD.__t.selId(), open:document.getElementById('wdOverlay').classList.contains('mz-sheet-open'), hr:getComputedStyle(document.getElementById('handrailBlock')).display})")
    check(st['sel'] == ids[1] and st['hr'] != 'none', 'زر تعديل بيختار البند وبيفرجي حقوله')
    check(st['open'] == mobile, 'اللوحة من تحت ' + ('مفتوحة' if mobile else 'مش مستعملة') )
    await pg.click('#mzEdBar .mz-ed-nav >> nth=1'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("WD.__t.selId()") == ids[2], 'زر البند الجاي')
    await pg.fill('#inWidth', '1600'); await pg.locator('#inWidth').blur(); await pg.wait_for_timeout(300)
    if mobile:
        await pg.click('#mzEdBar .mz-ed-close'); await pg.wait_for_timeout(300)
        check(not await pg.evaluate("document.getElementById('wdOverlay').classList.contains('mz-sheet-open')"), 'زر الإغلاق')
    await pg.evaluate("wdSaveAndClose()"); await pg.wait_for_timeout(800)
    rows = await pg.evaluate(ROWS); check(rows == ['1200x1400', '4000x1100', '1600x1500'], 'التعديل وصل للجدول')
    check(not errs, 'ما في أخطاء جافاسكربت')
    await ctx.close()

async def t_catalog(p, b, port):
    print('• الكتالوج: زر الرجوع وزر رجوع الموبايل')
    ctx = await new_ctx(p, b, True); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    await pg.goto(f'http://127.0.0.1:{port}/catalog.html?b=sy'); await pg.wait_for_timeout(1500)
    check(await pg.evaluate("document.getElementById('backBtn').hidden"), 'ما في زر رجوع بالصفحة الرئيسية')
    await pg.click('.cat >> nth=0'); await pg.wait_for_timeout(1500)
    check(not await pg.evaluate("document.getElementById('backBtn').hidden"), 'زر الأقسام ظاهر جوا القسم')
    await pg.click('[data-open="1"]'); await pg.wait_for_timeout(500); await pg.go_back(); await pg.wait_for_timeout(500)
    check(not await pg.evaluate("document.getElementById('lb').classList.contains('open')") and 'c=c1' in pg.url, 'رجوع الموبايل بيسكّر الصورة وبيضل بالقسم')
    await pg.click('#backBtn'); await pg.wait_for_timeout(1500)
    check('c=' not in pg.url and 'b=sy' in pg.url, 'زر الأقسام بيرجع لكل الأقسام مع نفس الفرع')
    check(not errs, 'ما في أخطاء جافاسكربت')
    await ctx.close()

async def t_drive_proxy(p, b, port):
    print('• درايف عن طريق السيرفر (المرحلة 2)')
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    if not os.path.isfile(os.path.join(sdir, 'drive-proxy.js')):
        print('  SKIP ما لقيت مستودع السيرفر (MZ_SERVER_DIR)'); return
    import subprocess, urllib.request
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_drive.js'), sdir], stdout=subprocess.PIPE, text=True)
    try:
        fport = int(proc.stdout.readline().split()[1]); LOCAL = 'http://127.0.0.1:%d' % fport
        state = lambda: json.loads(urllib.request.urlopen(LOCAL + '/__state').read())
        ctx = await new_ctx(p, b)
        direct, tokreq = [], []
        async def to_local(route):
            u = route.request.url
            resp = await route.fetch(url=LOCAL + u[len(SRV):])
            await route.fulfill(response=resp)
        async def gapi(route):
            direct.append(route.request.url); await route.fulfill(status=401, body='{}')
        await ctx.route(SRV + '/gdrive/**', to_local)
        await ctx.route(SRV + '/team/**', to_local)
        await ctx.route(SRV + '/gdrive-upload-session', to_local)
        await ctx.route('https://www.googleapis.com/**', gapi)
        ctx.on('request', lambda r: tokreq.append(r.url) if '/drive-token' in r.url else None)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
        UAE = '13q5WtejXrydWEeIEZ7pZoon6ocyVuX1D'
        r = await pg.evaluate("""async (UAE) => {
          const t = await getGoogleAccessToken(); const out = { t };
          out.year = await findYearFolderIfExists('2026', t, UAE);
          const y = await findOrCreateDriveFolder('2026', UAE, t); out.sameYear = (y === out.year);
          const ref = await findOrCreateDriveFolder('M-Q-260099', y, t); out.ref = ref;
          out.refAgain = (await findOrCreateDriveFolder('M-Q-260099', y, t)) === ref;
          const obj = { fields: { 'm-client': 'زبون تجربة', 'm-ref': 'M-Q-260099' }, n: [1,2,3] };
          const a = await uploadOrUpdateFileInDriveFolder('M-Q-260099-data.json', 'application/json', new Blob([JSON.stringify(obj)], {type:'application/json'}), ref, t);
          obj.fields['m-client'] = 'زبون معدّل';
          const b2 = await uploadOrUpdateFileInDriveFolder('M-Q-260099-data.json', 'application/json', new Blob([JSON.stringify(obj)], {type:'application/json'}), ref, t);
          out.sameFile = a && b2 && a.id === b2.id;
          const bytes = new Uint8Array(300000); for (let i = 0; i < bytes.length; i++) bytes[i] = (i * 7 + 3) & 255;
          const pdf = await uploadOrUpdateFileInDriveFolder('M-Q-260099.pdf', 'application/pdf', new Blob([bytes], {type:'application/pdf'}), ref, t);
          out.pdf = pdf && pdf.id;
          const pdf2 = await uploadOrUpdateFileInDriveFolder('M-Q-260099.pdf', 'application/pdf', new Blob([bytes.slice(0, 280000)], {type:'application/pdf'}), ref, t);
          out.pdfSame = pdf2 && pdf2.id === pdf.id;
          out.read = await downloadDriveJsonFile(a.id, t);
          out.kids = (await listDriveFolderChildrenSimple(ref, t)).map(f => f.name).sort();
          out.next = await computeNextReferenceSeq('M-Q-260', t, UAE);
          return out; }""", UAE)
        check(r['t'] == 'mzproxy', 'الصفحة ما بتاخد مفتاح درايف حقيقي')
        check(r['year'] and r['sameYear'], 'لقى مجلد السنة عن طريق السيرفر')
        check(r['ref'] and r['refAgain'], 'إنشاء مجلد عرض جديد وما بيتكرر')
        check(r['sameFile'] and r['read']['fields']['m-client'] == 'زبون معدّل', 'حفظ ملف البيانات وتحديثه وقراءته (عربي)')
        st = state(); f = {x['name']: x for x in st['files']}
        check(f.get('M-Q-260099.pdf', {}).get('mimeType') == 'application/pdf' and any(d['len'] == 300000 for d in st['directPuts']), 'رفع PDF بحجمه ونوعه الصحيح')
        check(any(d['len'] == 300000 and d['ctype'] == 'application/pdf' for d in st['directPuts']), 'الملف الكبير انرفع مباشرة لجوجل (مش عن طريق السيرفر)')
        check(not any('M-Q-260099.pdf' in u and 'multipart' in u for u in st['upstream']), 'محتوى الـPDF ما مرق بالسيرفر')
        check(r['pdfSame'] and f['M-Q-260099.pdf']['len'] == 280000 and any(d['len'] == 280000 for d in st['directPuts']), 'تحديث PDF موجود (رفع مباشر لنفس الملف)')
        check(r['kids'] == ['M-Q-260099-data.json', 'M-Q-260099.pdf'], 'قائمة ملفات مجلد العرض')
        check(r['next'] is not None, 'اقتراح الرقم المرجعي الجاي شغال (' + str(r['next']) + ')')
        await ctx.unroute(SRV + '/gdrive-upload-session')
        await ctx.route(SRV + '/gdrive-upload-session', lambda r: r.fulfill(status=503, body='{}'))
        r = await pg.evaluate("""async (UAE) => { const t = 'mzproxy'; const y = await findOrCreateDriveFolder('2026', UAE, t); const ref = await findOrCreateDriveFolder('M-Q-260099', y, t);
          const bytes = new Uint8Array(270000); bytes.fill(7);
          const up = await uploadOrUpdateFileInDriveFolder('fallback.pdf', 'application/pdf', new Blob([bytes], {type:'application/pdf'}), ref, t); return !!(up && up.id); }""", UAE)
        st = state(); f = {x['name']: x for x in st['files']}
        check(r and f.get('fallback.pdf', {}).get('len') == 270000, 'إذا الرفع المباشر ما زبط، بيرجع يرفع عن طريق السيرفر')
        await ctx.unroute(SRV + '/gdrive-upload-session'); await ctx.route(SRV + '/gdrive-upload-session', to_local)
        # الداشبورد
        await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3000)
        r = await pg.evaluate("""async () => {
          const t = await getDashGoogleAccessToken(false); const out = { t };
          const d = await downloadSyncData(t); out.sync = !!(d && d.merzona_contracts && d.merzona_contracts['M-Q-260001']);
          d.merzona_contracts['M-Q-260002'] = { client: 'جديد' }; await uploadSyncData(t, d);
          const d2 = await downloadSyncData(t); out.sync2 = !!d2.merzona_contracts['M-Q-260002'];
          out.folder = await findQuotationFolderId(t, 'M-Q-260001');
          out.kids = (await listDriveFolderChildren(t, out.folder)).map(f => f.name).sort();
          await deleteQuotationByRef('M-Q-260003', null);
          await uploadAutoBackupToDrive(t, { schema: 'merzona-backup-v1', note: 'نسخة' });
          const bytes = new Uint8Array(120000); for (let i = 0; i < bytes.length; i++) bytes[i] = (i * 13) & 255;
          const up = await uploadFileToDriveFolderDash('عقد-تجربة.pdf', 'application/pdf', new Blob([bytes], {type: 'application/pdf'}), out.folder, t);
          out.contract = !!(up && (up.id || up));
          await window.mzTrashOne('DRAFT_FILE_000001', 'uae', 'draft', 'مسودة تجربة');
          return out; }""")
        check(r['t'] == 'mzproxy' and r['sync'] and r['sync2'], 'الداشبورد: قراءة وكتابة ملف مزامنة الفريق')
        check(r['folder'] and 'M-Q-260001-data.json' in r['kids'], 'الداشبورد: لقى مجلد العرض وملفاته')
        st = state(); f = {x['name']: x for x in st['files']}
        check(f['M-Q-260003']['trashed'] is True, 'حذف عرض = نقل لسلة المحذوفات (مش حذف نهائي)')
        check(f.get('merzona-backup-auto.json', {}).get('text') and 'نسخة' in f['merzona-backup-auto.json']['text'], 'النسخة الاحتياطية التلقائية للداشبورد')
        check(r['contract'] and f.get('عقد-تجربة.pdf', {}).get('len') == 120000, 'رفع ملف عقد PDF')
        byid = {x['id']: x for x in st['files']}; d1 = byid['DRAFT_FILE_000001']
        check(not d1['trashed'] and byid[d1['parents'][0]]['name'].endswith('حذف يدوي') and '_manifest.json' in f, 'نقل مسودة لسلة مسودات النظام (نقل بين مجلدين)')
        await pg.evaluate("(function(){ var o = document.getElementById('catPhotosPane'); for(var e = o; e && e !== document.body; e = e.parentElement){ if(getComputedStyle(e).display === 'none') e.style.display = 'block'; } mzcShowCatalogPane('photos'); })()")
        await pg.wait_for_timeout(3000)
        home = await pg.evaluate("document.getElementById('mzc-overlay').innerText")
        check('برغولات' in home, 'كتالوجات الداشبورد: قائمة الأقسام من درايف')
        await pg.locator('#mzc-overlay').get_by_text('Showers').first.click(); await pg.wait_for_timeout(3000)
        imgs = await pg.evaluate("Array.from(document.querySelectorAll('#mzc-overlay img')).filter(function(i){ return /^blob:/.test(i.src) && i.naturalWidth > 0; }).length")
        check(imgs >= 2, 'كتالوجات الداشبورد: الصور بتنزل وبتنعرض (' + str(imgs) + ')')
        # 🗄️ المرحلة 3: بيانات الفريق عالسيرفر
        team = json.loads(urllib.request.urlopen(LOCAL + '/__team').read())
        check(team['status'] and team['status']['rev'] >= 2 and 'M-Q-260002' in team['data']['merzona_contracts'], 'بيانات الفريق انحفظت عالسيرفر (rev ' + str(team['status'] and team['status']['rev']) + ')')
        ctx2 = await new_ctx(p, b); await ctx2.route(SRV + '/gdrive/**', to_local); await ctx2.route(SRV + '/team/**', to_local); await ctx2.route('https://www.googleapis.com/**', gapi)
        pg2 = await ctx2.new_page(); pg2.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg2.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg2.wait_for_timeout(3000)
        push = """async (ref) => {
          const t = await getDashGoogleAccessToken(false);
          await driveSyncPullAndMerge(true);
          const orig = uploadSyncData; uploadSyncData = async function(){ await new Promise(r => setTimeout(r, 900)); return orig.apply(this, arguments); };
          const c = JSON.parse(localStorage.getItem('merzona_contracts') || '{}'); c[ref] = { client: 'جهاز ' + ref, paymentTables: [], createdAt: Date.now() };
          localStorage.setItem('merzona_contracts', JSON.stringify(c)); localStorage.setItem('merzona_sync_connected', '1');
          markSyncDirty('merzona_contracts', c);
          await driveSyncPushNow();
          return teamRev; }"""
        await asyncio.gather(pg.evaluate(push, 'M-Q-260010'), pg2.evaluate(push, 'M-Q-260011'))
        await pg.wait_for_timeout(6000)
        team = json.loads(urllib.request.urlopen(LOCAL + '/__team').read())
        both = all(k in team['data']['merzona_contracts'] for k in ('M-Q-260010', 'M-Q-260011'))
        check(both and 'M-Q-260002' in team['data']['merzona_contracts'], 'جهازين حفظوا بنفس اللحظة: ولا تعديل ضاع')
        await pg2.evaluate("driveSyncPullAndMerge(true)"); await pg2.wait_for_timeout(1500)
        seen = await pg2.evaluate("Object.keys(JSON.parse(localStorage.getItem('merzona_contracts')||'{}'))")
        check('M-Q-260010' in seen and 'M-Q-260011' in seen, 'الجهاز التاني بيشوف تعديل الأول بعد المزامنة')
        r = await pg2.evaluate("""async () => {
          localStorage.setItem('merzona-device-token', 'dev2'); localStorage.setItem('merzona-session-token', 's2');
          localStorage.setItem('merzona_payroll_employees', JSON.stringify({ old: { name: 'نسخة قديمة' } }));
          const d = await downloadSyncData('mzproxy');
          const out = { staffSees: !!d.merzona_payroll_employees, staffLocal: localStorage.getItem('merzona_payroll_employees'), contracts: !!d.merzona_contracts };
          localStorage.setItem('merzona-session-token', 's3');
          const d2 = await downloadSyncData('mzproxy'); out.paySees = !!(d2.merzona_payroll_employees && d2.merzona_payroll_employees.e1);
          return out; }""")
        check(not r['staffSees'] and r['staffLocal'] is None and r['contracts'], 'الموظف بدون صلاحية الرواتب ما بيوصلو شي منها، وبتنمسح من جهازو')
        check(r['paySees'], 'الموظف يلي عندو صلاحية الرواتب بيشوفها')
        await ctx2.close()
        # الأمان من جوا الصفحة نفسها
        r = await pg.evaluate("""async () => {
          const g = (u, o) => fetch('https://www.googleapis.com/drive/v3/' + u, o).then(r => r.status);
          const out = {};
          out.outside = await g('files?q=' + encodeURIComponent("'OUTSIDE_FOLDER_0001' in parents"));
          out.secret = await g('files/SECRET_FILE_00001?alt=media');
          out.inject = await g('files?q=' + encodeURIComponent("'13q5WtejXrydWEeIEZ7pZoon6ocyVuX1D' in parents or name contains 'secret'"));
          out.ownerAbout = await g('about?fields=user(emailAddress)');
          localStorage.setItem('merzona-device-token', 'dev2'); localStorage.setItem('merzona-session-token', 's2');
          out.staffList = await g('files?q=' + encodeURIComponent("'13q5WtejXrydWEeIEZ7pZoon6ocyVuX1D' in parents"));
          out.staffCat = await g('files?q=' + encodeURIComponent("'13QxtnBbXx3SuOZIu8hA90TiD7T2CiMoC' in parents"));
          const cat = await (await fetch('https://www.googleapis.com/drive/v3/files?q=' + encodeURIComponent("'13QxtnBbXx3SuOZIu8hA90TiD7T2CiMoC' in parents"))).json();
          out.staffCatTrash = await g('files/' + cat.files[0].id, { method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ trashed: true }) });
          out.staffAbout = await g('about?fields=user(emailAddress)');
          localStorage.setItem('merzona-session-token', 'bad');
          out.noLogin = await g('files?q=' + encodeURIComponent("'13q5WtejXrydWEeIEZ7pZoon6ocyVuX1D' in parents"));
          localStorage.setItem('merzona-device-token', 'dev1'); localStorage.setItem('merzona-session-token', 's1');
          return out; }""")
        check(r['outside'] == 403 and r['secret'] == 403 and r['inject'] == 400, 'ملفات درايف برّا مجلدات ميرزونا ممنوعة حتى للمالك')
        check(r['ownerAbout'] == 200 and r['staffAbout'] == 403, 'معلومات حساب درايف للمالك بس')
        check(r['staffList'] == 200 and r['staffCat'] == 200, 'الموظف بيشتغل عادي على العروض وبيشوف الكتالوج')
        check(r['staffCatTrash'] == 403, 'الموظف بدون صلاحية الكتالوج ما بيقدر يحذف صور')
        check(r['noLogin'] == 403, 'بدون تسجيل دخول مرفوض')
        # المشتريات
        await pg.goto(f'http://127.0.0.1:{port}/procurement.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.getElementById('btnDriveDesigns').click()"); await pg.wait_for_timeout(2500)
        msg = await pg.evaluate("(document.getElementById('drvMsg')||{}).textContent || ''")
        check('لقينا 1' in msg, 'المشتريات: سحب التصاميم من درايف عن طريق السيرفر (' + msg[:40] + ')')
        check(not direct, 'ولا طلب راح لجوجل مباشرة من المتصفح (' + str(len(direct)) + ')')
        check(not tokreq, 'ولا صفحة طلبت /drive-token (' + str(len(tokreq)) + ')')
        st = state()
        check(not any('SECRET_FILE' in u and 'fields=id,parents' not in u for u in st['upstream']), 'محتوى ملف برّا المجلدات ما انطلب من جوجل أبدًا (بس فحص مكانه)')
        check(not errs, 'ما في أخطاء جافاسكربت ' + '; '.join(errs[:2]))
        await ctx.close()
    finally:
        proc.kill()

async def t_share_pdf(p, b, port):
    print('• أرسل للزبون + خطوط الـPDF')
    ctx = await new_ctx(p, b)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
    r = await pg.evaluate("""() => [mzWaDigits('+971 50 000 0099'), mzWaDigits('0500000099'), mzWaDigits('0939919670'), mzWaDigits('00963939919670'), mzWaDigits('12')]""")
    check(r == ['971500000099', '971500000099', '963939919670', '963939919670', ''], 'تحويل أرقام الزبائن لواتس اب ' + str(r))
    r = await pg.evaluate("""async () => {
      const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); };
      set('m-ref', 'M-Q-260221'); set('m-client', 'Test Client'); set('m-number', '+971 50 000 0099');
      let saved = 0; runSaveToGoogleDriveInnerShared = async () => { saved++; };
      window.__mzLastPdf = { ref: 'M-Q-260221', blob: new Blob(['%PDF-1.4'], {type: 'application/pdf'}) };
      await shareQuotationToClient();
      const firstSaved = saved; document.getElementById('mzShareModal').remove();
      window.__mzLastSavedSig = mzQuoteSig(); await shareQuotationToClient();
      const skipped = (saved === firstSaved);
      runSaveToGoogleDriveInnerShared = async () => { throw new Error('test fail'); };
      window.__mzLastSavedSig = 'old'; document.getElementById('mzShareModal').remove();
      await shareQuotationToClient(); const afterFail = !!document.getElementById('mzShareModal'); document.getElementById('mzShareModal').remove();
      await shareQuotationToClient();
      const m = document.getElementById('mzShareModal');
      const bt = m ? Array.from(m.querySelectorAll('button')).map(b => b.textContent) : [];
      let opened = null; window.open = (u) => { opened = u; return null; };
      if(m) m.querySelector('button').click();
      return { saved, bt, opened, gone: !document.getElementById('mzShareModal'), skipped, afterFail }; }""")
    check(r['saved'] == 1, 'بيحفظ العرض قبل الإرسال')
    check(r['skipped'], 'إذا ما تغيّر شي من آخر حفظ، بيبعت فورًا بدون إعادة حفظ')
    check(r['afterFail'], 'إذا فشل الحفظ بيسأل وبيقدر يبعت آخر نسخة محفوظة')
    r2 = await pg.evaluate("""() => { const a = mzQuoteSig();
      document.querySelectorAll('.page textarea').forEach(t => { t.style.height = '123px'; });
      const b = mzQuoteSig(); const ta = document.querySelector('.page textarea'); const old = ta.value; ta.value = old + ' x'; const c = mzQuoteSig(); ta.value = old;
      return [a === b, a !== c, a === mzQuoteSig()]; }""")
    check(r2 == [True, True, True], 'بصمة العرض: ما بتتغيّر من ارتفاع الخانات، بتتغيّر لما يتغيّر النص ' + str(r2))
    check(r['opened'] and r['opened'].startswith('https://wa.me/971500000099?text=') and 'M-Q-260221' in __import__('urllib.parse').parse.unquote(r['opened']) and 'sign.html' in __import__('urllib.parse').parse.unquote(r['opened']), 'بيفتح محادثة الزبون نفسه مع رابط العرض')
    check(r['gone'] and any('انسخ' in x for x in r['bt']), 'نافذة الإرسال (فتح المحادثة / نسخ الرسالة)')
    r = await pg.evaluate("""() => { document.body.classList.add('pdf-capturing');
      const f1 = getComputedStyle(document.querySelector('.section-title')).fontFamily;
      const ar = document.querySelector('.section-title .ar'); const f2 = ar ? getComputedStyle(ar).fontFamily : '';
      document.body.classList.remove('pdf-capturing');
      const f3 = getComputedStyle(document.querySelector('.section-title')).fontFamily;
      return [f1, f2, f3]; }""")
    check(r[0].startswith('Georgia') and r[1].startswith('Tahoma') and 'DM Serif' in r[2], 'وقت إنشاء الـPDF بس: خطوط الجهاز (حتى ما تركب السطور فوق بعض) ' + str(r))
    r = await pg.evaluate("""async () => { document.body.classList.add('pdf-capturing'); await new Promise(r => setTimeout(r, 50));
      const t = Array.from(document.querySelectorAll('.mz-select-capture-text')).map(s => s.textContent);
      document.body.classList.remove('pdf-capturing'); await new Promise(r => setTimeout(r, 50)); return t; }""")
    check(not any('Select' in x or 'اختر' in x for x in r), 'خانة اللون الفاضية ما بتنطبع "-- Select --"')
    check(not errs, 'ما في أخطاء ' + '; '.join(errs[:2]))
    await ctx.close()

async def t_cad_import(p, b, port):
    print('• الكميات من مخطط أوتوكاد')
    import subprocess
    dxf = subprocess.check_output(['node', '-e', r"""
const L=[];const p=(c,v)=>L.push(String(c),String(v));
const T=(x,y,s,h=100)=>{p(0,'TEXT');p(8,'T');p(10,x);p(20,y);p(30,0);p(40,h);p(1,s);};
p(0,'SECTION');p(2,'HEADER');p(9,'$INSUNITS');p(70,4);p(0,'ENDSEC');p(0,'SECTION');p(2,'ENTITIES');
T(0,-300,'TYPE');T(1500,-300,'WIDTH');T(3000,-300,'HEIGHT');T(4500,-300,'QTY');
T(0,-600,'W1');T(1500,-600,'1200');T(3000,-600,'1500');T(4500,-600,'2');
T(0,-900,'D1');T(1500,-900,'900');T(3000,-900,'2100');T(4500,-900,'1');
T(9000,0,'W1',80);T(9500,0,'W1',80);T(9000,800,'D1',80);T(9500,800,'D1',80);
p(0,'ENDSEC');p(0,'EOF');process.stdout.write(L.join('\r\n'));"""]).decode()
    ctx = await new_ctx(p, b)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
    before = await pg.evaluate("() => document.querySelectorAll('#qty-rows tr').length")
    await pg.click('#cadImportBtn')
    await pg.set_input_files('#mzCadFile', files=[{'name': 'plan.dxf', 'mimeType': 'application/dxf', 'buffer': dxf.encode('utf8')}])
    await pg.wait_for_selector('.mzCadChk', timeout=10000)
    r = await pg.evaluate("""() => Array.from(document.querySelectorAll('#mzCadResult tbody tr')).map(tr => ({
      chk: tr.querySelector('.mzCadChk').checked, mark: tr.children[1].textContent, w: tr.querySelector('.mzCadW').value,
      h: tr.querySelector('.mzCadH').value, q: tr.querySelector('.mzCadQ').value, item: tr.querySelector('.mzCadItem').selectedOptions[0].textContent }))""")
    w1 = next((x for x in r if x['mark'] == 'W1'), None); d1 = next((x for x in r if x['mark'] == 'D1'), None)
    check(w1 and w1['chk'] and (w1['w'], w1['h'], w1['q']) == ('1200', '1500', '2'), 'W1 متطابق ومحدد ' + str(w1))
    check(d1 and not d1['chk'] and d1['q'] == '1', 'D1 عدده مختلف (جدول 1 / مسقط 2) فمش محدد تلقائياً ' + str(d1))
    check(w1 and 'اختار' not in w1['item'], 'تخمين الصنف للشباك ' + str(w1 and w1['item']))
    await pg.click('#mzCadAdd'); await pg.wait_for_timeout(300)
    rows = await pg.evaluate("""() => Array.from(document.querySelectorAll('#qty-rows tr')).filter(tr => tr.querySelector('.w-input')).map(tr => [tr.querySelector('.w-input').value, tr.querySelector('.h-input').value, tr.querySelector('.qty-input').value, tr.querySelector('.item-input').value])""")
    check(any(x[:3] == ['1200', '1500', '2'] and x[3] for x in rows) and not any(x[0] == '900' for x in rows), 'انضاف W1 بس لجدول الكميات ' + str(rows))
    await pg.click('#cadImportBtn')
    await pg.set_input_files('#mzCadFile', files=[{'name': 'plan.dwg', 'mimeType': 'application/octet-stream', 'buffer': b'AC1021' + bytes(200)}])
    await pg.wait_for_timeout(800)
    t = await pg.evaluate("() => document.getElementById('mzCadStatus').textContent")
    check('2007' in t and '2010' in t, 'DWG نسخة 2007: رسالة واضحة شو يعمل ' + t[:60])
    fx = os.environ.get('MZ_DWG_FIXTURES', '/tmp/claude-0/-home-claude/763d6975-41b8-5b57-9416-4a2e9e40fbf3/scratchpad/dwg/lw/test/test-data')
    if os.path.exists(os.path.join(fx, 'example_2018.dwg')):
        for v in ['2004', '2018']:
            await pg.set_input_files('#mzCadFile', os.path.join(fx, 'example_' + v + '.dwg'))
            await pg.wait_for_function("() => /لقيت|ما لقيت|❌/.test(document.getElementById('mzCadStatus').textContent)", timeout=30000)
            t = await pg.evaluate("() => document.getElementById('mzCadStatus').textContent")
            check('❌' not in t, 'ملف DWG ' + v + ' انقرا بالمتصفح بدون خطأ: ' + t[:50])
    user_dwg = '/mnt/user-data/attachments/763d6975-41b8-5b57-9416-4a2e9e40fbf3/ca42d3bf-Document_from_Merzona'
    if os.path.exists(user_dwg):
        await pg.set_input_files('#mzCadFile', files=[{'name': 'Document_from_Merzona.dwg', 'mimeType': 'application/octet-stream', 'buffer': open(user_dwg, 'rb').read()}])
        await pg.wait_for_function("() => /لقيت|ما لقيت|❌/.test(document.getElementById('mzCadStatus').textContent)", timeout=60000)
        t = await pg.evaluate("() => document.getElementById('mzCadStatus').textContent")
        check('❌' not in t, 'ملف DWG حقيقي 9MB (243 ألف كائن) بالمتصفح: ' + t[:60])
    # PDF حقيقي بالمتصفح (فك الضغط بـDecompressionStream)
    pdf64 = subprocess.check_output(['node', os.path.join(SRC, 'tests', 'pdf-fixture.js')]).decode()
    import base64
    await pg.set_input_files('#mzCadFile', files=[{'name': 'villa.pdf', 'mimeType': 'application/pdf', 'buffer': base64.b64decode(pdf64)}])
    await pg.wait_for_selector('.mzCadChk', timeout=15000)
    r = await pg.evaluate("""() => ({ st: document.getElementById('mzCadStatus').textContent,
      pages: Array.from(document.querySelectorAll('.mzCadPg')).map(c => [c.value, c.checked]),
      rows: Array.from(document.querySelectorAll('#mzCadResult tbody tr')).map(tr => [tr.children[1].textContent, tr.querySelector('.mzCadW').value, tr.querySelector('.mzCadH').value, tr.querySelector('.mzCadQ').value, tr.querySelector('.mzCadChk').checked]) })""")
    rows = {x[0]: x[1:] for x in r['rows']}
    check(rows.get('W1') == ['2500', '3700', '4', True] and rows.get('D1') == ['1000', '2600', '3', True], 'PDF بالمتصفح: جدول (ارتفاع×عرض) + عدّ بالمسقط المدوّر ' + str(r['rows'][:3]))
    check('ارتفاع × عرض' in r['st'], 'بيبيّن إنه المقاس مكتوب ارتفاع × عرض')
    await pg.select_option('#mzCadOrder', 'wh'); await pg.wait_for_timeout(200)
    w1 = await pg.evaluate("() => Array.from(document.querySelectorAll('#mzCadResult tbody tr')).filter(tr => tr.children[1].textContent === 'W1').map(tr => tr.querySelector('.mzCadW').value)[0]")
    check(w1 == '3700', 'تغيير الترتيب يدوياً بيقلب العرض والارتفاع')
    await pg.select_option('#mzCadOrder', ''); await pg.wait_for_timeout(200)
    await pg.evaluate("() => { const c = Array.from(document.querySelectorAll('.mzCadPg')).find(c => c.value === '2'); c.checked = false; c.dispatchEvent(new Event('change')); }")
    await pg.wait_for_timeout(200)
    q = await pg.evaluate("() => Array.from(document.querySelectorAll('#mzCadResult tbody tr')).filter(tr => tr.children[1].textContent === 'W1').map(tr => [tr.querySelector('.mzCadChk').checked, tr.textContent.includes('مصدر واحد')])[0]")
    check(q == [True, True] or q == [False, True], 'شيل صفحة المسقط من العدّ بيعيد الحساب ' + str(q))
    villa = '/mnt/user-data/attachments/763d6975-41b8-5b57-9416-4a2e9e40fbf3/363460f0-1-_ARCH_Drawings_-_Villa_Mr.Ali_Alnuaimi.pdf'
    if os.path.exists(villa):
        await pg.set_input_files('#mzCadFile', villa)
        await pg.wait_for_function("() => document.getElementById('mzCadStatus').textContent.includes('لقيت')", timeout=60000)
        r = await pg.evaluate("() => Object.fromEntries(Array.from(document.querySelectorAll('#mzCadResult tbody tr')).map(tr => [tr.children[1].textContent, tr.querySelector('.mzCadQ').value]))")
        check(r.get('W2') == '10' and r.get('D5') == '8' and r.get('OP2') == '4' and len(r) == 34, 'مخطط فيلا حقيقي (PDF من أوتوكاد) بالمتصفح: ' + str(len(r)) + ' رمز')
    check(not errs, 'ما في أخطاء ' + '; '.join(errs[:2]))
    await ctx.close()

FAKE_PDF = """window.html2pdf = function(){ var w = { prop: {}, from: function(){ return w; }, set: function(){ return w; },
  toContainer: async function(){ w.prop.container = document.createElement('div'); },
  toCanvas: async function(){ var c = document.createElement('canvas'); c.width = 900; c.height = 1200; w.prop.canvas = c; },
  toPdf: async function(){ w.prop.pdf = { getNumberOfPages: function(){ return 1; } }; },
  outputPdf: async function(){ return new Blob(['%PDF-1.4 fake'], { type: 'application/pdf' }); } }; return w; };"""

async def t_quotes_server(p, b, port):
    print('• عروض الأسعار عالسيرفر (المرحلة 3 - الجزء 2)')
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    if not os.path.isfile(os.path.join(sdir, 'quote-store.js')):
        print('  SKIP ما لقيت quote-store.js'); return
    import subprocess, urllib.request
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_drive.js'), sdir], stdout=subprocess.PIPE, text=True)
    try:
        fport = int(proc.stdout.readline().split()[1]); LOCAL = 'http://127.0.0.1:%d' % fport
        get = lambda pth: json.loads(urllib.request.urlopen(LOCAL + pth).read())
        for _ in range(50):
            if not get('/__quotes')['status'].get('running') and not get('/__quotes')['status'].get('never'): break
            await asyncio.sleep(0.1)
        st = get('/__quotes')
        check(st['status'].get('foldersFound') == 2 and st['status'].get('imported') == 2 and st['status'].get('match'), 'نقل العروض الموجودة من درايف مع مطابقة الأعداد ' + str({k: st['status'].get(k) for k in ('foldersFound', 'imported', 'match')}))
        async def to_local(route):
            u = route.request.url
            resp = await route.fetch(url=LOCAL + u[len(SRV):])
            await route.fulfill(response=resp)
        async def wire(ctx, dev, sess):
            await ctx.add_init_script("localStorage.setItem('merzona-device-token','%s');localStorage.setItem('merzona-session-token','%s');" % (dev, sess))
            for pat in ['/gdrive/**', '/team/**', '/gdrive-upload-session', '/quotes', '/quotes?*', '/quotes/**']:
                await ctx.route(SRV + pat, to_local)
            await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
            await ctx.add_init_script(FAKE_PDF)
        dialogs = []
        def on_dialog(d, answer):
            dialogs.append(d.message); asyncio.ensure_future(d.accept() if answer[0] else d.dismiss())
        # الجهاز الأول (المالك) بيعمل عرض جديد وبيحفظه
        ctxA = await new_ctx(p, b); await wire(ctxA, 'dev1', 's1')
        pa = await ctxA.new_page(); errs = []; pa.on('pageerror', lambda e: errs.append(str(e)[:200]))
        ansA = [True]; pa.on('dialog', lambda d: on_dialog(d, ansA))
        await pa.goto(f'http://127.0.0.1:{port}/index.html'); await pa.wait_for_timeout(2500)
        await pa.evaluate("""() => { const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); };
          set('m-ref', 'M-Q-260500'); set('m-client', 'زبون السيرفر'); set('m-number', '0501234567'); }""")
        r = await pa.evaluate("async () => { try { const x = await saveToGoogleDriveInner(); return { ok: true, s: x.summary }; } catch(e) { return { ok: false, e: String(e && e.message || e) }; } }")
        check(r['ok'], 'الحفظ الكامل (درايف + سيرفر) ' + str(r))
        await pa.wait_for_timeout(800)
        st = get('/__quotes'); it = st['items'].get('M-Q-260500') or {}
        drive = json.loads(urllib.request.urlopen(LOCAL + '/__file/M-Q-260500-data.json').read())
        check(it.get('rev') == 1 and it['data']['fields']['m-client'] == 'زبون السيرفر', 'العرض انحفظ عالسيرفر (نسخة 1)')
        check(drive.get('quotationSavedAt') == it['data'].get('quotationSavedAt'), 'نفس وقت الحفظ بدرايف وبالسيرفر')
        row = next((x for x in st['list']['items'] if x['ref'] == 'M-Q-260500'), {})
        check(row.get('url', '').startswith('https://drive.google.com/file/d/') and row.get('refFolderId') and it['data'].get('signBoxRect') is not None or row.get('url'), 'السيرفر سجّل مكان ملفات العرض على درايف ' + str(row.get('url')))
        check(not dialogs, 'عرض جديد: ما في أي سؤال ' + str(dialogs[:1]))
        # الجهاز التاني (sam) بيفتح نفس العرض من الداشبورد
        ctxB = await new_ctx(p, b); await wire(ctxB, 'dev2', 's2')
        await ctxB.add_init_script("if(!sessionStorage.getItem('mzOnce')){ sessionStorage.setItem('mzOnce','1'); localStorage.setItem('merzona-pending-load', %s); }" % json.dumps(json.dumps(drive)))
        pb = await ctxB.new_page(); pb.on('pageerror', lambda e: errs.append(str(e)[:200]))
        ansB = [False]; pb.on('dialog', lambda d: on_dialog(d, ansB))
        await pb.goto(f'http://127.0.0.1:{port}/index.html'); await pb.wait_for_timeout(3500)
        check(await pb.evaluate("document.getElementById('m-client').value") == 'زبون السيرفر', 'الجهاز التاني فتح العرض')
        # المالك بيعدّل وبيحفظ مرة تانية (عادي - هو آخر واحد حفظ)
        await pa.evaluate("() => { const e = document.getElementById('m-client'); e.value = 'تعديل المالك'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        r = await pa.evaluate("async () => { try { await saveToGoogleDriveInner(); return 'ok'; } catch(e) { return String(e.message); } }")
        await pa.wait_for_timeout(500)
        check(r == 'ok' and get('/__quotes')['items']['M-Q-260500']['rev'] == 2 and not dialogs, 'المالك حفظ تعديله التاني بدون أسئلة (نسخة 2)')
        # sam (فاتح النسخة القديمة) بيحفظ → تحذير، بيلغي → ما بينكتب شي
        await pb.evaluate("() => { const e = document.getElementById('m-client'); e.value = 'تعديل sam'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        r = await pb.evaluate("async () => { try { await saveToGoogleDriveInner(); return 'ok'; } catch(e) { return String(e.message); } }")
        await pb.wait_for_timeout(300)
        drive2 = json.loads(urllib.request.urlopen(LOCAL + '/__file/M-Q-260500-data.json').read())
        check(r == 'تم إلغاء الحفظ' and dialogs and 'جهاز تاني' in dialogs[-1] and 'المالك' in dialogs[-1], 'جهاز تاني حفظ بعدك → تحذير باسم مين وإيمتى ' + (dialogs[-1][:70] if dialogs else ''))
        check(drive2['fields']['m-client'] == 'تعديل المالك' and get('/__quotes')['items']['M-Q-260500']['rev'] == 2, 'إلغاء = لا درايف ولا السيرفر انكتب فوقهم')
        # sam بيأكد → بينكتب وبيتسجّل
        ansB[0] = True; n0 = len(dialogs)
        r = await pb.evaluate("async () => { try { await saveToGoogleDriveInner(); return 'ok'; } catch(e) { return String(e.message); } }")
        await pb.wait_for_timeout(600)
        st = get('/__quotes'); fo = [a for a in st['audit'] if a.get('op') == 'force-overwrite']
        check(r == 'ok' and len(dialogs) == n0 + 1 and st['items']['M-Q-260500']['rev'] == 3 and fo and fo[-1]['user'] == 'sam' and fo[-1]['overwrote']['savedBy'] == 'المالك', 'تأكيد الكتابة فوق → انحفظ وانسجّل مين كتب فوق مين')
        # السيرفر مقطوع → الحفظ على درايف بيكمل متل قبل
        urllib.request.urlopen(LOCAL + '/__quotes-off')
        await pa.evaluate("() => { const e = document.getElementById('m-ref'); e.value = 'M-Q-260501'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        r = await pa.evaluate("async () => { try { await saveToGoogleDriveInner(); return 'ok'; } catch(e) { return String(e.message); } }")
        urllib.request.urlopen(LOCAL + '/__quotes-on')
        names = [f['name'] for f in json.loads(urllib.request.urlopen(LOCAL + '/__state').read())['files']]
        check(r == 'ok' and 'M-Q-260501-data.json' in names and 'M-Q-260501' not in get('/__quotes')['items'], 'السيرفر مقطوع → الحفظ على درايف بيكمل عادي')
        # الداشبورد: القائمة من السيرفر بطلب واحد + الحذف
        pd = await ctxA.new_page(); pd.on('pageerror', lambda e: errs.append(str(e)[:200])); pd.on('dialog', lambda d: on_dialog(d, ansA))
        await pd.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pd.wait_for_timeout(3000)
        r = await pd.evaluate("""async () => { const used = await mzDashSyncQuotesFromServer(); const d = loadDiscoveredQuotations();
          const row = DATA.find(x => x.ref === 'M-Q-260500'); return { used, client: row && row.client, old: !!d['M-Q-260001'], total: d['M-Q-260001'] && d['M-Q-260001'].total }; }""")
        check(r['used'] and r['client'] == 'تعديل sam' and r['old'] and r['total'] == 1000, 'الداشبورد: القائمة من السيرفر (عرض جديد + عروض قديمة منقولة) ' + str(r))
        ansA[0] = True
        await pd.evaluate("async () => { await deleteQuotationByRef('M-Q-260500', null); }"); await pd.wait_for_timeout(500)
        row = next((x for x in get('/__quotes')['list']['items'] if x['ref'] == 'M-Q-260500'), {})
        check(row.get('deleted') and get('/__quotes')['items']['M-Q-260500'] is None or row.get('deleted'), 'حذف من الداشبورد = حذف ناعم عالسيرفر كمان')
        r = await pd.evaluate("async () => { await mzDashSyncQuotesFromServer(); return !!DATA.find(x => x.ref === 'M-Q-260500'); }")
        check(not r, 'العرض المحذوف ما بيرجع من السيرفر')
        check(not errs, 'ما في أخطاء ' + '; '.join(errs[:2]))
        await ctxA.close(); await ctxB.close()
    finally:
        proc.kill()

async def t_company(p, b, port):
    print('• إعدادات الشركة (نسخة لشركة تانية)')
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    if not os.path.isfile(os.path.join(sdir, 'company-store.js')):
        print('  SKIP'); return
    import subprocess, urllib.request, base64
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_drive.js'), sdir], stdout=subprocess.PIPE, text=True)
    try:
        fport = int(proc.stdout.readline().split()[1]); LOCAL = 'http://127.0.0.1:%d' % fport
        async def to_local(route):
            resp = await route.fetch(url=LOCAL + route.request.url[len(SRV):]); await route.fulfill(response=resp)
        errs = []
        ctx = await new_ctx(p, b)
        await ctx.add_init_script("localStorage.setItem('merzona-device-token','dev1');localStorage.setItem('merzona-session-token','s1');")
        for pat in ['/gdrive/**', '/team/**', '/quotes', '/quotes?*', '/quotes/**', '/company', '/company/**']:
            await ctx.route(SRV + pat, to_local)
        await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        # 1) ميرزونا: ولا شي بيتغيّر
        await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
        r = await pg.evaluate("""() => ({ def: MzCompany.isDefault(), addr: document.getElementById('branch-address-text').textContent, bank: document.getElementById('bank-info-section').textContent,
          vat: document.getElementById('vat-row').textContent, aux: getComputedStyle(document.documentElement).getPropertyValue('--aux1').trim(), ref: getBranchConfig(getCurrentBranch()).refPrefix })""")
        check(r['def'] and 'Info@Merzona.com' in r['addr'] and 'Mashreq' in r['bank'] and '104252457700003' in r['vat'] and r['aux'] == '#0f88cd' and r['ref'] == 'M', 'ميرزونا: كل شي متل ما هو ' + str(r)[:120])
        # 2) الإعدادات من الداشبورد: حفظ بدون تغيير = ولا شي بينخزن
        pd = await ctx.new_page(); pd.on('pageerror', lambda e: errs.append(str(e)[:200])); pd.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pd.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pd.wait_for_timeout(3000)
        await pd.evaluate("() => { window.applyMerzonaPermissions(null, true); }")
        check(await pd.evaluate("getComputedStyle(document.getElementById('companySettingsBtn')).display") != 'none', 'زر إعدادات الشركة بيبيّن للمالك')
        await pd.evaluate("() => { window.applyMerzonaPermissions({ quotation: true }, false); }")
        check(await pd.evaluate("getComputedStyle(document.getElementById('companySettingsBtn')).display") == 'none', 'وما بيبيّن للموظف')
        await pd.evaluate("mzOpenCompanySettings()"); await pd.wait_for_selector('#co-save')
        await pd.click('#co-save'); await pd.wait_for_timeout(800)
        pub = json.loads(urllib.request.urlopen(LOCAL + '/company/public').read())
        check(pub['rev'] == 1 and pub['profile'] == {}, 'حفظ بدون تعديل → ميرزونا بتضل افتراضية ' + str(pub)[:80])
        # 3) تعبئة Sufiya من الشاشة
        logo = 'data:image/png;base64,' + base64.b64encode(open(os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'sufiya-logo.png'), 'rb').read()).decode()
        await pd.evaluate("mzOpenCompanySettings()"); await pd.wait_for_selector('#co-save'); await pd.wait_for_timeout(300)
        await pd.evaluate("""(logo) => { const set = (id, v) => { document.getElementById(id).value = v; };
          set('co-nameEn', 'Sufiya Glass'); set('co-nameAr', 'صوفيه'); set('co-fullNameEn', 'Sufiya Glass for Aluminum & Glass'); set('co-email', 'info@sufiyaglass.com'); set('co-website', 'www.sufiyaglass.com'); set('co-phone', '+971500000001');
          set('co-uae-refPrefix', 'G'); set('co-uae-address', 'Dubai, UAE  Tel: +971500000001  e: info@sufiyaglass.com'); set('co-uae-trn', '100200300400500');
          set('co-uae-bankEn', 'Emirates NBD'); set('co-uae-bankAr', 'بنك الإمارات دبي الوطني'); set('co-uae-acc', '1234567'); set('co-uae-accName', 'Sufiya Glass'); set('co-uae-iban', 'AE000000000001234567');
          set('co-uae-jurEn', 'Dubai courts shall have exclusive jurisdiction over any dispute arising from this contract.'); set('co-uae-jurAr', 'الاختصاص القضائي لمحاكم دبي.');
          document.getElementById('co-syria-enabled').checked = false; set('co-accent', '#14aacc'); set('co-text', '#1d3856');
          const img = document.getElementById('co-logo-prev'); img.src = logo; }""", logo)
        await pd.evaluate("(logo) => { const inp = document.getElementById('co-logo'); }", logo)
        await pd.set_input_files('#co-logo', os.path.join(ROOT, 'tests', 'e2e', 'fixtures', 'sufiya-logo.png')); await pd.wait_for_timeout(600)
        await pd.click('#co-save'); await pd.wait_for_timeout(1200)
        pub = json.loads(urllib.request.urlopen(LOCAL + '/company/public').read())['profile']
        check(pub.get('nameEn') == 'Sufiya Glass' and pub['branches']['uae']['refPrefix'] == 'G' and pub['branches']['syria']['enabled'] is False and pub['logo'].startswith('data:image/') and pub['colors']['accent'] == '#14aacc', 'إعدادات Sufiya انحفظت عالسيرفر')
        # 4) عرض السعر صار باسم Sufiya
        await pg.reload(); await pg.wait_for_timeout(3000)
        r = await pg.evaluate("""() => ({ addr: document.getElementById('branch-address-text').textContent, bank: document.getElementById('bank-info-section').textContent,
          vat: document.getElementById('vat-row').textContent, aux: getComputedStyle(document.documentElement).getPropertyValue('--aux1').trim(),
          logo: (document.getElementById('logo-clone') || {}).src || '', alt: (document.getElementById('logo-clone') || {}).alt,
          branchRow: getComputedStyle(document.getElementById('m-branch').closest('.meta-row')).display, ref: getBranchConfig(getCurrentBranch()).refPrefix,
          body: document.body.innerText, jur: Array.from(document.querySelectorAll('#notes-rows textarea')).map(t => t.value).join(' | ') })""")
        check('sufiyaglass.com' in r['addr'] and 'Merzona' not in r['addr'], 'العنوان أسفل العرض ' + r['addr'][:60])
        check('Emirates NBD' in r['bank'] and 'AE000000000001234567' in r['bank'] and 'Sufiya Glass' in r['bank'] and 'Mashreq' not in r['bank'], 'الحساب البنكي')
        check('100200300400500' in r['vat'], 'الرقم الضريبي')
        check(r['aux'] == '#14aacc', 'اللون الأساسي ' + r['aux'])
        check(r['logo'].startswith('data:image/') and 'Sufiya' in r['alt'], 'اللوغو')
        check(r['branchRow'] == 'none' and r['ref'] == 'G', 'فرع واحد (قائمة الفروع مخفية) وحرف المرجع G')
        check('Dubai courts' in r['jur'] and 'Sharjah' not in r['jur'], 'بند المحاكم بالشروط')
        check('Merzona' not in r['body'] and 'ميرزونا' not in r['body'], 'ولا كلمة Merzona بالصفحة')
        msg = await pg.evaluate("() => { try { return mzShareMessageText ? mzShareMessageText('G-Q-260001', 'https://x') : ''; } catch(e) { return MzCompany.brand('تفضل عرض السعر من Merzona'); } }")
        check('Sufiya Glass' in msg and 'Merzona' not in msg, 'رسالة الواتس اب للزبون ' + msg[:50])
        # 5) صفحة توقيع الزبون
        ps = await ctx.new_page(); await ps.goto(f'http://127.0.0.1:{port}/sign.html'); await ps.wait_for_timeout(2000)
        t = await ps.evaluate("document.title + ' | ' + document.body.innerText")
        check('Sufiya Glass' in t and 'Merzona' not in t, 'صفحة توقيع الزبون باسم الشركة ' + t[:60])
        # 5ب) شركة بسوريا بس (متل Sufiya): فرع الإمارات موقّف، العروض بالدولار/الليرة، بلا ضريبة وبلا بنك
        cur = json.loads(urllib.request.urlopen(LOCAL + '/company/public').read())
        prof = cur['profile']; prof['email'] = 'sufiya.art79@gmail.com'; prof['phone'] = '+963116625999'
        prof['branches'] = {'uae': {'enabled': False}, 'syria': {'enabled': True, 'refPrefix': 'G', 'labelEn': 'Damascus, Syria', 'labelAr': 'دمشق، سوريا',
            'addressHtml': 'Damascus, Syria &nbsp; Tel: +963116625999 &nbsp; e: sufiya.art79@gmail.com', 'bank': None}}
        req = urllib.request.Request(LOCAL + '/company', data=json.dumps({'baseRev': cur['rev'], 'profile': prof}).encode(), method='PUT', headers={'Content-Type': 'application/json', 'x-device': 'dev1', 'x-session': 's1'})
        check(json.loads(urllib.request.urlopen(req).read()).get('ok'), 'حفظ إعدادات شركة بسوريا بس')
        await pg.reload(); await pg.wait_for_timeout(3000)
        r = await pg.evaluate("""() => ({ br: document.getElementById('m-branch').value, ref: document.getElementById('m-ref').value,
          cur: getComputedStyle(document.getElementById('currency-row')).display, vat: getComputedStyle(document.getElementById('vat-row')).display,
          bank: getComputedStyle(document.getElementById('bank-info-section')).display, addr: document.getElementById('branch-address-text').textContent,
          fromRef: getBranchFromRef('G-Q-260001'), row: getComputedStyle(document.getElementById('m-branch').closest('.meta-row')).display })""")
        check(r['br'] == 'syria' and r['ref'].startswith('G-Q-') and r['fromRef'] == 'syria', 'الفرع الوحيد سوريا، والمرجع G-Q ' + str(r)[:90])
        check(r['cur'] != 'none' and r['vat'] == 'none' and r['bank'] == 'none' and r['row'] == 'none', 'دولار/ليرة، بلا ضريبة، بلا بنك، بلا قائمة فروع')
        check('+963116625999' in r['addr'] and 'sufiya.art79@gmail.com' in r['addr'], 'عنوان دمشق ورقمهم وإيميلهم ' + r['addr'][:70])
        # 6) الداشبورد
        await pd.reload(); await pd.wait_for_timeout(3000)
        t = await pd.evaluate("document.title + ' | ' + document.body.innerText")
        check('Merzona' not in t and 'ميرزونا' not in t, 'الداشبورد ما فيه اسم ميرزونا')
        check(not errs, 'ما في أخطاء ' + '; '.join(errs[:2]))
        await ctx.close()
    finally:
        proc.kill()

FX_RATE = {'buy': 146.75, 'sell': 147.25, 'at': '2026-11-13T08:30:00Z', 'fetchedAt': '2026-11-13T08:31:00Z', 'prevSell': 146.5, 'source': {'name': 'sp-today.com', 'url': 'https://sp-today.com/currency/us-dollar'}}

async def t_fx_bar(p, b, port):
    """💵 شريط سعر الدولار فوق بكل صفحات الشغل (مش بصفحات الزبون)، وما بيغطّي شي."""
    print('• شريط سعر صرف الدولار')
    ctx = await b.new_context(viewport={"width": 1400, "height": 900})
    hits = []
    async def srv(route):
        u = route.request.url
        if '/fx/usd-syp' in u: hits.append(u); return await route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(FX_RATE))
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else {}
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    errs = []
    for page in ['Dashboard.html', 'index.html', 'accounting.html', 'procurement.html', 'salary.html']:
        pg = await ctx.new_page(); pg.on('pageerror', lambda e, page=page: errs.append(page + ': ' + str(e)[:120])); pg.on('dialog', lambda d: asyncio.ensure_future(d.dismiss()))
        await pg.goto(f'http://127.0.0.1:{port}/{page}'); await pg.wait_for_timeout(2000)
        r = await pg.evaluate("""(() => { const b = document.getElementById('mzFxBar'); if (!b) return null; const r = b.getBoundingClientRect();
            let nxt = b.nextElementSibling; while (nxt && (['fixed', 'absolute'].includes(getComputedStyle(nxt).position) || !nxt.getBoundingClientRect().height)) nxt = nxt.nextElementSibling; const n = nxt ? nxt.getBoundingClientRect() : null;
            return { text: b.innerText, top: r.top, h: r.height, w: r.width, first: document.body.firstElementChild === b, below: n ? n.top >= r.bottom - 1 : true,
                     printHidden: [...document.styleSheets].some(s => { try { return [...s.cssRules].some(x => x.cssText.includes('print') && x.cssText.includes('mzFxBar')); } catch (e) { return false; } }) }; })()""")
        check(r and '146.75' in r['text'] and '147.25' in r['text'] and '14,725' in r['text'] and '▲' in r['text'], page + ': سعر الدولار فوق ' + (r['text'][:90].replace('\n', ' ') if r else 'ما في شريط'))
        if r: check(r['first'] and r['top'] == 0 and r['h'] < 60 and r['w'] >= 1380 and r['below'] and r['printHidden'], page + ': الشريط بأول الصفحة، ما بيغطّي، وما بينطبع ' + str({k: r[k] for k in ('top', 'h', 'w', 'below', 'printHidden')}))
        if page == 'Dashboard.html': await pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'fx-dashboard.png'))
        await pg.close()
    # الموبايل: الشريط بيلتف وما بيعمل سكرول عرضي
    m = await b.new_context(viewport={"width": 375, "height": 800}); await m.route(SRV + '/**', srv)
    pg = await m.new_page(); await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2000)
    r = await pg.evaluate("(() => { const b = document.getElementById('mzFxBar'); return b ? { w: b.scrollWidth, cw: b.clientWidth, h: b.getBoundingClientRect().height } : null })()")
    check(r and r['w'] <= r['cw'] + 1 and r['h'] < 70, 'موبايل: الشريط ما بيطلع برّا الشاشة ' + str(r))
    await pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'fx-mobile.png')); await m.close()
    # صفحات الزبون: ما في سعر صرف
    for page in ['sign.html', 'catalog.html']:
        pg = await ctx.new_page(); await pg.goto(f'http://127.0.0.1:{port}/{page}'); await pg.wait_for_timeout(1500)
        check(not await pg.evaluate("!!document.getElementById('mzFxBar')"), page + ': صفحة الزبون بلا سعر صرف'); await pg.close()
    # السيرفر ما رد: ما في شريط فاضي ولا خطأ
    c3 = await b.new_context(); await c3.route(SRV + '/**', lambda r: asyncio.ensure_future(r.fulfill(status=503, body='{}')))
    pg = await c3.new_page(); await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(1500)
    check(not await pg.evaluate("!!document.getElementById('mzFxBar')"), 'إذا ما في سعر: ما في شريط فاضي'); await c3.close()
    check(all(h.startswith(SRV + '/fx/usd-syp') for h in hits), 'ميرزونا بتقرا السعر من سيرفرها')
    check(not errs, 'ما في أخطاء ' + '; '.join(errs[:3]))
    await ctx.close()

async def t_sufiya_site(p, b, port, root):
    """🏢 نسخة صوفيه (رابطها لحاله): ولا كلمة ميرزونا، كل الطلبات لبرنامج صوفيه بالسيرفر، والتخزين مفصول."""
    print('• نسخة صوفيه (رابط لحاله)')
    import subprocess
    dest = os.path.join(root, 'sufiya')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'release.py'), 'sufiya-build', dest], capture_output=True, text=True)
    if r.returncode != 0: check(False, 'بناء نسخة صوفيه ' + r.stdout + r.stderr); return
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    seed = os.path.join(sdir, 'tenants', 'sufiya', 'company.json')
    prof = json.load(open(seed, encoding='utf8')) if os.path.isfile(seed) else {'rev': 1, 'profile': json.load(open(os.path.join(ROOT, 'tools', 'sufiya', 'profile.json'), encoding='utf8'))}
    # الكتالوج (13Qxtn...) مشترك عن قصد من 2026-11-20 (حمدي: "خلي كتالوج صوفية من مجلد ميرزونا") - قراءة بس من صوفيه
    import re
    # 🆕 2026-11-20: روابط الكتالوج/التوقيع/الرواتب المبعوتة لزبائن صوفيه (واتساب بيقرا الصفحة بلا جافاسكربت) + أيقونة صوفيه
    for f in ['catalog.html', 'sign.html', 'salary.html', 'techcat.html']:
        raw = open(os.path.join(dest, f), encoding='utf8').read()
        check(not re.search('Merzona|MERZONA|ميرزونا|مرزونا', raw), f + ': ولا كلمة ميرزونا بالصفحة نفسها (معاينة الرابط بواتساب)')
    rawc = open(os.path.join(dest, 'catalog.html'), encoding='utf8').read()
    check('971508471158' not in rawc and 'wa: "963939919670"' in rawc and 'wa: "971' not in rawc, 'استفسارات واتساب من كتالوج صوفيه بتروح لرقم واتساب صوفيه (+963939919670 حسب طلب حمدي)')
    check(all('img/sufiya-icon.png' in open(os.path.join(dest, f), encoding='utf8').read() and 'catalog-icon.png' not in open(os.path.join(dest, f), encoding='utf8').read() for f in os.listdir(dest) if f.endswith('.html')), 'كل صفحات صوفيه أيقونتها لوغو صوفيه')
    import hashlib as _h
    check(_h.md5(open(os.path.join(dest, 'img', 'sufiya-icon.png'), 'rb').read()).hexdigest() == _h.md5(open(os.path.join(ROOT, 'tools', 'sufiya', 'icon.png'), 'rb').read()).hexdigest(), 'ملف الأيقونة = أيقونة صوفيه')
    MERZ = ['13q5WtejXrydWEeIEZ7pZoon6ocyVuX1D', '1tQkVAUHGy9_Tm2JZxlkkTvGUTxAWM8uS', '1FL-I0R4qXdAtqLF8JgcranzKsffKgLzy']
    reqs = []; errs = []
    ctx = await b.new_context(viewport={"width": 1400, "height": 900})
    # جهاز عليه ميرزونا من قبل (نفس github.io)
    await ctx.add_init_script("if(!window.MZ_TENANT){localStorage.setItem('merzona-device-token','MERZONA-DEV');localStorage.setItem('merzona-session-token','MERZONA-SES');}")
    async def srv(route):
        u = route.request.url; reqs.append(u)
        if u.split('?')[0].endswith('/t/sufiya/company/public'): return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'rev': prof['rev'], 'profile': prof['profile']}))
        if u.split('?')[0].endswith('/t/sufiya/fx/usd-syp'): return await route.fulfill(status=200, content_type='application/json', body=json.dumps(FX_RATE))
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else ([] if '/dashboard-seed' in u else {})
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    await ctx.route('https://www.googleapis.com/**', lambda r: (reqs.append(r.request.url), asyncio.ensure_future(r.fulfill(status=401, body='{}')))[1])
    first = []
    for page in ['Dashboard.html', 'index.html', 'sign.html', 'catalog.html', 'salary.html', 'accounting.html', 'procurement.html']:
        pg = await ctx.new_page(); pg.on('pageerror', lambda e, page=page: errs.append(page + ': ' + str(e)[:150])); pg.on('dialog', lambda d: asyncio.ensure_future(d.dismiss()))
        # أول ظهور (قبل ما يرد السيرفر): لازم يكون باسم صوفيه
        await pg.add_init_script("document.addEventListener('DOMContentLoaded',function(){setTimeout(function(){var o=[],w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n;while((n=w.nextNode())){var e=n.parentElement;if(!e||/^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(e.tagName)||!e.getClientRects().length)continue;o.push(n.nodeValue)}window.__first=document.title+' | '+o.join(' ')},50)})")
        await pg.goto(f'http://127.0.0.1:{port}/sufiya/{page}'); await pg.wait_for_timeout(2500)
        t = await pg.evaluate("document.title + ' | ' + document.body.innerText")
        f = await pg.evaluate("window.__first || ''")
        bad = [w for w in ['Merzona', 'MERZONA', 'ميرزونا', 'مرزونا'] if w in t or w in f]
        def ctxw(x):
            import re as _re
            return [x[max(0, m.start() - 40):m.end() + 20].replace('\n', ' ') for m in _re.finditer('Merzona|MERZONA|ميرزونا|مرزونا', x)][:3]
        check(not bad, page + ': ولا كلمة ميرزونا ' + (str(bad) + ' final=' + str(ctxw(t)) + ' first=' + str(ctxw(f)) if bad else ''))
        if page == 'Dashboard.html':
            ls = await pg.evaluate("({ dev: localStorage.getItem('merzona-device-token'), ses: localStorage.getItem('merzona-session-token'), n: localStorage.length })")
            check(ls['dev'] != 'MERZONA-DEV' and ls['ses'] != 'MERZONA-SES', 'صوفيه ما بتشوف جهاز/جلسة ميرزونا ' + str(ls))
            await pg.evaluate("localStorage.setItem('merzona-device-token','SUFIYA-DEV')")
            logos = await pg.evaluate("Array.from(document.images).filter(i => i.getAttribute('data-co-logo')).map(i => i.getAttribute('src').slice(0, 30))")
            sufStamp = 'data:image/png;base64,' + base64.b64encode(open(os.path.join(ROOT, 'tools', 'sufiya', 'stamp.png'), 'rb').read()).decode()
            check(await pg.evaluate("SETTLEMENT_STAMP_IMG") == sufStamp, 'ختم صوفيه على المخالصات والتسويات')
            check('147.25' in (await pg.evaluate("(document.getElementById('mzFxBar') || {}).innerText || ''")), 'صوفيه: سعر الدولار فوق (من برنامج صوفيه بالسيرفر)')
            check(not await pg.evaluate("!!document.getElementById('mzSeedWarn')"), 'ما في تحذير القائمة القديمة تبع ميرزونا')
            check(logos and all(('company-logo' in l or l.startswith('data:image')) for l in logos), 'لوغو صوفيه ' + str(logos[:3]))
        if page == 'accounting.html':
            nm = await pg.evaluate("mzCoNameOf('Merzona')")
            check(nm == 'Sufiya Glass · صوفيه', 'سند القبض والفواتير باسم صوفيه ' + nm)
        if page == 'index.html':
            r2 = await pg.evaluate("({ br: document.getElementById('m-branch').value, ref: document.getElementById('m-ref').value, vat: getComputedStyle(document.getElementById('vat-row')).display, bank: getComputedStyle(document.getElementById('bank-info-section')).display })")
            st = await pg.evaluate("({ stamp: (document.querySelector('img[alt=\"Company stamp\"]') || {}).src || '', print: (document.querySelector('.print-logo') || {}).src || '' })")
            sufStamp = 'data:image/png;base64,' + base64.b64encode(open(os.path.join(ROOT, 'tools', 'sufiya', 'stamp.png'), 'rb').read()).decode()
            check(st['stamp'] == sufStamp, 'ختم صوفيه على عرض السعر (مش ختم ميرزونا)')
            check(st['print'].endswith('img/company-logo.png'), 'ترويسة الطباعة لوغو صوفيه ' + st['print'][-40:])
            await pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'sufiya-quote.png'), full_page=True)
            check(r2['br'] == 'syria' and r2['ref'].startswith('S-') and r2['vat'] == 'none' and r2['bank'] == 'none', 'عرض السعر: فرع دمشق، S، بلا ضريبة وبلا بنك ' + str(r2))
        await pg.close()
    srvreq = [u for u in reqs if u.startswith(SRV)]
    check(srvreq and all(u.startswith(SRV + '/t/sufiya/') for u in srvreq), 'كل طلبات السيرفر لبرنامج صوفيه بس ' + str([u for u in srvreq if not u.startswith(SRV + '/t/sufiya/')][:3]))
    check(not [u for u in reqs if any(m in u for m in MERZ)], 'ولا طلب لمجلدات درايف ميرزونا')
    # وميرزونا على نفس الموقع ما تأثرت
    pa = await ctx.new_page(); await pa.goto(f'http://127.0.0.1:{port}/accounting.html'); await pa.wait_for_timeout(1500)
    nm = await pa.evaluate("mzCoNameOf('Merzona')")
    check(nm == 'Merzona', 'ميرزونا: الفواتير والسندات متل ما هي ' + nm); await pa.close()
    pm = await ctx.new_page(); await pm.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pm.wait_for_timeout(1500)
    ls = await pm.evaluate("({ dev: localStorage.getItem('merzona-device-token'), suf: localStorage.getItem('sufiya:merzona-device-token') })")
    check(ls['dev'] == 'MERZONA-DEV' and ls['suf'] == 'SUFIYA-DEV', 'جهاز ميرزونا ما تغيّر، وجهاز صوفيه لحاله ' + str(ls))
    # جهاز جديد (لسا ما انقبل): شاشة طلب الدخول كمان باسم صوفيه
    c2 = await b.new_context(viewport={"width": 1400, "height": 900})
    async def srv2(route):
        u = route.request.url
        if u.split('?')[0].endswith('/t/sufiya/company/public'): return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'rev': prof['rev'], 'profile': prof['profile']}))
        await route.fulfill(status=200, content_type='application/json', body=json.dumps({'status': 'pending'} if '/access/' in u else {}))
    await c2.route(SRV + '/**', srv2)
    for page in ['Dashboard.html', 'index.html']:
        g = await c2.new_page(); await g.goto(f'http://127.0.0.1:{port}/sufiya/{page}'); await g.wait_for_timeout(2500)
        t = await g.evaluate("document.title + ' | ' + document.documentElement.innerText")
        check(not any(w in t for w in ['Merzona', 'MERZONA', 'ميرزونا', 'مرزونا']), page + ' (جهاز جديد): ولا كلمة ميرزونا ' + t[:100].replace('\n', ' '))
    await c2.close()
    check(not errs, 'ما في أخطاء ' + '; '.join(errs[:3]))
    await ctx.close()

async def t_wa_quote_draft(p, b, port):
    """📱 مسودة عرض سعر من مساعد الواتس اب: الرابط بيعبّي الفرع والزبون والبنود، وما في حفظ لحاله."""
    print('• مسودة عرض سعر من الواتس اب')
    draft = {'id': 'abc123def456abc123', 'by': 'المالك', 'branch': 'syria', 'currency': 'usd', 'client': 'أبو سمير', 'phone': '0944000111', 'project': 'فيلا المزة', 'location': 'دمشق',
             'notes': 'الهاندريل للبلكونة', 'items': [{'name': 'Handrail (Hidden Glass)', 'w': 12000, 'h': 1000, 'qty': 1, 'price': ''}, {'name': 'باب المنيوم مع زجاج من مقاطع سلسلة الـ 600', 'w': 2000, 'h': 1000, 'qty': 2, 'price': 150}, {'name': 'شي غريب مش بالقائمة', 'w': 500, 'h': 500, 'qty': 1, 'price': ''}]}
    saved = []; seen = []
    ctx = await new_ctx(p, b)
    async def srv(route):
        u = route.request.url; seen.append((route.request.method, u, route.request.headers.get('x-device', '')))
        if '/wa-agent/quote-draft/abc123def456abc123' in u: return await route.fulfill(status=200, content_type='application/json', body=json.dumps(draft))
        if '/wa-agent/quote-draft/' in u: return await route.fulfill(status=404, content_type='application/json', body='{"error":"not-found"}')
        if '/quotes/item' in u and route.request.method == 'PUT': saved.append(u)
        if '/access/status' in u: return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'status': 'approved', 'isOwner': True}))
        await route.fulfill(status=200, content_type='application/json', body='{}')
    await ctx.route(SRV + '/**', srv)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/index.html#wadraft=abc123def456abc123'); await pg.wait_for_timeout(4000)
    st = await pg.evaluate("""(function(){var rows=[].slice.call(document.querySelectorAll('#qty-rows tr')).map(function(tr){return [tr.querySelector('.item-input').value, tr.querySelector('.w-input').value, tr.querySelector('.h-input').value, tr.querySelector('.qty-input').value, tr.querySelector('.price').value, tr.dataset.itemName||'']});
      return {rows:rows, branch:document.getElementById('m-branch').value, cur:document.getElementById('m-currency').value, client:document.getElementById('m-client').value, num:document.getElementById('m-number').value, proj:document.getElementById('m-project').value, loc:document.getElementById('m-location').value, ref:document.getElementById('m-ref').value, hash:location.hash, banner:(document.getElementById('mzWaDraftBanner')||{}).textContent||''}})()""")
    check(st['branch'] == 'syria' and st['cur'] == 'usd' and st['ref'].startswith('S-'), 'الفرع سوريا والعملة دولار والرقم S- ' + str((st['branch'], st['cur'], st['ref'])))
    check(st['client'] == 'أبو سمير' and st['num'] == '0944000111' and st['proj'] == 'فيلا المزة' and st['loc'] == 'دمشق', 'بيانات الزبون انعبّت')
    r = st['rows']
    check(len(r) == 3, '3 بنود بالجدول (بلا الصف الفاضي) ' + str(r))
    check(len(r) == 3 and r[0][5] == 'Handrail (Hidden Glass)' and r[0][1:4] == ['12000', '1000', '1'], 'البند الأول متطابق مع القائمة بالقياسات ' + str(r[:1]))
    check(len(r) == 3 and r[1][5] == 'Aluminum Door with Glass' and r[1][4] == '150' and r[1][3] == '2', 'بند بالعربي انطابق والسعر انحط ' + str(r[1:2]))
    check(len(r) == 3 and r[2][0] == 'شي غريب مش بالقائمة' and r[2][5] == '', 'بند مش بالقائمة انكتب كنص ' + str(r[2:3]))
    check('راجع الأسعار' in st['banner'] and 'مش من القائمة' in st['banner'] and 'بلا سعر' in st['banner'], 'شريط التنبيه واضح ' + st['banner'][:120])
    check(st['hash'] == '', 'الرابط انمسح (تحديث الصفحة ما بيعيد التعبئة)')
    check(any('/wa-agent/quote-draft/' in u and dev for m, u, dev in seen), 'المسودة انطلبت مع هوية الجهاز')
    check(not saved, 'ما في حفظ لحاله')
    tot = await pg.evaluate("document.querySelectorAll('#qty-rows tr')[1].querySelector('.line-total').value")
    check(tot.replace(',', '').startswith('600') or tot.replace(',', '').startswith('800'), 'الإجمالي انحسب للبند المسعّر ' + tot)
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1500)
    di = await pg.evaluate("WD.__t.items().map(function(it){return [it.shapeType||'', it.width, it.height]})")
    check(len(di) >= 2 and di[0][0] == 'handrail' and di[0][1] == 12000, 'المصمم رسم السكتشات من البنود (الهاندريل أول) ' + str(di))
    # رابط منتهي
    pg2 = await ctx.new_page(); pg2.on('pageerror', lambda e: errs.append(str(e)[:200]))
    await pg2.goto(f'http://127.0.0.1:{port}/index.html#wadraft=ffffffffffffffffff'); await pg2.wait_for_timeout(3500)
    check('انتهت' in await pg2.evaluate("(document.getElementById('mzWaDraftBanner')||{}).textContent||''"), 'مسودة منتهية: رسالة واضحة')
    check(not errs, 'بلا أخطاء جافاسكربت ' + str(errs[:2]))
    await ctx.close()

async def t_wa_pdf(p, b, port):
    """📄 PDF مسودة عرض السعر: نفس كود السيرفر بيطبع الأداة الحقيقية مع السكتشات وعلامة مسودة."""
    print('• PDF مسودة عرض السعر')
    import subprocess
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    out = os.path.join(tempfile.mkdtemp(prefix='mz-pdf-'), 'draft.pdf')
    r = subprocess.run(['node', os.path.join(ROOT, 'tests', 'e2e', 'render_pdf.js'), sdir, f'http://127.0.0.1:{port}/index.html', out], capture_output=True, text=True, timeout=300)
    line = [l for l in r.stdout.splitlines() if l.startswith('INFO ') or l.startswith('FAIL ')]
    check(r.returncode == 0 and line and line[-1].startswith('INFO '), 'انطبع PDF ' + (line[-1][:300] if line else r.stderr[-300:]))
    if r.returncode != 0: return
    info = json.loads(line[-1][5:])
    check(info['rows'] == 3, '3 بنود ' + str(info))
    check(info['sketches'] >= 3 and info.get('sketchPrint'), 'سكتش لكل بند بعد عرض السعر ' + str(info))
    check(info.get('stampShown') is False, 'المسودة بلا ختم وبلا توقيع الإدارة')
    check(not info.get('pageErrors'), 'بلا أخطاء بالصفحة ' + str(info.get('pageErrors')))
    data = open(out, 'rb').read()
    check(data[:4] == b'%PDF' and len(data) > 20000, 'ملف PDF حقيقي ' + str(len(data)))
    txt = subprocess.run(['pdftotext', '-layout', out, '-'], capture_output=True, text=True).stdout if shutil.which('pdftotext') else ''
    if txt:
        check('DRAFT' in txt, 'علامة مسودة/DRAFT بالملف')
        check('12000' in txt and '2000' in txt and 'S-Q-DRAFT' in txt, 'القياسات والرقم (مسودة) بالملف')
        check('-- Select' not in txt and 'Project name' not in txt and 'e.g. DXB' not in txt, 'خانات الإدخال بتنطبع كنص (بلا قوائم اختيار ولا نصوص مساعدة)')
    shutil.copy(out, '/tmp/claude-0/wa-draft-sample.pdf') if os.path.isdir('/tmp/claude-0') else None
    # 📚 بنود السيستم (من السيرفر) بتوصل للمسودة: بند مش بالقائمة الأساسية بيطلع بمواصفاتو
    cat = os.path.join(tempfile.mkdtemp(prefix='mz-cat-'), 'cat.json'); out2 = out.replace('draft.pdf', 'draft2.pdf')
    json.dump({'items': [{'en': 'Vetromax', 'ar': 'فيترومكس', 'specEn': 'Vetromax Sliding System XQZ', 'specAr': 'نظام فيترومكس', 'glassEn': '', 'glassAr': ''}], 'specAr': {}, 'draftItems': [{'name': 'Vetromax', 'w': 7000, 'h': 2800, 'qty': 1, 'price': 3600}]}, open(cat, 'w'))
    r2 = subprocess.run(['node', os.path.join(ROOT, 'tests', 'e2e', 'render_pdf.js'), sdir, f'http://127.0.0.1:{port}/index.html', out2], capture_output=True, text=True, timeout=300, env=dict(os.environ, MZ_CATALOG_JSON=cat))
    txt2 = subprocess.run(['pdftotext', '-layout', out2, '-'], capture_output=True, text=True).stdout if shutil.which('pdftotext') and os.path.exists(out2) else ''
    check(r2.returncode == 0 and ('XQZ' in txt2 or not shutil.which('pdftotext')), 'بند محفوظ بالسيستم (Vetromax) بيطلع بالمسودة بمواصفاتو')

async def t_price_sync(p, b, port):
    """💲 آخر سعر لكل بند بيتزامن مع السيرفر: بيجيب أسعار السيرفر، بيرفع القديم، وبيبعت كل سعر جديد."""
    print('• مزامنة الأسعار مع السيرفر')
    posts = []
    ctx = await b.new_context(viewport={"width": 1400, "height": 900})
    await ctx.add_init_script("if(!sessionStorage.getItem('x')){sessionStorage.setItem('x','1');localStorage.setItem('merzona-device-token','dev1');localStorage.setItem('merzona-access-status','approved');localStorage.setItem('merzona-price-memory', JSON.stringify({'uae|aed|Glass Room':'700'}));}")
    async def srv(route):
        u = route.request.url
        if u.endswith('/prices') and route.request.method == 'GET':
            return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'prices': {'syria|usd|Handrail (Hidden Glass)': {'v': '95', 'at': 1}}}))
        if u.endswith('/prices') and route.request.method == 'POST':
            posts.append(json.loads(route.request.post_data or '{}')); return await route.fulfill(status=200, content_type='application/json', body='{"ok":true}')
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else {}
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(6000)
    mem = await pg.evaluate("JSON.parse(localStorage.getItem('merzona-price-memory')||'{}')")
    check(mem.get('syria|usd|Handrail (Hidden Glass)') == '95', 'سعر السيرفر وصل للجهاز ' + str(mem))
    check(any('uae|aed|Glass Room' in (x.get('set') or {}) for x in posts), 'السعر القديم بالجهاز انرفع للسيرفر ' + str(posts))
    await pg.evaluate("(function(){ var i=ITEMS.findIndex(function(t){return t.en==='Glass Room'}); addQtyRow('1000','1000','1','',i); var rows=document.querySelectorAll('#qty-rows tr'); var pr=rows[rows.length-1].querySelector('.price'); pr.value='777'; onPriceInput(pr); })()")
    await pg.wait_for_timeout(2500)
    check(any('777' in (x.get('set') or {}).values() for x in posts), 'السعر الجديد انبعت للسيرفر ' + str(posts))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()

async def t_acct_en(p, b, port):
    """🌐 المحاسبة بالانكليزي: الواجهة مترجمة واتجاهها ltr، البيانات ما بتتغيّر، والعربي ما تأثّر."""
    print('• المحاسبة بالانكليزي')
    import subprocess, re as _re
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_acct.js'), sdir], stdout=subprocess.PIPE, text=True)
    aport = int(proc.stdout.readline().split()[1])
    try:
        async def mk(lang):
            ctx = await b.new_context(viewport={"width": 1300, "height": 900})
            await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','OWNERDEV'); localStorage.setItem('merzona-acct-book','syria');" + ("localStorage.setItem('mz-lang','en');" if lang == 'en' else "") + "}catch(e){}")
            async def fwd(route):
                u = route.request.url
                if '/access/status' in u: return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'status': 'approved', 'isOwner': True}))
                if '/acct/' in u or '/ai/' in u:
                    resp = await route.fetch(url=u.replace(SRV, f'http://127.0.0.1:{aport}'))
                    return await route.fulfill(response=resp)
                await route.fulfill(status=200, content_type='application/json', body='{}')
            await ctx.route(SRV + '/**', fwd)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.goto(f'http://127.0.0.1:{port}/accounting.html'); await pg.wait_for_timeout(2500)
            return ctx, pg, errs
        # عربي: متل ما كان
        ctx, pg, errs = await mk('ar')
        st = await pg.evaluate("[document.documentElement.dir, document.body.innerText.indexOf('المحاسبة')>=0, (document.querySelector('#mzLangSlot .mz-lang-btn')||{}).textContent]")
        check(st[0] == 'rtl' and st[1] and st[2] == 'EN', 'العربي متل ما هو، وفي زر EN ' + str(st))
        await ctx.close()
        # انكليزي: نسجّل سند قبض فيه اسم عربي ونتأكد إنو الاسم ما تترجم
        ctx, pg, errs = await mk('en')
        st = await pg.evaluate("[document.documentElement.dir, document.documentElement.lang, (document.querySelector('#mzLangSlot .mz-lang-btn')||{}).textContent]")
        check(st[0] == 'ltr' and st[1] == 'en' and st[2] == 'ع', 'الصفحة ltr وانكليزي، وزر ع للرجوع ' + str(st))
        await pg.evaluate("""(async function(){ var B=__acctT.S().book; })()""")
        views = ['home', 'docs', 'reports', 'accounts']
        leftovers = {}
        for v in ['#tabs button', 'nav button', '.tabs button']:
            pass
        btns = await pg.evaluate("Array.from(document.querySelectorAll('header button, nav button, .tabs button, .chip')).map(function(b){return b.textContent.trim()}).filter(Boolean).slice(0,30)")
        await pg.screenshot(path='/tmp/claude-0/acct-en-home.png', full_page=False)
        txt = await pg.evaluate("document.body.innerText")
        ar = _re.findall(r'[\u0621-\u064A][\u0621-\u064A ]*', txt)
        check(len(ar) <= 3, 'الصفحة الرئيسية شبه بلا عربي (' + str(len(ar)) + ') ' + ' | '.join(ar[:10]))
        # كل التبويبات + نموذج فاتورة
        tabs = await pg.evaluate("Array.from(document.querySelectorAll('[data-tab]')).map(function(b){return b.dataset.tab})")
        allar = {}
        for t in tabs:
            await pg.click(f'[data-tab="{t}"]'); await pg.wait_for_timeout(700)
            await pg.screenshot(path=f'/tmp/claude-0/acct-en-{t}.png', full_page=True)
            txt = await pg.evaluate("document.body.innerText")
            for a in _re.findall(r'[\u0621-\u064A][\u0621-\u064A ]*', txt):
                if a.strip() != 'ع': allar[a.strip()] = t
        txt_rep = ''
        await pg.click('[data-tab="reports"]') if 'reports' in tabs else None
        await pg.wait_for_timeout(500)
        txt_rep = await pg.evaluate("document.body.innerText")
        check(len(allar) == 0, 'كل التبويبات بلا عربي (' + str(len(allar)) + ') ' + str(list(allar.items())[:20]))
        check('Profit & loss' in txt_rep, 'أسماء التقارير بالانكليزي')
        await pg.click('[data-tab="home"]'); await pg.wait_for_timeout(500)
        await pg.click('text=Sales invoice'); await pg.wait_for_timeout(800)
        await pg.screenshot(path='/tmp/claude-0/acct-en-invoice.png', full_page=False)
        txt = await pg.evaluate("document.body.innerText")
        far = [a.strip() for a in _re.findall(r'[\u0621-\u064A][\u0621-\u064A ]*', txt) if a.strip() != 'ع']
        check(not far, 'نموذج الفاتورة بلا عربي ' + str(far[:15]))
        # تنبيه مترجم
        msg = await pg.evaluate("(function(){ var got=''; var o=window.__realAlert; return MZ_I18N.t('القيد مش موزون'); })()")
        check(msg == 'The entry is not balanced', 'رسائل التنبيه بتترجم')
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        await ctx.close()
        # رابط المحاسب ?lang=en بيفتح انكليزي وبيتذكّر
        ctx, pg, errs = await mk('ar')
        await pg.goto(f'http://127.0.0.1:{port}/accounting.html?lang=en'); await pg.wait_for_timeout(2500)
        check(await pg.evaluate("document.documentElement.dir") == 'ltr', 'رابط ?lang=en بيفتح انكليزي')
        await pg.goto(f'http://127.0.0.1:{port}/accounting.html'); await pg.wait_for_timeout(2000)
        check(await pg.evaluate("document.documentElement.dir") == 'ltr', 'وبيضل انكليزي بالمرات الجاية')
        await ctx.close()
    finally:
        proc.kill()

async def t_dash_en(p, b, port):
    """🌐 الداشبورد (العقود، الرواتب) والمشتريات بالانكليزي - بلا عربي بالواجهة، والعربي ما تأثّر."""
    print('• الداشبورد والمشتريات بالانكليزي')
    import re as _re
    async def mk(lang, page):
        ctx = await b.new_context(viewport={"width": 1400, "height": 900})
        await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','OWNERDEV');" + ("localStorage.setItem('mz-lang','en');" if lang == 'en' else "") + "}catch(e){}")
        async def srv(route):
            u = route.request.url
            body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else ({'isOwnerDevice': True} if '/users/status' in u else {})
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
        await ctx.route(SRV + '/**', srv)
        await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/{page}'); await pg.wait_for_timeout(3500)
        return ctx, pg, errs
    def leftovers(txt):
        names = ('ع', 'آية', 'أبو عبد الله', 'طلحة', 'علاء', 'نور')  # أسماء موظفين (بيانات) بتضل متل ما هي
        return sorted(set(a.strip() for a in _re.findall(r'[\u0621-\u064A][\u0621-\u064A ]*', txt) if a.strip() not in names))
    ctx, pg, errs = await mk('ar', 'Dashboard.html')
    st = await pg.evaluate("[document.documentElement.dir, (document.querySelector('#mzLangSlot .mz-lang-btn')||{}).textContent, document.body.innerText.indexOf('العقود')>=0]")
    check(st[0] == 'rtl' and st[1] == 'EN' and st[2], 'الداشبورد بالعربي متل ما هو + زر EN ' + str(st))
    await ctx.close()
    ctx, pg, errs = await mk('en', 'Dashboard.html')
    found = {}
    for fn, name in [('showContractsView', 'contracts'), ('showPayrollView', 'payroll'), ('showUsersView', 'users')]:
        await pg.evaluate(f"try{{ {fn}() }}catch(e){{}}"); await pg.wait_for_timeout(900)
        await pg.screenshot(path=f'/tmp/claude-0/dash-en-{name}.png', full_page=False)
        vis = await pg.evaluate("Array.from(document.querySelectorAll('.header, #contractsView, #payrollView, #usersView')).filter(function(e){return e.offsetParent!==null}).map(function(e){return e.innerText}).join('\\n')")
        for a in leftovers(vis): found.setdefault(a, name)
    print('LEFTOVERS_DASH', json.dumps(found, ensure_ascii=False))
    check(len(found) <= 5, 'الداشبورد (القوائم، العقود، الرواتب، المستخدمين) شبه بلا عربي: ' + str(len(found)))
    check(await pg.evaluate("document.documentElement.dir") == 'ltr', 'الداشبورد ltr')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()
    ctx, pg, errs = await mk('en', 'procurement.html')
    await pg.screenshot(path='/tmp/claude-0/proc-en.png', full_page=False)
    lf = leftovers(await pg.evaluate("document.body.innerText"))
    print('LEFTOVERS_PROC', json.dumps(lf, ensure_ascii=False))
    check(len(lf) <= 5, 'المشتريات شبه بلا عربي: ' + str(len(lf)))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()

async def t_auth_headers(p, b, port):
    """🔐 المسارات المحمية (قائمة العروض القديمة، قواعد المشتريات) بتنبعت مع هوية الجهاز والجلسة."""
    print('• هوية المستخدم بالمسارات المحمية')
    seen = {}
    ctx = await b.new_context(viewport={"width": 1300, "height": 900})
    await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','STAFFDEV1'); localStorage.setItem('merzona-session-token','SESS123'); }catch(e){}")
    async def srv(route):
        u = route.request.url; h = route.request.headers
        for k in ('dashboard-seed', 'procurement-rules'):
            if '/' + k in u: seen[k] = (h.get('x-device'), h.get('x-session'))
        body = {'status': 'approved'} if '/access/status' in u else ({'username': 'sami', 'permissions': {'dashboard': True, 'dashLog': True, 'procurement': True, 'quotation': True}} if '/users/me' in u else ([] if 'dashboard-seed' in u else {}))
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
    pg = await ctx.new_page(); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3500)
    await pg.evaluate("fetch('" + SRV + "/dashboard-seed?device=STAFFDEV1')")
    pp = await ctx.new_page(); await pp.goto(f'http://127.0.0.1:{port}/procurement.html'); await pp.wait_for_timeout(3000)
    await pp.evaluate("fetch('" + SRV + "/procurement-rules?device=STAFFDEV1')")
    await pg.wait_for_timeout(800)
    check(seen.get('dashboard-seed') == ('STAFFDEV1', 'SESS123'), 'قائمة العروض القديمة بتنطلب مع الجلسة ' + str(seen.get('dashboard-seed')))
    check(seen.get('procurement-rules') == ('STAFFDEV1', 'SESS123'), 'قواعد المشتريات بتنطلب مع الجلسة ' + str(seen.get('procurement-rules')))
    await ctx.close()

async def t_payroll_auto(p, b, port):
    """💵 راتب شهري ثابت بينزل لحاله أول كل شهر (آية 350$ من نيسان 2026)، بلا تكرار، والحذف بيضل محذوف."""
    print('• الراتب الشهري التلقائي')
    ctx = await b.new_context(viewport={"width": 1400, "height": 900})
    await ctx.add_init_script("""if(!sessionStorage.getItem('pa')){ sessionStorage.setItem('pa','1'); localStorage.setItem('merzona-device-token','OWNERDEV');
      localStorage.setItem('merzona_payroll_entries', JSON.stringify({ man1: { empId:'emp_aya', type:'monthly', month:'2026-05', amount:400, currency:'USD', note:'يدوي', paid:false, createdAt:1 } }));
      localStorage.setItem('merzona_payroll_payments', JSON.stringify({ p1: { empId:'emp_aya', amount:500, currency:'USD', date:'2026-06-01', createdAt:1 } })); }""")
    async def srv(route):
        u = route.request.url
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else {}
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3000)
    await pg.evaluate("showPayrollView()"); await pg.wait_for_timeout(800)
    now = await pg.evaluate("payrollMonthNow()")
    st = await pg.evaluate("""(function(){ var en = JSON.parse(localStorage.getItem('merzona_payroll_entries')); var aya = Object.values(en).filter(function(x){return x.empId==='emp_aya'});
      var e = JSON.parse(localStorage.getItem('merzona_payroll_employees')).emp_aya;
      return { months: aya.map(function(x){return x.month}).sort(), total: aya.reduce(function(a,x){return a+x.amount},0), auto: e.autoMonthly, start: e.salaryStart }; })()""")
    import datetime
    y, m = 2026, 4; exp = []
    while '%d-%02d' % (y, m) <= now: exp.append('%d-%02d' % (y, m)); m += 1; (y, m) = (y + 1, 1) if m > 12 else (y, m)
    check(st['auto'] and st['start'] == '2026-04', 'آية: راتب تلقائي من نيسان ' + str(st['start']))
    check(st['months'] == exp, 'شهر لكل شهر من نيسان لهلق بلا تكرار ' + str(st['months']))
    check(st['total'] == 400 + 350 * (len(exp) - 1), 'أيار اليدوي (400) ما انضاف فوقه، والباقي 350 ' + str(st['total']))
    due = await pg.evaluate("document.getElementById('payrollView').innerText")
    exp_due = 400 + 350 * (len(exp) - 1) - 500
    check(('{:,}'.format(exp_due) in due) or (str(exp_due) in due), 'المستحق بالملخص = الرواتب ناقص يلي انعطى (' + str(exp_due) + ')')
    # إعادة الفتح: ما بيتكرر
    await pg.reload(); await pg.wait_for_timeout(2500); await pg.evaluate("showPayrollView()"); await pg.wait_for_timeout(600)
    n2 = await pg.evaluate("Object.values(JSON.parse(localStorage.getItem('merzona_payroll_entries'))).filter(function(x){return x.empId==='emp_aya'}).length")
    check(n2 == len(exp), 'بعد إعادة الفتح ما في تكرار ' + str(n2))
    # حذف شهر تلقائي (إجازة) → ما بيرجع
    await pg.evaluate("document.querySelector('[data-delentry=\"pr_monthly_emp_aya_2026-06_0\"]').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("renderPayrollAll()"); await pg.wait_for_timeout(300)
    gone = await pg.evaluate("!JSON.parse(localStorage.getItem('merzona_payroll_entries'))['pr_monthly_emp_aya_2026-06_0'] && JSON.parse(localStorage.getItem('merzona_payroll_employees')).emp_aya.autoSkip.indexOf('2026-06')!==-1")
    check(gone, 'شهر محذوف بقصد ما بيرجع ينضاف لحاله')
    # جهاز مربوط بالمزامنة ولسا ما سحب: ما بينزل شي
    await pg.evaluate("localStorage.setItem('merzona_sync_connected','1'); window.__mzTeamPulledOnce=false; var en=JSON.parse(localStorage.getItem('merzona_payroll_entries')); delete en['pr_monthly_emp_aya_2026-07_0']; localStorage.setItem('merzona_payroll_entries', JSON.stringify(en)); renderPayrollAll();")
    held = await pg.evaluate("!JSON.parse(localStorage.getItem('merzona_payroll_entries'))['pr_monthly_emp_aya_2026-07_0']")
    check(held, 'قبل أول مزامنة بالجلسة ما بينزل رواتب على نسخة قديمة')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()

async def t_warranty_template(p, b, port):
    """🛡️ الضمانات حسب الفرع (سوريا بلا إلا بالمربع) + حقول قالب الواتس اب (ألمنيوم، زجاج، ضمانات، توريد، خصم)."""
    print('• الضمانات + حقول قالب عرض السعر')
    ctx = await new_ctx(p, b)
    async def srv(route):
        u = route.request.url
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else {}
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(3000)
    state = """(function(){ var vis=function(r){return getComputedStyle(r).display!=='none'};
      var acc=Array.from(document.querySelectorAll('#acc-rows .bi-row')); var notes=Array.from(document.querySelectorAll('#notes-rows .notes-item'));
      return { branch: document.getElementById('m-branch').value, on: document.getElementById('warranty-toggle').checked,
        accVis: acc.filter(vis).map(function(r){return r.querySelector('textarea').value}), notesWarranty: notes.filter(function(r){return /warranty/i.test(r.querySelector('textarea').value)}).map(vis),
        title: document.getElementById('acc-title-ar').textContent, rowVisible: getComputedStyle(document.getElementById('warranty-toggle-row')).display !== 'none' }; })()"""
    st = await pg.evaluate(state)
    check(st['branch'] == 'uae' and st['on'] and any('Warranty' in x for x in st['accVis']) and all(st['notesWarranty']), 'الإمارات: الضمانات ظاهرة افتراضيًا ' + str(st['accVis'][:3]))
    await pg.evaluate("document.getElementById('m-branch').value='syria'; onBranchChange()"); await pg.wait_for_timeout(300)
    st = await pg.evaluate(state)
    check(st['branch'] == 'syria' and not st['on'] and not any(('Warranty' in x or 'Years' in x or 'years' in x) for x in st['accVis']) and not any(st['notesWarranty']), 'سوريا: كل صفوف الضمانات مخفية ' + str(st['accVis']))
    check(any('Sillicon' in x for x in st['accVis']) and any('Screws' in x for x in st['accVis']), 'سوريا: الإكسسوارات العادية بتضل')
    check(st['title'] == 'الإكسسوارات', 'العنوان بسوريا بلا "الضمانات" ' + st['title'])
    pr = await pg.evaluate("(function(){ var w=window.open; return Array.from(document.querySelectorAll('#acc-rows .bi-row.mz-warranty-off')).length })()")
    await pg.emulate_media(media='print')
    hidden_print = await pg.evaluate("Array.from(document.querySelectorAll('#acc-rows .bi-row.mz-warranty-off')).every(function(r){return getComputedStyle(r).display==='none'}) && getComputedStyle(document.getElementById('warranty-toggle-row')).display==='none'")
    await pg.emulate_media(media='screen')
    check(pr >= 4 and hidden_print, 'بالطباعة كمان مخفية، والمربع ما بينطبع')
    await pg.evaluate("var t=document.getElementById('warranty-toggle'); t.checked=true; t.dispatchEvent(new Event('change'))"); await pg.wait_for_timeout(200)
    st = await pg.evaluate(state)
    check(st['on'] and any('Warranty' in x for x in st['accVis']) and st['title'] == 'الإكسسوارات و الضمانات', 'علّمت المربع بسوريا → رجعت الضمانات')
    # حفظ/فتح: الاختيار بيضل
    data = await pg.evaluate("captureFullQuotationData()")
    await pg.evaluate("resetAllNoConfirm()"); await pg.wait_for_timeout(200)
    await pg.evaluate("(d)=>applyFullQuotationData(d)", data); await pg.wait_for_timeout(400)
    st = await pg.evaluate(state)
    check(st['branch'] == 'syria' and st['on'], 'عرض سوريا محفوظ مع ضمانات بيفتح مع ضمانات')
    # مسودة واتس اب بحقول القالب
    await pg.evaluate("""(async function(){ await mzApplyWaDraft({ branch:'syria', currency:'usd', client:'أبو خالد', items:[{name:'Handrail (Hidden Glass)', w:12000, h:1000, qty:1, price:95}],
      aluminium:false, glassType:'guardian', warranty:null, deliveryDays:30, discountPct:5 }); })()"""); await pg.wait_for_timeout(500)
    st2 = await pg.evaluate("""({ alum: document.getElementById('alum-section-toggle').checked, alumHidden: document.getElementById('alum-section').classList.contains('section-hidden'),
      glass: document.getElementById('m-glassType').value, w: document.getElementById('warranty-toggle').checked, dd: document.getElementById('delivery-days').value, dp: document.getElementById('discount-pct').value,
      da: document.getElementById('discount-amount').value })""")
    check(st2['alum'] is False and st2['alumHidden'], 'ألمنيوم: لا → قسم الألمنيوم انشال')
    check(st2['glass'] == 'guardian' and st2['w'] is False and st2['dd'] == '30' and st2['dp'] == '5' and st2['da'] != '', 'الزجاج أمريكي، بلا ضمانات (سوريا)، توريد 30، خصم 5% انحسب ' + str(st2))
    await pg.evaluate("""(async function(){ await mzApplyWaDraft({ branch:'uae', currency:'aed', client:'Ali', items:[{name:'Glass Room', w:4000, h:3000, qty:1, price:''}], warranty:false, aluminium:true, alumColor:'9016' }); })()"""); await pg.wait_for_timeout(500)
    st3 = await pg.evaluate("({ w: document.getElementById('warranty-toggle').checked, alum: document.getElementById('alum-section-toggle').checked, color: document.getElementById('m-alumColor').value, banner: (document.getElementById('mzWaDraftBanner')||{}).textContent||'' })")
    check(st3['w'] is False and st3['alum'] is True, 'الإمارات + ضمانات 0 → بلا ضمانات ' + str(st3))
    check(('9016' in st3['color']) or ('لون الألمنيوم' in st3['banner']), 'لون الألمنيوم انختار أو في تنبيه واضح ' + str(st3['color']))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()

async def t_hr3d_toolbar(p, b, port):
    """🧊 زر "عرض ثري دي" فوق: الهاندريل يلي إلو مسقط بينرسم ثري دي حسب المسقط + المسقط تحته."""
    print('• زر الثري دي للهاندريل مع المسقط')
    ctx = await new_ctx(p, b); await ctx.add_init_script(THREE_STUB)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await open_tool(pg, port, [[7230, 1100, 'Glass Handrail for Balcony'], [1000, 2000, 'Aluminum Door with Glass']])
    await pg.evaluate("openDesignerFromToolbar()"); await pg.wait_for_timeout(1200)
    iid = await pg.evaluate("WD.__t.items()[0].id"); await pg.evaluate(f"WD.__t.sel({iid})"); await pg.wait_for_timeout(300)
    await pg.click('#btnHrPlanStart'); await pg.wait_for_timeout(400)
    segs = await pg.evaluate("WD.__t.items()[0].hrSegments.map(function(s){return s.id})")
    await pg.evaluate(f"onHrSegField({iid},'{segs[0]}','totalLength',6040); onHrSegField({iid},'{segs[0]}','panelCount',5); onHrSegField({iid},'{segs[1]}','totalLength',1190); onHrSegField({iid},'{segs[1]}','panelCount',1)")
    await pg.wait_for_timeout(300)
    await pg.evaluate("open3DPreview()"); await pg.wait_for_timeout(500)
    r = await pg.evaluate("""(function(){ var cards = Array.from(document.querySelectorAll('#threeDGrid .threeD-card')); var c = cards[0];
      var s3 = c && c.querySelector('.hr3d-plan-svg'); var pl = c && c.querySelector('.hr-plan-svg');
      return { cards: cards.length, has3d: !!s3, glass: s3 ? Array.from(s3.querySelectorAll('polygon')).filter(function(p){return /150,205,232/.test(p.getAttribute('fill'))}).length : 0,
        txt: s3 ? s3.textContent : '', plan: !!pl, other: cards[1] ? !cards[1].querySelector('.hr3d-plan-svg') && !!cards[1].querySelector('svg') : false,
        bbox: s3 ? [Math.round(s3.getBoundingClientRect().width), Math.round(s3.getBoundingClientRect().height)] : null }; })()""")
    await pg.screenshot(path='/tmp/claude-0/hr3d-toolbar.png', full_page=False)
    check(r['cards'] == 2 and r['has3d'] and r['plan'], 'الهاندريل: رسمة ثري دي حسب المسقط + المسقط تحتها ' + str(r))
    check(r['glass'] == 6, 'كل الألواح مرسومة (5 + 1) ' + str(r['glass']))
    check('6040' in r['txt'] and '1190' in r['txt'] and '7230' in r['txt'], 'أطوال الأضلاع والمجموع على الرسمة')
    check(r['bbox'] and r['bbox'][0] > 300 and r['bbox'][1] > 120, 'الرسمة بحجم واضح ' + str(r['bbox']))
    check(r['other'], 'البنود التانية (الباب) بتنرسم متل قبل')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()

async def t_save_speed(p, b, port):
    """⚡ حفظ عرض السعر لدرايف: الرفعات بنفس الوقت مع تجهيز الـPDF - كل الملفات بتنحفظ متل قبل وبوقت أقصر."""
    print('• سرعة حفظ عرض السعر لدرايف')
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    import subprocess, urllib.request, time as _t
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_drive.js'), sdir], stdout=subprocess.PIPE, text=True)
    try:
        fport = int(proc.stdout.readline().split()[1]); LOCAL = 'http://127.0.0.1:%d' % fport
        get = lambda pth: json.loads(urllib.request.urlopen(LOCAL + pth).read())
        UPL_DELAY = 1.2
        async def to_local(route):
            u = route.request.url
            try:
                if '/upload/' in u or '/__upload/' in u or 'uploadType' in u: await asyncio.sleep(UPL_DELAY)  # نت بطيء متل سوريا
                resp = await route.fetch(url=LOCAL + u[len(SRV):])
                await route.fulfill(response=resp)
            except Exception: pass  # الصفحة تسكّرت بنص الطلب
        ctx = await new_ctx(p, b)
        await ctx.add_init_script("localStorage.setItem('merzona-device-token','dev1');localStorage.setItem('merzona-session-token','s1');")
        for pat in ['/gdrive/**', '/team/**', '/gdrive-upload-session', '/quotes', '/quotes?*', '/quotes/**']:
            await ctx.route(SRV + pat, to_local)
        await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
        await ctx.add_init_script(FAKE_PDF.replace("toCanvas: async function(){", "toCanvas: async function(){ await new Promise(function(r){ setTimeout(r, 3000); });"))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""() => { const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); };
          set('m-ref', 'M-Q-260777'); set('m-client', 'زبون السرعة'); }""")
        t0 = _t.time()
        r = await pg.evaluate("async () => { try { await saveToGoogleDriveInner(); return 'ok'; } catch(e) { return String(e && e.message || e); } }")
        dt = _t.time() - t0
        names = [f['name'] for f in get('/__state')['files']]
        check(r == 'ok', 'الحفظ نجح ' + str(r))
        check('M-Q-260777.html' in names and 'M-Q-260777-data.json' in names and 'M-Q-260777.pdf' in names and any(n.startswith('M-Q-260777-نسخة-') for n in names), 'كل الملفات انحفظت: HTML + بيانات + سجل النسخ + PDF')
        data = json.loads(urllib.request.urlopen(LOCAL + '/__file/' + urllib.parse.quote('M-Q-260777-data.json')).read())
        check(data.get('fields', {}).get('m-client') == 'زبون السرعة', 'ملف البيانات فيه العرض الصح')
        # بالترتيب القديم: 4 رفعات × 1.2 + PDF 3 ثواني ≈ 7.8+ ثانية؛ هلق الرفعات بتمشي مع الـPDF
        check(dt < 7.0, 'الحفظ أسرع (الرفعات بنفس الوقت مع الـPDF): %.1f ثانية' % dt)
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        await ctx.close()
    finally:
        proc.kill()

# ⚡ 2026-11-16: الحفظ السريع (ثانيتين) + الرفع لدرايف بالخلفية - كل الحالات
def _start_fake_drive():
    import subprocess
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_drive.js'), sdir], stdout=subprocess.PIPE, text=True)
    fport = int(proc.stdout.readline().split()[1])
    return proc, 'http://127.0.0.1:%d' % fport

def _is_upload(u):
    return ('/upload/' in u) or ('gdrive-upload-session' in u) or ('/__upload/' in u)

async def _fast_ctx(p, b, LOCAL, ctl, mobile=False, real_pdf=False):
    """ctl: delay (ثواني لكل رفعة) / fail (عدد الرفعات يلي بتفشل؛ -1 = كلها) / wa (رسائل الواتساب يلي انبعتت) / log"""
    ctx = await new_ctx(p, b, mobile)
    async def to_local(route):
        u = route.request.url
        try:
            if _is_upload(u):
                ctl.setdefault('log', []).append(route.request.method + ' ' + u.split('?')[0][-40:])
                if ctl.get('delay'): await asyncio.sleep(ctl['delay'])
                if ctl.get('fail'):
                    if ctl['fail'] > 0: ctl['fail'] -= 1
                    ctl['failed'] = ctl.get('failed', 0) + 1
                    return await route.fulfill(status=503, body='{"error":"down"}')
                if ctl.get('swallow') and route.request.method == 'PATCH':  # الرفع وصل لجوجل بس الرد ضاع
                    ctl['swallow'] -= 1; ctl['swallowed'] = ctl.get('swallowed', 0) + 1
                    target = u if u.startswith(LOCAL) else LOCAL + u[len(SRV):]
                    await route.fetch(url=target)
                    return await route.fulfill(status=503, body='{"error":"lost"}')
            target = u if u.startswith(LOCAL) else LOCAL + u[len(SRV):]
            resp = await route.fetch(url=target)
            await route.fulfill(response=resp)
        except Exception: pass
    for pat in ['/gdrive/**', '/team/**', '/gdrive-upload-session', '/quotes', '/quotes?*', '/quotes/**']:
        await ctx.route(SRV + pat, to_local)
    await ctx.route(LOCAL + '/__upload/**', to_local)
    async def wa(route):
        try: ctl.setdefault('wa', []).append(json.loads(route.request.post_data or '{}'))
        except Exception: ctl.setdefault('wa', []).append({})
        await route.fulfill(status=200, content_type='application/json', body='{"ok":true}')
    await ctx.route(SRV + '/send-quotation', wa)
    await ctx.route(SRV + '/health', lambda r: r.fulfill(status=200, content_type='application/json', body='{"ok":true,"whatsappReady":true}'))
    if real_pdf:
        lib = os.path.join(os.environ.get('MZ_H2P', '/tmp/claude-0/-home-claude/763d6975-41b8-5b57-9416-4a2e9e40fbf3/scratchpad/h2p/dist'), 'html2pdf.bundle.min.js')
        await ctx.route('https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/**', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(lib, 'rb').read()))
    else:
        await ctx.add_init_script(FAKE_PDF.replace("toCanvas: async function(){", "toCanvas: async function(){ await new Promise(function(r){ setTimeout(r, window.__fakePdfMs || 1200); });"))
    await ctx.add_init_script("window.__mzDriveRetryWaits = [150, 300];")
    return ctx

async def _fast_page(ctx, port, ref, client, dialogs, answer=None):
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    def on_d(d):
        dialogs.append((d.type, d.message))
        ok = True if answer is None else answer[0]
        asyncio.ensure_future(d.accept() if ok else d.dismiss())
    pg.on('dialog', on_d)
    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate(ADD % json.dumps([[1200, 2100, 'Window'], [900, 2100, 'Door']]))
    await pg.evaluate("""([ref, client]) => { const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); };
      set('m-ref', ref); set('m-client', client); set('m-number', '0501112233');
      document.querySelectorAll('#qty-rows tr').forEach((tr, i) => { const n = tr.querySelector('.item-input'); if(n && !n.value){ n.value = ['Window', 'Door'][i] || 'Item'; n.dispatchEvent(new Event('input', {bubbles:true})); } }); }""", [ref, client])
    await pg.wait_for_timeout(300)
    return pg, errs

async def _status(pg):
    return await pg.evaluate("(() => { const e = document.getElementById('mzDriveStatus'); return e ? (e.dataset.state || '') + '|' + e.textContent : ''; })()")

async def _wait_status(pg, state, secs):
    for _ in range(int(secs * 10)):
        s = await _status(pg)
        if s.startswith(state + '|'): return s
        await pg.wait_for_timeout(100)
    return await _status(pg)

def _drive(LOCAL):
    import urllib.request
    return json.loads(urllib.request.urlopen(LOCAL + '/__state').read())['files']

def _dfile(LOCAL, name):
    import urllib.request, urllib.parse
    try: return urllib.request.urlopen(LOCAL + '/__file/' + urllib.parse.quote(name)).read()
    except Exception: return None

def _quotes(LOCAL):
    import urllib.request
    return json.loads(urllib.request.urlopen(LOCAL + '/__quotes').read())

async def t_fast_save(p, b, port):
    print('• ⚡ الحفظ السريع: "انحفظ" بثانيتين + الرفع لدرايف بالخلفية')
    import time as _t
    proc, LOCAL = _start_fake_drive()
    try:
        for _ in range(50):
            st = _quotes(LOCAL)['status']
            if not st.get('running') and not st.get('never'): break
            await asyncio.sleep(0.1)
        ctl = {'delay': 1.5}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl)
        pg, errs = await _fast_page(ctx, port, 'M-Q-260801', 'زبون أصلي', dialogs)
        # 1) كبسة زر الحفظ الحقيقي ← القفل بيبيّن ← "انحفظ" بأقل من ثانيتين
        t0 = _t.time()
        await pg.click('#driveSaveBtn')
        await pg.wait_for_timeout(150)
        locked = await pg.evaluate("!!document.getElementById('mzSaveLock')")
        s = await _wait_status(pg, 'busy', 5); t_fast = _t.time() - t0
        check(locked, 'وقت الحفظ الشاشة بتنقفل (ما بيتغيّر شي بالنص)')
        check(s.startswith('busy|') and t_fast < 2.0, '"✅ انحفظ" بأقل من ثانيتين: %.2f ثانية (النت بطيء: 1.5 ثانية لكل رفعة)' % t_fast)
        srv = _quotes(LOCAL)['items'].get('M-Q-260801') or {}
        check(srv.get('rev') == 1 and srv['data']['fields']['m-client'] == 'زبون أصلي', 'لحظة "انحفظ" العرض موجود عالسيرفر (نسخة 1)')
        pend = await pg.evaluate("JSON.parse(localStorage.getItem('merzona-drive-pending') || 'null')")
        check(pend and pend.get('ref') == 'M-Q-260801', 'علامة "لسا ما خلص رفعه" محفوظة بالمتصفح (لو تسكّرت الصفحة)')
        # 2) القفل بينشال بعد الـPDF (قبل ما يخلص الرفع) - وبيقدر يكمّل شغل
        for _ in range(60):
            if not await pg.evaluate("!!document.getElementById('mzSaveLock')"): break
            await pg.wait_for_timeout(100)
        t_unlock = _t.time() - t0
        st_now = await _status(pg)
        check(st_now.startswith('busy|'), 'الشاشة انفتحت بعد %.1f ثانية والرفع لسا شغال بالخلفية' % t_unlock)
        ev = await pg.evaluate("(() => { const e = new Event('beforeunload', {cancelable: true}); window.dispatchEvent(e); return e.defaultPrevented; })()")
        check(ev, 'إذا حاول يسكّر الصفحة والرفع شغال → المتصفح بيسأل')
        check(await pg.evaluate("window.__mzIsDriveSaveInFlight()"), 'فحص صلاحية الجهاز بيعرف إنو في حفظ شغال (ما بيعمل تحديث للصفحة بالنص)')
        # 3) بيعدّل بعد "انحفظ" والرفع شغال → درايف لازم ياخد النسخة يلي انحفظت، مش التعديل
        await pg.evaluate("() => { const e = document.getElementById('m-client'); e.value = 'تعديل بعد الحفظ'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        s = await _wait_status(pg, 'done', 30); t_full = _t.time() - t0
        check(s.startswith('done|'), 'الرفع لدرايف خلص بالخلفية (%.1f ثانية) وبيّنت "✅ خلص الرفع"' % t_full)
        data = json.loads(_dfile(LOCAL, 'M-Q-260801-data.json') or b'{}')
        html = (_dfile(LOCAL, 'M-Q-260801.html') or b'').decode('utf8', 'ignore')
        names = [f['name'] for f in _drive(LOCAL)]
        check(data.get('fields', {}).get('m-client') == 'زبون أصلي' and 'تعديل بعد الحفظ' not in html and 'زبون أصلي' in html, 'درايف فيه النسخة يلي انحفظت بالضبط (مش التعديل يلي صار بعدها)')
        check(data.get('quotationSavedAt') == srv['data'].get('quotationSavedAt'), 'نفس وقت الحفظ بدرايف وبالسيرفر')
        check('M-Q-260801.pdf' in names and sum(1 for n in names if n.startswith('M-Q-260801-نسخة-')) == 1, 'الـPDF + نسخة بسجل النسخ انرفعوا')
        check('id="mzSaveLock"' not in html and 'id="mzDriveStatus"' not in html, 'طبقة القفل والإشارة ما انحفظوا بنسخة الـHTML')
        await pg.wait_for_timeout(600)
        srv = _quotes(LOCAL)['items'].get('M-Q-260801') or {}
        row = next((x for x in _quotes(LOCAL)['list']['items'] if x['ref'] == 'M-Q-260801'), {})
        check(row.get('refFolderId') and row.get('url', '').startswith('https://drive.google.com/file/d/'), 'السيرفر سجّل مكان الملفات على درايف (finalize)')
        check(data.get('signBoxRect') is None or isinstance(data.get('signBoxRect'), dict), 'مكان صندوق التوقيع (إذا موجود) بملف البيانات')
        wa = ctl.get('wa') or []
        check(len(wa) == 1 and wa[0].get('client') == 'زبون أصلي' and wa[0].get('ref') == 'M-Q-260801' and len(wa[0].get('items') or []) >= 2, 'رسالة مجموعة الواتساب انبعتت مرة وحدة بمعلومات العرض يلي انحفظ ' + str([(w.get('client'), len(w.get('items') or [])) for w in wa]))
        pend = await pg.evaluate("localStorage.getItem('merzona-drive-pending')")
        check(pend is None, 'علامة "لسا ما خلص" انشالت')
        check(not await pg.evaluate("window.__mzIsDriveSaveInFlight()"), 'وبعد ما خلص: ما في حفظ شغال')
        ev = await pg.evaluate("(() => { const e = new Event('beforeunload', {cancelable: true}); window.dispatchEvent(e); return { prevented: e.defaultPrevented, dirty: window.__mzIsDirty && window.__mzIsDirty() }; })()")
        check(ev['dirty'] or not ev['prevented'], 'بعد ما يخلص الرفع: التسكير ما بيسأل إلا إذا في تعديل ما انحفظ')
        check(not [d for d in dialogs], 'ولا رسالة منبثقة بكل الحفظ ' + str(dialogs[:2]))
        # 4) حفظ تاني للتعديل، وفورًا حفظ تالت بدون تعديل (نفس الحفظة)
        ctl['delay'] = 1.0
        t0 = _t.time()
        await pg.click('#driveSaveBtn')
        s = await _wait_status(pg, 'busy', 5); t2 = _t.time() - t0
        for _ in range(60):
            if not await pg.evaluate("!!document.getElementById('mzSaveLock')"): break
            await pg.wait_for_timeout(100)
        revs_before = _quotes(LOCAL)['items']['M-Q-260801']['rev']
        await pg.click('#driveSaveBtn'); await pg.wait_for_timeout(500)
        revs_after = _quotes(LOCAL)['items']['M-Q-260801']['rev']
        check(t2 < 2.0 and revs_before == 2 and revs_after == 2, 'حفظ تاني بعد التعديل: %.2f ثانية (نسخة 2) - وكبسة حفظ تانية بدون تعديل ما بتعمل نسخة جديدة' % t2)
        s = await _wait_status(pg, 'done', 30)
        await pg.wait_for_timeout(600)
        data = json.loads(_dfile(LOCAL, 'M-Q-260801-data.json') or b'{}')
        names = [f['name'] for f in _drive(LOCAL)]
        cnt = lambda nm: sum(1 for n in names if n == nm)
        check(data.get('fields', {}).get('m-client') == 'تعديل بعد الحفظ' and cnt('M-Q-260801-data.json') == 1 and cnt('M-Q-260801.pdf') == 1 and cnt('M-Q-260801.html') == 1, 'درايف فيه آخر نسخة وما في ولا ملف مكرر')
        check(sum(1 for n in names if n.startswith('M-Q-260801-نسخة-')) == 2 and not dialogs, 'سجل النسخ فيه نسختين، بلا ولا سؤال ' + str(dialogs[:1]))
        # 5) حفظتين ورا بعض بسرعة (تعديل بين الاتنين) والرفع بطيء → التانية بتستنى الأولى، والنتيجة آخر نسخة
        ctl['delay'] = 1.5
        await pg.evaluate("() => { const e = document.getElementById('m-client'); e.value = 'نسخة 3'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        p1 = await pg.evaluate("() => { window.__r1 = runSaveToGoogleDriveInnerShared().then(()=>'ok', e=>String(e.message)); return 1; }")
        await pg.wait_for_timeout(50)
        await pg.evaluate("() => { const e = document.getElementById('m-client'); e.value = 'نسخة 4'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        await pg.evaluate("() => { window.__r2 = runSaveToGoogleDriveInnerShared().then(()=>'ok', e=>String(e.message)); return 1; }")
        r = await pg.evaluate("Promise.all([window.__r1, window.__r2])")
        await pg.wait_for_timeout(600)
        data = json.loads(_dfile(LOCAL, 'M-Q-260801-data.json') or b'{}')
        q = _quotes(LOCAL)['items']['M-Q-260801']
        names = [f['name'] for f in _drive(LOCAL)]
        check(r == ['ok', 'ok'] and q['rev'] == 4 and data['fields']['m-client'] == q['data']['fields']['m-client'], 'حفظتين بنفس اللحظة: الاتنين نجحوا (نسخة 4) ودرايف = السيرفر ' + str((r, q['rev'], data['fields'].get('m-client'), q['data']['fields'].get('m-client'))))
        check(sum(1 for n in names if n == 'M-Q-260801-data.json') == 1 and sum(1 for n in names if n == 'M-Q-260801.pdf') == 1 and not dialogs, 'وما في ملفات مكررة ولا أسئلة')
        check(not errs, 'بلا أخطاء بالصفحة ' + str(errs[:2]))
        await ctx.close()

        # 6) النت انقطع بنص الرفع (كل الرفعات بتفشل) ← "انحفظ" عالسيرفر + إشارة حمرا + أعد المحاولة
        ctl = {'delay': 0.2, 'fail': -1}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl)
        pg, errs = await _fast_page(ctx, port, 'M-Q-260802', 'زبون انقطاع', dialogs)
        t0 = _t.time(); await pg.click('#driveSaveBtn')
        s = await _wait_status(pg, 'busy', 5); t_fast = _t.time() - t0
        s = await _wait_status(pg, 'fail', 30)
        srv = _quotes(LOCAL)['items'].get('M-Q-260802') or {}
        check(t_fast < 2.0 and srv.get('rev') == 1, 'النت مقطوع عن درايف: "انحفظ" عالسيرفر بـ %.2f ثانية' % t_fast)
        check(s.startswith('fail|') and 'ما كمل' in s and any('انحفظ عالسيرفر' in m for _, m in dialogs), 'الرفع فشل بعد 3 محاولات ← إشارة حمرا + رسالة واضحة ' + s[:80])
        check(ctl.get('failed', 0) >= 3, 'جرّب كذا مرة قبل ما يستسلم (%d محاولة)' % ctl.get('failed', 0))
        ev = await pg.evaluate("(() => { const e = new Event('beforeunload', {cancelable: true}); window.dispatchEvent(e); return e.defaultPrevented; })()")
        pend = await pg.evaluate("JSON.parse(localStorage.getItem('merzona-drive-pending') || 'null')")
        check(ev and pend and pend['ref'] == 'M-Q-260802', 'الرفع فاشل: التسكير بيسأل + العلامة محفوظة')
        # الموظف بلّش عرض تاني بنفس الصفحة، والنت رجع، وكبس أعد المحاولة ← بيرفع العرض الأول (مش يلي مفتوح)
        await pg.evaluate("() => { const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); }; set('m-ref', 'M-Q-260803'); set('m-client', 'عرض تاني مفتوح'); }")
        ctl['fail'] = 0; nd = len(dialogs)
        await pg.click('#mzDriveRetryBtn')
        s = await _wait_status(pg, 'done', 30)
        await pg.wait_for_timeout(600)
        data = json.loads(_dfile(LOCAL, 'M-Q-260802-data.json') or b'{}')
        names = [f['name'] for f in _drive(LOCAL)]
        check(s.startswith('done|') and data.get('fields', {}).get('m-client') == 'زبون انقطاع' and 'M-Q-260802.pdf' in names and not any(n.startswith('M-Q-260803') for n in names), 'أعد المحاولة: رفع العرض الصح (يلي انحفظ) حتى لو فاتح عرض تاني')
        pend = await pg.evaluate("localStorage.getItem('merzona-drive-pending')")
        wa = ctl.get('wa') or []
        check(pend is None and len(wa) == 1 and wa[0].get('client') == 'زبون انقطاع' and len(dialogs) == nd, 'العلامة انشالت + رسالة الواتساب انبعتت للعرض الصح')
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        await ctx.close()

        # 7) نت متقطّع (أول رفعتين بيفشلوا) ← بيعيد لحاله وبينجح بلا أي رسالة
        ctl = {'delay': 0.2, 'fail': 2}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl)
        pg, errs = await _fast_page(ctx, port, 'M-Q-260804', 'زبون متقطع', dialogs)
        await pg.click('#driveSaveBtn')
        s = await _wait_status(pg, 'done', 30)
        names = [f['name'] for f in _drive(LOCAL)]
        check(s.startswith('done|') and ctl.get('failed') == 2 and 'M-Q-260804.pdf' in names and 'M-Q-260804-data.json' in names and not dialogs, 'نت متقطّع: فشلت رفعتين وأعاد لحاله ونجح بلا ولا رسالة')
        await ctx.close()

        # 8) الصفحة تسكّرت قبل ما يخلص الرفع ← أول ما تنفتح الأداة بتذكّر، وبكبسة بيكمّل
        ctl = {'delay': 0.2, 'fail': -1}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl)
        pg, errs = await _fast_page(ctx, port, 'M-Q-260805', 'زبون سكّر الصفحة', dialogs)
        await pg.click('#driveSaveBtn')
        await _wait_status(pg, 'busy', 5)
        await pg.wait_for_timeout(300)
        await pg.close()
        ctl['fail'] = 0
        pg2 = await ctx.new_page(); errs2 = []; pg2.on('pageerror', lambda e: errs2.append(str(e)[:200]))
        dialogs2 = []; pg2.on('dialog', lambda d: (dialogs2.append(d.message), asyncio.ensure_future(d.accept())))
        await pg2.goto(f'http://127.0.0.1:{port}/index.html')
        s = await _wait_status(pg2, 'fail', 12)
        check(s.startswith('fail|') and 'M-Q-260805' in s, 'فتح الأداة من جديد: "آخر حفظ للعرض ما خلص رفعه" مع زر يكمّل ' + s[:90])
        await pg2.click('#mzDriveRetryBtn')
        s = await _wait_status(pg2, 'done', 40)
        await pg2.wait_for_timeout(600)
        data = json.loads(_dfile(LOCAL, 'M-Q-260805-data.json') or b'{}')
        names = [f['name'] for f in _drive(LOCAL)]
        pend = await pg2.evaluate("localStorage.getItem('merzona-drive-pending')")
        check(s.startswith('done|') and data.get('fields', {}).get('m-client') == 'زبون سكّر الصفحة' and 'M-Q-260805.pdf' in names and pend is None, 'بكبسة وحدة: جاب العرض من السيرفر وكمّل رفعه لدرايف')
        check(_quotes(LOCAL)['items']['M-Q-260805']['rev'] == 2 and not [m for m in dialogs2 if 'جهاز تاني' in m or 'مسبق' in m], 'بلا تحذير "انعدّل من جهاز تاني" (نفس النسخة) ' + str(dialogs2[:2]))
        check(not errs2, 'بلا أخطاء ' + str(errs2[:2]))
        await ctx.close()

        # 9) جهاز تاني فتح العرض من درايف (أقدم) والسيرفر عندو أحدث ← بيعرض الأحدث
        ctl = {'delay': 0, 'fail': -1}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl)
        pg, errs = await _fast_page(ctx, port, 'M-Q-260801', 'نسخة 5 بالسيرفر بس', dialogs)
        await pg.evaluate("() => { window.__quotationSavedAtBaseline = %d; window.__mzOwnedRefSafe = 'M-Q-260801'; }" % int(json.loads(_dfile(LOCAL, 'M-Q-260801-data.json'))['quotationSavedAt']))
        await pg.click('#driveSaveBtn'); await _wait_status(pg, 'fail', 30)
        await ctx.close()
        older = json.loads(_dfile(LOCAL, 'M-Q-260801-data.json'))
        ctx = await _fast_ctx(p, b, LOCAL, {'delay': 0})
        await ctx.add_init_script("if(!sessionStorage.getItem('mzOnce')){ sessionStorage.setItem('mzOnce','1'); localStorage.setItem('merzona-pending-load', %s); localStorage.removeItem('merzona-drive-pending'); }" % json.dumps(json.dumps(older)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        dialogs = []; pg.on('dialog', lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.accept())))
        await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(5000)
        cl = await pg.evaluate("document.getElementById('m-client').value")
        check(not [m for m in dialogs if 'نسخة أحدث' in m] and cl == 'نسخة 5 بالسيرفر بس', 'فتح من درايف نسخة أقدم من السيرفر ← فتح الأحدث لحالو بلا ما يسأل')
        # ونفس الشي بس النسخة مطابقة ← ما بيسأل
        await ctx.close()
        ctx = await _fast_ctx(p, b, LOCAL, {'delay': 0})
        same = dict(older); same['quotationSavedAt'] = _quotes(LOCAL)['items']['M-Q-260801']['data']['quotationSavedAt']
        await ctx.add_init_script("if(!sessionStorage.getItem('mzOnce')){ sessionStorage.setItem('mzOnce','1'); localStorage.setItem('merzona-pending-load', %s); localStorage.removeItem('merzona-drive-pending'); }" % json.dumps(json.dumps(same)))
        pg = await ctx.new_page(); dialogs = []; pg.on('dialog', lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.accept())))
        await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(5000)
        check(not [m for m in dialogs if 'نسخة أحدث' in m], 'النسخة مطابقة للسيرفر ← ما بيسأل شي')
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        await ctx.close()

        # 10) السيرفر مقطوع ← الحفظ بيكمّل متل قبل بالضبط (بيستنى درايف ورسالة "تم الحفظ لجوجل درايف")
        import urllib.request
        urllib.request.urlopen(LOCAL + '/__quotes-off')
        ctl = {'delay': 0.2}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl)
        pg, errs = await _fast_page(ctx, port, 'M-Q-260806', 'زبون بلا سيرفر', dialogs)
        await pg.click('#driveSaveBtn')
        for _ in range(150):
            if any('تم الحفظ لجوجل درايف بنجاح' in m for _, m in dialogs): break
            await pg.wait_for_timeout(100)
        urllib.request.urlopen(LOCAL + '/__quotes-on')
        names = [f['name'] for f in _drive(LOCAL)]
        pend = await pg.evaluate("localStorage.getItem('merzona-drive-pending')")
        check(any('تم الحفظ لجوجل درايف بنجاح' in m for _, m in dialogs) and 'M-Q-260806.pdf' in names and 'M-Q-260806-data.json' in names and pend is None, 'السيرفر مقطوع: الحفظ متل قبل (بيخلص كامل وبعدين "تم الحفظ")')
        check(len(ctl.get('wa') or []) == 1 and not errs, 'ورسالة الواتساب انبعتت، بلا أخطاء')
        await ctx.close()

        # 11) "أرسل للزبون" بعد الحفظ والرفع لسا شغال ← بيستنى الرفع يخلص قبل ما يعطي الرابط
        ctl = {'delay': 1.5}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl)
        pg, errs = await _fast_page(ctx, port, 'M-Q-260807', 'زبون مشاركة', dialogs)
        await pg.click('#driveSaveBtn'); await _wait_status(pg, 'busy', 5)
        for _ in range(60):
            if not await pg.evaluate("!!document.getElementById('mzSaveLock')"): break
            await pg.wait_for_timeout(100)
        r = await pg.evaluate("""async () => { const before = (window.__mzLastSavedSig === mzQuoteSig()); await shareQuotationToClient(); return { before, modal: !!document.getElementById('mzShareModal'), saved: window.__mzLastSavedSig === mzQuoteSig() }; }""")
        names = [f['name'] for f in _drive(LOCAL)]
        check(not r['before'] and r['modal'] and r['saved'] and 'M-Q-260807.pdf' in names and 'M-Q-260807-data.json' in names, 'أرسل للزبون: استنى الرفع يخلص (الـPDF وملف البيانات بدرايف) وبعدين فتح المشاركة ' + str(r))
        check(_quotes(LOCAL)['items']['M-Q-260807']['rev'] == 1 and not errs, 'وما عمل حفظة زيادة، بلا أخطاء')
        await ctx.close()

        # 12) الموبايل: نفس الشي + الشاشة بترجع متل ما كانت (viewport)
        ctl = {'delay': 0.5}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl, mobile=True)
        pg, errs = await _fast_page(ctx, port, 'M-Q-260808', 'زبون موبايل', dialogs)
        vp0 = await pg.evaluate("document.querySelector('meta[name=viewport]').getAttribute('content')")
        t0 = _t.time(); await pg.evaluate("saveToGoogleDrive({ target: document.getElementById('driveSaveBtn') })")
        s = await _wait_status(pg, 'busy', 5); t_fast = _t.time() - t0
        s = await _wait_status(pg, 'done', 30)
        vp1 = await pg.evaluate("document.querySelector('meta[name=viewport]').getAttribute('content')")
        mob = await pg.evaluate("document.body.classList.contains('mode-mobile') + '|' + document.body.classList.contains('pdf-capturing')")
        check(t_fast < 2.0 and s.startswith('done|') and vp0 == vp1 and not mob.endswith('true'), 'الموبايل: "انحفظ" بـ %.2f ثانية، الرفع خلص، والشاشة رجعت متل ما كانت' % t_fast)
        check(not errs and not dialogs, 'بلا أخطاء ولا رسائل ' + str((errs[:1], dialogs[:1])))
        await ctx.close()

        # 13) الـPDF فشل بعد "انحفظ" ← رسالة واضحة + أعد المحاولة بيعيد الحفظ كامل
        ctl = {'delay': 0.2}; dialogs = []
        ctx = await _fast_ctx(p, b, LOCAL, ctl)
        await ctx.add_init_script("(function(){ var t = setInterval(function(){ if(window.html2pdf && !window.__wrapped){ window.__wrapped = 1; var o = window.html2pdf; window.html2pdf = function(){ var w = o.apply(this, arguments); var tc = w.toCanvas; w.toCanvas = async function(){ if(window.__breakPdf) throw new Error('canvas boom'); return tc.apply(this, arguments); }; return w; }; clearInterval(t); } }, 20); })();")
        pg, errs = await _fast_page(ctx, port, 'M-Q-260809', 'زبون PDF فاشل', dialogs)
        await pg.evaluate("window.__breakPdf = true")
        await pg.click('#driveSaveBtn')
        s = await _wait_status(pg, 'fail', 15)
        locked = await pg.evaluate("!!document.getElementById('mzSaveLock')")
        check(s.startswith('fail|') and 'M-Q-260809' in s and any('PDF' in m and 'انحفظ عالسيرفر' in m for _, m in dialogs) and not locked, 'الـPDF فشل بعد "انحفظ": رسالة واضحة + إشارة حمرا والشاشة مش مقفولة ' + s[:70])
        pend = await pg.evaluate("JSON.parse(localStorage.getItem('merzona-drive-pending') || 'null')")
        check(pend and pend['ref'] == 'M-Q-260809', 'والعلامة باقية لحتى يكمل')
        await pg.evaluate("window.__breakPdf = false")
        await pg.click('#mzDriveRetryBtn')
        s = await _wait_status(pg, 'done', 30)
        await pg.wait_for_timeout(600)
        names = [f['name'] for f in _drive(LOCAL)]
        pend = await pg.evaluate("localStorage.getItem('merzona-drive-pending')")
        check(s.startswith('done|') and 'M-Q-260809.pdf' in names and pend is None and not [m for _, m in dialogs if 'جهاز تاني' in m], 'أعد المحاولة: انعمل الـPDF وانرفع كل شي، بلا تحذير تعارض')
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        # 14) الرفع وصل لجوجل بس الرد ضاع ← إعادة المحاولة ما بتطلّع تحذير "جهاز تاني" غلط
        await pg.evaluate("() => { const e = document.getElementById('m-client'); e.value = 'رد ضايع'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        ctl['swallow'] = 3; n0 = len(dialogs)
        await pg.click('#driveSaveBtn')
        await _wait_status(pg, 'busy', 5)
        s = await _wait_status(pg, 'done', 30)
        await pg.wait_for_timeout(600)
        data = json.loads(_dfile(LOCAL, 'M-Q-260809-data.json') or b'{}')
        check(ctl.get('swallowed', 0) >= 1 and s.startswith('done|') and data['fields']['m-client'] == 'رد ضايع' and len(dialogs) == n0, 'الرد ضاع %d مرة: أعاد بهدوء، بلا تحذير غلط ' % ctl.get('swallowed', 0) + str(dialogs[n0:][:1]))
        # 15) حفظتين ورا بعض: الإشارة ما بتقول "خلص" إلا لما يخلصوا التنين
        ctl['delay'] = 1.2
        await pg.evaluate("() => { const e = document.getElementById('m-client'); e.value = 'أ'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        await pg.click('#driveSaveBtn'); await _wait_status(pg, 'busy', 5)
        for _ in range(60):
            if not await pg.evaluate("!!document.getElementById('mzSaveLock')"): break
            await pg.wait_for_timeout(100)
        await pg.evaluate("() => { const e = document.getElementById('m-client'); e.value = 'ب'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        await pg.click('#driveSaveBtn')
        seen = []
        for _ in range(400):
            st = await _status(pg); seen.append((await pg.evaluate("window.__mzIsDriveSaveInFlight()"), st.split('|')[0]))
            if st.startswith('done|') or not st: break
            await pg.wait_for_timeout(50)
        bad = [x for x in seen if x[1] == 'done' and x[0]]
        data = json.loads(_dfile(LOCAL, 'M-Q-260809-data.json') or b'{}')
        check(seen and seen[-1][1] == 'done' and not bad and data['fields']['m-client'] == 'ب', '"✅ خلص" بس لما يخلص آخر رفع (ودرايف فيه آخر نسخة)')
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        await ctx.close()
    finally:
        proc.kill()

async def t_fast_save_real_pdf(p, b, port):
    """نفس عرض السعر بمكتبة الـPDF الحقيقية: النسخة الجديدة لازم تطلّع نفس الـPDF يلي كانت تطلعو القديمة"""
    print('• ⚡ الحفظ السريع: الـPDF الحقيقي متل قبل بالضبط')
    lib = os.path.join(os.environ.get('MZ_H2P', '/tmp/claude-0/-home-claude/763d6975-41b8-5b57-9416-4a2e9e40fbf3/scratchpad/h2p/dist'), 'html2pdf.bundle.min.js')
    if not os.path.isfile(lib): print('  SKIP ما لقيت مكتبة html2pdf'); return
    old_html = os.environ.get('MZ_OLD_INDEX')
    proc, LOCAL = _start_fake_drive()
    try:
        out = {}
        for label, path in [('new', 'index.html'), ('old', 'index-old.html' if old_html else None)]:
            if not path: continue
            ctl = {'delay': 0}; dialogs = []
            ctx = await _fast_ctx(p, b, LOCAL, ctl, real_pdf=True)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
            pg.on('dialog', lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.accept())))
            await pg.goto(f'http://127.0.0.1:{port}/{path}'); await pg.wait_for_timeout(3000)
            await pg.evaluate(ADD % json.dumps([[1200, 2100, 'Window'], [900, 2100, 'Door'], [3000, 1000, 'Handrail (Hidden Glass)']]))
            ref = 'M-Q-26090' + ('1' if label == 'new' else '2')
            await pg.evaluate("""([ref]) => { const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); };
              set('m-ref', ref); set('m-client', 'زبون PDF حقيقي'); set('m-number', '0501112233'); }""", [ref])
            await pg.wait_for_timeout(500)
            import time as _t
            t0 = _t.time()
            r = await pg.evaluate("async () => { try { const x = await saveToGoogleDriveInner(); return { ok: true, n: x.pdfBlob.size, head: await x.pdfBlob.slice(0, 8).text() }; } catch(e) { return { ok: false, e: String(e && e.message || e) }; } }")
            dt = _t.time() - t0
            pdf = _dfile(LOCAL, ref + '.pdf') or b''
            if os.environ.get('MZ_DUMP_PDF'): open(os.path.join(os.environ['MZ_DUMP_PDF'], label + '.pdf'), 'wb').write(pdf)
            pages = pdf.count(b'/Type /Page') - pdf.count(b'/Type /Pages')
            data = json.loads(_dfile(LOCAL, ref + '-data.json') or b'{}')
            out[label] = {'ok': r.get('ok'), 'size': len(pdf), 'pages': pages, 'sign': data.get('signBoxRect'), 'dt': dt, 'errs': errs, 'dialogs': dialogs, 'r': r}
            await ctx.close()
        n = out['new']
        check(n['ok'] and n['size'] > 20000 and n['pages'] >= 1 and n['r'].get('head', '').startswith('%PDF'), 'الـPDF الحقيقي انعمل وانرفع (%d صفحة، %d كيلو، %.1f ثانية)' % (n['pages'], n['size'] // 1024, n['dt']))
        check(isinstance(n['sign'], dict) and all(k in n['sign'] for k in ('pageIndex', 'xMm', 'yMm', 'wMm', 'hMm')), 'مكان صندوق التوقيع انحفظ بملف البيانات (للتوقيع الإلكتروني) ' + str(n['sign']))
        if 'old' in out:
            o = out['old']
            check(o['ok'] and n['pages'] == o['pages'], 'نفس عدد الصفحات متل النسخة القديمة (%d = %d)' % (n['pages'], o['pages']))
            check(abs(n['size'] - o['size']) <= max(4096, o['size'] * 0.02), 'نفس حجم الـPDF تقريبًا متل القديمة (%d / %d كيلو)' % (n['size'] // 1024, o['size'] // 1024))
            so, sn = o['sign'] or {}, n['sign'] or {}
            check(so and all(abs(float(so[k]) - float(sn[k])) < 0.01 for k in ('xMm', 'yMm', 'wMm', 'hMm')) and so['pageIndex'] == sn['pageIndex'], 'مكان صندوق التوقيع نفسه بالضبط متل القديمة')
        check(not n['errs'] and not n['dialogs'], 'بلا أخطاء ولا رسائل ' + str((n['errs'][:1], n['dialogs'][:1])))
    finally:
        proc.kill()


async def t_print_titles(p, b, port):
    """🏷️ اسم ملف الـPDF وقت الطباعة: Sketch / 3D Sketch + رقم العرض - حتى لما الأداة جوا لوحة التحكم (عنوانها Merzona)"""
    print('• اسم ملف السكتش والثري دي وعرض السعر وقت الحفظ كـPDF')
    ctx = await new_ctx(p, b)
    await ctx.add_init_script("window.__titles = []; window.print = function(){ var t = null; try{ t = window.top.document.title; }catch(e){} window.__titles.push({ self: document.title, top: t }); };")
    host = f'http://127.0.0.1:{port}/__host.html'
    await ctx.route(host, lambda r: r.fulfill(status=200, content_type='text/html', body='<!doctype html><html><head><title>Merzona</title></head><body style="margin:0"><iframe id="f" src="index.html" style="width:1400px;height:900px;border:0"></iframe></body></html>'))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(host); await pg.wait_for_timeout(3500)
    fr = pg.frame_locator('#f'); f = pg.frames[1]
    await f.evaluate(ADD % json.dumps([[1200, 2100, 'Window'], [3000, 1000, 'Handrail (Hidden Glass)']]))
    await f.evaluate("""() => { const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); }; set('m-ref', 'M-Q-260555'); set('m-client', 'زبون تجربة'); }""")
    await f.wait_for_timeout(400)
    async def run(js, wait=900):
        await f.evaluate("window.__titles = []")
        await f.evaluate(js); await f.wait_for_timeout(wait)
        t = await f.evaluate("window.__titles.slice()")
        await f.evaluate("window.dispatchEvent(new Event('afterprint'))"); await f.wait_for_timeout(150)
        after = {'self': await f.evaluate("document.title"), 'top': await pg.evaluate("document.title")}
        return (t[-1] if t else {}), after
    t, after = await run("preparePrint()")
    check(t.get('self') == 'Sketch - M-Q-260555' and t.get('top') == 'Sketch - M-Q-260555', 'طباعة السكتش جوا لوحة التحكم: اسم الملف "Sketch - M-Q-260555" ' + str(t))
    check(after['top'] == 'Merzona' and after['self'] == 'M-Q-260555 - زبون تجربة', 'بعد الطباعة العناوين رجعت متل ما كانت ' + str(after))
    t, after = await run("open3DPreview(); print3DPreview()")
    check(t.get('self') == '3D Sketch - M-Q-260555' and t.get('top') == '3D Sketch - M-Q-260555', 'طباعة الثري دي: "3D Sketch - M-Q-260555" ' + str(t))
    await f.evaluate("close3DPreview()")
    t, after = await run("printMfgSizes()")
    check(t.get('self') == 'Sketch (Manufacturing Sizes) - M-Q-260555', 'طباعة مقاسات التصنيع: "Sketch (Manufacturing Sizes) - M-Q-260555" ' + str(t))
    t, after = await run("collectPrintWarnings = function(){ return []; }; doPrint()", 1500)
    check(t.get('self') == 'M-Q-260555 - زبون تجربة' and t.get('top') == 'M-Q-260555 - زبون تجربة', 'طباعة عرض السعر: "رقم العرض - الزبون" (مش Merzona) ' + str(t))
    check(after['top'] == 'Merzona', 'ولوحة التحكم رجع عنوانها')
    # الأداة لحالها (مش جوا لوحة التحكم)
    pg2 = await ctx.new_page(); pg2.on('pageerror', lambda e: errs.append(str(e)[:200])); pg2.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg2.goto(f'http://127.0.0.1:{port}/index.html'); await pg2.wait_for_timeout(2500)
    await pg2.evaluate(ADD % json.dumps([[1200, 2100, 'Window']]))
    await pg2.evaluate("""() => { const e = document.getElementById('m-ref'); e.value = 'M-Q-260556'; e.dispatchEvent(new Event('input', {bubbles:true})); }""")
    await pg2.evaluate("window.__titles = []; preparePrint()"); await pg2.wait_for_timeout(900)
    t = await pg2.evaluate("window.__titles.slice()")
    check(t and t[-1]['self'] == 'Sketch - M-Q-260556', 'الأداة لحالها: نفس الشي "Sketch - M-Q-260556" ' + str(t[-1:] if t else t))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_dash_accountant(p, b, port):
    """👤 حساب المحاسب (بس محاسبة، بلا جوجل درايف): ما في رسائل غلط ("الجهاز مش معتمد" / "اربط جوجل درايف")"""
    print('• حساب المحاسب بالداشبورد: بلا رسائل غلط')
    async def mk(seed_status, seed_body):
        ctx = await b.new_context(viewport={"width": 1400, "height": 900})
        await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','ACCDEV'); localStorage.removeItem('merzona_sync_banner_dismissed'); localStorage.removeItem('merzona_sync_connected'); }catch(e){}")
        async def srv(route):
            u = route.request.url
            if '/dashboard-seed' in u:
                return await route.fulfill(status=seed_status, content_type='application/json', body=json.dumps(seed_body))
            body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else ({'isOwnerDevice': True} if '/users/status' in u else {})
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
        await ctx.route(SRV + '/**', srv)
        await ctx.route('https://merzona-server-production.up.railway.app/**', srv)
        await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3500)
        return ctx, pg, errs
    ctx, pg, errs = await mk(403, {'error': 'no-permission'})
    await pg.evaluate("window.applyMerzonaPermissions({ dashboard: true, accounting: true }, false); showSyncBannerIfNeeded();")
    await pg.wait_for_timeout(300)
    st = await pg.evaluate("""({ acct: getComputedStyle(document.getElementById('accountingTabBtn')).display !== 'none',
        banner: document.getElementById('syncBanner').classList.contains('show'),
        warn: (document.getElementById('mzSeedWarn') || {}).textContent || '', warnShown: !!(document.getElementById('mzSeedWarn') && document.getElementById('mzSeedWarn').offsetParent) })""")
    check(st['acct'], 'المحاسب بيشوف تبويب المحاسبة')
    check(not st['banner'], 'ما بتطلعلو رسالة "اربط حسابك بجوجل درايف" (ما بيحتاجها)')
    check(not st['warnShown'] or 'معتمد' not in st['warn'], 'ما بتطلع رسالة "هالجهاز مش معتمد" الغلط ' + str(st['warn'][:60]))
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()
    # جهاز فعلاً مش معتمد (401) ← الرسالة لازم تضل تطلع
    ctx, pg, errs = await mk(401, {'error': 'unauthorized'})
    await pg.wait_for_timeout(500)
    w = await pg.evaluate("(document.getElementById('mzSeedWarn') || {}).textContent || ''")
    check('معتمد' in w, 'جهاز فعلاً مش معتمد: الرسالة بتضل تطلع ' + w[:60])
    # المالك (عندو كل الصلاحيات) ← رسالة الربط بدرايف بتضل متل قبل
    await pg.evaluate("localStorage.removeItem('merzona_sync_banner_dismissed'); localStorage.removeItem('merzona_sync_connected'); window.applyMerzonaPermissions(null, true); showSyncBannerIfNeeded();")
    b2 = await pg.evaluate("document.getElementById('syncBanner').classList.contains('show')")
    check(b2, 'المالك: رسالة ربط درايف متل قبل')
    await ctx.close()


async def t_quote_status(p, b, port):
    """🎯 حالة العروض: الأداة بتسجّل "انبعت"، صفحة التوقيع بتعرّف أجهزة الشركة، ولوحة المبيعات بالداشبورد"""
    print('• 🎯 حالة العروض والمبيعات')
    import datetime as _dt
    # 1) الأداة: كل طرق الإرسال بتسجّل "انبعت"
    ctx = await new_ctx(p, b)
    sent = []
    async def qs(route):
        try: sent.append(json.loads(route.request.post_data or '{}') | {'_dev': route.request.headers.get('x-device', '')})
        except Exception: sent.append({})
        await route.fulfill(status=200, content_type='application/json', body='{"ok":true,"status":{}}')
    await ctx.route(SRV + '/quote-status/sent', qs)
    await ctx.add_init_script("localStorage.setItem('merzona-device-token','DEV9');")
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("window.open = function(){ return null; }")
    await pg.evaluate("mzShareModal({ ref: 'M-Q-260401', text: 'مرحبا', phone: '0501112233', wa: 'https://wa.me/971501112233?text=x', file: null })")
    await pg.click('#mzShareModal button >> nth=0'); await pg.wait_for_timeout(400)
    await pg.evaluate("mzShareModal({ ref: 'M-Q-260402', text: 'مرحبا', phone: '', wa: '', file: null })")
    await pg.evaluate("navigator.clipboard.writeText = async function(){}")
    await pg.click("#mzShareModal button:has-text('انسخ الرسالة')"); await pg.wait_for_timeout(400)
    cancelled_before = len(sent)
    await pg.evaluate("mzShareModal({ ref: 'M-Q-260403', text: 'x', phone: '', wa: '', file: null })")
    await pg.click("#mzShareModal button:has-text('إلغاء')"); await pg.wait_for_timeout(300)
    got = [(x.get('ref'), x.get('via'), x.get('_dev')) for x in sent]
    check(('M-Q-260401', 'whatsapp', 'DEV9') in got and ('M-Q-260402', 'copy', 'DEV9') in got, 'زر الواتساب ونسخ الرسالة بيسجّلوا "انبعت" (مع هوية الجهاز) ' + str(got))
    check(len(sent) == cancelled_before, '"إلغاء" ما بيسجّل شي')
    await pg.route(SRV + '/quote-status/sent', lambda r: r.fulfill(status=500, body='x'))
    await pg.evaluate("mzMarkQuoteSent('M-Q-260404', 'copy')"); await pg.wait_for_timeout(300)
    check(not errs, 'إذا السيرفر فشل ما بيصير ولا خطأ ' + str(errs[:2]))
    await ctx.close()
    # 2) صفحة التوقيع: من جهاز الشركة بتبعت هوية الجهاز، من جهاز الزبون لأ
    for staff in (True, False):
        ctx = await b.new_context(); hdrs = []
        async def sg(route):
            hdrs.append(route.request.headers.get('x-device'))
            await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'ref': 'M-Q-260401', 'client': 'ز', 'total': 5, 'signed': False}))
        await ctx.route('https://merzona-server-production.up.railway.app/sign/**', sg)
        if staff: await ctx.add_init_script("localStorage.setItem('merzona-device-token','DEV9');")
        pg = await ctx.new_page(); await pg.goto(f'http://127.0.0.1:{port}/sign.html?ref=M-Q-260401&t=TOK'); await pg.wait_for_timeout(1500)
        check((hdrs[:1] == ['DEV9']) if staff else (hdrs[:1] == [None]), ('صفحة التوقيع من جهاز الشركة: بتعرّف حالها' if staff else 'صفحة التوقيع عند الزبون: ما في أي هوية') + ' ' + str(hdrs))
        await ctx.close()
    # 3) لوحة المبيعات بالداشبورد
    today = _dt.date.today(); iso = today.isoformat(); old = '2026-10-01'
    items = {
        'M-Q-260501': {'sentAt': 1, 'sentBy': 'سامي'},
        'M-Q-260502': {'sentAt': 1, 'viewedAt': 2, 'lastViewedAt': 9e12, 'views': 3},
        'M-Q-260503': {'sentAt': 1, 'viewedAt': 2, 'signedAt': 3, 'signerName': 'ز'},
        'M-Q-260504': {'sentAt': 1, 'rejectedAt': 4, 'rejectReason': 'غالي'},
    }
    ctx = await b.new_context(viewport={"width": 1400, "height": 900})
    await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','OWNERDEV'); }catch(e){}")
    posts = []
    async def srv(route):
        u = route.request.url
        if u.endswith('/quote-status'):
            return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'items': items}))
        if '/quote-status/reject' in u:
            bd = json.loads(route.request.post_data or '{}'); posts.append(bd)
            stt = dict(items.get(bd['ref'], {}))
            if bd.get('undo'): stt.pop('rejectedAt', None)
            else: stt['rejectedAt'] = 5; stt['rejectReason'] = bd.get('reason')
            items[bd['ref']] = stt
            return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'status': stt}))
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else ({'isOwnerDevice': True} if '/users/status' in u else {})
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    await ctx.route('https://merzona-server-production.up.railway.app/**', srv)
    await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    prompts = []
    def on_d(d):
        prompts.append(d.message)
        asyncio.ensure_future(d.accept('السعر غالي') if d.type == 'prompt' else d.accept())
    pg.on('dialog', on_d)
    await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3500)
    await pg.evaluate("""([iso, old]) => { DATA.length = 0;
      [['M-Q-260501', 1000], ['M-Q-260502', 2000], ['M-Q-260503', 3000], ['M-Q-260504', 4000], ['M-Q-260505', 500]].forEach(([r, t]) => DATA.push({ ref: r, client: 'زبون ' + r.slice(-1), phone: '0501112233', total: t, date: iso, year: iso.slice(0,4), url: '' }));
      DATA.push({ ref: 'M-Q-260300', client: 'قديم', phone: '', total: 100, date: old, year: '2026', url: '' });
      const c = loadContracts(); c['M-Q-260505'] = { client: 'زبون 5', ref: 'M-Q-260505' }; localStorage.setItem(CONTRACTS_KEY, JSON.stringify(c));
      showQuotationsView(); }""", [iso, old])
    await pg.wait_for_timeout(1500)
    k = await pg.evaluate("Array.from(document.querySelectorAll('#mzQsKpis .kpi')).map(e => e.querySelector('.kpi-value').textContent + '|' + (e.querySelector('p:last-child')||{}).textContent)")
    check(k and k[0].startswith('5|') and k[1].startswith('2|') and k[2].startswith('2|') and k[3].startswith('1|') and k[4].startswith('40%'), 'الأرقام هالشهر: انبعت 5، فتحهن 2، وقّعوا 2 (توقيع + عقد يدوي)، رفض 1، تحويل 40% ' + str(k))
    check('3,500' in k[2], 'قيمة يلي وقّعوا ' + k[2])
    if os.environ.get('MZ_SHOT'): await pg.evaluate("document.getElementById('mzQsPanel').scrollIntoView()"); await pg.screenshot(path=os.environ['MZ_SHOT'])
    hot = await pg.evaluate("document.getElementById('mzQsHot').innerText")
    check('M-Q-260502' in hot and 'M-Q-260503' not in hot, '🔥 "فتحه وما وقّع" فيه بس العرض الصح')
    badges = await pg.evaluate("Object.fromEntries(Array.from(document.querySelectorAll('#tableBody tr')).map(tr => [tr.querySelector('.ref-badge').textContent.trim(), (tr.querySelector('.mz-qs-badge')||{}).dataset.qs]))")
    check(badges.get('M-Q-260501') == 'sent' and badges.get('M-Q-260502') == 'viewed' and badges.get('M-Q-260503') == 'signed' and badges.get('M-Q-260504') == 'rejected' and badges.get('M-Q-260505') == 'signed' and badges.get('M-Q-260300') == 'old', 'إشارة الحالة بسجل العروض صح لكل عرض ' + str(badges))
    await pg.click("#tableBody tr:has-text('M-Q-260501') .mz-qs-act"); await pg.wait_for_timeout(800)
    b2 = await pg.evaluate("document.querySelector(\"#tableBody tr .mz-qs-badge\") && Array.from(document.querySelectorAll('#tableBody tr')).find(tr => tr.textContent.indexOf('M-Q-260501') >= 0).querySelector('.mz-qs-badge').dataset.qs")
    check(posts and posts[-1].get('ref') == 'M-Q-260501' and posts[-1].get('reason') == 'السعر غالي' and b2 == 'rejected', 'زر "رفض؟" بيسأل عن السبب وبيعلّم العرض مرفوض')
    await pg.click("#tableBody tr:has-text('M-Q-260501') .mz-qs-act"); await pg.wait_for_timeout(800)
    b3 = await pg.evaluate("Array.from(document.querySelectorAll('#tableBody tr')).find(tr => tr.textContent.indexOf('M-Q-260501') >= 0).querySelector('.mz-qs-badge').dataset.qs")
    check(posts[-1].get('undo') and b3 == 'sent', '↩️ بيلغي الرفض')
    await pg.click(".mz-qs-period[data-p='all']"); await pg.wait_for_timeout(300)
    k = await pg.evaluate("document.querySelector('#mzQsKpis .kpi p:last-child').textContent")
    check('من 5' in k, '"الكل": العروض قبل التتبع ما بتنحسب بالنسبة ' + k)
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_tickets(p, b, port):
    """🎫 طلبات عروض الأسعار المفتوحة (تيكيتات): شارة، شريط بالرئيسية، لوحة، فتح/تسكير/إرجاع، وبلا صلاحية ما بيبيّن شي"""
    print('• 🎫 طلبات عروض الأسعار المفتوحة')
    import time as _t
    nowms = int(_t.time() * 1000)
    items = [
        {'id': 1, 'at': nowms - 2 * 86400000, 'status': 'open', 'client': 'جلازورا', 'summary': 'Vetromax', 'details': '7×2.8\n3.5×2.8', 'by': 'حمدي', 'source': 'whatsapp', 'draftId': 'abc', 'notes': [{'at': nowms, 'by': 'سامي', 'text': 'بدو أسود'}]},
        {'id': 2, 'at': nowms - 3600000, 'status': 'open', 'client': '', 'summary': 'اتصل بأبو سمير', 'details': 'اتصل بأبو سمير', 'by': 'حمدي', 'source': 'whatsapp', 'notes': []},
        {'id': 3, 'at': nowms - 5 * 86400000, 'status': 'closed', 'closedAt': nowms - 86400000, 'closedBy': 'تلقائي', 'quoteRef': 'M-Q-260400', 'client': 'فيلا', 'summary': 'x', 'details': 'x', 'notes': []},
    ]
    for allowed in (True, False):
        ctx = await b.new_context(viewport={"width": 1400, "height": 900})
        await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','OWNERDEV'); }catch(e){}")
        posts = []
        async def srv(route):
            u = route.request.url; m = route.request.method
            if '/tickets' in u:
                if not allowed: return await route.fulfill(status=403, content_type='application/json', body='{"error":"no-permission"}')
                if m == 'GET': return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'items': items}))
                bd = json.loads(route.request.post_data or '{}'); posts.append((u.split('/tickets')[1], bd))
                if u.endswith('/tickets'):
                    t = {'id': 4, 'at': nowms, 'status': 'open', 'client': bd.get('client'), 'summary': bd.get('summary'), 'details': bd.get('details'), 'by': 'المالك', 'source': 'dashboard', 'notes': []}; items.insert(0, t)
                    return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'ticket': t}))
                tid = int(u.split('/tickets/')[1].split('/')[0]); t = next(x for x in items if x['id'] == tid)
                if u.endswith('/close'): t['status'] = 'closed'; t['closedAt'] = nowms; t['closeNote'] = bd.get('note')
                if u.endswith('/reopen'): t['status'] = 'open'
                return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'ticket': t}))
            body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else ({'isOwnerDevice': True} if '/users/status' in u else ({'items': {}} if u.endswith('/quote-status') else {}))
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
        await ctx.route(SRV + '/**', srv)
        await ctx.route('https://merzona-server-production.up.railway.app/**', srv)
        await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.on('dialog', lambda d: asyncio.ensure_future(d.accept('انلغى') if d.type == 'prompt' else d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3500)
        dot = await pg.evaluate("(document.querySelector('#quotationsTabBtn .mz-tk-dot')||{}).textContent || ''")
        banner = await pg.evaluate("document.getElementById('mzTkHomeBanner').innerText")
        if not allowed:
            check(dot == '' and banner.strip() == '' and await pg.evaluate("document.getElementById('mzTkPanel').style.display") == 'none', 'بلا صلاحية: ولا شارة ولا شريط ولا لوحة')
            check(not errs, 'بلا أخطاء (بلا صلاحية) ' + str(errs[:2]))
            await ctx.close(); continue
        check(dot == '2' and 'في 2 طلبات' in banner, 'شارة 2 عتبويب عروض الأسعار + شريط بالصفحة الرئيسية ' + repr(dot) + ' ' + banner)
        await pg.click('#mzTkHomeGo'); await pg.wait_for_timeout(1200)
        txt = await pg.evaluate("document.getElementById('mzTkList').innerText")
        vis = await pg.evaluate("document.getElementById('quotationsView').style.display !== 'none' && document.getElementById('mzTkPanel').style.display !== 'none'")
        check(vis and '#1 جلازورا' in txt and 'متأخر' in txt and 'بدو أسود' in txt and 'في مسودة' in txt and '#2' in txt and 'فيلا' not in txt, 'الشريط بيفتح اللوحة، والمفتوحين بيبيّنوا مع "متأخر" والملاحظات ' + txt[:200])
        if os.environ.get('MZ_SHOT'): await pg.evaluate("document.getElementById('mzTkPanel').scrollIntoView()"); await pg.screenshot(path=os.environ['MZ_SHOT'])
        await pg.click("#mzTkList [data-tk='2'] .mz-tk-act"); await pg.wait_for_timeout(1200)
        check(posts and posts[-1] == ('/2/close', {'note': 'انلغى'}) and await pg.evaluate("(document.querySelector('#quotationsTabBtn .mz-tk-dot')||{}).textContent") == '1', '"✓ خلص" بيسكّر مع ملاحظة والشارة بتنزل لـ1 ' + str(posts[-1:]))
        await pg.click('#mzTkShowClosed'); await pg.wait_for_timeout(300)
        ctxt = await pg.evaluate("document.getElementById('mzTkList').innerText")
        check('فيلا' in ctxt and 'M-Q-260400' in ctxt and 'تلقائي' in ctxt, 'المسكّرة بتبيّن مع رقم العرض يلي سكّرها ' + ctxt[:150])
        await pg.click("#mzTkList [data-tk='2'] .mz-tk-act"); await pg.wait_for_timeout(1200)
        check(posts[-1][0] == '/2/reopen', 'رجّعه مفتوح')
        await pg.click('#mzTkShowClosed'); await pg.click('#mzTkNewBtn')
        await pg.fill('#mzTkClient', 'فيلا المزة'); await pg.fill('#mzTkDetails', 'درابزين 12 متر\nلون أسود')
        await pg.click('#mzTkSave'); await pg.wait_for_timeout(1200)
        txt = await pg.evaluate("document.getElementById('mzTkList').innerText")
        check(posts[-1] == ('', {'client': 'فيلا المزة', 'details': 'درابزين 12 متر\nلون أسود', 'summary': 'درابزين 12 متر'}) and '#4 فيلا المزة' in txt and await pg.evaluate("document.getElementById('mzTkNew').style.display") == 'none', '➕ طلب جديد بينفتح ويبيّن فورًا')
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        await ctx.close()


async def t_items_sync(p, b, port):
    """📚 بنود السيستم بتنرفع للسيرفر وبتنجاب منه (هيك مساعد الواتس اب ومسودة الـPDF بيعرفوها)"""
    print('• 📚 مزامنة بنود السيستم مع السيرفر')
    server = {'items': [], 'specAr': {}, 'at': 0}; posts = []
    async def srv(route):
        u = route.request.url
        if u.endswith('/quote-items'):
            if route.request.method == 'POST':
                bd = json.loads(route.request.post_data or '{}'); posts.append(bd)
                server['items'] = bd['items']; server['specAr'] = bd.get('specAr') or {}; server['at'] += 1000
                return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'at': server['at']}))
            return await route.fulfill(status=200, content_type='application/json', body=json.dumps(server))
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else {}
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    async def open_dev(init_js):
        ctx = await b.new_context(viewport={"width": 1400, "height": 900})
        await ctx.add_init_script("if(!sessionStorage.getItem('x')){sessionStorage.setItem('x','1');localStorage.setItem('merzona-device-token','dev1');localStorage.setItem('merzona-access-status','approved');" + init_js + "}")
        await ctx.route(SRV + '/**', srv)
        await ctx.route('https://merzona-server-production.up.railway.app/**', srv)
        await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_timeout(5500)
        return ctx, pg, errs
    # 1) جهاز حمدي: فيه بند Vetromax بس بهالمتصفح ← بينرفع
    ctx, pg, errs = await open_dev("")
    await pg.evaluate("ITEMS.push({en:'Vetromax', ar:'فيترومكس', specEn:'Vetromax sliding system', specAr:'نظام فيترومكس سحاب', glassEn:'', glassAr:''}); localStorage.setItem('merzona-items', JSON.stringify(ITEMS)); localStorage.removeItem('merzona-items__srv'); localStorage.removeItem('merzona-items__ts');")
    await pg.evaluate("mzItemsSync()"); await pg.wait_for_timeout(800)
    check(posts and any(x['en'] == 'Vetromax' for x in posts[-1]['items']), 'بنود الجهاز (مع Vetromax) انرفعت للسيرفر')
    n_items = len(server['items'])
    # تعديل بند ← بينرفع لحالو
    await pg.evaluate("ITEMS.push({en:'Glazora Special', ar:'خاص', specEn:'', glassEn:'', glassAr:''}); saveItemsToStorage();"); await pg.wait_for_timeout(2800)
    check(any(x['en'] == 'Glazora Special' for x in server['items']), 'إضافة بند بتنرفع بعد ثانيتين')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()
    # 2) جهاز جديد (بلا بنود محفوظة): بياخد بنود السيستم وما بيرفع شي
    np = len(posts)
    ctx, pg, errs = await open_dev("")
    has = await pg.evaluate("ITEMS.some(x => x.en === 'Vetromax') && ITEMS.some(x => x.en === 'Glazora Special') && JSON.parse(localStorage.getItem('merzona-items')||'[]').some(x => x.en === 'Vetromax')")
    dl = await pg.evaluate("Array.from(document.querySelectorAll('#items-datalist option')).some(o => o.value === 'Vetromax')")
    check(has and dl and len(posts) == np, 'جهاز جديد بياخد بنود السيستم (وبتبيّن بالقائمة) بلا ما يرفع شي')
    check(not errs, 'بلا أخطاء (جهاز جديد) ' + str(errs[:2]))
    await ctx.close()
    # 3) جهاز قديم فيه بند لحالو + السيرفر فيه بنود تانية ← ولا بند بيضيع
    ctx, pg, errs = await open_dev("localStorage.setItem('merzona-items', JSON.stringify([{en:'Old Device Item', ar:'بند قديم', specEn:'', glassEn:'', glassAr:''}]));")
    await pg.wait_for_timeout(1500)
    names = await pg.evaluate("ITEMS.map(x => x.en)")
    check('Old Device Item' in names and 'Vetromax' in names and any(x['en'] == 'Old Device Item' for x in server['items']) and any(x['en'] == 'Vetromax' for x in server['items']), 'بنود الجهازين انضمّوا (ما في بند ضاع) ' + str(len(names)))
    await ctx.close()


async def t_proc_products(p, b, port):
    """📦 إعدادات المشتريات: المواد حسب المنتج (شيل مادة مو لازمة + مواد خاصة بمنتج)"""
    print('• 📦 إعدادات المشتريات: المواد حسب المنتج')
    ctx = await new_ctx(p, b)
    await ctx.route(SRV + '/procurement-rules**', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps({'rev': 0, 'rules': None}) if r.request.method == 'GET' else json.dumps({'ok': True, 'rev': 1})))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/procurement.html'); await pg.wait_for_timeout(2500)
    keys = lambda js: pg.evaluate("(() => { const T = window.__mzProcTest; " + js + " })()")
    HR = "T.generic('هاندريل', { aluMm: 3000, glassM2: 2, hw: { hinges: 4, handles: 2, locks: 1 }, leaves: 0 })"
    FD = "T.generic('باب فولدينغ', { aluMm: 5000, glassM2: 4, hw: { hinges: 6, handles: 1, locks: 1, rollers: 2 }, leaves: 3 })"
    k0 = await keys("return T.boq(" + HR + ").map(r => r.key);")
    check(set(k0) >= {'alu', 'glass', 'hinges', 'handle', 'lock'}, 'قبل الإعدادات: الهاندريل كان يطلع فيه مفصلات وقفل ومسكة ' + str(k0))
    check(await keys("return T.productKeyOf(" + HR + ") + '|' + T.productKeyOf(" + FD + ") + '|' + T.productKeyOf(T.generic('بند آخر', {}));") == 'g:handrail|g:foldingDoor|g:other', 'كل منتج بيتعرف صح')
    await keys("T.setRules({ exclude: { 'g:handrail': ['hinges', 'lock', 'handle'] }, extras: [ { id: 'sil', name: 'سيليكون', qty: 2, unit: 'أنبوب', basis: 'per_item', products: ['g:handrail'] }, { id: 'old', name: 'برغي قديم', qty: 1, unit: 'علبة', basis: 'per_item', types: ['generic'] } ] }); return 1;")
    k1 = await keys("return T.boq(" + HR + ").map(r => r.key);")
    k2 = await keys("return T.boq(" + FD + ").map(r => r.key);")
    check('hinges' not in k1 and 'lock' not in k1 and 'handle' not in k1 and 'alu' in k1 and 'glass' in k1, 'بعد الإعدادات: الهاندريل بلا مفصلات/قفل/مسكة، والألمنيوم والزجاج باقيين ' + str(k1))
    check('hinges' in k2 and 'lock' in k2, 'باب الفولدينغ ما تأثّر ' + str(k2))
    check('x_sil' in k1 and 'x_sil' not in k2, 'مادة خاصة بالهاندريل (سيليكون) بتطلع بس معه')
    check('x_old' in k1 and 'x_old' in k2, 'مواد إضافية قديمة (محددة بالنوع) لسا شغالة متل قبل على كل الفولدينغ/شاور/هاندريل')
    n0 = await keys("const r = T.normalize({ exclude: { 'g:handrail': ['hinges', 'BAD KEY'], 'evil': ['x'] } }); return JSON.stringify(r.exclude);")
    check(n0 == '{"g:handrail":["hinges"]}', 'القيم الغلط بتنشال ' + n0)
    # الواجهة: تبويب الإعدادات
    await keys("T.setRules({}); return 1;")
    await pg.click("button[data-tab='settings']"); await pg.wait_for_timeout(500)
    cards = await pg.evaluate("Array.from(document.querySelectorAll('#productsMaterials .product-card')).map(c => c.dataset.product)")
    check(len(cards) == 9 and 'g:handrail' in cards, 'قائمة المنتجات بصفحة الإعدادات (' + str(len(cards)) + ')')
    await pg.evaluate("document.querySelector(\"#productsMaterials .product-card[data-product='g:handrail']\").open = true")
    await pg.click("#productsMaterials .product-card[data-product='g:handrail'] input[data-mat='hinges']"); await pg.wait_for_timeout(300)
    ex = await keys("return JSON.stringify(T.rules().exclude);")
    saved = await pg.evaluate("JSON.parse(localStorage.getItem('merzona-proc-rules-v1')).rules.exclude")
    check(ex == '{"g:handrail":["hinges"]}' and saved == {'g:handrail': ['hinges']}, 'شيلت العلامة عن "مفصلات" للهاندريل ← انحفظت ' + ex)
    await pg.click("#productsMaterials .product-card[data-product='g:handrail'] button"); await pg.wait_for_timeout(400)
    ex2 = await keys("const x = T.rules().extras; return x.length + '|' + JSON.stringify(x[x.length-1].products);")
    check(ex2 == '1|["g:handrail"]', 'زر "+ مادة خاصة بـهاندريل" بيضيف مادة مربوطة فيه ' + ex2)
    if os.environ.get('MZ_SHOT'): await pg.evaluate("document.getElementById('productsMaterials').scrollIntoView()"); await pg.screenshot(path=os.environ['MZ_SHOT'])
    await pg.reload(); await pg.wait_for_timeout(2500)
    await pg.click("button[data-tab='settings']"); await pg.wait_for_timeout(500)
    st = await pg.evaluate("[document.querySelector(\"#productsMaterials .product-card[data-product='g:handrail'] input[data-mat='hinges']\").checked, document.querySelector(\"#productsMaterials .product-card[data-product='g:handrail'] input[data-mat='glass']\").checked]")
    check(st == [False, True], 'بعد إعادة فتح الصفحة الإعدادات باقية ' + str(st))
    # 💲 تكلفة الزجاج (28$ للمتر المربع - بتتغيّر من الإعدادات)
    await keys("T.setRules({}); return 1;")
    c0 = await keys("const rows = T.boq(" + HR + "); const g = rows.find(r => r.key === 'glass'); return [g.qty, T.cost(g), T.rules().costs.glassPerM2, T.cost(rows.find(r => r.key === 'alu'))];")
    check(c0 == [2, 56, 28, None], 'الزجاج: 2 م² × 28$ = 56$ (والألمنيوم لسا بلا سعر) ' + str(c0))
    await keys("T.setRules({ wasteGlassPct: 10, costs: { glassPerM2: 30 } }); return 1;")
    c1 = await keys("const g = T.boq(" + HR + ").find(r => r.key === 'glass'); return [g.qty, T.cost(g)];")
    check(c1 == [2.2, 66], 'مع هدر 10% وسعر 30$: 2.2 م² × 30 = 66$ ' + str(c1))
    bad = await keys("return [T.normalize({ costs: { glassPerM2: -5 } }).costs.glassPerM2, T.normalize({ costs: { glassPerM2: 'abc' } }).costs.glassPerM2, T.normalize({}).costs.glassPerM2];")
    check(bad == [0, 28, 28], 'قيم غلط ما بتخرّب: سالب=0، نص=28، قديم بلا سعر=28 ' + str(bad))
    await keys("T.setRules({}); T.addItem(" + HR + "); T.addItem(" + FD + "); return 1;")
    await pg.click("button[data-tab='boq']"); await pg.wait_for_timeout(500)
    tot = await pg.evaluate("(document.getElementById('boqCostTotal')||{}).textContent || ''")
    if os.environ.get('MZ_SHOT2'): await pg.screenshot(path=os.environ['MZ_SHOT2'], full_page=True)
    check('280 $' in tot and '10 م²' in tot, 'جدول المشتريات: مجموع التكلفة (شباك المثال 4 + هاندريل 2 + فولدينغ 4 = 10 م² × 28 = 280$) ' + tot[:90])
    await pg.click("button[data-tab='settings']"); await pg.wait_for_timeout(400)
    inp = pg.locator("label.rule-field:has-text('تكلفة متر مربع الزجاج') input")
    check(await inp.input_value() == '28', 'خانة "تكلفة متر مربع الزجاج" بالإعدادات = 28')
    await inp.fill('35'); await inp.dispatch_event('change'); await pg.wait_for_timeout(300)
    saved = await pg.evaluate("JSON.parse(localStorage.getItem('merzona-proc-rules-v1')).rules.costs.glassPerM2")
    await pg.click("button[data-tab='boq']"); await pg.wait_for_timeout(400)
    tot = await pg.evaluate("document.getElementById('boqCostTotal').textContent")
    check(saved == 35 and '350 $' in tot, 'غيّرت السعر لـ35$ ← انحفظ والتكلفة صارت 350$ ' + tot[:60])
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def t_collections(p, b, port):
    """💰 المرحلة ٣: تذكير الدفعات + كشف حساب العقد بالواتساب + سعر الصرف يوم الاستلام + كشف المحاسبة"""
    print('• 💰 التحصيل: تذكير الدفعات وكشف الحساب')
    import datetime as _dt
    today = _dt.date.today().isoformat(); past = '2026-11-01'; future = '2027-03-01'
    contracts = {
        'M-Q-260601': {'client': 'زبون إمارات', 'total': 10000, 'payments': [
            {'id': 'a', 'desc': 'الدفعة الأولى', 'pct': 30, 'status': 'received', 'receivedAt': '2026-10-20'},
            {'id': 'b', 'desc': 'الدفعة التانية', 'pct': 40, 'status': 'due', 'dueDate': past},
            {'id': 'c', 'desc': 'الدفعة الأخيرة', 'pct': 30, 'status': 'due', 'dueDate': future}]},
        'S-Q-260602': {'client': 'زبون سوريا', 'total': 5000, 'payments': [
            {'id': 'd', 'desc': 'دفعة مقدمة', 'pct': 50, 'status': 'due', 'dueDate': today},
            {'id': 'e', 'desc': 'عند التسليم', 'pct': 50, 'status': 'notdue'}]}
    }
    ctx = await b.new_context(viewport={"width": 1400, "height": 900})
    await ctx.add_init_script("""if(!sessionStorage.getItem('c3')){ sessionStorage.setItem('c3','1'); localStorage.setItem('merzona-device-token','OWNERDEV');
      localStorage.setItem('merzona_contracts', %s); localStorage.setItem('mz-fx-usd-syp-v1', JSON.stringify({ buy: 11400, sell: 11500, at: '2026-11-16' })); }""" % json.dumps(json.dumps(contracts, ensure_ascii=False)))
    async def srv(route):
        u = route.request.url
        body = {'status': 'approved', 'isOwner': True} if '/access/status' in u else ({'isOwnerDevice': True} if '/users/status' in u else {})
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    await ctx.route('https://merzona-server-production.up.railway.app/**', srv)
    await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    dialogs = []; pg.on('dialog', lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.accept())))
    await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3500)
    await pg.evaluate("""() => { DATA.push({ ref: 'M-Q-260601', client: 'زبون إمارات', phone: '0501234567', total: 10000, date: '2026-10-01', year: '2026', url: '' });
      DATA.push({ ref: 'S-Q-260602', client: 'زبون سوريا', phone: '0944123456', total: 5000, date: '2026-10-05', year: '2026', url: '' });
      window.__opened = []; window.open = function(u){ window.__opened.push(u || ''); return { document: { open(){}, write(h){ window.__printed = h; }, close(){} } }; };
      payRange = 'all'; renderExpectedPayments(); }""")
    tot = await pg.evaluate("document.getElementById('expectedPaymentsTotal').textContent")
    check('7,000' in tot and 'د.إ' in tot and '2,500' in tot and 'USD' in tot, 'الدفعات المتوقعة: كل عملة لحالها (7,000 د.إ · 2,500 USD) بدل ما ينجمعوا ' + tot)
    late = await pg.evaluate("Array.from(document.querySelectorAll('#expectedPaymentsBody tr')).map(tr => tr.textContent.indexOf('⚠️') >= 0)")
    check(late.count(True) == 1, 'الدفعة المتأخرة معلّمة ⚠️ ' + str(late))
    await pg.evaluate("Array.from(document.querySelectorAll('#expectedPaymentsBody tr')).find(tr => tr.textContent.indexOf('الدفعة التانية') >= 0).querySelector('[data-remind-i]').click()")
    u = await pg.evaluate("window.__opened[window.__opened.length - 1]")
    import urllib.parse as _up
    txt = _up.unquote(u.split('?text=')[-1]) if '?text=' in u else ''
    check(u.startswith('https://wa.me/971501234567?text=') and 'الدفعة التانية' in txt and '4,000' in txt and 'كانت مستحقة' in txt and 'المتبقي من العقد: 7,000' in txt, 'زر "💬 ذكّر": محادثة الزبون ورسالة فيها الدفعة والمبلغ والتاريخ والمتبقي ' + txt[:120].replace('\\n', ' | '))
    await pg.evaluate("Array.from(document.querySelectorAll('#expectedPaymentsBody tr')).find(tr => tr.textContent.indexOf('دفعة مقدمة') >= 0).querySelector('[data-remind-i]').click()")
    u2 = await pg.evaluate("window.__opened[window.__opened.length - 1]")
    t2 = _up.unquote(u2.split('?text=')[-1])
    check(u2.startswith('https://wa.me/963944123456?text=') and '2,500 USD' in t2 and 'المستحقة بتاريخ' in t2, 'تذكير زبون سوريا: رقم سوري وبالدولار ' + u2[:40])
    # كشف الحساب
    st = await pg.evaluate("mzStatementText('M-Q-260601')")
    check('قيمة العقد: 10,000 د.إ' in st and 'المستلم: 3,000' in st and 'المتبقي: 7,000' in st and '✅ الدفعة الأولى' in st and '⚠️ الدفعة التانية' in st and '⏳ الدفعة الأخيرة' in st, 'نص كشف الحساب صح (مستلم/متأخر/مستحق)')
    await pg.evaluate("showContractsView()"); await pg.wait_for_timeout(800)
    await pg.click("#contractsListBody [data-stmt-ref='M-Q-260601']"); await pg.wait_for_timeout(400)
    mt = await pg.evaluate("(document.getElementById('mzStmtModal')||{}).innerText || ''")
    check('كشف حساب - M-Q-260601' in mt and '10,000' in mt and 'مستلمة' in mt, 'زر "📄 كشف" بالعقود بيفتح كشف الحساب')
    await pg.click("#mzStmtModal button:has-text('ابعت للزبون')"); await pg.wait_for_timeout(200)
    u3 = await pg.evaluate("window.__opened[window.__opened.length - 1]")
    check(u3.startswith('https://wa.me/971501234567?text=') and 'كشف حساب' in _up.unquote(u3), 'الكشف بينبعت للزبون بالواتساب')
    await pg.click("#mzStmtModal button:has-text('طباعة')"); await pg.wait_for_timeout(200)
    ph = await pg.evaluate("window.__printed || ''")
    check('كشف حساب' in ph and 'M-Q-260601' in ph and 'window.print' in ph, 'نسخة طباعة/PDF للكشف')
    # سعر الصرف يوم الاستلام (عقد بالدولار)
    r = await pg.evaluate("""() => { currentContractRef = 'S-Q-260602'; tempPayments = JSON.parse(JSON.stringify(loadContracts()['S-Q-260602'].payments)); renderPaymentRows();
      document.querySelector('#paymentRowsBody [data-toggle="1"]').click(); const p = tempPayments[1]; const a = [p.status, p.receivedAt, p.fxSyp];
      document.querySelector('#paymentRowsBody [data-toggle="1"]').click(); const q = tempPayments[1]; return a.concat([q.status, q.receivedAt || null, q.fxSyp || null]); }""")
    check(r[:3] == ['received', today, 11500], 'علّمت دفعة دولار "مستلمة": انحفظ تاريخ اليوم وسعر الصرف 11,500 ' + str(r))
    check(r[3:] == ['due', None, None], 'ورجّعتها "مستحقة": انشال التاريخ والسعر')
    r2 = await pg.evaluate("""() => { currentContractRef = 'M-Q-260601'; tempPayments = [{ id: 'z', desc: 'x', pct: 10, status: 'notdue' }]; renderPaymentRows();
      document.querySelector('#paymentRowsBody [data-toggle="0"]').click(); return [tempPayments[0].status, !!tempPayments[0].receivedAt, tempPayments[0].fxSyp || null]; }""")
    check(r2 == ['received', True, None], 'عقد بالدرهم: تاريخ الاستلام بس، بلا سعر صرف ' + str(r2))
    check(not errs and not dialogs, 'بلا أخطاء ولا رسائل ' + str((errs[:2], dialogs[:1])))
    await ctx.close()


async def t_acct_statement_wa(p, b, port):
    """💬 كشف حساب المحاسبة بالواتساب للزبون"""
    print('• كشف حساب المحاسبة بالواتساب')
    import subprocess, urllib.parse as _up
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_acct.js'), sdir], stdout=subprocess.PIPE, text=True)
    aport = int(proc.stdout.readline().split()[1])
    try:
        ctx = await b.new_context(viewport={"width": 1300, "height": 900})
        await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','OWNERDEV'); localStorage.setItem('merzona-acct-book','syria'); }catch(e){}")
        async def fwd(route):
            u = route.request.url
            if '/access/status' in u: return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'status': 'approved', 'isOwner': True}))
            if '/acct/' in u:
                resp = await route.fetch(url=u.replace(SRV, f'http://127.0.0.1:{aport}'))
                return await route.fulfill(response=resp)
            await route.fulfill(status=200, content_type='application/json', body='{}')
        await ctx.route(SRV + '/**', fwd)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        dialogs = []; pg.on('dialog', lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.accept())))
        await pg.goto(f'http://127.0.0.1:{port}/accounting.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""() => { const B = __acctT.S().book; B.parties.pz1 = { id: 'pz1', name: 'أبو سامر', kind: 'customer', phone: '0944555666' }; B.parties.pz2 = { id: 'pz2', name: 'بلا رقم', kind: 'customer' };
          window.__opened = []; window.open = function(u){ window.__opened.push(u); return null; }; __acctT.statement('pz1'); }""")
        await pg.wait_for_timeout(300)
        await pg.click("button:has-text('💬 واتساب')"); await pg.wait_for_timeout(200)
        u = await pg.evaluate("window.__opened[0] || ''")
        t = _up.unquote(u.split('?text=')[-1]) if '?text=' in u else ''
        check(u.startswith('https://wa.me/963944555666?text=') and 'كشف حساب' in t and 'أبو سامر' in t, 'زر "💬 واتساب" بكشف الحساب بيفتح محادثة الزبون والكشف جاهز ' + u[:40])
        await pg.evaluate("document.querySelectorAll('.modal, .mdl, [class*=modal]').forEach(function(m){ m.remove(); }); __acctT.statement('pz2')"); await pg.wait_for_timeout(300)
        await pg.click("button:has-text('ما في رقم')"); await pg.wait_for_timeout(300)
        check(any('ما في رقم' in m for m in dialogs) and len(await pg.evaluate("window.__opened")) == 1, 'طرف بلا رقم: رسالة واضحة وما بيفتح شي')
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        await ctx.close()
    finally:
        proc.kill()


async def t_acct_syp_invoice(p, b, port):
    """💱 فاتورة سوريا بالليرة: سعر الصرف بيتعبّى لحاله من سعر السوق، والفاتورة بتنحفظ (بالإنكليزي متل المحاسب)"""
    print('• 💱 فاتورة سوريا بالليرة (سعر الصرف التلقائي)')
    import subprocess
    sdir = os.environ.get('MZ_SERVER_DIR') or os.path.join(os.path.dirname(ROOT), 'merzona-server')
    proc = subprocess.Popen(['node', os.path.join(ROOT, 'tests', 'e2e', 'fake_acct.js'), sdir], stdout=subprocess.PIPE, text=True)
    aport = int(proc.stdout.readline().split()[1])
    try:
        for fx_ok in (False, True):
            ctx = await b.new_context(viewport={"width": 1300, "height": 900})
            await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','OWNERDEV'); localStorage.setItem('merzona-acct-book','syria'); localStorage.removeItem('mz-fx-usd-syp-v1'); }catch(e){}")
            async def fwd(route, _req=None, fx_ok=fx_ok):
                u = route.request.url
                if '/access/status' in u: return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'status': 'approved', 'isOwner': True}))
                if '/fx/usd-syp' in u:
                    return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'buy': 11400, 'sell': 11500, 'at': '2026-11-17T08:00:00Z'})) if fx_ok else await route.fulfill(status=503, body='{}')
                if '/acct/' in u:
                    resp = await route.fetch(url=u.replace(SRV, f'http://127.0.0.1:{aport}'))
                    return await route.fulfill(response=resp)
                await route.fulfill(status=200, content_type='application/json', body='{}')
            await ctx.route(SRV + '/**', fwd)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.goto(f'http://127.0.0.1:{port}/accounting.html?lang=en'); await pg.wait_for_timeout(2500)
            nm = 'زبون ليرة ' + ('1' if fx_ok else '2')
            await pg.evaluate("(nm) => fetch('" + SRV + "/acct/syria/op', { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-device': 'OWNERDEV' }, body: JSON.stringify({ op: 'saveParty', data: { name: nm, kind: 'customer' }, baseRev: __acctT.S().book.rev }) })", nm)
            await pg.reload(); await pg.wait_for_timeout(2500)
            await pg.click("button[data-tab='sales']"); await pg.wait_for_timeout(400)
            await pg.click("button[data-new='invoice']"); await pg.wait_for_timeout(600)
            await pg.evaluate("""() => { const sel = document.getElementById('fP'); sel.selectedIndex = sel.options.length - 1; sel.dispatchEvent(new Event('change', {bubbles:true}));
              const tr = document.querySelector('.lines tbody tr'); const ins = tr.querySelectorAll('input'); ins[0].value = 'بند'; ins[0].dispatchEvent(new Event('input', {bubbles:true}));
              tr.querySelectorAll('input.num').forEach(i => { i.value = '1000000'; i.dispatchEvent(new Event('input', {bubbles:true})); });
              const fc = document.getElementById('fC'); fc.value = 'SYP'; fc.dispatchEvent(new Event('change', {bubbles:true})); }""")
            await pg.wait_for_timeout(800)
            fxv = await pg.evaluate("document.getElementById('fX').value")
            if fx_ok:
                hint = await pg.evaluate("document.getElementById('fxHint').innerText")
                check(fxv == '11500' and "Today's market rate" in hint and 'edit it if needed' in hint, 'اختار الليرة ← سعر الصرف تعبّى لحاله 11500 (سعر السوق) ' + repr(fxv) + ' ' + hint[:70])
                ph = await pg.evaluate("document.getElementById('fNo').placeholder")
                check('S-INV-' in ph, 'خانة رقم الفاتورة: فاضية = رقم تلقائي ' + ph)
                await pg.fill('#fNo', 'SY-1050')
                await pg.locator("button:has-text('Save')").last.click(); await pg.wait_for_timeout(1500)
                docs = await pg.evaluate("Object.values(__acctT.S().book.docs).filter(d => d.type === 'invoice' && d.currency === 'SYP').map(d => [d.no, d.fx])")
                check(len(docs) == 1 and docs[0][0] == 'SY-1050', 'فاتورة سوريا بالليرة انحفظت برقم يدوي ' + str(docs))
            else:
                check(fxv == '', 'السيرفر ما عطى سعر ← الخانة بتضل فاضية (ما منحط رقم غلط) ' + repr(fxv))
                await pg.fill('#fX', '12000'); await pg.wait_for_timeout(500)
                check(await pg.evaluate("document.getElementById('fX').value") == '12000', 'والمحاسب بيكتب السعر بإيده عادي')
            check(not errs, 'بلا أخطاء ' + str(errs[:2]))
            await ctx.close()
    finally:
        proc.kill()


async def t_owner_stale_session(p, b, port):
    """👑 جهاز المالك عليه تسجيل دخول قديم بحساب موظف: لازم يضل يشوف "المستخدمين" و"المحاسبة" (ما ينسحبوا بالفحص الدوري)"""
    print('• 👑 جهاز المالك + جلسة موظف قديمة')
    for owner in (True, False):
        ctx = await b.new_context(viewport={"width": 1400, "height": 900})
        await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','DEVX'); localStorage.setItem('merzona-access-status','approved'); localStorage.setItem('merzona-session-token','OLDSESSION'); }catch(e){}")
        staff = {'dashboard': True, 'quotation': True, 'contracts': True, 'payroll': True, 'accounting': False, 'manageUsers': False}
        async def srv(route, _r=None, owner=owner):
            u = route.request.url
            if '/users/status' in u: body = {'isOwnerDevice': True, 'hasAccount': True} if owner else {'hasAccount': True, 'username': 'sami'}
            elif '/users/me' in u: body = {'username': 'sami', 'permissions': staff, 'lang': 'ar'}
            elif '/access/status' in u: body = {'status': 'approved', 'isOwner': owner}
            else: body = {}
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
        await ctx.route(SRV + '/**', srv)
        await ctx.route('https://merzona-server-production.up.railway.app/**', srv)
        await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3500)
        vis = lambda: pg.evaluate("['usersTabBtn','accountingTabBtn','payrollTabBtn'].map(id => { const e = document.getElementById(id); return !!e && getComputedStyle(e).display !== 'none'; })")
        v0 = await vis()
        await pg.evaluate("window.__mzRevalidatePermissionsNow && window.__mzRevalidatePermissionsNow()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); await pg.wait_for_timeout(800)
        v1 = await vis()
        if owner:
            check(v0 == [True, True, True] and v1 == [True, True, True], 'جهاز المالك: "المستخدمين" و"المحاسبة" بيضلوا ظاهرين بعد الفحص الدوري ' + str((v0, v1)))
        else:
            check(v1 == [False, False, True], 'جهاز موظف: الفحص الدوري لسا بيطبّق صلاحياته متل قبل ' + str((v0, v1)))
        check(not errs, 'بلا أخطاء ' + str(errs[:2]))
        await ctx.close()


async def t_dash_seed_load(p, b, port):
    """🛠️ الداشبورد بتنفتح ببيانات حقيقية محفوظة (قائمة العروض من نسخة سابقة): ولا خطأ وقت التحميل، وكل التبويبات بتطلع للمالك"""
    print('• الداشبورد مع بيانات محفوظة وقت التحميل')
    rows = [{'ref': 'M-Q-26%04d' % i, 'client': 'زبون %d' % i, 'phone': '0501234567', 'total': 1000 + i, 'date': '2026-11-%02d' % (1 + i % 15), 'year': '2026', 'url': ''} for i in range(1, 40)]
    contracts = {'M-Q-260001': {'client': 'زبون 1', 'total': 1001, 'payments': [{'id': 'a', 'desc': 'دفعة', 'pct': 50, 'status': 'due', 'dueDate': '2026-11-01'}]}}
    ctx = await b.new_context(viewport={"width": 1400, "height": 900})
    await ctx.add_init_script("try{ localStorage.setItem('merzona-device-token','OWNERDEV'); localStorage.setItem('merzona-access-status','approved'); localStorage.setItem('merzona_dash_seed_cache_v1', %s); localStorage.setItem('merzona_contracts', %s); }catch(e){}" % (json.dumps(json.dumps(rows, ensure_ascii=False)), json.dumps(json.dumps(contracts, ensure_ascii=False))))
    async def srv(route, _r=None):
        u = route.request.url
        body = {'isOwnerDevice': True, 'hasAccount': True} if '/users/status' in u else ({'status': 'approved', 'isOwner': True} if '/access/status' in u else {})
        await route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    await ctx.route(SRV + '/**', srv)
    await ctx.route('https://merzona-server-production.up.railway.app/**', srv)
    await ctx.route('https://www.googleapis.com/**', lambda r: r.fulfill(status=401, body='{}'))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(3500)
    check(not errs, 'ولا خطأ وقت تحميل الداشبورد مع بيانات محفوظة ' + str(errs[:2]))
    vis = await pg.evaluate("['usersTabBtn','accountingTabBtn','contractsTabBtn','payrollTabBtn'].map(id => { const e = document.getElementById(id); return !!e && getComputedStyle(e).display !== 'none'; })")
    check(vis == [True, True, True, True], 'المالك بيشوف المستخدمين والمحاسبة والعقود والرواتب ' + str(vis))
    for fn in ['showQuotationsView', 'showContractsView', 'showPayrollView', 'showClientsView', 'showCatalogsView']:
        e0 = len(errs)
        try: await pg.evaluate("typeof %s === 'function' && %s()" % (fn, fn)); await pg.wait_for_timeout(300)
        except Exception as e: errs.append(str(e)[:150])
        check(len(errs) == e0, 'فتح ' + fn + ' بلا أخطاء ' + str(errs[e0:e0+1]))
    rowsN = await pg.evaluate("document.querySelectorAll('#tableBody tr .mz-qs-badge').length")
    check(rowsN >= 39, 'إشارة حالة العرض ظاهرة بكل صفوف السجل (%d)' % rowsN)
    await ctx.close()


async def t_users_columns(p, b, port):
    """👥 جدول المستخدمين: كل مربّع تحت عنوانه الصح (كان عنوان "محاسبة" ناقص فكل الأعمدة مزاحة)"""
    print('• جدول المستخدمين: العناوين مطابقة للمربعات')
    ctx = await new_ctx(p, b)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    await pg.goto(f'http://127.0.0.1:{port}/Dashboard.html'); await pg.wait_for_timeout(2500)
    r = await pg.evaluate("""() => { renderUsersRows([{ username: 'accountant', permissions: { dashboard: true, accounting: true }, isAdmin: false, lang: 'en' }]);
      const heads = Array.from(document.querySelectorAll('#usersTableHead th')).map(th => th.textContent.trim());
      const tds = Array.from(document.querySelectorAll('#usersTableBody tr:first-child td'));
      const iAcc = tds.findIndex(td => td.querySelector('input[data-perm="accounting"]'));
      const iAdm = tds.findIndex(td => td.querySelector('.mz-users-isadmin'));
      const iLang = tds.findIndex(td => td.querySelector('.mz-users-lang'));
      return { n: [heads.length, tds.length], acc: heads[iAcc], adm: heads[iAdm], lang: heads[iLang], checked: tds[iAcc].querySelector('input').checked }; }""")
    check(r['n'][0] == r['n'][1], 'عدد العناوين = عدد الخانات ' + str(r['n']))
    check(r['acc'] == 'محاسبة' and r['checked'], 'مربّع المحاسبة تحت عنوان "محاسبة" ومعلّم ' + str(r))
    check(r['adm'] == 'أدمن' and r['lang'] == 'اللغة', '"أدمن" و"اللغة" بمكانهن الصح')
    check(not errs, 'بلا أخطاء ' + str(errs[:2]))
    await ctx.close()


async def main():
    tmp = prepare(); httpd = serve(tmp); port = httpd.server_address[1]
    print('فحص:', SRC)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        only = sys.argv[sys.argv.index('--only') + 1].split(',') if '--only' in sys.argv else None
        for fn, args in [(t_types_and_roundtrip, ()), (t_old_misguessed, ()), (t_handrail_plan, ()), (t_handrail_draw, (False,)), (t_handrail_draw, (True,)), (t_edit_panel, (False,)), (t_edit_panel, (True,)), (t_catalog, ()), (t_drive_proxy, ()),
                         (t_share_pdf, ()), (t_cad_import, ()), (t_quotes_server, ()), (t_company, ()), (t_fx_bar, ()), (t_acct_ai, ()), (t_acct_en, ()), (t_dash_en, ()), (t_auth_headers, ()), (t_payroll_auto, ()), (t_warranty_template, ()), (t_hr3d_toolbar, ()), (t_print_titles, ()), (t_dash_accountant, ()), (t_quote_status, ()), (t_tickets, ()), (t_sliding_ids, ()), (t_view_version, ()), (t_shower_wall, ()), (t_camera_quad, ()), (t_real3d, ()), (t_real3d_pergola, ()), (t_pergola_posts, ()), (t_hr_sizes_steppers, ()), (t_survey, ()), (t_cutplan, ()), (t_install_checklist, ()), (t_techcat, ()), (t_design_new_item_confirm, ()), (t_mobile_delete_item, ()), (t_refresh_restore, ()), (t_items_sync, ()), (t_proc_products, ()), (t_collections, ()), (t_acct_statement_wa, ()), (t_acct_syp_invoice, ()), (t_owner_stale_session, ()), (t_dash_seed_load, ()), (t_users_columns, ()), (t_save_speed, ()), (t_fast_save, ()), (t_fast_save_real_pdf, ()), (t_wa_quote_draft, ()), (t_wa_pdf, ()), (t_price_sync, ()), (t_sufiya_site, (tmp,))]:
            if only and fn.__name__ not in only: continue
            await fn(p, b, port, *args)
        await b.close()
    httpd.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for ok, n in results if not ok]
    print(('كل الفحوصات نجحت: %d' % len(results)) if not bad else ('فشل %d من %d' % (len(bad), len(results))))
    sys.exit(1 if bad else 0)

asyncio.run(main())
