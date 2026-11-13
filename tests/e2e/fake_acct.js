/* سيرفر محلي لفحص المساعد المحاسبي: acct-routes.js + acct-ai.js الحقيقيين (من مستودع السيرفر)، وذكاء اصطناعي وهمي.
   تشغيل: node tests/e2e/fake_acct.js <مسار مستودع السيرفر>  → بيطبع PORT <رقم> */
'use strict';
const http = require('http'), fs = require('fs'), os = require('os'), path = require('path');
const SERVER_DIR = process.argv[2];
const DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'fake-acct-'));
const routes = [];
const reg = (m) => (p, ...h) => { const keys = []; const re = new RegExp('^' + p.replace(/:([a-z]+)/g, (_, k) => { keys.push(k); return '([^/]+)'; }) + '$'); routes.push({ m, re, keys, h }); };
const app = { get: reg('GET'), post: reg('POST') };
const devices = { OWNERDEV: { status: 'approved', isOwner: true }, STAFFDEV: { status: 'approved' } };
const store = {};
const acct = require(path.join(SERVER_DIR, 'acct-routes.js'))(app, {
  loadDevices: () => devices, loadSessions: () => ({ S1: { username: 'sami', createdAt: Date.now() } }), loadUsers: () => ({ sami: { username: 'sami', permissions: { accounting: true } } }),
  sanitizePermissions: (p) => p || {}, readJsonStore: (f) => store[f] || null, writeJsonStore: (f, v) => { store[f] = JSON.parse(JSON.stringify(v)); }, dataDir: DATA, drive: null,
});
// الذكاء الاصطناعي الوهمي: بيرجّع حسب الرسالة
const asked = [];
const fakeFetch = async (u, o) => {
  const b = JSON.parse(o.body); asked.push(b);
  const last = b.messages[b.messages.length - 1];
  const parts = Array.isArray(last.content) ? last.content : [{ type: 'text', text: last.content }];
  const txt = parts.filter((c) => c.type === 'text').map((c) => c.text).join('\n');
  const hasImg = parts.some((c) => c.type === 'image');
  let out;
  if (/قبضت/.test(txt)) out = { reply: 'حضّرتلك سند قبض. أبو أحمد مش موجود فرح ينضاف زبون جديد.', actions: [{ summary: 'قبض 2000$ كاش من أبو أحمد - دفعة مقدمة', newParty: { name: 'أبو أحمد', kind: 'customer' }, doc: { type: 'receipt', date: '2026-11-13', currency: 'USD', acct: '1000', amount: 2000, project: 'فيلا الخويش', notes: 'دفعة أولى' } }] };
  else if (hasImg) out = { reply: 'قريت الفاتورة: مؤسسة النور، زجاج 14 لوح.', actions: [{ summary: 'فاتورة مورد مؤسسة النور - زجاج', newParty: { name: 'مؤسسة النور', kind: 'vendor' }, doc: { type: 'bill', date: '2026-11-12', currency: 'USD', ref: '125', lines: [{ desc: 'زجاج سكريت 10مم', acct: '5010', qty: 14, price: 85 }] } }] };
  else if (/غلط/.test(txt)) out = { reply: 'تفضل', actions: [{ summary: 'مصروف بدون حساب', doc: { type: 'expense', date: '2026-11-13', currency: 'USD', lines: [{ desc: 'مازوت', acct: '6300', amount: 50 }] } }] };
  else out = { reply: 'الصندوق فيه رصيد حسب الدفتر.', actions: [] };
  return { ok: true, status: 200, json: async () => ({ content: [{ type: 'text', text: JSON.stringify(out) }], usage: { input_tokens: 9000, output_tokens: 400 } }) };
};
const { createAcctAi, mountAcctAiRoutes } = require(path.join(SERVER_DIR, 'acct-ai.js'));
const ai = createAcctAi({ dataDir: DATA, getKey: () => 'sk-ant-test', fetch: fakeFetch, log: { error() {} } });
mountAcctAiRoutes(app, ai, { who: acct.who, books: acct.BOOK_IDS });
app.get('/__asked', (req, res) => res.json({ n: asked.length, last: asked[asked.length - 1] ? { model: asked[asked.length - 1].model, types: (asked[asked.length - 1].messages.slice(-1)[0].content || []).map ? asked[asked.length - 1].messages.slice(-1)[0].content.map((c) => c.type) : [] } : null }));

http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*'); res.setHeader('Access-Control-Allow-Headers', '*'); res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,OPTIONS');
  if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }
  const u = new URL(req.url, 'http://x');
  res.status = (c) => { res.statusCode = c; return res; }; res.json = (o) => { res.setHeader('content-type', 'application/json'); res.end(JSON.stringify(o)); }; res.set = (k, v) => res.setHeader(k, v);
  req.query = Object.fromEntries(u.searchParams); req.path = u.pathname;
  const r = routes.find((x) => x.m === req.method && x.re.test(u.pathname));
  if (!r) { res.statusCode = 404; return res.end('{}'); }
  const m = r.re.exec(u.pathname); req.params = {}; r.keys.forEach((k, i) => { req.params[k] = decodeURIComponent(m[i + 1]); });
  const run = () => { let i = 0; const next = () => { const f = r.h[i++]; if (f) f(req, res, next); }; next(); };
  if (req.method === 'POST' && !/\/ai\//.test(u.pathname)) { const ch = []; req.on('data', (c) => ch.push(c)); req.on('end', () => { try { req.body = JSON.parse(Buffer.concat(ch).toString('utf8') || '{}'); } catch (_) { req.body = {}; } run(); }); }
  else run();
}).listen(0, '127.0.0.1', function () { console.log('PORT ' + this.address().port); });
