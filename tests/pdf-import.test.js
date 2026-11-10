/* فحوصات قارئ الـPDF (pdf-text.js) + استخراج الشبابيك والأبواب منه - ملفات PDF مبنية هون بكل الحالات الصعبة:
   ضغط Flate، Object Stream، خط Type0 (Identity-H) مع ToUnicode، صفحة مدوّرة، Form XObject، TJ مع مسافات */
'use strict';
const P = require('../pdf-text.js');
const C = require('../cad-import.js');
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('✗', m); } };

const { buildPdf, T, sample } = require('./pdf-fixture.js');

(async () => {
  const { sched, plan, pdf } = sample();
  const pages = await P.readPdf(pdf);
  ok(pages.length === 3, 'pages ' + pages.length);
  const w1 = pages[0].words.find((w) => w.text === 'W01');
  ok(w1 && Math.abs(w1.x - 60) < 0.5 && Math.abs(w1.y - 725) < 0.5, 'word position ' + JSON.stringify(w1));
  ok(pages[1].width === 842 && pages[1].height === 1191, 'rotated page size');
  const pw = pages[1].words.map((w) => w.text);
  ok(pw.filter((t) => t === 'W1').length === 4 && pw.filter((t) => t === 'D1').length === 3, 'Type0+ToUnicode tags ' + pw.join(','));
  ok(pw.includes('GROUND') && pw.includes('FLOOR') && pw.includes('PLAN'), 'TJ word split ' + pw.join(','));
  const r1 = pages[1].words.find((w) => w.text === 'W1');
  ok(r1 && Math.abs(r1.x - (842 - 300)) < 0.5 && Math.abs(r1.y - 100) < 0.5 && r1.angle === 90, 'rotate 270 → display coords ' + JSON.stringify(r1));
  const d2 = pages[2].words.find((w) => w.text === 'D2');
  ok(d2 && Math.abs(d2.x - 110) < 0.5 && Math.abs(d2.y - 110) < 0.5, 'form xobject matrix ' + JSON.stringify(d2));

  const r = C.fromPdfPages(pages);
  const f = (m) => r.rows.find((x) => x.mark === m);
  ok(r.order === 'hw', 'size order detected H×W ' + r.order + ' ' + r.orderWhy);
  ok(r.unit === 'cm', 'unit cm ' + r.unit);
  ok(f('W1') && f('W1').w === 2500 && f('W1').h === 3700 && f('W1').qty === 4 && f('W1').ok, 'W1 ' + JSON.stringify(f('W1')));
  ok(f('W2') && f('W2').w === 700 && f('W2').h === 3300 && f('W2').ok, 'W2');
  ok(f('D1') && f('D1').w === 1000 && f('D1').h === 2600 && f('D1').ok, 'D1 3 = 3');
  ok(f('D2') && f('D2').qty === 1 && f('D2').ok, 'D2 counted inside form xobject ' + JSON.stringify(f('D2')));
  ok(r.pages.find((p) => p.page === 2).counted, 'plan page counted');
  // نفس الملف بدون Object Stream
  const r2 = C.fromPdfPages(await P.readPdf(buildPdf([{ content: sched }, { content: plan, rotate: 270 }])));
  ok(r2.rows.find((x) => x.mark === 'W1').ok, 'without object stream');
  // ترتيب مفروض من المستخدم
  const r3 = C.fromPdfPages(pages, { order: 'wh' });
  ok(r3.rows.find((x) => x.mark === 'D1').w === 2600, 'user order override');
  // صفحة دليل (كل رمز مرة) ما بتنعد
  let legend = '';
  ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'D1', 'D2'].forEach((m, k) => { legend += T(60 + k * 50, 100, m, 7); });
  const r4 = C.fromPdfPages(await P.readPdf(buildPdf([{ content: plan, rotate: 270 }, { content: legend }])));
  ok(r4.rows.find((x) => x.mark === 'W1').qty === 4 && r4.pages.find((p) => p.page === 2).legend && !r4.pages.find((p) => p.page === 2).counted, 'legend page not counted');
  const r5 = C.fromPdfPages(await P.readPdf(buildPdf([{ content: plan, rotate: 270 }, { content: legend }])), { countPages: [1, 2] });
  ok(r5.rows.find((x) => x.mark === 'W1').qty === 5, 'user picks pages');
  // نص عادي فيه كلمات width / height ما بيصير جدول
  const prose = T(60, 500, 'The minimum net clear opening height dimension shall be 24 inches') + T(60, 480, 'width shall be 20 inches and size W1 W2');
  const r6 = C.fromPdfPages(await P.readPdf(buildPdf([{ content: prose }])));
  ok(r6.stats.tables === 0, 'prose is not a table');
  // ملف مكسور / مش PDF
  ok((await P.readPdf(new Uint8Array([1, 2, 3]))).length === 0, 'garbage file');
  const cut = pdf.slice(0, Math.floor(pdf.length * 0.6));
  let threw = false; try { await P.readPdf(cut); } catch (e) { threw = true; }
  ok(!threw, 'truncated pdf does not throw');

  console.log(fail ? 'PDF IMPORT FAIL ' + fail : 'PDF IMPORT PASS ' + pass);
  process.exit(fail ? 1 : 0);
})();
