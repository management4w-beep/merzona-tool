/* =====================================================================================
   📐 قارئ ملفات DWG خاص بميرزونا - 2026-11-10
   حمدي: "مالح اقدر من الموبايل اعمل حفظ وغير صيغة الملف لازم حتما السيستم يقراه".
   المكتبة الجاهزة (LibreDWG) ما قدرنا نشغّلها ونجربها هون، فهاد قارئ مكتوب من الصفر (اعتماداً على وصف
   الصيغة المنشور) وبيقرا بس يلي بيلزمنا: النصوص (TEXT / MTEXT)، البلوكات (INSERT) وخصائصها (ATTRIB)،
   وأسماء البلوكات ونقطة أساسها. النتيجة بنفس شكل قارئ الـDXF، وبعدين نفس الاستخراج والتحقق.
   الإصدارات: R2000 (AC1015)، R2004 (AC1018)، R2010 (AC1024)، R2013 (AC1027)، R2018 (AC1032).
   ===================================================================================== */
(function (root) {
  'use strict';

  const R2000 = 15, R2004 = 18, R2007 = 21, R2010 = 24, R2013 = 27, R2018 = 32;
  const VERS = { AC1015: R2000, AC1018: R2004, AC1021: R2007, AC1024: R2010, AC1027: R2013, AC1032: R2018 };

  /* ---------- 1) قارئ البتات ---------- */
  const F64 = new DataView(new ArrayBuffer(8));
  function Bits(u8, startByte, sizeBytes, ver) {
    this.u = u8; this.base = startByte; this.end = Math.min(u8.length, startByte + sizeBytes); this.p = startByte * 8; this.ver = ver;
  }
  Bits.prototype = {
    get pos() { return this.p - this.base * 8; },
    set pos(v) { this.p = this.base * 8 + v; },
    over() { return (this.p >> 3) >= this.end; },
    B() { const b = this.p >> 3; if (b >= this.end) throw new Error('eob'); const v = (this.u[b] >> (7 - (this.p & 7))) & 1; this.p++; return v; },
    BB() { return (this.B() << 1) | this.B(); },
    RC() {
      const b = this.p >> 3, o = this.p & 7;
      if (b >= this.end) throw new Error('eob');
      let v = o === 0 ? this.u[b] : ((this.u[b] << o) | ((b + 1 < this.u.length ? this.u[b + 1] : 0) >> (8 - o))) & 255;
      this.p += 8; return v;
    },
    RS() { const a = this.RC(); return a | (this.RC() << 8); },
    RL() { const a = this.RS(); return (a | (this.RS() << 16)) >>> 0; },
    RD() { for (let i = 0; i < 8; i++) F64.setUint8(i, this.RC()); return F64.getFloat64(0, true); },
    BS() { const c = this.BB(); return c === 0 ? this.RS() : c === 1 ? this.RC() : c === 2 ? 0 : 256; },
    BL() { const c = this.BB(); return c === 0 ? this.RL() : c === 1 ? this.RC() : 0; },
    BLL() { const n = (this.BB() << 1) | this.B(); let v = 0; for (let i = 0; i < n; i++) v += this.RC() * Math.pow(256, i); return v; },
    BD() { const c = this.BB(); return c === 0 ? this.RD() : c === 1 ? 1 : 0; },
    DD(def) {
      const c = this.BB();
      if (c === 0) return def;
      if (c === 3) return this.RD();
      F64.setFloat64(0, def, true);
      if (c === 2) { F64.setUint8(4, this.RC()); F64.setUint8(5, this.RC()); }
      for (let i = 0; i < 4; i++) F64.setUint8(i, this.RC());
      return F64.getFloat64(0, true);
    },
    BT() { return this.ver >= R2000 && this.B() ? 0 : this.BD(); },
    BE() { if (this.ver >= R2000 && this.B()) return [0, 0, 1]; return [this.BD(), this.BD(), this.BD()]; },
    BD3() { return [this.BD(), this.BD(), this.BD()]; },
    RD2() { return [this.RD(), this.RD()]; },
    BOT() { const c = this.BB(); return c === 0 ? this.RC() : c === 1 ? this.RC() + 0x1f0 : this.RS(); },
    MC() {
      let r = 0, sh = 0;
      for (let i = 0; i < 5; i++) {
        let b = this.RC();
        if (!(b & 0x80)) { let neg = false; if (b & 0x40) { neg = true; b &= 0xbf; } r += b * Math.pow(2, sh); return neg ? -r : r; }
        r += (b & 0x7f) * Math.pow(2, sh); sh += 7;
      }
      return r;
    },
    UMC() { let r = 0, sh = 0; for (let i = 0; i < 8; i++) { const b = this.RC(); r += (b & 0x7f) * Math.pow(2, sh); if (!(b & 0x80)) return r; sh += 7; } return r; },
    MS() { const a = this.RS(); if (!(a & 0x8000)) return a; const b = this.RS(); return (a & 0x7fff) + b * 0x8000; },
    H() { const c = this.RC(); const size = c & 15, code = c >> 4; if (size > 8) throw new Error('bad handle'); let v = 0; for (let i = 0; i < size; i++) v = v * 256 + this.RC(); return { code, size, v }; },
    skipBytes(n) { this.p += n * 8; },
  };

  /* ---------- 2) فك الضغط (LZ77 تبع R2004+) ---------- */
  function decompress(src, s, e, out, o0, oEnd) {
    let i = s, o = o0;
    const rc = () => (i < e ? src[i++] : 0);
    const litLen = (op) => { let l = op & 15; if (l === 0) { let b; while ((b = rc()) === 0 && i < e) l += 255; l += 15 + b; } return l + 3; };
    const compBytes = (op, bits) => { let n = op & bits; if (n === 0) { let b; while ((b = rc()) === 0 && i < e) n += 255; n += b + bits; } return n + 2; };
    const copyLit = (n) => { for (let k = 0; k < n && o < oEnd; k++) out[o++] = rc(); return rc(); };
    let op = rc();
    if ((op & 0xf0) === 0) op = copyLit(litLen(op));
    while (i < e && o < oEnd && op !== 0x11) {
      let n = 0, off = 0;
      if (op < 0x10 || op >= 0x40) { n = (op >> 4) - 1; const op2 = rc(); off = (((op >> 2) & 3) | (op2 << 2)) + 1; }
      else if (op < 0x20) { n = compBytes(op, 7); off = (op & 8) << 11; const a = rc(), b = rc(); off |= (a >> 2) | (b << 6); off += 0x4000; op = a; }
      else { n = compBytes(op, 0x1f); const a = rc(), b = rc(); off = ((a >> 2) | (b << 6)) + 1; op = a; }
      if (o - off < o0 || off <= 0) throw new Error('decompress offset');
      for (let k = 0; k < n && o < oEnd; k++, o++) out[o] = out[o - off];
      let l = op & 3;
      if (l === 0) { op = rc(); if ((op & 0xf0) === 0) l = litLen(op); }
      if (l) op = copyLit(l);
    }
    return o - o0;
  }

  /* ---------- 3) حاوية الملف: R2004 / R2010+ ---------- */
  const rl = (u, p) => (u[p] | (u[p + 1] << 8) | (u[p + 2] << 16) | (u[p + 3] << 24)) >>> 0;
  const rll = (u, p) => rl(u, p) + rl(u, p + 4) * 4294967296;
  function sectionsR2004(u8) {
    // ترويسة مشفّرة بـ0x80
    const h = new Uint8Array(0x6c); let seed = 1;
    for (let i = 0; i < 0x6c; i++) { seed = (Math.imul(seed, 0x343fd) + 0x269ec3) >>> 0; h[i] = u8[0x80 + i] ^ (seed >>> 16); }
    if (String.fromCharCode.apply(null, h.subarray(0, 11)) !== 'AcFssFcAJMB') throw new Error('ترويسة DWG غير صالحة');
    const mapAddr = rll(h, 0x54) + 0x100, infoId = rl(h, 0x5c) | 0;
    if (rl(u8, mapAddr) !== 0x41630e3b) throw new Error('خريطة الصفحات مش موجودة');
    const mapDec = new Uint8Array(rl(u8, mapAddr + 4) + 64);
    const mapLen = decompress(u8, mapAddr + 0x14, mapAddr + 0x14 + rl(u8, mapAddr + 8), mapDec, 0, mapDec.length);
    const pages = new Map(); let addr = 0x100;
    for (let p = 0; p + 8 <= mapLen;) {
      const num = rl(mapDec, p) | 0, size = rl(mapDec, p + 4); p += 8;
      pages.set(num, { addr, size }); addr += size;
      if (num < 0) p += 16;
    }
    const ip = pages.get(infoId);
    if (!ip || rl(u8, ip.addr) !== 0x4163003b) throw new Error('جدول الأقسام مش موجود');
    const infDec = new Uint8Array(rl(u8, ip.addr + 4) + 64);
    decompress(u8, ip.addr + 0x14, ip.addr + 0x14 + rl(u8, ip.addr + 8), infDec, 0, infDec.length);
    const nDesc = rl(infDec, 0); const descs = new Map(); let q = 20;
    for (let d = 0; d < nDesc && q + 96 <= infDec.length; d++) {
      const size = rll(infDec, q), np = rl(infDec, q + 8), maxd = rl(infDec, q + 12), comp = rl(infDec, q + 20), enc = rl(infDec, q + 28);
      let name = ''; for (let k = 0; k < 64 && infDec[q + 32 + k]; k++) name += String.fromCharCode(infDec[q + 32 + k]);
      q += 96;
      const plist = [];
      for (let k = 0; k < np && q + 16 <= infDec.length; k++) { plist.push({ num: rl(infDec, q) | 0, size: rl(infDec, q + 4), off: rll(infDec, q + 8) }); q += 16; }
      descs.set(name, { size, maxd, comp, enc, pages: plist });
    }
    return function read(name) {
      const d = descs.get(name); if (!d) return null;
      if (d.enc === 1) throw new Error('القسم ' + name + ' مشفّر');
      const out = new Uint8Array(Math.max(d.size, d.pages.length * d.maxd) + 16);
      for (const pg of d.pages) {
        const pp = pages.get(pg.num); if (!pp) continue;
        const a = pp.addr, mask = (0x4164536b ^ a) >>> 0;
        const f = []; for (let k = 0; k < 8; k++) f.push((rl(u8, a + k * 4) ^ mask) >>> 0);
        const dataSize = f[2], pageSize = f[3], start = f[4];
        if (d.comp === 2) decompress(u8, a + 32, Math.min(u8.length, a + 32 + dataSize), out, start, Math.min(out.length, start + d.maxd));
        else out.set(u8.subarray(a + 32, a + 32 + Math.min(pageSize, out.length - start)), start);
      }
      return out.subarray(0, d.size);
    };
  }

  /* ---------- 4) خريطة الكائنات (Handles) ---------- */
  function objectMap(buf) {
    const map = new Map(); let p = 0;
    while (p + 2 <= buf.length) {
      const start = p; const size = (buf[p] << 8) | buf[p + 1]; p += 2;
      if (size <= 2) break;
      const r = new Bits(buf, p, buf.length - p, R2004);
      let h = 0, off = 0;
      while ((r.p >> 3) - start < size) { h += r.UMC(); off += r.MC(); map.set(h, off); }
      p = (r.p >> 3) + 2; // CRC
      if (p <= start) break;
    }
    return map;
  }

  /* ---------- 5) قراءة كائن ---------- */
  const T_TEXT = 1, T_ATTRIB = 2, T_ATTDEF = 3, T_INSERT = 7, T_MINSERT = 8, T_MTEXT = 44, T_BLOCK_HEADER = 49;
  function absRef(h, base) {
    switch (h.code) { case 6: return base + 1; case 8: return base - 1; case 0xA: return base + h.v; case 0xC: return base - h.v; default: return h.v; }
  }
  function makeText(ver, dec) {
    // R2007+: النصوص UTF-16 بقسم آخر الكائن؛ قبل: بايتات بترميز الملف
    return function (r) {
      const n = r.BS();
      if (ver >= R2007) { let s = ''; for (let i = 0; i < n; i++) s += String.fromCharCode(r.RS()); return s.replace(/\0+$/, ''); }
      const b = new Uint8Array(n); for (let i = 0; i < n; i++) b[i] = r.RC();
      let e = n; while (e > 0 && b[e - 1] === 0) e--;
      return dec(b.subarray(0, e));
    };
  }
  function parseObject(buf, off, ver, T) {
    const pre = new Bits(buf, off, buf.length - off, ver);
    const size = pre.MS();
    let hs = 0; if (ver >= R2010) hs = pre.UMC();
    const start = pre.p >> 3;
    if (size <= 0 || start + size > buf.length) return null;
    const r = new Bits(buf, start, size, ver);
    const type = ver >= R2010 ? r.BOT() : r.BS();
    const want = type === T_TEXT || type === T_ATTRIB || type === T_INSERT || type === T_MINSERT || type === T_MTEXT || type === T_BLOCK_HEADER;
    if (!want) return { type };
    let bitsize;
    if (ver >= R2010) bitsize = size * 8 - hs; else bitsize = r.RL();
    // مجرى النصوص (R2007+)
    let S = r;
    if (ver >= R2007) {
      S = new Bits(buf, start, size, ver);
      S.pos = bitsize - 1;
      if (S.B()) {
        S.pos = bitsize - 1 - 16; let ds = S.RS();
        if (ds & 0x8000) { S.pos = bitsize - 1 - 32; const hi = S.RS(); ds = (ds & 0x7fff) | (hi << 15); S.pos = bitsize - 1 - 32 - ds; }
        else S.pos = bitsize - 1 - 16 - ds;
      }
    }
    const H = new Bits(buf, start, size, ver); H.pos = bitsize;
    const handle = r.H().v;
    // EED
    for (let k = 0; k < 1000; k++) { const n = r.BS(); if (!n) break; r.H(); r.skipBytes(n); }
    const o = { type, handle };
    if (type === T_BLOCK_HEADER) {
      r.BL(); if (ver >= R2004) r.B(); if (ver >= R2013) r.B();
      o.name = T(S);
      if (ver <= R2004) { r.B(); r.BS(); r.B(); } else r.BS();
      r.B(); r.B(); const isx = r.B(), ovl = r.B();
      if (ver >= R2000) r.B();
      if (ver >= R2004 && !isx && !ovl) r.BL();
      o.base = r.BD3();
      return o;
    }
    // بيانات الكيان المشتركة
    if (r.B()) { const n = ver >= R2010 ? r.BLL() : r.RL(); r.skipBytes(n); }
    o.entmode = r.BB();
    const nReact = r.BL();
    const xdicMissing = ver >= R2004 ? r.B() : 0;
    const nolinks = ver <= R2000 ? r.B() : 1;
    if (ver >= R2013) r.B();
    let colorHandle = false;
    if (ver >= R2004) {
      const raw = r.BS(), fl = raw >> 8;
      if (fl & 0x20) r.BL();
      if (fl & 0x40) colorHandle = true; else if (fl & 0x80) r.BL();
      if ((fl & 0x41) === 0x41) T(S);
      if ((fl & 0x42) === 0x42) T(S);
    } else r.BS();
    r.BD();
    const ltf = r.BB();
    let psf = 0, matf = 0, shad = 0, vs = [0, 0, 0];
    if (ver < R2007) psf = r.BB(); else { matf = r.BB(); psf = r.BB(); shad = r.RC(); }
    if (ver >= R2010) vs = [r.B(), r.B(), r.B()];
    r.BS(); r.RC();
    // البيانات الخاصة
    if (type === T_TEXT || type === T_ATTRIB) {
      const df = r.RC();
      if (!(df & 1)) r.RD();
      const ins = r.RD2();
      let al = ins; if (!(df & 2)) al = [r.DD(ins[0]), r.DD(ins[1])];
      r.BE(); r.BT();
      if (!(df & 4)) r.RD();
      o.rot = !(df & 8) ? r.RD() : 0;
      o.h = r.RD();
      if (!(df & 0x10)) r.RD();
      o.text = T(S);
      if (!(df & 0x20)) r.BS();
      const ha = !(df & 0x40) ? r.BS() : 0;
      const va = !(df & 0x80) ? r.BS() : 0;
      o.x = ins[0]; o.y = ins[1];
      if (ha || va) { o.ax = al[0]; o.ay = al[1]; }
      if (type === T_ATTRIB) {
        if (ver >= R2010) r.RC();
        let mt = 1; if (ver >= R2018) mt = r.RC();
        if (mt <= 1) o.tag = T(S);
      }
    } else if (type === T_MTEXT) {
      const ins = r.BD3(); r.BD3(); r.BD3(); r.BD(); if (ver >= R2007) r.BD();
      o.h = r.BD(); r.BS(); r.BS(); r.BD(); r.BD();
      o.text = T(S); o.mtext = true; o.x = ins[0]; o.y = ins[1];
    } else if (type === T_INSERT || type === T_MINSERT) {
      const ins = r.BD3(); let sx = 1, sy = 1;
      if (ver >= R2000) {
        const sf = r.BB();
        if (sf === 3) { /* 1,1,1 */ } else if (sf === 1) { sy = r.DD(1); r.DD(1); } else if (sf === 2) { sx = sy = r.RD(); } else { sx = r.RD(); sy = r.DD(sx); r.DD(sx); }
      } else { sx = r.BD(); sy = r.BD(); r.BD(); }
      o.rot = r.BD(); r.BD3();
      const hasAtt = r.B(); let nOwned = 0;
      if (ver >= R2004 && hasAtt) nOwned = r.BL();
      o.x = ins[0]; o.y = ins[1]; o.sx = sx; o.sy = sy;
      // مجرى المراجع: نوصل لمرجع تعريف البلوك
      if (colorHandle) H.H();
      if (o.entmode === 0) o.owner = absRef(H.H(), handle);
      for (let k = 0; k < nReact; k++) H.H();
      if (!xdicMissing) H.H();
      if (ver <= R2000 && !nolinks) { H.H(); H.H(); }
      H.H(); // layer
      if (ltf === 3) H.H();
      if (ver >= R2007) { if (matf === 3) H.H(); if (shad === 3) H.H(); }
      if (psf === 3) H.H();
      if (ver >= R2010) vs.forEach((x) => { if (x) H.H(); });
      o.block = absRef(H.H(), handle);
      void nOwned;
      return o;
    }
    // المالك (البلوك يلي فيه الكيان أو البلوك المُدرج للخاصية)
    if (o.entmode === 0) {
      if (colorHandle) H.H();
      o.owner = absRef(H.H(), handle);
    }
    return o;
  }

  /* ---------- 6) R2000: الحاوية بدون ضغط ---------- */
  function sectionsR2000(u8) {
    const n = rl(u8, 0x15); const recs = {};
    for (let i = 0; i < n && i < 10; i++) { const p = 0x19 + i * 9; recs[u8[p]] = { addr: rl(u8, p + 1), size: rl(u8, p + 5) }; }
    return recs;
  }

  /* ---------- 7) القراءة الكاملة ---------- */
  function readDwg(u8, opts) {
    opts = opts || {};
    if (!(u8 instanceof Uint8Array)) u8 = new Uint8Array(u8);
    const sig = String.fromCharCode.apply(null, u8.subarray(0, 6));
    const ver = VERS[sig];
    if (!ver) throw new Error(/^AC1\.|^AC10(0|1[0-4])/.test(sig) ? 'نسخة DWG قديمة كتير (' + sig + ') - احفظها من أوتوكاد بنسخة أحدث' : 'مش ملف DWG مدعوم (' + sig + ')');
    if (ver === R2007) throw new Error('UNSUPPORTED_2007');
    const cp = u8[0x13] | (u8[0x14] << 8);
    const enc = { 28: 'windows-1250', 29: 'windows-1251', 30: 'windows-1252', 32: 'windows-1253', 33: 'windows-1254', 34: 'windows-1255', 35: 'windows-1256', 36: 'windows-1257', 37: 'windows-874', 38: 'shift_jis', 39: 'gbk', 40: 'euc-kr', 41: 'big5' }[cp] || 'windows-1252';
    let td; try { td = new TextDecoder(enc); } catch (e) { td = new TextDecoder('windows-1252'); }
    const dec = (b) => td.decode(b);
    const T = makeText(ver, dec);

    let objs, map, fileAbs = false;
    if (ver >= R2004) {
      const read = sectionsR2004(u8);
      objs = read('AcDb:AcDbObjects'); const hd = read('AcDb:Handles');
      if (!objs || !hd) throw new Error('أقسام الكائنات مش موجودة');
      map = objectMap(hd);
    } else {
      const recs = sectionsR2000(u8);
      if (!recs[2]) throw new Error('خريطة الكائنات مش موجودة');
      objs = u8; fileAbs = true;
      map = objectMap(u8.subarray(recs[2].addr, recs[2].addr + recs[2].size));
    }
    void fileAbs;
    const blocksByHandle = new Map(), ents = [];
    let bad = 0, n = 0;
    for (const [h, off] of map) {
      n++;
      let o = null;
      try { o = parseObject(objs, off, ver, T); } catch (e) { bad++; continue; }
      if (!o || o.handle === undefined) continue;
      if (o.type === T_BLOCK_HEADER) blocksByHandle.set(o.handle, { name: (/^\*[A-Za-z]$/.test(o.name || '') ? o.name + o.handle.toString(16).toUpperCase() : o.name || ''), bx: o.base ? o.base[0] : 0, by: o.base ? o.base[1] : 0, items: [] });
      else if (o.type !== undefined && (o.text !== undefined || o.block !== undefined)) ents.push(o);
      if (opts.onProgress && n % 5000 === 0) opts.onProgress(n, map.size);
    }
    // ترتيب الكيانات حسب مالكها
    const byHandle = new Map(); ents.forEach((e) => byHandle.set(e.handle, e));
    const doc = { units: 0, blocks: {}, entities: [], version: sig, codepage: enc, stats: { objects: map.size, failed: bad, texts: 0, inserts: 0 } };
    for (const b of blocksByHandle.values()) doc.blocks[b.name] = b;
    const nameOf = (h) => (blocksByHandle.get(h) || {}).name;
    for (const e of ents) {
      let item;
      if (e.type === T_INSERT || e.type === T_MINSERT) { item = { kind: 'insert', name: nameOf(e.block) || '', x: e.x, y: e.y, sx: e.sx, sy: e.sy, rot: (e.rot || 0) * 180 / Math.PI, layer: '', attribs: [] }; e.item = item; doc.stats.inserts++; }
      else if (e.type === T_ATTRIB) continue;
      else { item = { kind: 'text', x: e.x, y: e.y, h: e.h || 0, raw: e.text || '', mtext: !!e.mtext, layer: '' }; doc.stats.texts++; }
      const ob = e.entmode === 0 ? blocksByHandle.get(e.owner) : null;
      if (ob) ob.items.push(item);
      else if (e.entmode === 1 || e.entmode === 2) doc.entities.push(item);
    }
    for (const e of ents) if (e.type === T_ATTRIB) {
      const ins = byHandle.get(e.owner);
      if (ins && ins.item) ins.item.attribs.push({ tag: e.tag || '', raw: e.text || '', x: e.x, y: e.y, h: e.h });
    }
    // جداول أوتوكاد (*T): البلوك تبعها بينرسم من كيان ACAD_TABLE؛ إذا ما في INSERT إله منحطّه بمكان لحاله
    const inserted = new Set();
    const walk = (items) => items.forEach((it) => { if (it.kind === 'insert') inserted.add(it.name); });
    walk(doc.entities); for (const b of Object.values(doc.blocks)) walk(b.items);
    let k = 0;
    for (const b of Object.values(doc.blocks)) if (/^\*T[0-9A-F]*$/i.test(b.name) && !inserted.has(b.name) && b.items.length) {
      doc.entities.push({ kind: 'insert', name: b.name, x: b.bx + 1e8 * (++k), y: b.by, sx: 1, sy: 1, rot: 0, layer: '', attribs: [] });
    }
    return doc;
  }

  const api = { readDwg, _decompress: decompress, _Bits: Bits };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MzDwg = api;
})(typeof window !== 'undefined' ? window : this);
