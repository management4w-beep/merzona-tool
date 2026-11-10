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
          out.read = await downloadDriveJsonFile(a.id, t);
          out.kids = (await listDriveFolderChildrenSimple(ref, t)).map(f => f.name).sort();
          out.next = await computeNextReferenceSeq('M-Q-260', t, UAE);
          return out; }""", UAE)
        check(r['t'] == 'mzproxy', 'الصفحة ما بتاخد مفتاح درايف حقيقي')
        check(r['year'] and r['sameYear'], 'لقى مجلد السنة عن طريق السيرفر')
        check(r['ref'] and r['refAgain'], 'إنشاء مجلد عرض جديد وما بيتكرر')
        check(r['sameFile'] and r['read']['fields']['m-client'] == 'زبون معدّل', 'حفظ ملف البيانات وتحديثه وقراءته (عربي)')
        st = state(); f = {x['name']: x for x in st['files']}
        check(f.get('M-Q-260099.pdf', {}).get('len') == 300000 and f['M-Q-260099.pdf']['mimeType'] == 'application/pdf', 'رفع PDF بحجمه ونوعه الصحيح')
        check(r['kids'] == ['M-Q-260099-data.json', 'M-Q-260099.pdf'], 'قائمة ملفات مجلد العرض')
        check(r['next'] is not None, 'اقتراح الرقم المرجعي الجاي شغال (' + str(r['next']) + ')')
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
        await b.close()
    httpd.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for ok, n in results if not ok]
    print(('كل الفحوصات نجحت: %d' % len(results)) if not bad else ('فشل %d من %d' % (len(bad), len(results))))
    sys.exit(1 if bad else 0)

asyncio.run(main())
