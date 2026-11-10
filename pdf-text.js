/* =====================================================================================
   📄 قارئ نصوص PDF خاص بميرزونا - 2026-11-10
   ليش مش pdf.js؟ لأنه ما قدرنا نجرّبه هون (نظام الحماية رفض تشغيل كود خارجي)، وما منزّل شي ما انجرّب.
   هاد قارئ صغير بيطلّع كل كلمة بالمخطط مع مكانها الحقيقي (x,y) وحجمها واتجاهها، وبعدين cad-import.js
   بيشتغل عليها متل ما بيشتغل على DXF (جداول + رموز بالمساقط).
   بيدعم: ضغط Flate، Object Streams (PDF 1.5+)، خطوط Type0/CID (Identity-H) مع ToUnicode، خطوط عادية
   WinAnsi/Differences، Type3، Form XObjects، تدوير الصفحة (Rotate)، Inline images.
   ===================================================================================== */
(function (root) {
  'use strict';

  /* ---------- أدوات ---------- */
  function Name(n) { this.n = n; }
  function Str(b) { this.b = b; }
  function Ref(n, g) { this.n = n; this.g = g; }
  const isWs = (c) => c === 32 || c === 10 || c === 13 || c === 9 || c === 12 || c === 0;
  const isDelim = (c) => c === 40 || c === 41 || c === 60 || c === 62 || c === 91 || c === 93 || c === 123 || c === 125 || c === 47 || c === 37;
  function latin1(u8, a, b) {
    let s = '';
    for (let i = a; i < b; i += 8192) s += String.fromCharCode.apply(null, u8.subarray(i, Math.min(b, i + 8192)));
    return s;
  }

  /* ---------- 1) لِكسر (Lexer) عام للـPDF والمحتوى ---------- */
  function Lexer(u8, pos) { this.u = u8; this.p = pos || 0; }
  Lexer.prototype.skip = function () {
    const u = this.u; let p = this.p;
    for (;;) {
      while (p < u.length && isWs(u[p])) p++;
      if (u[p] === 37) { while (p < u.length && u[p] !== 10 && u[p] !== 13) p++; continue; }
      break;
    }
    this.p = p;
  };
  // بيرجّع: رقم، Name، Str، مصفوفة، قاموس (Map)، true/false/null، أو {op:'كلمة'} للأوامر
  Lexer.prototype.next = function () {
    this.skip();
    const u = this.u; let p = this.p;
    if (p >= u.length) return undefined;
    const c = u[p];
    if (c === 47) { // /Name
      p++; let s = '';
      while (p < u.length && !isWs(u[p]) && !isDelim(u[p])) {
        if (u[p] === 35 && p + 2 < u.length) { s += String.fromCharCode(parseInt(String.fromCharCode(u[p + 1], u[p + 2]), 16)); p += 3; }
        else s += String.fromCharCode(u[p++]);
      }
      this.p = p; return new Name(s);
    }
    if (c === 40) { // (literal)
      p++; let depth = 1; const out = [];
      while (p < u.length) {
        const ch = u[p++];
        if (ch === 92) {
          const e = u[p++];
          if (e === 110) out.push(10); else if (e === 114) out.push(13); else if (e === 116) out.push(9); else if (e === 98) out.push(8); else if (e === 102) out.push(12);
          else if (e === 13) { if (u[p] === 10) p++; } else if (e === 10) { /* سطر مكمّل */ }
          else if (e >= 48 && e <= 55) { let v = e - 48; for (let k = 0; k < 2 && u[p] >= 48 && u[p] <= 55; k++) v = v * 8 + (u[p++] - 48); out.push(v & 255); }
          else out.push(e);
        } else if (ch === 40) { depth++; out.push(ch); }
        else if (ch === 41) { if (--depth === 0) break; out.push(ch); }
        else out.push(ch);
      }
      this.p = p; return new Str(Uint8Array.from(out));
    }
    if (c === 60) {
      if (u[p + 1] === 60) { this.p = p + 2; return this.dict(); }
      p++; let hex = '';
      while (p < u.length && u[p] !== 62) { if (!isWs(u[p])) hex += String.fromCharCode(u[p]); p++; }
      this.p = p + 1; if (hex.length % 2) hex += '0';
      const b = new Uint8Array(hex.length / 2); for (let i = 0; i < b.length; i++) b[i] = parseInt(hex.substr(i * 2, 2), 16) || 0;
      return new Str(b);
    }
    if (c === 91) { this.p = p + 1; const a = []; for (;;) { this.skip(); if (this.u[this.p] === 93) { this.p++; break; } if (this.p >= u.length) break; const v = this.next(); if (v === undefined) break; a.push(v); } return fixRefs(a); }
    if (c === 93 || c === 62 || c === 125 || c === 41) { this.p = p + 1; return { op: String.fromCharCode(c) }; }
    if (c === 123) { this.p = p + 1; return { op: '{' }; }
    // رقم أو كلمة
    let s = '';
    while (p < u.length && !isWs(u[p]) && !isDelim(u[p])) s += String.fromCharCode(u[p++]);
    if (!s) { this.p = p + 1; return { op: String.fromCharCode(c) }; }
    this.p = p;
    if (/^[+-]?(\d+\.?\d*|\.\d+)$/.test(s)) return parseFloat(s);
    if (/^[+-]?\d*\.?\d*[eE]?[+-]?\d+$/.test(s) && !isNaN(parseFloat(s))) return parseFloat(s);
    if (s === 'true') return true; if (s === 'false') return false; if (s === 'null') return null;
    return { op: s };
  };
  Lexer.prototype.dict = function () {
    const d = new Map();
    for (;;) {
      this.skip();
      if (this.u[this.p] === 62 && this.u[this.p + 1] === 62) { this.p += 2; break; }
      if (this.p >= this.u.length) break;
      const k = this.next();
      if (!(k instanceof Name)) { if (k && k.op === '>') continue; if (k === undefined) break; continue; }
      const v = this.obj();
      d.set(k.n, v);
    }
    return d;
  };
  // قيمة كاملة مع المراجع "n g R"
  Lexer.prototype.obj = function () {
    const v = this.next();
    if (typeof v === 'number' && Number.isInteger(v) && v >= 0) {
      const save = this.p;
      const g = this.next();
      if (typeof g === 'number' && Number.isInteger(g)) {
        const r = this.next();
        if (r && r.op === 'R') return new Ref(v, g);
      }
      this.p = save;
    }
    if (Array.isArray(v)) return v.map((x) => x); // المراجع جوّا المصفوفات منحلّها تحت
    return v;
  };
  // المصفوفات بتنقرى بـ next() فما بتعرف "n g R": منصلحها هون
  function fixRefs(a) {
    if (!Array.isArray(a)) return a;
    const out = [];
    for (let i = 0; i < a.length; i++) {
      const x = a[i];
      if (typeof x === 'number' && typeof a[i + 1] === 'number' && a[i + 2] && a[i + 2].op === 'R') { out.push(new Ref(x, a[i + 1])); i += 2; }
      else out.push(Array.isArray(x) ? fixRefs(x) : x);
    }
    return out;
  }

  /* ---------- 2) فهرسة كائنات الملف ---------- */
  async function openPdf(u8, inflate) {
    const objs = new Map(); // num -> {v, stream:{dict,raw}}
    const s = latin1(u8, 0, u8.length);
    const re = /(\d+)\s+(\d+)\s+obj\b/g;
    let m;
    const objStms = [];
    while ((m = re.exec(s))) {
      const num = +m[1];
      const L = new Lexer(u8, m.index + m[0].length);
      let v;
      try { v = L.obj(); } catch (e) { continue; }
      if (Array.isArray(v)) v = fixRefs(v);
      if (v instanceof Map) for (const [k, x] of v) if (Array.isArray(x)) v.set(k, fixRefs(x));
      L.skip();
      let rec = { v };
      if (v instanceof Map && s.startsWith('stream', L.p)) {
        let p = L.p + 6;
        if (u8[p] === 13) p++; if (u8[p] === 10) p++;
        let len = v.get('Length'), end = -1;
        if (typeof len === 'number' && p + len <= u8.length && /^\s*endstream/.test(s.substr(p + len, 20))) end = p + len;
        if (end < 0) { end = s.indexOf('endstream', p); if (end < 0) end = u8.length; let e2 = end; while (e2 > p && (u8[e2 - 1] === 10 || u8[e2 - 1] === 13)) e2--; end = e2; }
        rec = { v, raw: u8.subarray(p, end) };
        re.lastIndex = Math.max(re.lastIndex, end);
        const t = v.get('Type');
        if (t instanceof Name && t.n === 'ObjStm') objStms.push(rec);
      }
      objs.set(num, rec); // آخر تعريف بيربح (تحديثات تراكمية)
    }
    const pdf = { u8, objs, inflate, cache: new Map() };
    for (const os of objStms) {
      try {
        const data = await streamData(pdf, os);
        const n = +get(pdf, os.v, 'N') || 0, first = +get(pdf, os.v, 'First') || 0;
        const L = new Lexer(data, 0); const pairs = [];
        for (let i = 0; i < n; i++) { const a = L.next(), b = L.next(); pairs.push([a, b]); }
        for (const [num, off] of pairs) {
          if (objs.has(num) && !objs.get(num).fromStm) continue;
          const L2 = new Lexer(data, first + off);
          let v = L2.obj(); if (Array.isArray(v)) v = fixRefs(v);
          if (v instanceof Map) for (const [k, x] of v) if (Array.isArray(x)) v.set(k, fixRefs(x));
          objs.set(num, { v, fromStm: true });
        }
      } catch (e) { /* object stream تالف - منكمّل بالباقي */ }
    }
    return pdf;
  }
  function deref(pdf, v) { let k = 0; while (v instanceof Ref && k++ < 20) { const o = pdf.objs.get(v.n); v = o ? o.v : null; } return v; }
  function rec(pdf, v) { return v instanceof Ref ? pdf.objs.get(v.n) : null; }
  function get(pdf, d, k) { d = deref(pdf, d); return d instanceof Map ? deref(pdf, d.get(k)) : undefined; }
  const nm = (v) => (v instanceof Name ? v.n : null);

  async function streamData(pdf, r) {
    if (!r || !r.raw) return new Uint8Array(0);
    if (r.dec) return r.dec;
    let f = get(pdf, r.v, 'Filter'); f = Array.isArray(f) ? f.map((x) => nm(deref(pdf, x))) : f ? [nm(f)] : [];
    let parms = get(pdf, r.v, 'DecodeParms'); parms = Array.isArray(parms) ? parms.map((x) => deref(pdf, x)) : [parms];
    let d = r.raw;
    for (let i = 0; i < f.length; i++) {
      if (f[i] === 'FlateDecode' || f[i] === 'Fl') {
        d = await pdf.inflate(d);
        const pr = parms[i] instanceof Map ? parms[i] : null;
        const pred = pr ? +deref(pdf, pr.get('Predictor')) || 1 : 1;
        if (pred >= 10) d = pngUnpredict(d, pr ? +deref(pdf, pr.get('Columns')) || 1 : 1, pr ? +deref(pdf, pr.get('Colors')) || 1 : 1, pr ? +deref(pdf, pr.get('BitsPerComponent')) || 8 : 8);
      } else if (f[i] === 'ASCIIHexDecode' || f[i] === 'AHx') {
        const h = latin1(d, 0, d.length).replace(/[^0-9a-fA-F]/g, ''); const o = new Uint8Array(h.length >> 1); for (let k = 0; k < o.length; k++) o[k] = parseInt(h.substr(k * 2, 2), 16); d = o;
      } else if (f[i] === 'ASCII85Decode' || f[i] === 'A85') d = a85(d);
      else return new Uint8Array(0); // فلاتر الصور (DCT/JBIG2...) ما بتلزمنا
    }
    r.dec = d; return d;
  }
  function pngUnpredict(d, cols, colors, bpc) {
    const bpp = Math.max(1, (colors * bpc) >> 3), rowLen = (cols * colors * bpc + 7) >> 3;
    const out = new Uint8Array(Math.floor(d.length / (rowLen + 1)) * rowLen); let prev = new Uint8Array(rowLen);
    for (let r = 0, ip = 0, op = 0; ip + rowLen < d.length + 1 && op < out.length; r++) {
      const t = d[ip++]; const row = out.subarray(op, op + rowLen);
      for (let i = 0; i < rowLen; i++) {
        const x = d[ip + i], a = i >= bpp ? row[i - bpp] : 0, b = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
        let v = x;
        if (t === 1) v = x + a; else if (t === 2) v = x + b; else if (t === 3) v = x + ((a + b) >> 1);
        else if (t === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v = x + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c); }
        row[i] = v & 255;
      }
      prev = row; ip += rowLen; op += rowLen;
    }
    return out;
  }
  function a85(d) {
    const s = latin1(d, 0, d.length).replace(/\s/g, '').replace(/^<~/, '').replace(/~>.*$/, ''); const out = [];
    for (let i = 0; i < s.length;) {
      if (s[i] === 'z') { out.push(0, 0, 0, 0); i++; continue; }
      const ch = s.substr(i, 5); i += 5; const pad = 5 - ch.length; let v = 0;
      for (let k = 0; k < 5; k++) v = v * 85 + ((k < ch.length ? ch.charCodeAt(k) : 117) - 33);
      const b = [(v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255]; out.push(...b.slice(0, 4 - pad));
    }
    return Uint8Array.from(out);
  }

  /* ---------- 3) الخطوط: من الرمز للحرف وعرض الحرف ---------- */
  const WINANSI = (() => {
    const t = []; for (let i = 0; i < 256; i++) t[i] = i >= 32 && i < 127 ? String.fromCharCode(i) : i >= 160 ? String.fromCharCode(i) : '';
    const hi = { 128: '€', 130: '‚', 131: 'ƒ', 132: '„', 133: '…', 134: '†', 135: '‡', 136: 'ˆ', 137: '‰', 138: 'Š', 139: '‹', 140: 'Œ', 142: 'Ž', 145: '‘', 146: '’', 147: '“', 148: '”', 149: '•', 150: '–', 151: '—', 152: '˜', 153: '™', 154: 'š', 155: '›', 156: 'œ', 158: 'ž', 159: 'Ÿ' };
    for (const k in hi) t[k] = hi[k]; return t;
  })();
  const GLYPH = { space: ' ', exclam: '!', quotedbl: '"', numbersign: '#', dollar: '$', percent: '%', ampersand: '&', quotesingle: "'", quoteright: '’', parenleft: '(', parenright: ')', asterisk: '*', plus: '+', comma: ',', hyphen: '-', minus: '-', period: '.', slash: '/', zero: '0', one: '1', two: '2', three: '3', four: '4', five: '5', six: '6', seven: '7', eight: '8', nine: '9', colon: ':', semicolon: ';', less: '<', equal: '=', greater: '>', question: '?', at: '@', bracketleft: '[', backslash: '\\', bracketright: ']', underscore: '_', braceleft: '{', bar: '|', braceright: '}', multiply: '×', degree: '°', plusminus: '±', Oslash: 'Ø', oslash: 'ø', endash: '–', emdash: '—', bullet: '•', periodcentered: '·', x: 'x' };
  function glyphToUni(g) {
    if (!g) return '';
    if (GLYPH[g] != null) return GLYPH[g];
    if (/^[A-Za-z]$/.test(g)) return g;
    let m = /^uni([0-9A-Fa-f]{4,})/.exec(g); if (m) { let s = ''; for (let i = 0; i + 4 <= m[1].length; i += 4) s += String.fromCharCode(parseInt(m[1].substr(i, 4), 16)); return s; }
    m = /^u([0-9A-Fa-f]{4,6})$/.exec(g); if (m) return String.fromCodePoint(parseInt(m[1], 16));
    m = /^([A-Za-z])\.\w+$/.exec(g); if (m) return m[1];
    return '';
  }
  function parseCMap(u8) {
    const s = latin1(u8, 0, u8.length);
    const map = new Map(); const spaces = [];
    const hex = (h) => parseInt(h || '0', 16);
    const utf16 = (h) => { let o = ''; for (let i = 0; i + 4 <= h.length; i += 4) o += String.fromCharCode(parseInt(h.substr(i, 4), 16)); if (h.length % 4 === 2) o += String.fromCharCode(parseInt(h.substr(h.length - 2), 16)); return o; };
    let m;
    const csr = /begincodespacerange([\s\S]*?)endcodespacerange/g;
    while ((m = csr.exec(s))) { const r = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>/g; let x; while ((x = r.exec(m[1]))) spaces.push({ n: x[1].length >> 1, lo: hex(x[1]), hi: hex(x[2]) }); }
    const bc = /beginbfchar([\s\S]*?)endbfchar/g;
    while ((m = bc.exec(s))) { const r = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]*)>/g; let x; while ((x = r.exec(m[1]))) map.set(hex(x[1]), utf16(x[2])); }
    const br = /beginbfrange([\s\S]*?)endbfrange/g;
    while ((m = br.exec(s))) {
      const r = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*(<[0-9a-fA-F]*>|\[[^\]]*\])/g; let x;
      while ((x = r.exec(m[1]))) {
        const lo = hex(x[1]), hi = Math.min(hex(x[2]), lo + 65535);
        if (x[3][0] === '[') { const items = x[3].match(/<([0-9a-fA-F]*)>/g) || []; for (let c = lo; c <= hi && c - lo < items.length; c++) map.set(c, utf16(items[c - lo].slice(1, -1))); }
        else { const d = x[3].slice(1, -1); const base = parseInt(d.slice(-4) || '0', 16), pre = d.length > 4 ? utf16(d.slice(0, -4)) : ''; for (let c = lo; c <= hi; c++) map.set(c, pre + String.fromCharCode(base + (c - lo))); }
      }
    }
    const cidc = /begincidrange([\s\S]*?)endcidrange/g; const cid = [];
    while ((m = cidc.exec(s))) { const r = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*(\d+)/g; let x; while ((x = r.exec(m[1]))) cid.push([hex(x[1]), hex(x[2]), +x[3]]); }
    return { map, spaces, cid };
  }
  async function loadFont(pdf, ref) {
    const key = ref instanceof Ref ? 'r' + ref.n : null;
    if (key && pdf.cache.has(key)) return pdf.cache.get(key);
    const d = deref(pdf, ref);
    const f = { type: 'Type1', twoByte: false, widths: new Map(), dw: 0.55, toU: null, enc: WINANSI.slice(), scale: 0.001, spaces: null, name: '' };
    if (d instanceof Map) {
      f.type = nm(get(pdf, d, 'Subtype')) || 'Type1';
      f.name = nm(get(pdf, d, 'BaseFont')) || '';
      const tu = rec(pdf, d.get('ToUnicode'));
      if (tu) { try { f.toU = parseCMap(await streamData(pdf, tu)).map; } catch (e) { /* */ } }
      if (f.type === 'Type0') {
        f.twoByte = true;
        const enc = d.get('Encoding'), encName = nm(deref(pdf, enc));
        if (!encName && rec(pdf, enc)) { try { const cm = parseCMap(await streamData(pdf, rec(pdf, enc))); if (cm.spaces.length && cm.spaces.every((x) => x.n === 1)) f.twoByte = false; f.spaces = cm.spaces; f.cidMap = cm.cid; } catch (e) { /* */ } }
        const desc = deref(pdf, (get(pdf, d, 'DescendantFonts') || [])[0]);
        f.dw = ((desc && +get(pdf, desc, 'DW')) || 1000) / 1000;
        const W = desc ? get(pdf, desc, 'W') : null;
        if (Array.isArray(W)) {
          for (let i = 0; i < W.length;) {
            const a = deref(pdf, W[i]), b = deref(pdf, W[i + 1]);
            if (Array.isArray(b)) { b.forEach((w, k) => f.widths.set(a + k, (+deref(pdf, w)) / 1000)); i += 2; }
            else { const w = +deref(pdf, W[i + 2]); for (let c = a; c <= b && c - a < 65536; c++) f.widths.set(c, w / 1000); i += 3; }
          }
        }
      } else {
        if (f.type === 'Type3') { const fm = get(pdf, d, 'FontMatrix'); f.scale = Array.isArray(fm) ? Math.abs(+deref(pdf, fm[0])) || 0.001 : 0.001; }
        const fc = +get(pdf, d, 'FirstChar') || 0, W = get(pdf, d, 'Widths');
        if (Array.isArray(W)) W.forEach((w, k) => f.widths.set(fc + k, (+deref(pdf, w)) * f.scale));
        const enc = get(pdf, d, 'Encoding');
        const diffs = enc instanceof Map ? deref(pdf, enc.get('Differences')) : null;
        if (Array.isArray(diffs)) { let c = 0; for (const x of diffs) { const v = deref(pdf, x); if (typeof v === 'number') c = v; else if (v instanceof Name) { f.enc[c] = glyphToUni(v.n); c++; } } }
      }
    }
    if (key) pdf.cache.set(key, f);
    return f;
  }
  // بايتات النص -> [{code, ch, w}]
  function decodeStr(f, b) {
    const out = [];
    if (f.twoByte || (f.spaces && f.spaces.length)) {
      for (let i = 0; i < b.length;) {
        let n = 2;
        if (f.spaces && f.spaces.length) { n = 0; for (const sp of f.spaces) { if (i + sp.n > b.length) continue; let v = 0; for (let k = 0; k < sp.n; k++) v = v * 256 + b[i + k]; if (v >= sp.lo && v <= sp.hi) { n = sp.n; break; } } if (!n) n = f.twoByte ? 2 : 1; }
        let code = 0; for (let k = 0; k < n && i + k < b.length; k++) code = code * 256 + b[i + k]; i += n;
        let cid = code;
        if (f.cidMap && f.cidMap.length) { for (const [lo, hi, st] of f.cidMap) if (code >= lo && code <= hi) { cid = st + code - lo; break; } }
        const ch = f.toU && f.toU.has(code) ? f.toU.get(code) : '';
        out.push({ code, ch, w: f.widths.has(cid) ? f.widths.get(cid) : f.dw, single: false });
      }
    } else {
      for (let i = 0; i < b.length; i++) {
        const c = b[i];
        const ch = f.toU && f.toU.has(c) ? f.toU.get(c) : f.enc[c] || '';
        out.push({ code: c, ch, w: f.widths.has(c) ? f.widths.get(c) : (f.type === 'Type3' ? 0.5 : 0.55), single: true });
      }
    }
    return out;
  }

  /* ---------- 4) تشغيل محتوى الصفحة وتجميع الحروف بكلمات ---------- */
  const mul = (a, b) => [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]];
  async function runContent(pdf, data, res, ctm0, glyphs, depth, budget) {
    const L = new Lexer(data, 0);
    let ops = [];
    let gs = { ctm: ctm0 }; const stack = [];
    let tm = [1, 0, 0, 1, 0, 0], tlm = tm, font = null, fs = 1, Tc = 0, Tw = 0, Th = 1, TL = 0, Ts = 0;
    const fonts = get(pdf, res, 'Font'), xobjs = get(pdf, res, 'XObject');
    const show = (str) => {
      if (!font || !(str instanceof Str)) return;
      for (const g of decodeStr(font, str.b)) {
        const trm = mul([fs * Th, 0, 0, fs, 0, Ts], mul(tm, gs.ctm));
        const adv = (g.w * fs + Tc + (g.single && g.code === 32 ? Tw : 0)) * Th;
        glyphs.push({ x: trm[4], y: trm[5], ux: trm[0], uy: trm[1], vx: trm[2], vy: trm[3], ch: g.ch, w: g.w });
        tm = mul([1, 0, 0, 1, adv, 0], tm);
      }
    };
    for (;;) {
      if (budget.n-- <= 0) break;
      const t = L.next();
      if (t === undefined) break;
      if (!(t && t.op !== undefined) || t.op === '[' ) { ops.push(t); continue; }
      const op = t.op;
      switch (op) {
        case 'q': stack.push(gs); gs = { ctm: gs.ctm }; break;
        case 'Q': if (stack.length) gs = stack.pop(); break;
        case 'cm': if (ops.length >= 6) gs = { ctm: mul(ops.slice(-6), gs.ctm) }; break;
        case 'BT': tm = tlm = [1, 0, 0, 1, 0, 0]; break;
        case 'Tf': { const n = ops[ops.length - 2]; fs = +ops[ops.length - 1] || 0; font = n instanceof Name && fonts instanceof Map ? await loadFont(pdf, fonts.get(n.n)) : null; break; }
        case 'Tc': Tc = +ops[ops.length - 1] || 0; break;
        case 'Tw': Tw = +ops[ops.length - 1] || 0; break;
        case 'Tz': Th = (+ops[ops.length - 1] || 100) / 100; break;
        case 'TL': TL = +ops[ops.length - 1] || 0; break;
        case 'Ts': Ts = +ops[ops.length - 1] || 0; break;
        case 'Td': tlm = mul([1, 0, 0, 1, +ops[ops.length - 2] || 0, +ops[ops.length - 1] || 0], tlm); tm = tlm; break;
        case 'TD': TL = -(+ops[ops.length - 1] || 0); tlm = mul([1, 0, 0, 1, +ops[ops.length - 2] || 0, +ops[ops.length - 1] || 0], tlm); tm = tlm; break;
        case 'Tm': if (ops.length >= 6) { tlm = ops.slice(-6).map(Number); tm = tlm; } break;
        case 'T*': tlm = mul([1, 0, 0, 1, 0, -TL], tlm); tm = tlm; break;
        case 'Tj': show(ops[ops.length - 1]); break;
        case "'": tlm = mul([1, 0, 0, 1, 0, -TL], tlm); tm = tlm; show(ops[ops.length - 1]); break;
        case '"': Tw = +ops[ops.length - 3] || 0; Tc = +ops[ops.length - 2] || 0; tlm = mul([1, 0, 0, 1, 0, -TL], tlm); tm = tlm; show(ops[ops.length - 1]); break;
        case 'TJ': {
          const arr = ops[ops.length - 1];
          if (Array.isArray(arr)) for (const x of arr) {
            if (typeof x === 'number') { const tx = -x / 1000 * fs * Th; tm = mul([1, 0, 0, 1, tx, 0], tm); if (x < -250) glyphs.push({ brk: true }); }
            else show(x);
          }
          break;
        }
        case 'ET': glyphs.push({ brk: true }); break;
        case 'Do': {
          const n = ops[ops.length - 1];
          if (n instanceof Name && xobjs instanceof Map && depth < 8) {
            const r = rec(pdf, xobjs.get(n.n));
            if (r && r.raw && nm(get(pdf, r.v, 'Subtype')) === 'Form') {
              const M = get(pdf, r.v, 'Matrix'); const mtx = Array.isArray(M) ? M.map((x) => +deref(pdf, x)) : [1, 0, 0, 1, 0, 0];
              const r2 = get(pdf, r.v, 'Resources') || res;
              try { await runContent(pdf, await streamData(pdf, r), r2, mul(mtx, gs.ctm), glyphs, depth + 1, budget); } catch (e) { /* */ }
              glyphs.push({ brk: true });
            }
          }
          break;
        }
        case 'BI': { // صورة مدموجة: منقفز فوق بياناتها
          const u = L.u; let p = L.p;
          for (; p < u.length - 1; p++) if (u[p] === 73 && u[p + 1] === 68 && isWs(u[p - 1] || 32) && isWs(u[p + 2] || 32)) break;
          p += 3;
          for (; p < u.length - 1; p++) if (u[p] === 69 && u[p + 1] === 73 && isWs(u[p - 1]) && (p + 2 >= u.length || isWs(u[p + 2]))) { p += 2; break; }
          L.p = p; break;
        }
        default: break;
      }
      ops = [];
    }
  }

  function wordsFromGlyphs(glyphs, rot) {
    // تحويل لإحداثيات العرض (بعد تدوير الصفحة) - y لفوق
    const W = rot.w, H = rot.h, r = rot.r, x0 = rot.x0, y0 = rot.y0;
    const P = (x, y) => { x -= x0; y -= y0; return r === 90 ? [y, W - x] : r === 180 ? [W - x, H - y] : r === 270 ? [H - y, x] : [x, y]; };
    const V = (x, y) => (r === 90 ? [y, -x] : r === 180 ? [-x, -y] : r === 270 ? [-y, x] : [x, y]);
    const words = [];
    let cur = null;
    const flush = () => {
      if (cur && cur.t.trim()) {
        let t = cur.t.normalize('NFKC').replace(/\s+/g, ' ').trim();
        if (/[؀-ۿ]/.test(t) && cur.ltr) t = [...t].reverse().join(''); // العربي بالـPDF بينكتب بترتيب العرض
        words.push({ text: t, x: cur.x, y: cur.y, ex: cur.ex, ey: cur.ey, h: cur.h, angle: cur.ang });
      }
      cur = null;
    };
    for (const g of glyphs) {
      if (g.brk) { flush(); continue; }
      const [x, y] = P(g.x, g.y);
      const [ux, uy] = V(g.ux, g.uy), [vx, vy] = V(g.vx, g.vy);
      const size = Math.hypot(vx, vy) || Math.hypot(ux, uy);
      const len = Math.hypot(ux, uy) || 1, dx = ux / len, dy = uy / len;
      const adv = g.w * len;
      if (!g.ch || /^\s+$/.test(g.ch)) { flush(); continue; }
      if (cur) {
        const ex = x - cur.ex, ey = y - cur.ey;
        const along = ex * cur.dx + ey * cur.dy, perp = -ex * cur.dy + ey * cur.dx;
        const same = Math.abs(dx - cur.dx) < 0.05 && Math.abs(dy - cur.dy) < 0.05 && Math.abs(size - cur.h) < cur.h * 0.3;
        if (!same || Math.abs(perp) > cur.h * 0.4 || along > cur.h * 0.3 || along < -cur.h * 0.6) flush();
      }
      if (!cur) cur = { t: '', x, y, h: size, dx, dy, ang: Math.round(Math.atan2(dy, dx) * 180 / Math.PI), ltr: true };
      cur.t += g.ch; cur.ex = x + dx * adv; cur.ey = y + dy * adv;
    }
    flush();
    return words;
  }

  async function readPdf(u8, opts) {
    opts = opts || {};
    const inflate = opts.inflate || defaultInflate;
    const pdf = await openPdf(u8, inflate);
    // الصفحات بالترتيب من شجرة Pages
    let cat = null;
    for (const [, o] of pdf.objs) if (o.v instanceof Map && nm(o.v.get('Type')) === 'Catalog') cat = o.v;
    const pages = [];
    const walk = (node, inh, depth) => {
      node = deref(pdf, node); if (!(node instanceof Map) || depth > 30) return;
      const ih = { res: node.has('Resources') ? node.get('Resources') : inh.res, mb: node.has('MediaBox') ? get(pdf, node, 'MediaBox') : inh.mb, cb: node.has('CropBox') ? get(pdf, node, 'CropBox') : inh.cb, rot: node.has('Rotate') ? +get(pdf, node, 'Rotate') : inh.rot };
      const kids = get(pdf, node, 'Kids');
      if (Array.isArray(kids)) kids.forEach((k) => walk(k, ih, depth + 1));
      else pages.push({ node, ...ih });
    };
    if (cat) walk(cat.get('Pages'), { res: null, mb: [0, 0, 612, 792], cb: null, rot: 0 }, 0);
    if (!pages.length) for (const [, o] of pdf.objs) if (o.v instanceof Map && nm(o.v.get('Type')) === 'Page') pages.push({ node: o.v, res: o.v.get('Resources'), mb: get(pdf, o.v, 'MediaBox') || [0, 0, 612, 792], cb: null, rot: +get(pdf, o.v, 'Rotate') || 0 });
    const out = [];
    for (let pi = 0; pi < pages.length; pi++) {
      if (opts.onProgress) opts.onProgress(pi + 1, pages.length);
      const pg = pages[pi];
      const box = (Array.isArray(pg.cb) ? pg.cb : pg.mb).map((x) => +deref(pdf, x));
      const r = (((pg.rot || 0) % 360) + 360) % 360;
      const w = box[2] - box[0], h = box[3] - box[1];
      let cont = pg.node.get('Contents'); const parts = Array.isArray(deref(pdf, cont)) && !(cont instanceof Ref && rec(pdf, cont).raw) ? deref(pdf, cont) : [cont];
      const chunks = [];
      for (const c of parts) { const rr = rec(pdf, c); if (rr) chunks.push(await streamData(pdf, rr)); }
      let tot = 0; chunks.forEach((c) => (tot += c.length + 1)); const data = new Uint8Array(tot); let o = 0; for (const c of chunks) { data.set(c, o); o += c.length; data[o++] = 10; }
      const glyphs = [];
      await runContent(pdf, data, deref(pdf, pg.res), [1, 0, 0, 1, 0, 0], glyphs, 0, { n: 5e7 });
      const words = wordsFromGlyphs(glyphs, { r, w, h, x0: box[0], y0: box[1] });
      out.push({ page: pi + 1, width: r % 180 ? h : w, height: r % 180 ? w : h, words });
    }
    return out;
  }
  async function defaultInflate(u8) {
    if (typeof DecompressionStream !== 'undefined') {
      const ds = new DecompressionStream('deflate');
      const w = ds.writable.getWriter(); w.write(u8).catch(() => {}); w.close().catch(() => {});
      const rd = ds.readable.getReader(); const parts = []; let n = 0;
      try { for (;;) { const { done, value } = await rd.read(); if (done) break; parts.push(value); n += value.length; } } catch (e) { /* نهاية تالفة: منحتفظ باللي انقرا */ }
      const o = new Uint8Array(n); let k = 0; for (const p of parts) { o.set(p, k); k += p.length; } return o;
    }
    const zlib = require('zlib');
    return new Uint8Array(zlib.inflateSync(Buffer.from(u8), { finishFlush: zlib.constants.Z_SYNC_FLUSH }));
  }

  const api = { readPdf, parseCMap, _Lexer: Lexer };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MzPdf = api;
})(typeof window !== 'undefined' ? window : this);
