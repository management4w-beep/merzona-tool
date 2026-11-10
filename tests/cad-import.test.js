/* فحوصات قراءة مخططات الأوتوكاد (cad-import.js) - ملفات DXF مبنية هون بنفس شكل يلي بيطلّعه أوتوكاد */
'use strict';
const C = require('../cad-import.js');
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('✗', m); } };

// كاتب DXF مصغّر
function dxf({ units = 4, blocks = [], entities = [], crlf = false }) {
  const L = [];
  const p = (c, v) => { L.push(String(c), String(v)); };
  p(0, 'SECTION'); p(2, 'HEADER'); p(9, '$ACADVER'); p(1, 'AC1027'); p(9, '$INSUNITS'); p(70, units); p(0, 'ENDSEC');
  p(0, 'SECTION'); p(2, 'BLOCKS');
  for (const b of blocks) { p(0, 'BLOCK'); p(8, '0'); p(2, b.name); p(70, 0); p(10, b.bx || 0); p(20, b.by || 0); p(30, 0); b.items.forEach((e) => e(p)); p(0, 'ENDBLK'); p(8, '0'); }
  p(0, 'ENDSEC');
  p(0, 'SECTION'); p(2, 'ENTITIES'); entities.forEach((e) => e(p)); p(0, 'ENDSEC'); p(0, 'EOF');
  return L.join(crlf ? '\r\n' : '\n');
}
const TEXT = (x, y, s, h = 100, layer = 'TEXT') => (p) => { p(0, 'TEXT'); p(8, layer); p(10, x); p(20, y); p(30, 0); p(40, h); p(1, s); };
const MTEXT = (x, y, s, h = 100) => (p) => { p(0, 'MTEXT'); p(8, 'TEXT'); p(10, x); p(20, y); p(30, 0); p(40, h); if (s.length > 250) { p(3, s.slice(0, 250)); p(1, s.slice(250)); } else p(1, s); };
const LINE = (x1, y1, x2, y2) => (p) => { p(0, 'LINE'); p(8, '0'); p(10, x1); p(20, y1); p(30, 0); p(11, x2); p(21, y2); p(31, 0); };
const INSERT = (name, x, y, attribs = [], sx = 1, sy = 1, rot = 0) => (p) => {
  p(0, 'INSERT'); p(8, 'WIN'); if (attribs.length) p(66, 1); p(2, name); p(10, x); p(20, y); p(30, 0); p(41, sx); p(42, sy); p(50, rot);
  if (attribs.length) { attribs.forEach(([tag, val]) => { p(0, 'ATTRIB'); p(8, 'WIN'); p(10, x); p(20, y); p(40, 50); p(1, val); p(2, tag); p(70, 0); }); p(0, 'SEQEND'); p(8, 'WIN'); }
};
const find = (r, mk) => r.rows.find((x) => x.mark === mk);

// 1) جدول صفوف عادي + رموز بالمساقط (واحد منهم عدده غلط)
{
  const ents = [
    TEXT(0, 0, 'WINDOWS & DOORS SCHEDULE', 150),
    TEXT(0, -300, 'TYPE'), TEXT(1500, -300, 'WIDTH'), TEXT(3000, -300, 'HEIGHT'), TEXT(4500, -300, 'QTY'),
    TEXT(0, -600, 'W1'), TEXT(1500, -600, '1200'), TEXT(3000, -600, '1500'), TEXT(4500, -600, '4'),
    TEXT(0, -900, 'W2'), TEXT(1500, -900, '600'), TEXT(3000, -900, '600'), TEXT(4500, -900, '2'),
    TEXT(0, -1200, 'D1'), TEXT(1500, -1200, '900'), TEXT(3000, -1200, '2100'), TEXT(4500, -1200, '2'),
  ];
  // المسقط: W1 ×4، W2 ×2، D1 ×3 (الجدول بيقول 2)
  [[20000, 5000], [22000, 5000], [24000, 5000], [26000, 5000]].forEach(([x, y]) => ents.push(TEXT(x, y, 'W1', 80, 'TAGS')));
  [[20000, 8000], [21000, 8000]].forEach(([x, y]) => ents.push(TEXT(x, y, 'W-2', 80, 'TAGS')));
  [[20000, 9000], [21000, 9000], [22000, 9000]].forEach(([x, y]) => ents.push(TEXT(x, y, 'D01', 80, 'TAGS')));
  const r = C.readDxf(dxf({ entities: ents }));
  ok(r.unit === 'mm', 'unit mm ' + r.unit);
  const w1 = find(r, 'W1'), w2 = find(r, 'W2'), d1 = find(r, 'D1');
  ok(w1 && w1.w === 1200 && w1.h === 1500 && w1.qty === 4 && w1.ok, 'W1 1200x1500 ×4 confirmed by plan tags ' + JSON.stringify(w1));
  ok(w2 && w2.w === 600 && w2.h === 600 && w2.qty === 2 && w2.ok, 'W2 (tag written "W-2") matched');
  ok(d1 && d1.w === 900 && d1.h === 2100 && d1.qty === 2 && !d1.ok && d1.issues.some((s) => /2.*3/.test(s)), 'D1 qty mismatch flagged (schedule 2, plan 3)');
  ok(d1.kind === 'door' && w1.kind === 'window', 'kinds');
  ok(r.rows.length === 3, 'no junk rows ' + r.rows.map((x) => x.mark));
}

// 2) جدول أوتوكاد (ACAD_TABLE = بلوك *T فيه MTEXT منسّق) مُدرج بمكان تاني + CRLF
{
  const cell = (x, y, s) => MTEXT(x, y, '{\\fArial|b0|i0|c0|p34;' + s + '}', 80);
  const blk = { name: '*T1', items: [cell(0, 0, 'MARK'), cell(1000, 0, 'SIZE'), cell(2500, 0, 'NO.'),
    cell(0, -250, 'W3'), cell(1000, -250, '1800 x 1500'), cell(2500, -250, '6'),
    cell(0, -500, 'SD1'), cell(1000, -500, '3000X2400'), cell(2500, -500, '1')] };
  const ents = [INSERT('*T1', 50000, 30000)];
  for (let k = 0; k < 6; k++) ents.push(TEXT(1000 * k, 90000, 'W3', 80));
  ents.push(MTEXT(70000, 90000, '\\A1;SD1', 80));
  const r = C.readDxf(dxf({ blocks: [blk], entities: ents, crlf: true }));
  const w3 = find(r, 'W3'), sd1 = find(r, 'SD1');
  ok(w3 && w3.w === 1800 && w3.h === 1500 && w3.qty === 6 && w3.ok, 'table block W3 ' + JSON.stringify(w3));
  ok(sd1 && sd1.w === 3000 && sd1.h === 2400 && sd1.qty === 1 && sd1.ok && sd1.kind === 'sliding-door', 'SD1 from formatted MTEXT ' + JSON.stringify(sd1));
}

// 2ب) نفس الجدول بس مرسوم بأمر TABLE (كيان ACAD_TABLE مش INSERT)
{
  const cell = (x, y, s) => MTEXT(x, y, s, 80);
  const blk = { name: '*T7', items: [cell(0, 0, 'MARK'), cell(1000, 0, 'WIDTH'), cell(2000, 0, 'HEIGHT'), cell(3000, 0, 'QTY'), cell(0, -250, 'D9'), cell(1000, -250, '1000'), cell(2000, -250, '2400'), cell(3000, -250, '2')] };
  const TABLE = (p) => { p(0, 'ACAD_TABLE'); p(8, 'TBL'); p(100, 'AcDbBlockReference'); p(2, '*T7'); p(10, 40000); p(20, 20000); p(30, 0); p(100, 'AcDbTable'); };
  const r = C.readDxf(dxf({ blocks: [blk], entities: [TABLE, TEXT(0, 0, 'D9', 80), TEXT(900, 0, 'D9', 80)] }));
  const d9 = find(r, 'D9');
  ok(d9 && d9.w === 1000 && d9.h === 2400 && d9.qty === 2 && d9.ok, 'ACAD_TABLE schedule ' + JSON.stringify(d9));
}

// 3) نص واحد فيه كل شي + بلوكات نوافذ بخصائص بدون جدول
{
  const winBlk = { name: 'WINDOW-TAG', items: [LINE(0, 0, 900, 0), LINE(900, 0, 900, 100)] };
  const ents = [TEXT(0, 0, 'FW1 - 2400x1200 (3)'), TEXT(5000, 5000, 'FW1'), TEXT(6000, 5000, 'FW1'), TEXT(7000, 5000, 'FW1')];
  for (let k = 0; k < 3; k++) ents.push(INSERT('WINDOW-TAG', 10000 + k * 2000, 0, [['MARK', 'W5'], ['WIDTH', '900'], ['HEIGHT', '1200']]));
  const r = C.readDxf(dxf({ blocks: [winBlk], entities: ents }));
  const fw = find(r, 'FW1'), w5 = find(r, 'W5');
  ok(fw && fw.w === 2400 && fw.h === 1200 && fw.qty === 3 && fw.ok && fw.kind === 'fixed-window', 'inline text FW1 ' + JSON.stringify(fw));
  ok(w5 && w5.w === 900 && w5.h === 1200 && w5.qty === 3 && !w5.ok && w5.issues.some((s) => /مصدر واحد/.test(s)), 'attributed blocks W5 (single source flagged) ' + JSON.stringify(w5));
}

// 4) جدول مقلوب (العناوين بعمود والرموز ماشية بالعرض) بالسنتيمتر + عناوين عربي
{
  const ents = [
    TEXT(0, 0, 'الرمز', 20), TEXT(0, -50, 'العرض', 20), TEXT(0, -100, 'الارتفاع', 20), TEXT(0, -150, 'العدد', 20),
    TEXT(200, 0, 'W7', 20), TEXT(200, -50, '120', 20), TEXT(200, -100, '150', 20), TEXT(200, -150, '5', 20),
    TEXT(400, 0, 'W8', 20), TEXT(400, -50, '60', 20), TEXT(400, -100, '90', 20), TEXT(400, -150, '1', 20),
  ];
  for (let k = 0; k < 5; k++) ents.push(TEXT(3000 + k * 300, 2000, 'W7', 15));
  ents.push(TEXT(3000, 2500, 'W8', 15));
  const r = C.readDxf(dxf({ units: 5, entities: ents }));
  const w7 = find(r, 'W7'), w8 = find(r, 'W8');
  ok(r.unit === 'cm', 'unit cm guessed ' + r.unit);
  ok(w7 && w7.w === 1200 && w7.h === 1500 && w7.qty === 5 && w7.ok, 'transposed Arabic W7 → mm ' + JSON.stringify(w7));
  ok(w8 && w8.w === 600 && w8.h === 900 && w8.qty === 1 && w8.ok, 'transposed W8');
  const rm = C.readDxf(dxf({ units: 5, entities: ents }), { unit: 'mm' });
  ok(find(rm, 'W7').w === 120, 'unit override');
}

// 5) أشياء ما لازم تنفهم كرموز / ملف فاضي / ملف مكسور
{
  const ents = [TEXT(0, 0, 'WALL 200'), TEXT(0, 100, 'DWG-01'), TEXT(0, 200, 'W'), TEXT(0, 300, 'Level 1'), TEXT(0, 400, 'D 1200'), TEXT(0, 500, 'SECTION A-A')];
  const r = C.readDxf(dxf({ entities: ents }));
  ok(r.rows.length === 0, 'no false marks ' + r.rows.map((x) => x.mark));
  ok(C.readDxf('').rows.length === 0, 'empty file');
  ok(C.readDxf('0\nSECTION\n2\nENTITIES\n0\nTEXT\n1\n').rows.length === 0, 'truncated file does not crash');
  ok(C.cleanMtext('{\\fArial|b1;W1}\\PSecond') === 'W1\nSecond', 'mtext cleanup');
  ok(C.normMark('w 01') === 'W1' && C.normMark('SD-02') === 'SD2' && C.normMark('ن3') === 'ن3' && C.normMark('W12A') === 'W12A' && !C.normMark('W1234'), 'mark normalisation');
}

// 6) بلوك مدوّر ومكبّر فيه الجدول (تحويل الإحداثيات)
{
  const blk = { name: 'SCHED', bx: 100, by: 100, items: [TEXT(100, 100, 'TYPE', 10), TEXT(250, 100, 'WIDTH', 10), TEXT(400, 100, 'HEIGHT', 10), TEXT(100, 70, 'D3', 10), TEXT(250, 70, '1000', 10), TEXT(400, 70, '2200', 10)] };
  const r = C.readDxf(dxf({ blocks: [blk], entities: [INSERT('SCHED', 5000, 5000, [], 10, 10, 90), TEXT(0, 0, 'D3', 80), TEXT(500, 0, 'D3', 80)] }));
  const d3 = find(r, 'D3');
  ok(d3 && d3.w === 1000 && d3.h === 2200 && d3.qty === 2, 'rotated+scaled schedule block ' + JSON.stringify(d3));
}

console.log(fail ? 'CAD IMPORT FAIL ' + fail : 'CAD IMPORT PASS ' + pass);
process.exit(fail ? 1 : 0);
