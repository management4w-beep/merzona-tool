/* سيرفر محلي للفحوصات: drive-proxy.js الحقيقي (من مستودع السيرفر) + جوجل درايف وهمي بالذاكرة.
   الصفحات بالفحص بتحكي معو بدل السيرفر الحقيقي، فمنتأكد إنو كل طلبات درايف تبع الصفحات بتمرق صح.
   تشغيل: node tests/e2e/fake_drive.js <مسار مستودع السيرفر>  → بيطبع PORT <رقم> */
'use strict';
const http = require('http'), fs = require('fs'), os = require('os'), path = require('path');
const SERVER_DIR = process.argv[2];
const mount = require(path.join(SERVER_DIR, 'drive-proxy.js'));

const routes = [];
const exact = {};
const app = { all: (re, ...h) => routes.push({ re, h }), post: (p, h) => { exact['POST ' + p] = h; } };
const express = { raw: () => (req, res, next) => { const ch = []; req.on('data', (c) => ch.push(c)); req.on('end', () => { req.body = Buffer.concat(ch); next(); }); } };

const UAE = '13q5WtejXrydWEeIEZ7pZoon6ocyVuX1D', SYR = '1tQkVAUHGy9_Tm2JZxlkkTvGUTxAWM8uS', CAT = '13QxtnBbXx3SuOZIu8hA90TiD7T2CiMoC', BK = '1FL-I0R4qXdAtqLF8JgcranzKsffKgLzy', OUT = 'OUTSIDE_FOLDER_0001';
const FOLDER = 'application/vnd.google-apps.folder';
const files = new Map(); let n = 0; const upstream = []; const sessionsUp = {}; const directPuts = [];
const nid = () => 'FAKE' + String(++n).padStart(10, '0');
function add(id, parent, name, mimeType, content) { files.set(id, { id, name, mimeType: mimeType || 'application/json', parents: parent ? [parent] : [], trashed: false, content: Buffer.from(content || ''), modifiedTime: new Date(Date.now() - 3600e3).toISOString() }); return id; }
add('MYROOT00000001', null, 'My Drive', FOLDER);
[UAE, SYR, CAT, BK, OUT].forEach((id) => add(id, 'MYROOT00000001', id, FOLDER));
add('SECRET_FILE_00001', OUT, 'secret.pdf', 'application/pdf', 'SECRET');
const y = add(nid(), UAE, '2026', FOLDER);
const rf = add(nid(), y, 'M-Q-260001', FOLDER);
add(nid(), rf, 'M-Q-260001-data.json', 'application/json', JSON.stringify({ fields: { 'm-client': 'Test Client', 'm-ref': 'M-Q-260001' }, grandTotal: 1000 }));
add(nid(), rf, 'M-Q-260001.html', 'text/html', '<html>q</html>');
const rf2 = add(nid(), y, 'M-Q-260003', FOLDER);
add(nid(), rf2, 'M-Q-260003-data.json', 'application/json', '{"fields":{"m-ref":"M-Q-260003"}}');
add(nid(), UAE, 'merzona-sync-data.json', 'application/json', JSON.stringify({ merzona_contracts: { 'M-Q-260001': { client: 'Test Client' } }, merzona_payroll_employees: { e1: { name: 'موظف', salary: 100 } }, merzona_payroll_employees__ts: { e1: 1 } }));
const sh = add(nid(), CAT, 'Showers', FOLDER);
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');
add(nid(), sh, 'a.png', 'image/png', PNG); add(nid(), sh, 'b.png', 'image/png', PNG);
add(nid(), CAT, 'pergolas', FOLDER);
const dz = add(nid(), UAE, '_Designs', FOLDER);
const dr = add(nid(), UAE, '_Drafts', FOLDER);
add('DRAFT_FILE_000001', dr, 'd1.json', 'application/json', JSON.stringify({ draftId: 'd1', label: 'مسودة تجربة', data: {} }));
add(nid(), dz, 'M-Q-260001-design.json', 'application/json', JSON.stringify({ ref: 'M-Q-260001', name: 'تصميم تجربة', savedAt: Date.now(), designItems: [{ id: 1, shapeType: 'window', width: 1200, height: 1500, label: 'W1' }] }));

function evalQ(q, f) {
  const parents = [...q.matchAll(/'([^']+)' in parents/g)].map((m) => m[1]);
  if (!f.parents.some((p) => parents.includes(p))) return false;
  const un = (s) => s.replace(/\\(.)/g, '$1');
  let m;
  if ((m = /name = '((?:[^'\\]|\\.)*)'/.exec(q)) && f.name !== un(m[1])) return false;
  if ((m = /name contains '((?:[^'\\]|\\.)*)'/.exec(q)) && f.name.indexOf(un(m[1])) < 0) return false;
  if ((m = /mimeType = '([^']*)'/.exec(q)) && f.mimeType !== m[1]) return false;
  if ((m = /mimeType != '([^']*)'/.exec(q)) && f.mimeType === m[1]) return false;
  if ((m = /trashed = (true|false)/.exec(q)) && String(f.trashed) !== m[1]) return false;
  return true;
}
const pub = (f) => ({ id: f.id, name: f.name, mimeType: f.mimeType, parents: f.parents, modifiedTime: f.modifiedTime, trashed: f.trashed, md5Checksum: require('crypto').createHash('md5').update(f.content).digest('hex'), webViewLink: 'https://drive.google.com/file/d/' + f.id + '/view', size: String(f.content.length) });
const R = (status, obj, ct) => new Response(Buffer.isBuffer(obj) ? obj : JSON.stringify(obj), { status, headers: { 'content-type': ct || 'application/json; charset=UTF-8' } });
function parseMultipart(body, ct) {
  const b = '--' + /boundary=(?:"([^"]+)"|([^;]+))/.exec(ct).slice(1).find(Boolean).trim();
  const raw = body.toString('latin1'); const parts = raw.split(b).slice(1, -1).map((s) => { const i = s.indexOf('\r\n\r\n'); return { head: s.slice(0, i), body: Buffer.from(s.slice(i + 4, -2), 'latin1') }; });
  return { meta: JSON.parse(parts[0].body.toString('utf8')), media: parts[1] ? parts[1].body : Buffer.alloc(0), mediaType: ((parts[1] && /content-type:\s*([^\r\n;]+)/i.exec(parts[1].head)) || [])[1] };
}
async function fakeFetch(url, o) {
  o = o || {}; const u = new URL(url); const p = u.pathname; const m = o.method || 'GET';
  upstream.push(m + ' ' + p + u.search);
  if (o.headers.Authorization !== 'Bearer REAL-SERVER-TOKEN') return R(401, { error: 'bad token' });
  let mm;
  if (u.searchParams.get('uploadType') === 'resumable') {
    const sid = 'S' + (++n); const meta = JSON.parse(Buffer.from(o.body || '{}').toString() || '{}');
    sessionsUp[sid] = { method: m, id: (/files\/([^/?]+)/.exec(p) || [])[1], meta, ctype: o.headers['X-Upload-Content-Type'], origin: o.headers.Origin };
    return new Response('', { status: 200, headers: { location: 'http://127.0.0.1:' + server.address().port + '/__upload/' + sid } });
  }
  if (p === '/drive/v3/about') return R(200, { user: { emailAddress: 'owner@x' }, storageQuota: { usage: '10', limit: '100' } });
  if (p === '/drive/v3/files' && m === 'GET') return R(200, { files: [...files.values()].filter((f) => evalQ(u.searchParams.get('q'), f)).sort((a, b) => a.name.localeCompare(b.name)).map(pub) });
  if ((mm = /^\/drive\/v3\/files\/([^/]+)$/.exec(p))) {
    const f = files.get(mm[1]); if (!f) return R(404, { error: { code: 404 } });
    if (m === 'GET') return u.searchParams.get('alt') === 'media' ? R(200, f.content, f.mimeType) : R(200, pub(f));
    if (m === 'PATCH') {
      const j = o.body ? JSON.parse(Buffer.from(o.body).toString() || '{}') : {};
      if ('trashed' in j) f.trashed = j.trashed; if (j.name) f.name = j.name;
      const add2 = u.searchParams.get('addParents'), rem = u.searchParams.get('removeParents');
      if (add2) f.parents = f.parents.filter((x) => x !== rem).concat([add2]);
      f.modifiedTime = new Date().toISOString(); return R(200, pub(f));
    }
  }
  if (p === '/drive/v3/files' && m === 'POST') { const j = JSON.parse(Buffer.from(o.body).toString()); return R(200, pub(files.get(add(nid(), j.parents[0], j.name, j.mimeType)))); }
  if (p === '/upload/drive/v3/files' && m === 'POST') { const mp = parseMultipart(Buffer.from(o.body), o.headers['Content-Type']); return R(200, pub(files.get(add(nid(), mp.meta.parents[0], mp.meta.name, mp.meta.mimeType || mp.mediaType, mp.media)))); }
  if ((mm = /^\/upload\/drive\/v3\/files\/([^/]+)$/.exec(p)) && m === 'PATCH') { const f = files.get(mm[1]); f.content = Buffer.from(o.body); f.modifiedTime = new Date().toISOString(); return R(200, pub(f)); }
  return R(404, { error: 'fake: ' + m + ' ' + p });
}
const devices = { dev1: { status: 'approved', isOwner: true, name: 'Owner' }, dev2: { status: 'approved', name: 'Staff' } };
const sessions = { s2: { username: 'sam', createdAt: Date.now() } };
const users = { sam: { username: 'sam', permissions: { quotation: true, catalogs: false } } };
const proxy = mount(app, { express, loadDevices: () => devices, loadSessions: () => sessions, loadUsers: () => users, effectivePermissions: (u) => Object.assign({}, u.permissions),
  getAccessToken: async () => 'REAL-SERVER-TOKEN', dataDir: fs.mkdtempSync(path.join(os.tmpdir(), 'fd-')), fetch: fakeFetch, log: { error() {} },
  areas: { work: [UAE, SYR, BK], catalog: [CAT] } });

// بيانات الفريق عالسيرفر (team-store.js الحقيقي) - أول مرة بتستورد ملف المزامنة الوهمي يلي فوق
const team = require(path.join(SERVER_DIR, 'team-store.js'));
const syncFile = () => [...files.values()].find((f) => f.name === 'merzona-sync-data.json');
const teamStore = team.createTeamStore({ dataDir: fs.mkdtempSync(path.join(os.tmpdir(), 'ft-')), mirrorDelayMs: 200, log: { log() {}, error() {} },
  readDriveSyncFile: async () => JSON.parse(syncFile().content.toString() || '{}'),
  writeDriveSyncFile: async (d) => { syncFile().content = Buffer.from(JSON.stringify(d)); } });
team.mountTeamRoutes({ get: (p, h) => { exact['GET ' + p] = h; }, put: (p, h) => { exact['PUT ' + p] = h; } }, teamStore, { who: proxy.who });
users.pay = { username: 'pay', permissions: { quotation: true, payroll: true } }; sessions.s3 = { username: 'pay', createdAt: Date.now() };

// عروض الأسعار عالسيرفر (quote-store.js الحقيقي) - بينقل العروض الموجودة بدرايف الوهمي أول ما يشتغل
const qs = require(path.join(SERVER_DIR, 'quote-store.js'));
const quoteDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fq-'));
const quoteStore = qs.createQuoteStore({ dataDir: quoteDir, roots: { uae: UAE, syria: SYR }, log: { log() {}, error() {} },
  drive: { list: async (id) => [...files.values()].filter((f) => f.parents.includes(id) && !f.trashed).map((f) => ({ id: f.id, name: f.name, mimeType: f.mimeType, modifiedTime: f.modifiedTime })),
    text: async (id) => files.get(id).content.toString('utf8') } });
const chain = (hs) => (req, res) => { let i = 0; const nx = () => { const f = hs[i++]; if (f) f(req, res, nx); }; nx(); };
qs.mountQuoteRoutes({ get: (p, ...h) => { exact['GET ' + p] = chain(h); }, put: (p, ...h) => { exact['PUT ' + p] = chain(h); }, post: (p, ...h) => { exact['POST ' + p] = chain(h); } }, quoteStore, { who: proxy.who });
quoteStore.startImport('فحص');

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.url.startsWith('/__file/')) { const nm = decodeURIComponent(req.url.slice(8)); const f = [...files.values()].filter((x) => x.name === nm).pop(); if (!f) { res.statusCode = 404; return res.end(); } res.setHeader('Content-Type', f.mimeType); return res.end(f.content); }
  if (req.url === '/__state') { res.setHeader('Content-Type', 'application/json'); return res.end(JSON.stringify({ files: [...files.values()].map((f) => Object.assign(pub(f), { text: /json|html|text/.test(f.mimeType) ? f.content.toString() : null, len: f.content.length })), upstream, directPuts })); }
  res.set = (k, v) => { res.setHeader(k, v); return res; };
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (o) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(o)); return res; };
  res.send = (t) => { res.end(t); return res; };
  req.originalUrl = req.url;
  if (req.method === 'OPTIONS') { res.setHeader('Access-Control-Allow-Headers', '*'); res.setHeader('Access-Control-Allow-Methods', '*'); return res.end(); }
  if (req.url.startsWith('/__upload/') && req.method === 'PUT') {
    const se = sessionsUp[req.url.slice(10)]; const ch = [];
    req.on('data', (c) => ch.push(c)); req.on('end', () => {
      if (!se) { res.statusCode = 404; return res.end('{}'); }
      const body = Buffer.concat(ch); directPuts.push({ len: body.length, ctype: req.headers['content-type'], origin: se.origin });
      let f;
      if (se.method === 'POST') f = files.get(add(nid(), se.meta.parents[0], se.meta.name, se.meta.mimeType || se.ctype, body));
      else { f = files.get(se.id); f.content = body; f.modifiedTime = new Date().toISOString(); }
      delete sessionsUp[req.url.slice(10)];
      res.setHeader('Content-Type', 'application/json'); res.statusCode = se.method === 'POST' ? 200 : 200; res.end(JSON.stringify(pub(f)));
    }); return;
  }
  if (req.url === '/__quotes') { let audit = []; try { audit = fs.readFileSync(path.join(quoteDir, 'quotes', 'quotes-audit.jsonl'), 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)); } catch (_) {} return res.json({ list: quoteStore.list(true), status: quoteStore.importStatus(), audit, items: Object.fromEntries(quoteStore.list(true).items.map((x) => [x.ref, quoteStore.get(x.ref)])) }); }
  if (req.url === '/__quotes-off') { exact.__off = true; return res.json({ ok: true }); }
  if (req.url === '/__quotes-on') { exact.__off = false; return res.json({ ok: true }); }
  if (exact.__off && req.url.startsWith('/quotes')) { res.statusCode = 503; return res.end('{}'); }
  if (req.url === '/__team') return res.json({ status: teamStore.status(), data: teamStore.status() ? teamStore.view({ admin: true, perms: {} }).data : null });
  const ex = exact[req.method + ' ' + req.url.split('?')[0]];
  if (ex) { req.query = Object.fromEntries(new URL(req.url, 'http://x').searchParams); const ch = []; req.on('data', (c) => ch.push(c)); req.on('end', () => { try { req.body = ch.length ? JSON.parse(Buffer.concat(ch).toString()) : {}; } catch (_) { req.body = {}; } ex(req, res); }); return; }
  const p = req.url.split('?')[0]; const r = routes.find((x) => x.re.test(p));
  if (!r) { res.statusCode = 404; return res.end('no route'); }
  req.params = { 0: r.re.exec(p)[1] };
  let i = 0; const next = () => { const fn = r.h[i++]; if (fn) fn(req, res, next); }; next();
});
server.listen(0, '127.0.0.1', () => console.log('PORT ' + server.address().port));
