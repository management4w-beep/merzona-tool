/* فحوصات قارئ الـDWG (dwg-read.js):
   كل نسخة أوتوكاد (2000 / 2004 / 2010 / 2013 / 2018) منقارنها بملف DXF يلي طلّعه أوتوكاد نفسه لنفس الرسمة:
   كل نص لازم يطلع بنفس الكلام ونفس المكان، والاستخراج (الرموز والجداول) لازم يطلع نفس الشي من الصيغتين.
   ملفات الفحص من مشروع LibreDWG (رخصة GPL) فما منحطها بالمستودع: منقراها من MZ_DWG_FIXTURES إذا موجودة. */
'use strict';
const fs = require('fs'), path = require('path');
const D = require('../dwg-read.js');
const C = require('../cad-import.js');
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('✗', m); } };

const DIR = process.env.MZ_DWG_FIXTURES || '/tmp/claude-0/-home-claude/763d6975-41b8-5b57-9416-4a2e9e40fbf3/scratchpad/dwg/lw/test/test-data';
if (!fs.existsSync(path.join(DIR, 'example_2004.dwg'))) {
  console.log('DWG IMPORT SKIP (ما في ملفات فحص DWG بـ ' + DIR + ')');
  process.exit(0);
}
const textsOf = (doc) => {
  const out = [];
  const take = (items) => items.forEach((it) => {
    if (it.kind === 'text') out.push(it.text + '@' + it.x.toFixed(1) + ',' + it.y.toFixed(1));
    else if (it.kind === 'insert') it.attribs.forEach((a) => out.push(a.text + '@' + a.x.toFixed(1) + ',' + a.y.toFixed(1)));
  });
  take(doc.entities); Object.values(doc.blocks).forEach((b) => take(b.items));
  return out.sort();
};
for (const v of ['2000', '2004', '2010', '2013', '2018']) {
  const dwg = path.join(DIR, 'example_' + v + '.dwg'), dxf = path.join(DIR, 'example_' + v + '.dxf');
  const t0 = Date.now();
  const doc = C.dwgToDoc(D.readDwg(new Uint8Array(fs.readFileSync(dwg))));
  const ms = Date.now() - t0;
  const ref = C.parseDxf(fs.readFileSync(dxf, 'latin1'));
  const a = textsOf(doc), b = textsOf(ref);
  ok(doc.stats.failed === 0, v + ': كل الكائنات انقرت ' + doc.stats.failed);
  ok(a.length === b.length && a.every((x, i) => x === b[i]), v + ': النصوص ومكانها متل الـDXF ' + a.length + '/' + b.length + ' ' + a.filter((x) => b.indexOf(x) < 0).slice(0, 3).join(' | '));
  const ins = (d) => { const n = []; const w = (items) => items.forEach((it) => { if (it.kind === 'insert') { const nm = it.name.replace(/^\*([A-Z])[0-9A-F]+$/i, '*$1'); n.push(nm + (/^\*T$/i.test(nm) ? '' : '@' + it.x.toFixed(1) + ',' + it.y.toFixed(1))); } }); w(d.entities); Object.values(d.blocks).forEach((bb) => w(bb.items)); return n.sort(); };
  const ia = ins(doc), ib = ins(ref).map((x) => x.replace(/^\*([A-Z])\d+(@|$)/i, '*$1$2').replace(/^\*T@.*$/i, '*T')).sort();
  ok(ia.join() === ib.join(), v + ': البلوكات المدرجة متل الـDXF ' + ia.length + '/' + ib.length);
  const ra = C.extract(doc), rb = C.extract(ref);
  ok(JSON.stringify(ra.rows) === JSON.stringify(rb.rows), v + ': نفس نتيجة الاستخراج');
  ok(ms < 3000, v + ': سرعة ' + ms + 'ms');
}
// ملفات تانية من نفس المجموعة: ما لازم ولا كائن يفشل
for (const f of ['sample_2000.dwg', 'sample_2018.dwg', '2004/Leader.dwg', '2018/Leader.dwg', '2010/Text.dwg', '2013/Text.dwg']) {
  const p = path.join(DIR, f); if (!fs.existsSync(p)) continue;
  let d = null; try { d = D.readDwg(new Uint8Array(fs.readFileSync(p))); } catch (e) { /* */ }
  ok(d && d.stats.failed === 0, f + ' بينقرا كامل');
}
// رسائل واضحة للصيغ يلي ما بتنقرا
const err = (bytes) => { try { D.readDwg(bytes); return ''; } catch (e) { return e.message; } };
ok(err(new Uint8Array(fs.readFileSync(path.join(DIR, 'example_2007.dwg')))) === 'UNSUPPORTED_2007', 'نسخة 2007: رسالة خاصة');
ok(/قديمة/.test(err(new Uint8Array(fs.readFileSync(path.join(DIR, 'example_r14.dwg'))))), 'نسخة قديمة: رسالة واضحة');
ok(/مش ملف DWG/.test(err(new Uint8Array([1, 2, 3, 4, 5, 6, 7]))), 'ملف مش DWG');
const cut = new Uint8Array(fs.readFileSync(path.join(DIR, 'example_2018.dwg'))).slice(0, 3000);
ok(err(cut) !== '', 'ملف مقطوع ما بيعلّق (بيرمي خطأ مفهوم)');
// أرقام لوحات قائمة الرسومات (W-101 لوحة مياه) ما بتنحسب شبابيك
const lst = { units: 0, blocks: {}, entities: ['A-101', 'A-102', 'S-101', 'W-101', 'W-102', 'E-101'].map((t, k) => ({ kind: 'text', x: 0, y: -k * 50, h: 30, text: t, layer: '' })) };
ok(C.extract(lst).rows.length === 0, 'قائمة الرسومات ما بتطلع رموز شبابيك');

console.log(fail ? 'DWG IMPORT FAIL ' + fail : 'DWG IMPORT PASS ' + pass);
process.exit(fail ? 1 : 0);
