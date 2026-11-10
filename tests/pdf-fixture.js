/* ملف PDF تجريبي (للفحوصات بس): جدول نصي + مسقط مدوّر بخط Type0 + بلوك Form */
'use strict';
const zlib = require('zlib');
// كاتب PDF مصغّر
function buildPdf(pagesSpec, { objStm = false } = {}) {
  const objs = []; // [num, body(Buffer|string), streamData?]
  const add = (body, stream) => { objs.push([objs.length + 1, body, stream]); return objs.length; };
  const fontHelv = 0, catalog = add(''), pagesId = add('');
  const helv = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding /FirstChar 32 /LastChar 126 /Widths [' + Array(95).fill(556).join(' ') + '] >>');
  // خط Type0: الرموز حرفين بايت، والـToUnicode بيرجّعهم لحروفهم (رموز مخربطة عن قصد: 'A'=0x0100+code)
  const cmap = '/CIDInit /ProcSet findresource begin 12 dict begin begincmap 1 begincodespacerange <0000> <FFFF> endcodespacerange 1 beginbfrange <0120> <017E> <0020> endbfrange endcmap end end';
  const tu = add('<< /Length ' + Buffer.byteLength(cmap) + ' >>', Buffer.from(cmap));
  const cidf = add('<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Arial /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /DW 600 /W [ 288 [ 278 ] ] >>');
  const t0 = add('<< /Type /Font /Subtype /Type0 /BaseFont /Arial /Encoding /Identity-H /DescendantFonts [ ' + cidf + ' 0 R ] /ToUnicode ' + tu + ' 0 R >>');
  const pageIds = [];
  for (const sp of pagesSpec) {
    const content = Buffer.from(sp.content);
    const z = zlib.deflateSync(content);
    const cid = add('<< /Length ' + z.length + ' /Filter /FlateDecode >>', z);
    let xo = '';
    if (sp.form) { const fz = zlib.deflateSync(Buffer.from(sp.form)); const f = add('<< /Type /XObject /Subtype /Form /BBox [0 0 2000 2000] /Matrix [1 0 0 1 100 100] /Resources << /Font << /F1 ' + helv + ' 0 R >> >> /Length ' + fz.length + ' /Filter /FlateDecode >>', fz); xo = ' /XObject << /Fm1 ' + f + ' 0 R >>'; }
    pageIds.push(add('<< /Type /Page /Parent ' + pagesId + ' 0 R /MediaBox [0 0 1191 842]' + (sp.rotate ? ' /Rotate ' + sp.rotate : '') + ' /Resources << /Font << /F1 ' + helv + ' 0 R /F2 ' + t0 + ' 0 R >>' + xo + ' >> /Contents ' + cid + ' 0 R >>'));
  }
  objs[catalog - 1][1] = '<< /Type /Catalog /Pages ' + pagesId + ' 0 R >>';
  objs[pagesId - 1][1] = '<< /Type /Pages /Kids [' + pageIds.map((i) => i + ' 0 R').join(' ') + '] /Count ' + pageIds.length + ' >>';
  // Object stream: منحط فيه خط Helvetica (متل ملفات PDF 1.5+)
  let stmPart = [];
  if (objStm) {
    const inner = objs.filter(([n, , st]) => n === helv && !st);
    const hdr = inner.map(([n], k) => n + ' ' + 0).join(' ');
    let body = '', offs = [];
    for (const [n, b] of inner) { offs.push(body.length); body += b + '\n'; }
    const head = inner.map(([n], k) => n + ' ' + offs[k]).join(' ') + '\n';
    const z = zlib.deflateSync(Buffer.from(head + body));
    const osId = objs.length + 1;
    stmPart = [[osId, '<< /Type /ObjStm /N ' + inner.length + ' /First ' + Buffer.byteLength(head) + ' /Length ' + z.length + ' /Filter /FlateDecode >>', z]];
    for (const o of objs) if (o[0] === helv) o[1] = null; // ما عاد موجود برّا الـObjStm
    void hdr;
  }
  const parts = [Buffer.from('%PDF-1.5\n%\xe2\xe3\xcf\xd3\n', 'latin1')];
  for (const [n, b, st] of objs.concat(stmPart)) {
    if (b == null) continue;
    parts.push(Buffer.from(n + ' 0 obj\n' + b + (st ? '\nstream\n' : '\n'), 'latin1'));
    if (st) parts.push(st, Buffer.from('\nendstream', 'latin1'));
    parts.push(Buffer.from('\nendobj\n', 'latin1'));
  }
  parts.push(Buffer.from('trailer\n<< /Root ' + catalog + ' 0 R >>\n%%EOF\n', 'latin1'));
  return new Uint8Array(Buffer.concat(parts));
}
const esc = (s) => s.replace(/[()\\]/g, (c) => '\\' + c);
const T = (x, y, s, size = 10) => 'BT /F1 ' + size + ' Tf 1 0 0 1 ' + x + ' ' + y + ' Tm (' + esc(s) + ') Tj ET\n';
// نفس النص بخط Type0 (كل حرف = 0x0100 + رمزه)
const T2 = (x, y, s, size = 10) => 'BT /F2 ' + size + ' Tf ' + x + ' ' + y + ' Td <' + [...s].map((c) => (0x100 + c.charCodeAt(0)).toString(16).padStart(4, '0')).join('') + '> Tj ET\n';

function sample(opts) {
  // صفحة 1: جدول نصي (عناوين بكلمتين "STRUCT SIZE")، المقاسات ارتفاع×عرض متل مكتب البراق، بالسنتيمتر
  let sched = T(60, 780, 'SCHEDULE OF WINDOWS', 14) + T(60, 750, 'TYPE') + T(140, 750, 'STRUCT. SIZE') + T(260, 750, 'LOCATION') + T(400, 750, 'NOS');
  const rows = [['W01', '370x250', 4], ['W02', '330x70', 2], ['D1', '260x100', 3], ['D2', '220x90', 1]];
  rows.forEach(([m, s, q], k) => { const y = 725 - k * 22; sched += T(60, y, m) + T(140, y, s) + T(260, y, 'GROUND FLOOR') + T(400, y, String(q)); });
  // صفحة 2: مسقط (رموز بخط Type0 + كلمات متقطعة بـTJ) - مدوّرة 270 درجة
  let plan = '';
  for (let k = 0; k < 4; k++) plan += T2(100 + k * 60, 300, 'W1', 7);
  plan += T2(100, 400, 'W2', 7) + T2(160, 400, 'W2', 7);
  for (let k = 0; k < 3; k++) plan += T2(300 + k * 40, 500, 'D1', 7);
  plan += 'BT /F1 9 Tf 50 60 Td [(GROUND) -600 (FLOOR) -600 (PLAN)] TJ ET\n';
  // صفحة 3: D2 جوّا Form XObject (بلوك مكرّر)
  const page3 = 'q 1 0 0 1 0 0 cm /Fm1 Do Q\n';
  const form = T(10, 10, 'D2', 7);
  return { sched, plan, page3, form, pdf: buildPdf([{ content: sched }, { content: plan, rotate: 270 }, { content: page3, form }], opts || { objStm: true }) };
}
module.exports = { buildPdf, T, T2, sample };
if (require.main === module) process.stdout.write(Buffer.from(sample().pdf).toString('base64'));
