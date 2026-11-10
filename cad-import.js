/* =====================================================================================
   📐 قراءة مخططات الأوتوكاد (DXF) - 2026-11-10، طلب حمدي: "بدي السيستم يقرا مخططات الاوتوكاد ويطالع
   الكميات... تفاصيل النوافذ والأبواب (مقاساتهم) وبحيث يكونوا 100% صحيح".
   - ملف واحد بدون أي مكتبة خارجية (بيشتغل بالمتصفح وبـ node للفحوصات).
   - بيقرا: نصوص (TEXT / MTEXT)، بلوكات (INSERT) مع خصائصها (ATTRIB)، ومحتوى البلوكات المدموجة
     (جداول أوتوكاد ACAD_TABLE بتنحفظ كبلوك فيه نصوص) - كل شي بإحداثياته الحقيقية.
   - بيطلّع النوافذ والأبواب من 3 مصادر مستقلة وبيقارن بينهم:
       1) جدول النوافذ والأبواب (Schedule): صف لكل رمز (W1، D2...) مع العرض والارتفاع والعدد.
       2) بلوكات النوافذ/الأبواب يلي إلها خصائص (رمز + عرض + ارتفاع).
       3) عدّ الرموز المكتوبة عالمخطط (كم مرة W1 مكتوب بالمساقط) = العدد الفعلي.
   - "100% صحيح" ما بيجي من القراءة لحالها: كل بند بيطلع مع مصدره، وإذا مصدرين ما اتفقوا (العدد بالجدول
     غير عدد الرموز بالمخطط، أو المقاس بالجدول غير البلوك) بيتعلّم ⚠️ وما بينضاف إلا بعد ما تأكده إنت.
   ===================================================================================== */
(function (root) {
  'use strict';

  /* ---------- 1) قراءة ملف DXF (أزواج: رمز / قيمة) ---------- */
  function pairs(text) {
    const lines = String(text).replace(/\r\n?/g, '\n').split('\n');
    const out = [];
    for (let i = 0; i + 1 < lines.length; i += 2) {
      const c = parseInt(lines[i].trim(), 10);
      if (Number.isNaN(c)) { i -= 1; continue; } // سطر شاذ - منزيح سطر ومنكمّل
      out.push([c, lines[i + 1]]);
    }
    return out;
  }
  // MTEXT فيه تنسيقات: {\fArial|b1;نص} \P سطر جديد \A1; \H2.5x; ...
  function cleanMtext(s) {
    return String(s)
      .replace(/\\P/g, '\n')
      .replace(/\\[ACFHQTWfhqtwcp][^;\\{}]*;/g, '')
      .replace(/\\S([^;]*);/g, (m, a) => a.replace(/[#^]/, '/'))
      .replace(/\\[LlOoKkNn~]/g, ' ')
      .replace(/\\U\+([0-9A-Fa-f]{4})/g, (m, h) => String.fromCharCode(parseInt(h, 16)))
      .replace(/[{}]/g, '')
      .replace(/\\\\/g, '\\')
      .replace(/%%[cC]/g, 'Ø').replace(/%%[dD]/g, '°').replace(/%%[pP]/g, '±').replace(/%%[uUoO]/g, '')
      .replace(/[ \t]+/g, ' ')
      .trim();
  }
  function cleanText(s) {
    return String(s).replace(/\\U\+([0-9A-Fa-f]{4})/g, (m, h) => String.fromCharCode(parseInt(h, 16)))
      .replace(/%%[cC]/g, 'Ø').replace(/%%[dD]/g, '°').replace(/%%[pP]/g, '±').replace(/%%[uUoO]/g, '').trim();
  }

  function parseDxf(text) {
    const P = pairs(text);
    const doc = { units: 0, blocks: {}, entities: [], warnings: [] };
    let i = 0;
    const n = P.length;
    // كيان واحد: من رمز 0 للرمز 0 الجاي
    function readEntity() {
      const type = P[i][1].trim();
      const e = { type, codes: [] };
      i++;
      while (i < n && P[i][0] !== 0) { e.codes.push(P[i]); i++; }
      return e;
    }
    function num(e, code, d) { for (const [c, v] of e.codes) if (c === code) { const x = parseFloat(v); return Number.isFinite(x) ? x : d; } return d; }
    function str(e, code) { for (const [c, v] of e.codes) if (c === code) return v; return null; }
    function strs(e, code) { return e.codes.filter(([c]) => c === code).map(([, v]) => v); }

    function toItem(e) {
      const t = e.type;
      if (t === 'TEXT' || t === 'ATTRIB' || t === 'ATTDEF') {
        return { kind: t === 'TEXT' ? 'text' : t.toLowerCase(), x: num(e, 10, 0), y: num(e, 20, 0), h: num(e, 40, 0), text: cleanText(str(e, 1) || ''), tag: str(e, 2), layer: str(e, 8) || '' };
      }
      if (t === 'MTEXT') {
        const raw = strs(e, 3).join('') + (str(e, 1) || '');
        return { kind: 'text', x: num(e, 10, 0), y: num(e, 20, 0), h: num(e, 40, 0), text: cleanMtext(raw), layer: str(e, 8) || '', mtext: true };
      }
      // جدول أوتوكاد (TABLE): بينحفظ كبلوك *T ومرسوم بنقطة إدراج متل INSERT
      if (t === 'ACAD_TABLE') return { kind: 'insert', name: str(e, 2) || '', x: num(e, 10, 0), y: num(e, 20, 0), sx: 1, sy: 1, rot: 0, layer: str(e, 8) || '', attribs: [] };
      if (t === 'INSERT') {
        return { kind: 'insert', name: str(e, 2) || '', x: num(e, 10, 0), y: num(e, 20, 0), sx: num(e, 41, 1), sy: num(e, 42, 1), rot: num(e, 50, 0), layer: str(e, 8) || '', attribs: [] };
      }
      if (t === 'DIMENSION') {
        return { kind: 'dim', value: num(e, 42, NaN), text: str(e, 1) || '', x: num(e, 11, num(e, 10, 0)), y: num(e, 21, num(e, 20, 0)), layer: str(e, 8) || '' };
      }
      if (t === 'LINE') return { kind: 'line', pts: [[num(e, 10, 0), num(e, 20, 0)], [num(e, 11, 0), num(e, 21, 0)]] };
      if (t === 'LWPOLYLINE') {
        const xs = strs(e, 10).map(parseFloat), ys = strs(e, 20).map(parseFloat);
        return { kind: 'line', pts: xs.map((x, k) => [x, ys[k]]) };
      }
      return null;
    }
    // يجمع الكيانات لحد ENDSEC أو ENDBLK، والـATTRIB بيلزق بآخر INSERT
    function readList(stopTypes) {
      const list = [];
      let lastInsert = null;
      while (i < n) {
        if (P[i][0] !== 0) { i++; continue; }
        const t = P[i][1].trim();
        if (stopTypes.indexOf(t) >= 0) return list;
        const e = readEntity();
        if (e.type === 'SEQEND') { lastInsert = null; continue; }
        const it = toItem(e);
        if (!it) continue;
        if (it.kind === 'attrib') { if (lastInsert) lastInsert.attribs.push({ tag: it.tag || '', text: it.text, x: it.x, y: it.y, h: it.h }); continue; }
        if (it.kind === 'insert') lastInsert = it; else if (it.kind !== 'attdef') lastInsert = null;
        list.push(it);
      }
      return list;
    }

    while (i < n) {
      const [c, v] = P[i];
      if (c === 0 && v.trim() === 'SECTION' && i + 1 < n && P[i + 1][0] === 2) {
        const sec = P[i + 1][1].trim();
        i += 2;
        if (sec === 'HEADER') {
          while (i < n && !(P[i][0] === 0 && P[i][1].trim() === 'ENDSEC')) {
            if (P[i][0] === 9 && P[i][1].trim() === '$INSUNITS' && i + 1 < n) doc.units = parseInt(P[i + 1][1], 10) || 0;
            i++;
          }
        } else if (sec === 'BLOCKS') {
          while (i < n && !(P[i][0] === 0 && P[i][1].trim() === 'ENDSEC')) {
            if (P[i][0] === 0 && P[i][1].trim() === 'BLOCK') {
              const b = readEntity();
              const name = (b.codes.find(([cc]) => cc === 2) || [0, ''])[1];
              const bx = num(b, 10, 0), by = num(b, 20, 0);
              const items = readList(['ENDBLK', 'ENDSEC']);
              if (i < n && P[i][1].trim() === 'ENDBLK') readEntity();
              doc.blocks[name] = { name, bx, by, items };
            } else i++;
          }
        } else if (sec === 'ENTITIES') {
          doc.entities = readList(['ENDSEC']);
        } else {
          while (i < n && !(P[i][0] === 0 && P[i][1].trim() === 'ENDSEC')) i++;
        }
      } else i++;
    }
    return doc;
  }

  /* ---------- 2) فرد كل شي لإحداثيات المخطط الحقيقية (مع البلوكات المتداخلة) ---------- */
  function flatten(doc) {
    const texts = [], inserts = [], dims = [];
    function walk(items, tf, depth, ctx) {
      for (const it of items) {
        if (it.kind === 'text') { const p = tf(it.x, it.y); texts.push({ x: p[0], y: p[1], h: Math.abs(it.h * (tf.s || 1)) || 0, text: it.text, layer: it.layer, inBlock: ctx }); }
        else if (it.kind === 'dim') { const p = tf(it.x, it.y); dims.push({ x: p[0], y: p[1], value: it.value * (tf.s || 1), text: it.text }); }
        else if (it.kind === 'insert') {
          const p = tf(it.x, it.y);
          const b = doc.blocks[it.name];
          const rec = { name: it.name, x: p[0], y: p[1], sx: it.sx * (tf.s || 1), sy: it.sy * (tf.s || 1), attribs: it.attribs.map((a) => ({ tag: a.tag, text: a.text })), bbox: null, inBlock: ctx };
          inserts.push(rec);
          // النصوص الحرة جوا البلوك (ATTRIB منفصلة فوق): جداول أوتوكاد، عناوين...
          if (b && depth < 6) {
            const r = (it.rot || 0) * Math.PI / 180, cs = Math.cos(r), sn = Math.sin(r);
            const child = (x, y) => { const lx = (x - b.bx) * it.sx, ly = (y - b.by) * it.sy; return tf(it.x + lx * cs - ly * sn, it.y + lx * sn + ly * cs); };
            child.s = (tf.s || 1) * Math.abs(it.sy || 1);
            walk(b.items, child, depth + 1, ctx || it.name);
            // حجم البلوك من خطوطه (للنافذة/الباب المرسوم كبلوك بدون خصائص)
            let mnx = Infinity, mny = Infinity, mxx = -Infinity, mxy = -Infinity;
            for (const li of b.items) if (li.kind === 'line') for (const [x, y] of li.pts) { mnx = Math.min(mnx, x); mny = Math.min(mny, y); mxx = Math.max(mxx, x); mxy = Math.max(mxy, y); }
            if (mnx < Infinity) rec.bbox = { w: (mxx - mnx) * Math.abs(it.sx), h: (mxy - mny) * Math.abs(it.sy) };
          }
        }
      }
    }
    const id = (x, y) => [x, y]; id.s = 1;
    walk(doc.entities, id, 0, null);
    return { texts: texts.filter((t) => t.text), inserts, dims };
  }

  /* ---------- 3) التعرّف على الرموز والمقاسات ---------- */
  // رموز النوافذ والأبواب الشائعة بالمخططات: W1 D2 SD3 SW-1 CW01 FW1 GD1 WD1 V1 ن1 ب1
  const MARK_RE = /^(?:(W|D|WD|DW|SD|SW|CW|FW|FD|GD|AD|ED|MD|WN|DR|OP|V|SK|ن|ب|ش)[\s.\-_]?(\d{1,3})([A-Za-z])?)$/i;
  // رموز بتنقبل بس إذا مكتوبة بنفس حجم رموز الشبابيك والأبواب بنفس الصفحة أو موجودة بالجدول (C1 ممكن تكون عمود إنشائي)
  const MARK_EXT_RE = /^(?:(C)[\s.\-_]?(\d{1,3})([A-Za-z])?)$/i;
  function normMark(s, ext) {
    const t = String(s).trim().replace(/\s+/g, '');
    const m = MARK_RE.exec(t) || (ext ? MARK_EXT_RE.exec(t) : null);
    if (!m) return null;
    return (m[1].toUpperCase() + m[2].replace(/^0+(?=\d)/, '') + (m[3] ? m[3].toUpperCase() : ''));
  }
  const SIZE_RE = /(\d{1,5}(?:[.,]\d+)?)\s*(?:[xX×*]|\s[xX]\s)\s*(\d{1,5}(?:[.,]\d+)?)/;
  const numOf = (s) => parseFloat(String(s).replace(',', '.'));
  const HEAD = {
    mark: /^(type|mark|ref|code|no\.?|tag|symbol|item|الرمز|رمز|النوع|نوع|الرقم|رقم)$/i,
    width: /^(w|width|wid|wdth|w\s*\(mm\)|width\s*\(mm\)|عرض|العرض|عرض\s*\(مم\))$/i,
    height: /^(h|height|hgt|ht|h\s*\(mm\)|height\s*\(mm\)|ارتفاع|الارتفاع|طول|الطول)$/i,
    qty: /^(qty|qty\.|quantity|nos?\.?|count|no\.?\s*of|total|عدد|العدد|الكمية|كمية)$/i,
    size: /^(size|sizes|dimensions?|dim\.?|المقاس|مقاس|المقاسات|الأبعاد|ابعاد|الابعاد)$/i,
  };
  function headKind(t) {
    const s = String(t).trim().replace(/[:：]/g, '').replace(/\s+/g, ' ');
    for (const k of ['width', 'height', 'qty', 'size', 'mark']) if (HEAD[k].test(s)) return k;
    // عنوان من كلمتين أو تلاتة: "STRUCT SIZE"، "OVERALL WIDTH"، "NO. OF UNITS"
    const ws = s.split(' ');
    if (ws.length >= 2 && ws.length <= 3 && s.length <= 24) {
      for (const k of ['width', 'height', 'size']) if (HEAD[k].test(ws[ws.length - 1]) && ws[ws.length - 1].length > 1) return k;
      if (/^(no\.?\s*of|number\s*of)\b/i.test(s)) return 'qty';
    }
    return null;
  }

  /* ---------- 4) الاستخراج ---------- */
  function extract(doc, opts) { return extractFlat(flatten(doc), doc.units, opts); }
  // F = {texts:[{x,y,h,text,page?,angle?}], inserts:[...]} - من DXF أو DWG أو PDF
  function extractFlat(F, unitsCode, opts) {
    opts = opts || {};
    F.inserts = F.inserts || [];
    const T = F.texts.filter((t) => t.text);
    // رموز C وأمثالها: منقبلها إذا حجم خطها متل رموز W/D بنفس الصفحة
    const stdTagH = new Map();
    for (const t of T) if (normMark(t.text)) { const k = t.page || 0; (stdTagH.get(k) || stdTagH.set(k, []).get(k)).push(t.h); }
    const extOk = (t) => (stdTagH.get(t.page || 0) || []).some((h) => Math.abs(h - t.h) <= Math.max(h, t.h) * 0.08);
    const markOf = (t) => normMark(t.text) || (MARK_EXT_RE.test(String(t.text).trim()) && extOk(t) ? normMark(t.text, true) : null);
    const hMed = (() => { const hs = T.map((t) => t.h).filter((h) => h > 0).sort((a, b) => a - b); return hs.length ? hs[Math.floor(hs.length / 2)] : 1; })();
    const tol = (t) => Math.max((t.h || hMed) * 0.6, hMed * 0.3);
    const schedule = new Map(); // mark -> {w,h,qty,src[]}
    const usedTexts = new Set();
    const note = (mark, rec, src) => {
      const cur = schedule.get(mark) || { mark, w: null, h: null, qty: null, srcs: [] };
      ['w', 'h', 'qty'].forEach((k) => { if (rec[k] != null && cur[k] == null) cur[k] = rec[k]; else if (rec[k] != null && cur[k] != null && Math.abs(cur[k] - rec[k]) > 0.01) cur.conflict = (cur.conflict || []).concat(k + ': ' + cur[k] + ' / ' + rec[k]); });
      if (rec.pair) cur.pair = true;
      cur.srcs.push(src);
      schedule.set(mark, cur);
    };

    // (أ) نص واحد فيه الرمز والمقاس: "W1 1200x1500" أو "W1 - 120*150 (4)"
    for (const t of T) {
      const m = /^\s*([A-Za-z؀-ۿ]{1,3}[\s.\-_]?\d{1,3}[A-Za-z]?)\s*[:\-–=]?\s*(.*)$/.exec(t.text.replace(/\n/g, ' '));
      if (!m) continue;
      const mk = normMark(m[1]); if (!mk) continue;
      const sz = SIZE_RE.exec(m[2]);
      if (!sz) continue;
      const qm = /(?:\(|qty\s*[:=]?\s*|عدد\s*[:=]?\s*|×\s*|nos?\s*[:=]?\s*)(\d{1,3})\)?\s*$/i.exec(m[2].slice(sz.index + sz[0].length));
      note(mk, { w: numOf(sz[1]), h: numOf(sz[2]), qty: qm ? parseInt(qm[1], 10) : null, pair: true }, 'نص بالمخطط: "' + t.text.replace(/\n/g, ' ').slice(0, 60) + '"');
      usedTexts.add(t);
    }

    // (ب) جداول: صفوف (نفس الارتفاع y) أو أعمدة (نفس x) فيها عناوين عرض/ارتفاع/عدد
    const heads = T.filter((t) => headKind(t.text));
    const tables = [];
    // جداول أفقية: عناوين على نفس السطر
    const usedHead = new Set();
    for (const h of heads) {
      if (usedHead.has(h)) continue;
      const row = heads.filter((o) => Math.abs(o.y - h.y) <= tol(h));
      const kinds = new Set(row.map((o) => headKind(o.text)));
      if (row.length >= 2 && (kinds.has('width') || kinds.has('size')) ) { row.forEach((o) => usedHead.add(o)); tables.push({ dir: 'rows', heads: row, y: h.y }); }
    }
    // جداول عمودية (مقلوبة): عناوين فوق بعض بنفس العمود والرموز ماشية بالعرض
    for (const h of heads) {
      if (usedHead.has(h)) continue;
      const col = heads.filter((o) => !usedHead.has(o) && Math.abs(o.x - h.x) <= Math.max(tol(h) * 3, hMed * 2));
      const kinds = new Set(col.map((o) => headKind(o.text)));
      if (col.length >= 2 && (kinds.has('width') || kinds.has('size'))) { col.forEach((o) => usedHead.add(o)); tables.push({ dir: 'cols', heads: col, x: h.x }); }
    }
    // أرقام اللوحات بقائمة الرسومات (W-101 مياه، A-101 معماري، S-101 إنشائي...) مش رموز شبابيك: منشيلها إذا بعمودها أرقام لوحات تانية
    const sheetNo = /^[A-Z]{1,2}-\d{2,3}$/;
    const markTexts = T.filter((t) => {
      if (!markOf(t)) return false;
      if (sheetNo.test(t.text.trim())) {
        const col = T.filter((o) => o !== t && (o.page || 0) === (t.page || 0) && Math.abs(o.x - t.x) <= Math.max(t.h, o.h) * 1.5 && sheetNo.test(o.text.trim()) && !markOf(o));
        if (col.length >= 2) return false;
      }
      return true;
    });
    const realTables = [], noteMain = note;
    for (const tb of tables) {
      const hk = (k) => tb.heads.find((o) => headKind(o.text) === k);
      const pend = []; // جدول حقيقي = فيه رمزين مختلفين عالأقل، وإلا غالباً عناوين رسومات مش جدول
      const note = (mk, rec, src, m) => pend.push([mk, rec, src, m]);
      if (tb.dir === 'rows') {
        const hy = tb.y, below = T.filter((t) => t.y < hy - tol(t) * 0.5);
        // كل رمز تحت العناوين = صف
        const rowsMarks = markTexts.filter((m) => m.y < hy - tol(m) * 0.5 && !usedTexts.has(m));
        // عمود الرمز: إذا في عنوان "TYPE/MARK" منقيّد بعرضه، وإلا كل رمز تحت الجدول بنطاق عرض العناوين
        const minX = Math.min(...tb.heads.map((o) => o.x)) - hMed * 15, maxX = Math.max(...tb.heads.map((o) => o.x)) + hMed * 15;
        for (const m of rowsMarks) {
          if (m.x < minX || m.x > maxX) continue;
          const cells = below.filter((t) => t !== m && Math.abs(t.y - m.y) <= tol(m));
          const nearest = (head) => { if (!head) return null; let best = null, bd = Infinity; for (const c of cells) { const d = Math.abs(c.x - head.x); if (d < bd) { bd = d; best = c; } } return bd <= hMed * 12 ? best : null; };
          let w = null, h = null, q = null, pair = false;
          const sc = nearest(hk('size'));
          if (sc && SIZE_RE.test(sc.text)) { const s = SIZE_RE.exec(sc.text); w = numOf(s[1]); h = numOf(s[2]); pair = true; }
          const wc = nearest(hk('width')), hc = nearest(hk('height')), qc = nearest(hk('qty'));
          if (wc && /^\s*\d+([.,]\d+)?\s*$/.test(wc.text)) w = numOf(wc.text);
          if (hc && /^\s*\d+([.,]\d+)?\s*$/.test(hc.text)) h = numOf(hc.text);
          if (qc && /^\s*\d{1,4}\s*$/.test(qc.text)) q = parseInt(qc.text, 10);
          if (w != null || h != null) { note(markOf(m), { w, h, qty: q, pair }, 'جدول النوافذ والأبواب (صف ' + m.text.trim() + ')', m); }
        }
      } else {
        const hx = tb.x;
        const rowY = (k) => { const o = hk(k); return o ? o.y : null; };
        const markRowY = rowY('mark');
        const marksRight = markTexts.filter((m) => m.x > hx + hMed && !usedTexts.has(m) && (markRowY == null ? Math.min(...tb.heads.map((o) => o.y)) <= m.y + tol(m) : Math.abs(m.y - markRowY) <= tol(m)));
        for (const m of marksRight) {
          const cellAt = (y) => { if (y == null) return null; let best = null, bd = Infinity; for (const t of T) { if (t === m) continue; if (Math.abs(t.y - y) > tol(t)) continue; const d = Math.abs(t.x - m.x); if (d < bd) { bd = d; best = t; } } return bd <= hMed * 8 ? best : null; };
          let w = null, h = null, q = null, pair = false;
          const sc = cellAt(rowY('size')); if (sc && SIZE_RE.test(sc.text)) { const s = SIZE_RE.exec(sc.text); w = numOf(s[1]); h = numOf(s[2]); pair = true; }
          const wc = cellAt(rowY('width')), hc = cellAt(rowY('height')), qc = cellAt(rowY('qty'));
          if (wc && /^\s*\d+([.,]\d+)?\s*$/.test(wc.text)) w = numOf(wc.text);
          if (hc && /^\s*\d+([.,]\d+)?\s*$/.test(hc.text)) h = numOf(hc.text);
          if (qc && /^\s*\d{1,4}\s*$/.test(qc.text)) q = parseInt(qc.text, 10);
          if (w != null || h != null) { note(markOf(m), { w, h, qty: q, pair }, 'جدول النوافذ والأبواب (عمود ' + m.text.trim() + ')', m); }
        }
      }
      const kinds = new Set(tb.heads.map((o) => headKind(o.text)));
      if (new Set(pend.map((x) => x[0])).size >= 2 || (pend.length && kinds.has("mark") && kinds.size >= 3)) { realTables.push(tb); for (const [mk, rec, src, m] of pend) { noteMain(mk, rec, src); usedTexts.add(m); } }
    }

    // (ج) بلوكات إلها خصائص: رمز + عرض + ارتفاع
    const blockMarks = new Map();
    for (const ins of F.inserts) {
      if (!ins.attribs.length) continue;
      let mk = null, w = null, h = null;
      for (const a of ins.attribs) {
        const k = headKind(a.tag) || (/^(mark|tag|type|ref|no|code|name)$/i.test(a.tag) ? 'mark' : null);
        if (k === 'mark' || (!mk && normMark(a.text))) mk = normMark(a.text) || mk;
        if (k === 'width' && /\d/.test(a.text)) w = numOf(a.text);
        if (k === 'height' && /\d/.test(a.text)) h = numOf(a.text);
        if (k === 'size' && SIZE_RE.test(a.text)) { const s = SIZE_RE.exec(a.text); w = numOf(s[1]); h = numOf(s[2]); }
      }
      if (!mk) continue;
      const cur = blockMarks.get(mk) || { count: 0, sizes: [] };
      cur.count++; if (w != null || h != null) cur.sizes.push([w, h]);
      blockMarks.set(mk, cur);
    }

    // (د) عدّ الرموز المكتوبة بالمساقط (برّا الجداول وبرّا خصائص البلوكات)
    // بالـPDF: كل صفحة لحال. صفحة الجدول وصفحة "الدليل" (كل رمز مرسوم مرة وحدة تحت رسمة الواجهة) ما بتنعد
    const tablePages = new Set([...usedTexts].filter((t) => t.page).map((t) => t.page));
    const pageInfo = new Map();
    for (const t of markTexts) {
      if (usedTexts.has(t)) continue;
      const pg = t.page || 0; const pi = pageInfo.get(pg) || pageInfo.set(pg, { page: pg, total: 0, marks: new Map() }).get(pg);
      pi.total++; const mk = markOf(t); pi.marks.set(mk, (pi.marks.get(mk) || 0) + 1);
    }
    const pages = [...pageInfo.values()].sort((a, b) => a.page - b.page).map((pi) => {
      const distinct = pi.marks.size;
      const legend = !!pi.page && distinct >= 6 && pi.total / distinct < 1.3;
      const auto = !(pi.page && (tablePages.has(pi.page) || legend));
      const counted = opts.countPages ? opts.countPages.indexOf(pi.page) >= 0 : auto;
      return { page: pi.page, total: pi.total, distinct, legend, schedule: tablePages.has(pi.page), counted, marks: pi.marks };
    });
    const tagCount = new Map();
    for (const pi of pages) if (pi.counted) for (const [mk, c] of pi.marks) tagCount.set(mk, (tagCount.get(mk) || 0) + c);

    // الوحدة: من إعداد الملف أو من حجم الأرقام
    const allWH = [...schedule.values()].flatMap((r) => [r.w, r.h]).concat([...blockMarks.values()].flatMap((b) => b.sizes.flat())).filter((v) => v != null && v > 0);
    const mx = allWH.length ? Math.max(...allWH) : 0;
    let unit = opts.unit || (mx && mx < 30 ? 'm' : mx && mx < 700 ? 'cm' : 'mm');
    // ترتيب المقاس: بعض المكاتب بتكتب "الارتفاع × العرض" (260x100 للباب). منعرفها من عنوان الجدول أو من الأبواب
    let order = opts.order || null, orderWhy = '';
    if (!order) {
      const hd = T.find((t) => /\b(h|height|ht)\s*[xX×*]\s*(w|width)\b|الارتفاع\s*[xX×*]\s*العرض/i.test(t.text));
      const wd = T.find((t) => /\b(w|width)\s*[xX×*]\s*(h|height|ht)\b|العرض\s*[xX×*]\s*الارتفاع/i.test(t.text));
      if (hd && !wd) { order = 'hw'; orderWhy = 'عنوان الجدول: ' + hd.text; }
      else if (wd && !hd) { order = 'wh'; orderWhy = 'عنوان الجدول: ' + wd.text; }
      else {
        const doors = [...schedule.values()].filter((r) => r.pair && /^(D|DR|FD|GD|AD|ED|MD|ب)\d/.test(r.mark) && r.w && r.h);
        const tall = doors.filter((r) => r.w > r.h * 1.3).length, wide = doors.filter((r) => r.h > r.w * 1.3).length;
        if (doors.length >= 2 && tall >= Math.max(2, doors.length * 0.75)) { order = 'hw'; orderWhy = 'الأبواب مكتوبة الرقم الكبير أول (ارتفاع × عرض)'; }
        else { order = 'wh'; orderWhy = wide ? 'الأبواب مكتوبة عرض × ارتفاع' : 'الافتراضي: عرض × ارتفاع'; }
      }
    }
    if (order === 'hw') for (const r of schedule.values()) if (r.pair) { const t = r.w; r.w = r.h; r.h = t; }
    const k = unit === 'm' ? 1000 : unit === 'cm' ? 10 : 1;
    const mm = (v) => (v == null ? null : Math.round(v * k));

    // المطابقة بين المصادر
    const marks = new Set([...schedule.keys(), ...blockMarks.keys(), ...tagCount.keys()]);
    const rows = [];
    for (const mk of [...marks].sort(markSort)) {
      const s = schedule.get(mk), b = blockMarks.get(mk), tc = tagCount.get(mk) || 0;
      let w = s && s.w != null ? mm(s.w) : null, h = s && s.h != null ? mm(s.h) : null;
      const issues = [], evidence = [];
      if (s) evidence.push(...s.srcs.slice(0, 2));
      if (s && s.conflict) issues.push('الجدول فيه قيمتين مختلفتين لنفس الرمز (' + s.conflict.join('، ') + ')');
      if (b) {
        evidence.push('بلوكات بالمخطط: ' + b.count);
        const bs = b.sizes.map(([bw, bh]) => [mm(bw), mm(bh)]);
        if (w == null && bs.length) { w = bs[0][0]; h = bs[0][1]; }
        else if (bs.some(([bw, bh]) => (bw != null && w != null && bw !== w) || (bh != null && h != null && bh !== h))) issues.push('مقاس البلوك بالمخطط غير مقاس الجدول');
        if (new Set(bs.map((x) => x.join('x'))).size > 1) issues.push('بلوكات بنفس الرمز بمقاسات مختلفة');
      }
      if (tc) evidence.push('مكتوب بالمساقط: ' + tc + ' مرة' + (pages.some((p) => p.page) ? ' (صفحات ' + pages.filter((p) => p.counted && p.marks.has(mk)).map((p) => p.page).join('، ') + ')' : ''));
      const qSched = s && s.qty != null ? s.qty : null;
      const counted = b ? b.count : tc;
      let qty = qSched != null ? qSched : (counted || null);
      if (qSched != null && counted && qSched !== counted) issues.push('العدد بالجدول ' + qSched + ' بس بالمخطط ' + counted);
      if (w == null || h == null) issues.push(w == null && h == null ? 'ما لقينا مقاس' : (w == null ? 'ما لقينا العرض' : 'ما لقينا الارتفاع'));
      if (qty == null) issues.push('ما لقينا العدد');
      const sources = (s ? 1 : 0) + (b ? 1 : 0) + (tc ? 1 : 0);
      if (sources < 2 && !issues.length) issues.push('مصدر واحد بس - راجعه');
      rows.push({ mark: mk, kind: kindOf(mk), w, h, qty, ok: issues.length === 0, issues, evidence });
    }
    const pagesOut = pages.filter((p) => p.page).map((p) => ({ page: p.page, total: p.total, distinct: p.distinct, legend: p.legend, schedule: p.schedule, counted: p.counted }));
    return { unit, unitFromFile: unitsCode, order, orderWhy, rows, pages: pagesOut, stats: { texts: T.length, inserts: F.inserts.length, tables: realTables.length } };
  }
  function markSort(a, b) {
    const pa = /^([A-Z؀-ۿ]+)(\d+)(.*)$/.exec(a) || [0, a, 0, ''], pb = /^([A-Z؀-ۿ]+)(\d+)(.*)$/.exec(b) || [0, b, 0, ''];
    return pa[1] === pb[1] ? (Number(pa[2]) - Number(pb[2]) || String(pa[3]).localeCompare(pb[3])) : String(pa[1]).localeCompare(pb[1]);
  }
  function kindOf(mk) {
    const p = (/^[A-Z؀-ۿ]+/.exec(mk) || [''])[0];
    if (p === 'SD') return 'sliding-door';
    if (p === 'SW') return 'sliding-window';
    if (p === 'CW') return 'curtain-wall';
    if (p === 'FW' || p === 'V') return 'fixed-window';
    if (p === 'SK') return 'skylight';
    if (/^(D|DR|FD|GD|AD|ED|MD|DW|ب)$/.test(p)) return 'door';
    if (p === 'OP') return 'opening';
    return 'window';
  }

  // صفحات PDF (من pdf-text.js) -> نفس الاستخراج
  function fromPdfPages(pages, opts) {
    const texts = [];
    // الـPDF بيعطي كلمات؛ منلزق الكلمات المتجاورة على نفس السطر بخلية وحدة (متل نص الأوتوكاد الأصلي)
    for (const p of pages) {
      const ws = p.words.slice().sort((a, b) => (a.angle - b.angle) || (Math.round(b.y / Math.max(a.h, 0.5) * 2) - Math.round(a.y / Math.max(a.h, 0.5) * 2)) || (a.x - b.x));
      const used = new Set();
      const horiz = (w) => !w.angle;
      for (const w of ws) {
        if (used.has(w)) continue;
        used.add(w);
        const cell = { x: w.x, y: w.y, h: w.h, text: w.text, page: p.page, angle: w.angle || 0, ex: w.ex, ey: w.ey };
        if (horiz(w)) {
          for (;;) {
            let best = null, bd = Infinity;
            for (const o of p.words) {
              if (used.has(o) || !horiz(o) || Math.abs(o.h - cell.h) > cell.h * 0.2 || Math.abs(o.y - cell.y) > cell.h * 0.3) continue;
              const gap = o.x - (cell.ex != null ? cell.ex : cell.x);
              if (gap >= -cell.h * 0.2 && gap <= cell.h * 0.75 && gap < bd) { bd = gap; best = o; }
            }
            if (!best) break;
            used.add(best); cell.text += ' ' + best.text; cell.ex = best.ex; cell.ey = best.ey;
          }
        }
        texts.push(cell);
      }
    }
    const r = extractFlat({ texts, inserts: [] }, 0, opts);
    r.pdf = true;
    // إذا ما في ولا جدول مقروء: غالباً الجدول مرسوم خطوط (خط SHX) - منقولها صراحة
    if (!r.stats.tables) r.rows.forEach((x) => { x.issues = x.issues.map((s) => (s === 'ما لقينا مقاس' ? 'ما لقينا مقاس: جدول الفتحات بهالـPDF مرسوم خطوط مش نص - اكتب المقاس أو استعمل ملف الـDWG' : s)); });
    return r;
  }
  // ناتج dwg-read.js -> نفس شكل parseDxf (مع تنظيف تنسيقات النص)
  function dwgToDoc(raw) {
    const fix = (items) => items.forEach((it) => {
      if (it.kind === 'text') it.text = it.mtext ? cleanMtext(it.raw) : cleanText(it.raw);
      else if (it.kind === 'insert') it.attribs.forEach((a) => { a.text = cleanText(a.raw); });
    });
    fix(raw.entities); Object.values(raw.blocks).forEach((b) => fix(b.items));
    return raw;
  }
  const api = { parseDxf, flatten, extract, extractFlat, fromPdfPages, dwgToDoc, normMark, cleanMtext, readDxf: (text, opts) => extract(parseDxf(text), opts) };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MzCad = api;
})(typeof window !== 'undefined' ? window : this);
