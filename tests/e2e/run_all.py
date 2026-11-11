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
    # منكشف قائمة البنود للفحص بس (ما بيتغير الملف الأصلي)
    ip = os.path.join(tmp, 'index.html'); s = open(ip, encoding='utf8').read()
    a = "window.WD = window.WD || {};\n"
    assert a in s, 'designer anchor missing'
    s = s.replace(a, a + "WD.__t = { items: function(){ return items; }, selId: function(){ return selectedId; }, sel: function(id){ selectItem(id); } };\n", 1)
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
    r = await pg.evaluate("""() => [mzWaDigits('+971 58 197 5655'), mzWaDigits('0581975655'), mzWaDigits('0939919670'), mzWaDigits('00963939919670'), mzWaDigits('12')]""")
    check(r == ['971581975655', '971581975655', '963939919670', '963939919670', ''], 'تحويل أرقام الزبائن لواتس اب ' + str(r))
    r = await pg.evaluate("""async () => {
      const set = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); };
      set('m-ref', 'M-Q-260221'); set('m-client', 'Hanzalah'); set('m-number', '+971 58 197 5655');
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
    check(r['opened'] and r['opened'].startswith('https://wa.me/971581975655?text=') and 'M-Q-260221' in __import__('urllib.parse').parse.unquote(r['opened']) and 'sign.html' in __import__('urllib.parse').parse.unquote(r['opened']), 'بيفتح محادثة الزبون نفسه مع رابط العرض')
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
          set('co-nameEn', 'Sufiya Glass'); set('co-nameAr', 'صوفيا جلاس'); set('co-fullNameEn', 'Sufiya Glass for Aluminum & Glass'); set('co-email', 'info@sufiyaglass.com'); set('co-website', 'www.sufiyaglass.com'); set('co-phone', '+971500000001');
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
        # 6) الداشبورد
        await pd.reload(); await pd.wait_for_timeout(3000)
        t = await pd.evaluate("document.title + ' | ' + document.body.innerText")
        check('Merzona' not in t and 'ميرزونا' not in t, 'الداشبورد ما فيه اسم ميرزونا')
        check(not errs, 'ما في أخطاء ' + '; '.join(errs[:2]))
        await ctx.close()
    finally:
        proc.kill()

async def main():
    tmp = prepare(); httpd = serve(tmp); port = httpd.server_address[1]
    print('فحص:', SRC)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        await t_types_and_roundtrip(p, b, port)
        await t_old_misguessed(p, b, port)
        await t_edit_panel(p, b, port, False)
        await t_edit_panel(p, b, port, True)
        await t_catalog(p, b, port)
        await t_drive_proxy(p, b, port)
        await t_share_pdf(p, b, port)
        await t_cad_import(p, b, port)
        await t_quotes_server(p, b, port)
        await t_company(p, b, port)
        await b.close()
    httpd.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for ok, n in results if not ok]
    print(('كل الفحوصات نجحت: %d' % len(results)) if not bad else ('فشل %d من %d' % (len(bad), len(results))))
    sys.exit(1 if bad else 0)

asyncio.run(main())
