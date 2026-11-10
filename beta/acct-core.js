/* =====================================================================================
   Merzona Accounting Core (acct-core.js) — 2026-11-07
   قلب النظام المحاسبي: كل الحسابات (القيود، الأرصدة، التقارير) بمكان واحد.
   نفس هالملف بالضبط بيستخدمه السيرفر (للتحقق قبل الحفظ) والصفحة (للعرض والتقارير)،
   فما في رقم بينحسب بطريقتين مختلفتين.

   المبادئ:
   - قيد مزدوج: كل مستند بيتحوّل لقيود (مدين/دائن) بعملة الدفتر الأساسية، ولازم تكون موزونة.
   - المستندات ما بتنحذف: بتنلغى (void) وبتضل مسجّلة.
   - كل المبالغ بتتقرّب لخانتين (سنتات) بطريقة وحدة (r2).
   - دفترين منفصلين: الإمارات (درهم + ضريبة 5%) وسوريا (دولار، ومسموح ليرة بسعر صرف).
   ===================================================================================== */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.AcctCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var VERSION = '1.0.0';

  /* ---------------------------------- أرقام ---------------------------------- */
  // تقريب لخانتين بدون أخطاء الفاصلة العائمة (1.005 → 1.01)
  function r2(n) {
    n = Number(n);
    if (!isFinite(n)) return 0;
    var s = n < 0 ? -1 : 1;
    return s * Math.round((Math.abs(n) + 1e-9) * 100) / 100;
  }
  function own(o, k) { return o && Object.prototype.hasOwnProperty.call(o, k) ? o[k] : undefined; }
  function num(v) { var n = Number(v); return isFinite(n) ? n : 0; }
  function isNum(v) { return v !== '' && v !== null && v !== undefined && isFinite(Number(v)); }
  var DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  function isDate(s) {
    if (typeof s !== 'string' || !DATE_RE.test(s)) return false;
    var d = new Date(s + 'T00:00:00Z');
    return !isNaN(d) && d.toISOString().slice(0, 10) === s;
  }

  /* ---------------------------------- الدفاتر ---------------------------------- */
  var BOOKS = {
    uae: { id: 'uae', name: 'فرع الإمارات', base: 'AED', currencies: ['AED', 'USD'], vatRate: 5, prefix: '' },
    syria: { id: 'syria', name: 'فرع سوريا', base: 'USD', currencies: ['USD', 'SYP'], vatRate: 0, prefix: 'S-' },
  };
  var CURRENCY_LABEL = { AED: 'د.إ', USD: 'USD', SYP: 'ل.س' };

  var TYPES = ['asset', 'liability', 'equity', 'income', 'cogs', 'expense'];
  var TYPE_LABEL = { asset: 'أصول', liability: 'خصوم', equity: 'حقوق ملكية', income: 'إيرادات', cogs: 'تكاليف مباشرة', expense: 'مصاريف' };
  function debitNormal(type) { return type === 'asset' || type === 'cogs' || type === 'expense'; }

  // حسابات النظام (ما بتنحذف وما بيتغيّر نوعها)
  var SYS = { AR: '1100', AP: '2000', VAT_OUT: '2200', VAT_IN: '1400', FX: '7900', OPENING: '3900', RETAINED: '3200' };

  function defaultChart(bookId) {
    var uae = bookId === 'uae';
    var A = [
      ['1000', 'الصندوق (كاش)', 'asset', 'cash'],
      ['1010', 'البنك', 'asset', 'bank'],
      ['1100', 'ذمم الزبائن (مدينون)', 'asset', 'ar'],
      ['1200', 'مخزون مواد', 'asset', ''],
      ['1300', 'دفعات مقدمة للموردين', 'asset', ''],
      uae ? ['1400', 'ضريبة القيمة المضافة - مدخلات (قابلة للاسترداد)', 'asset', 'vat_in'] : null,
      ['1500', 'معدات وآلات', 'asset', ''],
      ['1510', 'سيارات', 'asset', ''],
      ['1590', 'مجمع الإهلاك', 'asset', ''],
      ['2000', 'ذمم الموردين (دائنون)', 'liability', 'ap'],
      ['2100', 'دفعات مقدمة من الزبائن', 'liability', ''],
      uae ? ['2200', 'ضريبة القيمة المضافة - مخرجات (مستحقة)', 'liability', 'vat_out'] : null,
      ['2300', 'رواتب مستحقة', 'liability', ''],
      ['2400', 'قروض', 'liability', ''],
      ['3000', 'رأس المال', 'equity', ''],
      ['3100', 'مسحوبات شخصية', 'equity', ''],
      ['3200', 'أرباح مدوّرة', 'equity', 'retained'],
      ['3900', 'أرصدة افتتاحية', 'equity', 'opening'],
      ['4000', 'إيرادات عقود ألمنيوم وزجاج', 'income', ''],
      ['4100', 'إيرادات أخرى', 'income', ''],
      ['5000', 'مواد ألمنيوم', 'cogs', ''],
      ['5010', 'زجاج', 'cogs', ''],
      ['5020', 'إكسسوارات وقطع', 'cogs', ''],
      ['5100', 'مقاولين باطن', 'cogs', ''],
      ['5200', 'أجور تركيب', 'cogs', ''],
      ['5300', 'نقل وتوصيل', 'cogs', ''],
      ['6000', 'رواتب وأجور', 'expense', ''],
      ['6100', 'إيجار', 'expense', ''],
      ['6200', 'كهرباء وماء', 'expense', ''],
      ['6300', 'وقود وسيارات', 'expense', ''],
      ['6400', 'عدة وصيانة', 'expense', ''],
      ['6500', 'تسويق وإعلان', 'expense', ''],
      ['6600', 'رسوم حكومية وتراخيص', 'expense', ''],
      ['6700', 'عمولات بنكية', 'expense', ''],
      ['6800', 'اتصالات وإنترنت', 'expense', ''],
      ['6900', 'مصاريف متنوعة', 'expense', ''],
      ['7900', 'فروقات أسعار صرف', 'expense', 'fx'],
    ];
    return A.filter(Boolean).map(function (a) { return { code: a[0], name: a[1], type: a[2], role: a[3] || '', archived: false }; });
  }

  function newBook(bookId) {
    var b = BOOKS[bookId];
    if (!b) throw new Error('unknown-book');
    return {
      book: bookId,
      rev: 0,
      coreVersion: VERSION,
      base: b.base,
      settings: { companyName: 'Merzona', trn: '', address: '', vatRate: b.vatRate, lockDate: '', invoiceNote: '' },
      accounts: defaultChart(bookId),
      parties: {},
      docs: {},
      seq: {},
      recon: {},
    };
  }

  /* ---------------------------------- المستندات ---------------------------------- */
  var DOC_TYPES = {
    invoice: { label: 'فاتورة مبيعات', prefix: 'INV', party: 'customer' },
    credit: { label: 'إشعار دائن (مرتجع/خصم لزبون)', prefix: 'CN', party: 'customer' },
    receipt: { label: 'سند قبض', prefix: 'RV', party: 'customer' },
    bill: { label: 'فاتورة مورد', prefix: 'BILL', party: 'vendor' },
    vcredit: { label: 'إشعار مدين من مورد (مرتجع)', prefix: 'DN', party: 'vendor' },
    vpayment: { label: 'سند صرف لمورد', prefix: 'PV', party: 'vendor' },
    expense: { label: 'مصروف مباشر', prefix: 'EXP', party: '' },
    deposit: { label: 'مقبوضات أخرى', prefix: 'DEP', party: '' },
    transfer: { label: 'تحويل بين الصناديق/البنوك', prefix: 'TRF', party: '' },
    journal: { label: 'قيد يومية', prefix: 'JV', party: '' },
  };

  function acctMap(book) { var m = Object.create(null); (book.accounts || []).forEach(function (a) { m[a.code] = a; }); return m; }
  function roleAcct(book, role, fallback) {
    var a = (book.accounts || []).filter(function (x) { return x.role === role; })[0];
    return a ? a.code : fallback;
  }
  function sysAccts(book) {
    return {
      AR: roleAcct(book, 'ar', SYS.AR), AP: roleAcct(book, 'ap', SYS.AP),
      VAT_OUT: roleAcct(book, 'vat_out', SYS.VAT_OUT), VAT_IN: roleAcct(book, 'vat_in', SYS.VAT_IN),
      FX: roleAcct(book, 'fx', SYS.FX), OPENING: roleAcct(book, 'opening', SYS.OPENING), RETAINED: roleAcct(book, 'retained', SYS.RETAINED),
    };
  }
  function isMoneyAcct(a) { return !!a && (a.role === 'cash' || a.role === 'bank'); }

  function docFx(doc, book) {
    // fx = كم وحدة من عملة المستند بتساوي 1 من عملة الدفتر (مثلاً 1 USD = 13000 SYP → fx = 13000)
    if (!doc.currency || doc.currency === book.base) return 1;
    var f = Number(doc.fx);
    return f > 0 && isFinite(f) ? f : NaN;
  }
  function toBase(amount, fx) { return r2(num(amount) / fx); }

  // مجموع الفاتورة/فاتورة المورد/المصروف بعملة المستند
  function lineAmount(l, type) {
    if (type === 'expense' || type === 'deposit') return r2(num(l.amount));
    return r2(num(l.qty === undefined || l.qty === '' ? 1 : l.qty) * num(l.price));
  }
  function docTotals(doc, book) {
    var t = doc.type;
    if (t === 'invoice' || t === 'credit' || t === 'bill' || t === 'vcredit' || t === 'expense' || t === 'deposit') {
      var rate = num(doc.taxRate);
      var sub = 0, tax = 0;
      (doc.lines || []).forEach(function (l) {
        var a = lineAmount(l, t);
        sub = r2(sub + a);
        if (l.tax && rate > 0) tax = r2(tax + r2(a * rate / 100));
      });
      return { subtotal: sub, tax: tax, total: r2(sub + tax) };
    }
    if (t === 'receipt' || t === 'vpayment' || t === 'transfer') { var a = r2(num(doc.amount)); return { subtotal: a, tax: 0, total: a }; }
    if (t === 'journal') {
      var dr = 0; (doc.lines || []).forEach(function (l) { dr = r2(dr + num(l.dr)); });
      return { subtotal: dr, tax: 0, total: dr };
    }
    return { subtotal: 0, tax: 0, total: 0 };
  }

  /* --------------------------- تحويل المستند لقيود ---------------------------
     كل سطر قيد: { acct, dr, cr, party, project, docId, memo } بعملة الدفتر الأساسية.
     - مجموع الذمم = تحويل "إجمالي المستند" لعملة الدفتر، وفرق السنتات (لو في) بينحط على آخر سطر،
       فالفاتورة المدفوعة بالكامل بتسكّر ذمتها بالضبط بدون ولا سنت باقي.
     - الدفعة المطبّقة على فاتورة بتسكّر من ذمتها بسعر صرف الفاتورة المحفوظ مع التطبيق (ap.fx)،
       وبالتراكم (مجموع المطبّق لهلق) حتى آخر دفعة تسكّر الباقي بالضبط. الفرق عن سعر اليوم → فروقات صرف. */
  var APPLY_TYPES = { receipt: 1, vpayment: 1, credit: 1, vcredit: 1 };
  function applyIndex(book) {
    var idx = Object.create(null);
    Object.keys(book.docs).forEach(function (id) {
      var d = book.docs[id];
      if (!d || d.void || !APPLY_TYPES[d.type]) return;
      (d.applies || []).forEach(function (ap) { (idx[ap.docId] = idx[ap.docId] || []).push({ key: (d.date || '') + '|' + d.id, amt: num(ap.amount), docId: d.id }); });
    });
    return idx;
  }
  function targetFx(book, ap) {
    if (ap && Number(ap.fx) > 0) return Number(ap.fx);
    var t = own(book.docs, ap.docId);
    return t ? docFx(t, book) : 1;
  }
  // كم بتسكّر هالتطبيق من الذمة بعملة الدفتر (تراكمي)
  function applyBase(book, doc, ap, idx) {
    var tfx = targetFx(book, ap);
    var myKey = (doc.date || '') + '|' + (doc.id || '~');
    var before = 0;
    (idx[ap.docId] || []).forEach(function (x) { if (x.docId !== doc.id && x.key < myKey) before = r2(before + x.amt); });
    return r2(toBase(r2(before + num(ap.amount)), tfx) - toBase(before, tfx));
  }
  function docPostings(doc, book, idx) {
    var S = sysAccts(book);
    var fx = docFx(doc, book);
    var out = [];
    var proj = doc.project || '';
    function P(acct, dr, cr, extra) {
      dr = r2(dr); cr = r2(cr);
      if (dr < 0) { cr = r2(cr - dr); dr = 0; }
      if (cr < 0) { dr = r2(dr - cr); cr = 0; }
      if (!dr && !cr) return;
      var p = { acct: acct, dr: dr, cr: cr, party: (extra && extra.party) || '', project: (extra && extra.project !== undefined ? extra.project : proj) || '', docId: doc.id, date: doc.date, type: doc.type, no: doc.no || '', memo: (extra && extra.memo) || '' };
      if (extra && extra.li !== undefined) p.li = extra.li;
      if (extra && extra.isTax) p.isTax = true;
      out.push(p);
    }
    function sumSide(side) { return r2(out.reduce(function (s, p) { return s + p[side]; }, 0)); }
    var t = doc.type, rate = num(doc.taxRate);
    var applies = APPLY_TYPES[t] ? (doc.applies || []) : [];
    if (applies.length && !idx) idx = applyIndex(book);

    // سطور + ضريبة، بعدين تصحيح السنتات لحتى يطلع المجموع = إجمالي المستند بعملة الدفتر
    function linesWithTax(side, taxAcct) {
      var tax = 0, last = -1;
      (doc.lines || []).forEach(function (l, li) {
        var a = lineAmount(l, t), b = toBase(a, fx);
        var ex = { memo: l.desc, project: l.project || proj, li: li };
        if (side === 'dr') P(l.acct, b, 0, ex); else P(l.acct, 0, b, ex);
        if (out.length) last = out.length - 1;
        if (l.tax && rate > 0) tax = r2(tax + r2(a * rate / 100));
      });
      if (tax) { var tb = toBase(tax, fx); if (side === 'dr') P(taxAcct, tb, 0, { isTax: true }); else P(taxAcct, 0, tb, { isTax: true }); }
      var want = toBase(docTotals(doc, book).total, fx);
      var d = r2(want - sumSide(side));
      if (d && last >= 0) { out[last][side] = r2(out[last][side] + d); }
      return want;
    }

    if (t === 'invoice') { var v1 = linesWithTax('cr', S.VAT_OUT); P(S.AR, v1, 0, { party: doc.partyId }); }
    else if (t === 'credit') { var v2 = linesWithTax('dr', S.VAT_OUT); creditSide(v2, 'AR'); }
    else if (t === 'bill') { var v3 = linesWithTax('dr', S.VAT_IN); P(S.AP, 0, v3, { party: doc.partyId }); }
    else if (t === 'vcredit') { var v4 = linesWithTax('cr', S.VAT_IN); creditSide(v4, 'AP'); }
    else if (t === 'expense') { var v5 = linesWithTax('dr', S.VAT_IN); P(doc.acct, 0, v5, { party: doc.partyId || '' }); }
    else if (t === 'deposit') { var v6 = linesWithTax('cr', S.VAT_OUT); P(doc.acct, v6, 0, { party: doc.partyId || '' }); }
    else if (t === 'receipt' || t === 'vpayment') {
      var cash = toBase(doc.amount, fx);
      var rel = 0, appliedAmt = 0;
      applies.forEach(function (ap) { rel = r2(rel + applyBase(book, doc, ap, idx)); appliedAmt = r2(appliedAmt + num(ap.amount)); });
      rel = r2(rel + toBase(r2(num(doc.amount) - appliedAmt), fx));
      var diff = r2(cash - rel);
      if (t === 'receipt') { P(doc.acct, cash, 0, { party: doc.partyId }); P(S.AR, 0, rel, { party: doc.partyId }); if (diff) { if (diff > 0) P(S.FX, 0, diff); else P(S.FX, -diff, 0); } }
      else { P(S.AP, rel, 0, { party: doc.partyId }); P(doc.acct, 0, cash, { party: doc.partyId }); if (diff) { if (diff < 0) P(S.FX, 0, -diff); else P(S.FX, diff, 0); } }
    } else if (t === 'transfer') {
      var amt = toBase(doc.amount, fx);
      P(doc.to, amt, 0); P(doc.from, 0, amt);
    } else if (t === 'journal') {
      (doc.lines || []).forEach(function (l) { P(l.acct, num(l.dr), num(l.cr), { party: l.party || '', project: l.project || proj, memo: l.memo || '' }); });
    }
    // الإشعار (دائن/مدين): الجزء المطبّق بيسكّر الذمة بسعر الفاتورة، والباقي بسعر الإشعار، والفرق → فروقات صرف
    function creditSide(totalBase, side) {
      var rel = 0, appliedAmt = 0;
      applies.forEach(function (ap) { rel = r2(rel + applyBase(book, doc, ap, idx)); appliedAmt = r2(appliedAmt + num(ap.amount)); });
      var totalDoc = docTotals(doc, book).total;
      rel = r2(rel + toBase(r2(totalDoc - appliedAmt), fx));
      var diff = r2(rel - totalBase);
      if (side === 'AR') { P(S.AR, 0, rel, { party: doc.partyId }); if (diff) { if (diff > 0) P(S.FX, diff, 0); else P(S.FX, 0, -diff); } }
      else { P(S.AP, rel, 0, { party: doc.partyId }); if (diff) { if (diff > 0) P(S.FX, 0, diff); else P(S.FX, -diff, 0); } }
    }
    return out;
  }

  /* ---------------------------------- التحقق ---------------------------------- */
  /* بند مفتوح = فاتورة، فاتورة مورد، أو قيد افتتاحي منقول (رصيد فاتورة قديمة من QuickBooks) */
  function itemKind(d) {
    if (!d) return '';
    if (d.type === 'invoice') return 'ar';
    if (d.type === 'bill') return 'ap';
    if (d.type === 'journal' && d.openItem && (d.openItem.kind === 'ar' || d.openItem.kind === 'ap')) return d.openItem.kind;
    return '';
  }
  function itemTotal(d, book) { return d.type === 'journal' ? r2(num(d.openItem && d.openItem.amount)) : docTotals(d, book).total; }
  function openBalanceOf(book, targetId, excludeDocId) {
    var target = own(book.docs, targetId);
    if (!target || target.void || !itemKind(target)) return 0;
    var total = itemTotal(target, book);
    var used = 0;
    Object.keys(book.docs).forEach(function (id) {
      var d = book.docs[id];
      if (!d || d.void || id === excludeDocId || !APPLY_TYPES[d.type]) return;
      (d.applies || []).forEach(function (ap) { if (ap.docId === targetId) used = r2(used + num(ap.amount)); });
    });
    return r2(total - used);
  }
  // مجموع المطبّق على كل بند - مرّة وحدة (بدل ما نلف على كل المستندات لكل بند)
  function appliedMap(book, asOf) {
    var m = Object.create(null);
    Object.keys(book.docs).forEach(function (id) {
      var d = book.docs[id];
      if (!d || d.void || !APPLY_TYPES[d.type]) return;
      if (asOf && d.date > asOf) return;
      (d.applies || []).forEach(function (ap) { m[ap.docId] = r2((m[ap.docId] || 0) + num(ap.amount)); });
    });
    return m;
  }

  function validateDoc(doc, book, opts) {
    opts = opts || {};
    var E = [];
    var def = DOC_TYPES[doc && doc.type];
    if (!doc || !def) return ['نوع المستند غير معروف'];
    var A = acctMap(book);
    if (!isDate(doc.date)) E.push('التاريخ غلط');
    if (doc.due !== undefined && doc.due !== '' && doc.due !== null && !isDate(doc.due)) E.push('تاريخ الاستحقاق غلط');
    if (doc.due && isDate(doc.due) && isDate(doc.date) && doc.due < doc.date) E.push('تاريخ الاستحقاق قبل تاريخ المستند');
    if (doc.openItem && doc.openItem.due && !isDate(doc.openItem.due)) E.push('تاريخ استحقاق البند غلط');
    (doc.applies || []).forEach(function (ap) { if (ap && ap.fx !== undefined && !(Number(ap.fx) > 0)) E.push('سعر صرف التطبيق غلط'); });
    var lock = book.settings && book.settings.lockDate;
    if (lock && isDate(doc.date) && doc.date <= lock) E.push('الفترة مقفلة لغاية ' + lock + ' - ما فيك تضيف أو تعدّل قبلها');
    if (opts.prevDate && lock && opts.prevDate <= lock) E.push('المستند الأصلي ضمن فترة مقفلة (' + lock + ')');
    var cur = doc.currency || book.base;
    var bk = BOOKS[book.book];
    if (bk && bk.currencies.indexOf(cur) === -1) E.push('العملة ' + cur + ' مش مسموحة بهالدفتر');
    var fx = docFx(doc, book);
    if (!(fx > 0)) E.push('سعر الصرف لازم يكون رقم أكبر من صفر');
    if (def.party) {
      var p = Object.prototype.hasOwnProperty.call(book.parties, doc.partyId) ? book.parties[doc.partyId] : null;
      if (!p) E.push(def.party === 'customer' ? 'لازم تختار زبون' : 'لازم تختار مورد');
      else if (p.kind !== def.party && p.kind !== 'both') E.push(def.party === 'customer' ? 'الطرف المختار مش زبون' : 'الطرف المختار مش مورد');
    }
    function chkAcct(code, what, allowed) {
      var a = A[code];
      if (!a) { E.push(what + ': الحساب ' + (code || '(فاضي)') + ' مش موجود'); return null; }
      if (a.archived) E.push(what + ': الحساب ' + a.name + ' مؤرشف');
      if (allowed && allowed.indexOf(a.type) === -1) E.push(what + ': الحساب ' + a.name + ' نوعه مش مناسب');
      return a;
    }
    var t = doc.type;
    var S = sysAccts(book);
    var CONTROL = [S.AR, S.AP];
    if (['invoice', 'credit', 'bill', 'vcredit', 'expense', 'deposit'].indexOf(t) !== -1) {
      if (!Array.isArray(doc.lines) || !doc.lines.length) E.push('لازم سطر واحد عالأقل');
      (doc.lines || []).forEach(function (l, i) {
        var w = 'السطر ' + (i + 1);
        var allowed = (t === 'invoice' || t === 'credit' || t === 'deposit') ? ['income', 'liability', 'equity', 'asset'] : ['expense', 'cogs', 'asset', 'liability', 'equity'];
        var a = chkAcct(l.acct, w, allowed);
        if (a && (CONTROL.indexOf(a.code) !== -1 || a.role === 'vat_in' || a.role === 'vat_out')) E.push(w + ': ما فيك تستخدم حساب نظام (' + a.name + ') بسطر - النظام بيقيدو لحالو');
        if (a && isMoneyAcct(a)) E.push(w + ': ما فيك تحط صندوق/بنك بسطر - للتحويل بين الصناديق استخدم "تحويل"');
        if (t === 'expense' || t === 'deposit') { if (!isNum(l.amount) || num(l.amount) <= 0) E.push(w + ': المبلغ لازم يكون أكبر من صفر'); }
        else {
          if (l.qty !== undefined && l.qty !== '' && (!isNum(l.qty) || num(l.qty) <= 0)) E.push(w + ': الكمية لازم تكون أكبر من صفر');
          if (!isNum(l.price) || num(l.price) < 0) E.push(w + ': السعر غلط');
        }
      });
      if (!isNum(doc.taxRate) || num(doc.taxRate) < 0 || num(doc.taxRate) > 100) E.push('نسبة الضريبة غلط');
      if (num(doc.taxRate) > 0 && !num(book.settings.vatRate)) E.push('الضريبة مش مفعّلة بهالدفتر');
      if (docTotals(doc, book).total <= 0) E.push('مجموع المستند لازم يكون أكبر من صفر');
      if (t === 'expense' || t === 'deposit') { var m = chkAcct(doc.acct, 'حساب الدفع', ['asset']); if (m && !isMoneyAcct(m)) E.push('حساب الدفع لازم يكون صندوق أو بنك'); }
    }
    if (t === 'receipt' || t === 'vpayment') {
      var mm = chkAcct(doc.acct, 'الصندوق/البنك', ['asset']);
      if (mm && !isMoneyAcct(mm)) E.push('لازم تختار صندوق أو بنك');
      if (!isNum(doc.amount) || num(doc.amount) <= 0) E.push('المبلغ لازم يكون أكبر من صفر');
    }
    if (t === 'receipt' || t === 'vpayment' || t === 'credit' || t === 'vcredit') {
      var want = (t === 'receipt' || t === 'credit') ? 'ar' : 'ap';
      var appliedSum = 0, seen = Object.create(null);
      (doc.applies || []).forEach(function (ap, i) {
        var tg = own(book.docs, ap.docId);
        var w = 'التطبيق ' + (i + 1);
        if (seen[ap.docId]) E.push(w + ': نفس الفاتورة مكررة'); seen[ap.docId] = 1;
        if (!tg || tg.void) { E.push(w + ': الفاتورة مش موجودة أو ملغاة'); return; }
        if (itemKind(tg) !== want) E.push(w + ': نوع المستند المطبّق عليه غلط');
        if (tg.partyId !== doc.partyId) E.push(w + ': الفاتورة ' + (tg.no || '') + ' مش لنفس الطرف');
        if ((tg.currency || book.base) !== cur) E.push(w + ': عملة الفاتورة ' + (tg.no || '') + ' غير عملة السند');
        if (!isNum(ap.amount) || num(ap.amount) <= 0) E.push(w + ': المبلغ لازم يكون أكبر من صفر');
        var open = openBalanceOf(book, ap.docId, doc.id);
        if (num(ap.amount) > open + 0.004) E.push(w + ': المبلغ (' + r2(ap.amount) + ') أكبر من المتبقي على ' + (tg.no || 'الفاتورة') + ' (' + open + ')');
        // دفعة مقدمة (سند أقدم من الفاتورة) مسموحة - شائعة بالمقاولات
        appliedSum = r2(appliedSum + num(ap.amount));
      });
      var limit = (t === 'credit' || t === 'vcredit') ? docTotals(doc, book).total : num(doc.amount);
      if (appliedSum > limit + 0.004) E.push('مجموع المطبّق (' + appliedSum + ') أكبر من مبلغ المستند (' + r2(limit) + ')');
    }
    if (!APPLY_TYPES[t] && doc.applies && doc.applies.length) E.push('هالنوع من المستندات ما بيتطبّق على فواتير');
    if (t === 'transfer') {
      var f = chkAcct(doc.from, 'من حساب', ['asset']), to = chkAcct(doc.to, 'لحساب', ['asset']);
      if (f && !isMoneyAcct(f)) E.push('"من" لازم يكون صندوق أو بنك');
      if (to && !isMoneyAcct(to)) E.push('"إلى" لازم يكون صندوق أو بنك');
      if (doc.from && doc.from === doc.to) E.push('ما فيك تحوّل لنفس الحساب');
      if (!isNum(doc.amount) || num(doc.amount) <= 0) E.push('المبلغ لازم يكون أكبر من صفر');
    }
    if (t === 'journal') {
      if (!Array.isArray(doc.lines) || doc.lines.length < 2) E.push('القيد لازم يكون فيه سطرين عالأقل');
      if (cur !== book.base) E.push('قيد اليومية بعملة الدفتر الأساسية بس (' + book.base + ')');
      var dr = 0, cr = 0;
      (doc.lines || []).forEach(function (l, i) {
        var w = 'السطر ' + (i + 1);
        var a = chkAcct(l.acct, w);
        var d = num(l.dr), c = num(l.cr);
        if ((l.dr !== '' && l.dr !== undefined && !isNum(l.dr)) || (l.cr !== '' && l.cr !== undefined && !isNum(l.cr))) E.push(w + ': المبلغ مش رقم');
        if (d < 0 || c < 0) E.push(w + ': ما في مبالغ سالبة - استخدم الجهة التانية');
        if (d && c) E.push(w + ': يا مدين يا دائن، مش التنين');
        if (!d && !c) E.push(w + ': السطر فاضي');
        if (a && (a.code === S.AR || a.code === S.AP)) {
          var pp = Object.prototype.hasOwnProperty.call(book.parties, l.party) ? book.parties[l.party] : null;
          if (!pp) E.push(w + ': حساب ' + a.name + ' لازم معه ' + (a.code === S.AR ? 'زبون' : 'مورد'));
          else if (pp.kind !== 'both' && pp.kind !== (a.code === S.AR ? 'customer' : 'vendor')) E.push(w + ': ' + pp.name + ' مش ' + (a.code === S.AR ? 'زبون' : 'مورد'));
        }
        dr = r2(dr + d); cr = r2(cr + c);
      });
      if (dr !== cr) E.push('القيد مش موزون: مدين ' + dr + ' ≠ دائن ' + cr);
      if (doc.openItem) {
        var oi = doc.openItem, ctl = oi.kind === 'ar' ? S.AR : oi.kind === 'ap' ? S.AP : '';
        if (!ctl) E.push('نوع البند المفتوح غلط');
        if (!isNum(oi.amount) || num(oi.amount) <= 0) E.push('مبلغ البند المفتوح غلط');
        if (!own(book.parties, doc.partyId)) E.push('البند المفتوح لازم إلو طرف');
        var lineAmt = 0;
        (doc.lines || []).forEach(function (l) { if (l.acct === ctl && l.party === doc.partyId) lineAmt = r2(lineAmt + (oi.kind === 'ar' ? num(l.dr) - num(l.cr) : num(l.cr) - num(l.dr))); });
        if (num(oi.amount) > lineAmt + 0.004) E.push('مبلغ البند المفتوح أكبر من قيده');
      }
    }
    // الضمانة الأخيرة: القيود الناتجة لازم تكون موزونة وأرقامها سليمة
    if (!E.length) {
      var ps = docPostings(doc, book);
      var D = 0, C = 0, bad = false;
      ps.forEach(function (p) { if (!isFinite(p.dr) || !isFinite(p.cr)) bad = true; D = r2(D + p.dr); C = r2(C + p.cr); if (!A[p.acct]) E.push('قيد على حساب مش موجود: ' + p.acct); });
      if (bad) E.push('قيم غير رقمية بالقيود');
      if (D !== C) E.push('خطأ داخلي: القيود مش موزونة (' + D + ' / ' + C + ')');
      if (!ps.length) E.push('المستند ما بينتج أي قيد');
    }
    return E;
  }

  // ما فيك تلغي فاتورة إذا في سند مطبّق عليها لسا شغّال
  function dependents(book, docId) {
    return Object.keys(book.docs).filter(function (id) {
      var d = book.docs[id];
      return d && !d.void && APPLY_TYPES[d.type] && (d.applies || []).some(function (ap) { return ap.docId === docId; });
    }).map(function (id) { return book.docs[id]; });
  }

  /* ---------------------------------- الدفتر العام ---------------------------------- */
  function ledger(book, opts) {
    opts = opts || {};
    var out = [], idx = applyIndex(book);
    Object.keys(book.docs).forEach(function (id) {
      var d = book.docs[id];
      if (!d || d.void) return;
      if (opts.from && d.date < opts.from) return;
      if (opts.to && d.date > opts.to) return;
      var seen = Object.create(null);
      // مفتاح ثابت للمطابقة البنكية: المستند + الحساب + ترتيب السطر على هالحساب (ما بيتغيّر لو انضاف سطر لحساب تاني)
      docPostings(d, book, idx).forEach(function (p) { var n = seen[p.acct] = (seen[p.acct] || 0) + 1; p.key = d.id + ':' + p.acct + ':' + n; out.push(p); });
    });
    out.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : (a.docId < b.docId ? -1 : a.docId > b.docId ? 1 : 0); });
    return out;
  }
  function balances(book, opts) {
    var A = acctMap(book), bal = Object.create(null);
    (book.accounts || []).forEach(function (a) { bal[a.code] = { code: a.code, name: a.name, type: a.type, role: a.role, dr: 0, cr: 0, net: 0 }; });
    ledger(book, opts).forEach(function (p) {
      if (opts && opts.project && p.project !== opts.project) return;
      var b = bal[p.acct]; if (!b) { var a = A[p.acct] || { name: p.acct, type: 'expense' }; b = bal[p.acct] = { code: p.acct, name: a.name, type: a.type, dr: 0, cr: 0, net: 0 }; }
      b.dr = r2(b.dr + p.dr); b.cr = r2(b.cr + p.cr);
    });
    Object.keys(bal).forEach(function (k) { var b = bal[k]; b.net = debitNormal(b.type) ? r2(b.dr - b.cr) : r2(b.cr - b.dr); });
    return bal;
  }

  /* ---------------------------------- التقارير ---------------------------------- */
  function trialBalance(book, opts) {
    var bal = balances(book, opts);
    var rows = Object.keys(bal).map(function (k) { return bal[k]; }).filter(function (b) { return b.dr || b.cr; })
      .sort(function (a, b) { return a.code < b.code ? -1 : 1; })
      .map(function (b) { var d = r2(b.dr - b.cr); return { code: b.code, name: b.name, type: b.type, debit: d > 0 ? d : 0, credit: d < 0 ? -d : 0 }; });
    var td = r2(rows.reduce(function (s, r) { return s + r.debit; }, 0)), tc = r2(rows.reduce(function (s, r) { return s + r.credit; }, 0));
    return { rows: rows, totalDebit: td, totalCredit: tc, balanced: td === tc };
  }
  function profitLoss(book, opts) {
    var bal = balances(book, opts);
    var g = { income: [], cogs: [], expense: [] };
    Object.keys(bal).forEach(function (k) { var b = bal[k]; if (g[b.type] && (b.dr || b.cr)) g[b.type].push({ code: b.code, name: b.name, amount: b.net }); });
    Object.keys(g).forEach(function (k) { g[k].sort(function (a, b) { return a.code < b.code ? -1 : 1; }); });
    var inc = r2(g.income.reduce(function (s, x) { return s + x.amount; }, 0));
    var cogs = r2(g.cogs.reduce(function (s, x) { return s + x.amount; }, 0));
    var exp = r2(g.expense.reduce(function (s, x) { return s + x.amount; }, 0));
    return { income: g.income, cogs: g.cogs, expense: g.expense, totalIncome: inc, totalCogs: cogs, grossProfit: r2(inc - cogs), totalExpense: exp, netProfit: r2(inc - cogs - exp) };
  }
  function balanceSheet(book, asOf) {
    var bal = balances(book, { to: asOf });
    var S = sysAccts(book);
    var g = { asset: [], liability: [], equity: [] };
    var earnings = 0;
    Object.keys(bal).forEach(function (k) {
      var b = bal[k];
      if (b.type === 'income') earnings = r2(earnings + b.net);
      else if (b.type === 'cogs' || b.type === 'expense') earnings = r2(earnings - b.net);
      else if (g[b.type] && (b.dr || b.cr)) g[b.type].push({ code: b.code, name: b.name, amount: b.net });
    });
    g.equity.push({ code: '', name: 'صافي الربح المتراكم (غير مقفل)', amount: earnings, computed: true });
    var ta = r2(g.asset.reduce(function (s, x) { return s + x.amount; }, 0));
    var tl = r2(g.liability.reduce(function (s, x) { return s + x.amount; }, 0));
    var te = r2(g.equity.reduce(function (s, x) { return s + x.amount; }, 0));
    return { assets: g.asset, liabilities: g.liability, equity: g.equity, totalAssets: ta, totalLiabilities: tl, totalEquity: te, balanced: ta === r2(tl + te), retainedAcct: S.RETAINED };
  }
  function accountLedger(book, code, opts) {
    opts = opts || {};
    var A = acctMap(book), a = A[code];
    var dn = a ? debitNormal(a.type) : true;
    var open = 0, rows = [], run = 0;
    ledger(book, {}).forEach(function (p) {
      if (p.acct !== code) return;
      if (opts.party && p.party !== opts.party) return;
      if (opts.project && p.project !== opts.project) return;
      var delta = dn ? r2(p.dr - p.cr) : r2(p.cr - p.dr);
      if (opts.from && p.date < opts.from) { open = r2(open + delta); return; }
      if (opts.to && p.date > opts.to) return;
      rows.push(p);
    });
    run = open;
    rows = rows.map(function (p) { run = r2(run + (dn ? p.dr - p.cr : p.cr - p.dr)); var o = {}; for (var k in p) o[k] = p[k]; o.balance = run; return o; });
    return { opening: open, rows: rows, closing: run };
  }
  // كشف حساب زبون/مورد (بعملة الدفتر)
  function partyStatement(book, partyId, opts) {
    var p = own(book.parties, partyId);
    var S = sysAccts(book);
    var code = p && p.kind === 'vendor' ? S.AP : S.AR;
    var r = accountLedger(book, code, { party: partyId, from: opts && opts.from, to: opts && opts.to });
    if (p && p.kind === 'both') {
      // زبون ومورد بنفس الوقت: منعرض التنين
      var r2_ = accountLedger(book, S.AP, { party: partyId, from: opts && opts.from, to: opts && opts.to });
      return { ar: r, ap: r2_ };
    }
    return p && p.kind === 'vendor' ? { ap: r } : { ar: r };
  }
  // الفواتير المفتوحة (بعملة الفاتورة) + الأعمار
  function openItems(book, kind, asOf) {
    var want = kind === 'ap' ? 'ap' : 'ar';
    var today = asOf || new Date().toISOString().slice(0, 10);
    var out = [], am = appliedMap(book, asOf);
    Object.keys(book.docs).forEach(function (id) {
      var d = book.docs[id];
      if (!d || d.void || itemKind(d) !== want) return;
      if (asOf && d.date > asOf) return;
      var total = itemTotal(d, book);
      var used = am[id] || 0;
      var open = r2(total - used);
      if (open <= 0.004) return;
      var due = d.due || (d.openItem && d.openItem.due) || d.date;
      var days = Math.floor((Date.parse(today) - Date.parse(due)) / 86400000);
      var bucket = days <= 0 ? 'current' : days <= 30 ? 'd30' : days <= 60 ? 'd60' : days <= 90 ? 'd90' : 'd90p';
      var fx = docFx(d, book);
      out.push({ id: d.id, no: d.no, date: d.date, due: due, partyId: d.partyId, project: d.project || '', currency: d.currency || book.base, total: total, paid: used, open: open, openBase: r2(toBase(total, fx) - toBase(used, fx)), days: days, bucket: bucket });
    });
    out.sort(function (a, b) { return a.due < b.due ? -1 : 1; });
    return out;
  }
  function aging(book, kind, asOf) {
    var items = openItems(book, kind, asOf);
    var by = Object.create(null);
    items.forEach(function (it) {
      var r = by[it.partyId] || (by[it.partyId] = { partyId: it.partyId, current: 0, d30: 0, d60: 0, d90: 0, d90p: 0, total: 0 });
      r[it.bucket] = r2(r[it.bucket] + it.openBase); r.total = r2(r.total + it.openBase);
    });
    // متل QuickBooks: الدفعات المقدّمة / الأرصدة غير المطبّقة بتطلع بعمود "credit" (بالسالب)،
    // فمجموع التقرير دايمًا = رصيد حساب الذمم بالدفتر
    var S = sysAccts(book), ctl = kind === 'ar' ? S.AR : S.AP, led = Object.create(null);
    ledger(book, { to: asOf }).forEach(function (p) {
      if (p.acct !== ctl) return;
      var k = p.party || '';
      led[k] = r2((led[k] || 0) + (kind === 'ar' ? p.dr - p.cr : p.cr - p.dr));
    });
    Object.keys(by).forEach(function (k) { by[k].credit = 0; });
    Object.keys(led).forEach(function (k) {
      var r = by[k] || (by[k] = { partyId: k, current: 0, d30: 0, d60: 0, d90: 0, d90p: 0, total: 0, credit: 0 });
      var diff = r2(led[k] - r.total);
      if (Math.abs(diff) > 0.004) { r.credit = diff; r.total = r2(r.total + diff); }
    });
    var rows = Object.keys(by).map(function (k) { return by[k]; }).filter(function (r) { return Math.abs(r.total) > 0.004 || Math.abs(r.credit) > 0.004 || r.current || r.d30 || r.d60 || r.d90 || r.d90p; }).sort(function (a, b) { return b.total - a.total; });
    var tot = { current: 0, d30: 0, d60: 0, d90: 0, d90p: 0, credit: 0, total: 0 };
    rows.forEach(function (r) { Object.keys(tot).forEach(function (k) { tot[k] = r2(tot[k] + r[k]); }); });
    return { rows: rows, totals: tot, items: items };
  }
  // ربح كل مشروع (عقد): إيرادات - تكاليف مباشرة - مصاريف محمّلة على المشروع
  function projectProfit(book, opts) {
    var A = acctMap(book), by = Object.create(null);
    ledger(book, opts).forEach(function (p) {
      if (!p.project) return;
      var a = A[p.acct]; if (!a) return;
      if (['income', 'cogs', 'expense'].indexOf(a.type) === -1) return;
      var r = by[p.project] || (by[p.project] = { project: p.project, income: 0, cogs: 0, expense: 0 });
      if (a.type === 'income') r.income = r2(r.income + p.cr - p.dr);
      else r[a.type] = r2(r[a.type] + p.dr - p.cr);
    });
    return Object.keys(by).map(function (k) { var r = by[k]; r.profit = r2(r.income - r.cogs - r.expense); r.margin = r.income ? Math.round(r.profit / r.income * 1000) / 10 : 0; return r; })
      .sort(function (a, b) { return b.income - a.income; });
  }
  // تقرير ضريبة القيمة المضافة (الإمارات)
  // تقرير ضريبة القيمة المضافة (الإمارات) - محسوب من المستندات نفسها (مش من حركة الحساب)،
  // فقيد تسديد الضريبة للهيئة ما بيأثر عليه، والإيداعات غير الإيرادية (رأس مال، قروض) ما بتنعد مبيعات.
  function vatReport(book, opts) {
    var A = acctMap(book);
    var out = { outputVat: 0, inputVat: 0, salesTaxable: 0, salesZero: 0, purchasesTaxable: 0, net: 0 };
    Object.keys(book.docs).forEach(function (id) {
      var d = book.docs[id];
      if (!d || d.void) return;
      if (opts && opts.from && d.date < opts.from) return;
      if (opts && opts.to && d.date > opts.to) return;
      var rate = num(d.taxRate);
      var sg = (d.type === 'credit' || d.type === 'vcredit') ? -1 : 1;
      var sales = d.type === 'invoice' || d.type === 'credit' || d.type === 'deposit';
      var purch = d.type === 'bill' || d.type === 'vcredit' || d.type === 'expense';
      if (!sales && !purch) return;
      // من القيود نفسها (بعد تقريب السنتات) حتى التقرير = حساب الضريبة بالدفتر بالضبط
      docPostings(d, book).forEach(function (p) {
        var amt = r2(Math.abs(p.dr - p.cr));
        if (p.isTax) { if (sales) out.outputVat = r2(out.outputVat + sg * amt); else out.inputVat = r2(out.inputVat + sg * amt); return; }
        if (p.li === undefined) return;
        var l = (d.lines || [])[p.li] || {}, taxed = l.tax && rate > 0, acc = A[l.acct] || {};
        if (sales) {
          if (taxed) out.salesTaxable = r2(out.salesTaxable + sg * amt);
          else if (acc.type === 'income') out.salesZero = r2(out.salesZero + sg * amt);
        } else if (taxed) out.purchasesTaxable = r2(out.purchasesTaxable + sg * amt);
      });
    });
    out.net = r2(out.outputVat - out.inputVat);
    return out;
  }
  function moneyAccounts(book) {
    var bal = balances(book, {});
    return (book.accounts || []).filter(isMoneyAcct).map(function (a) { return { code: a.code, name: a.name, role: a.role, archived: a.archived, balance: bal[a.code] ? bal[a.code].net : 0 }; });
  }
  // مطابقة البنك: أسطر الحساب مع علامة "مطابَق"
  function reconView(book, code, statementBalance) {
    var rec = own(book.recon, code) || {};
    var lines = ledger(book, {}).filter(function (p) { return p.acct === code; });
    var cleared = 0, uncl = [], changed = [], map = Object.create(null);
    lines.forEach(function (p) {
      var amt = r2(p.dr - p.cr), m = rec[p.key];
      if (!m) { uncl.push(p); return; }
      var parts = String(m).split('|'), markedAmt = parts.length > 1 ? r2(parts[1]) : null;
      // العلامة محفوظة مع المبلغ وقت المطابقة: لو المبلغ تغيّر بعدها ما منعدّها مطابقة
      if (markedAmt !== null && markedAmt !== amt) { changed.push(p); uncl.push(p); return; }
      map[p.key] = parts[0]; cleared = r2(cleared + amt);
    });
    var bookBal = r2(lines.reduce(function (s, p) { return s + p.dr - p.cr; }, 0));
    return { lines: lines, clearedMap: map, clearedBalance: cleared, bookBalance: bookBal, uncleared: uncl, changed: changed, difference: isNum(statementBalance) ? r2(num(statementBalance) - cleared) : null };
  }

  /* --------------------------- فحص سلامة الدفتر كامل ---------------------------
     بيستخدمه السيرفر بعد كل حفظ، والصيانة. أي مشكلة هون = خط أحمر. */
  function integrity(book) {
    var problems = [];
    var A = acctMap(book);
    var tb = trialBalance(book, {});
    if (!tb.balanced) problems.push('ميزان المراجعة مش موزون: ' + tb.totalDebit + ' / ' + tb.totalCredit);
    var bs = balanceSheet(book);
    if (!bs.balanced) problems.push('الميزانية مش متوازنة: أصول ' + bs.totalAssets + ' ≠ خصوم ' + bs.totalLiabilities + ' + حقوق ' + bs.totalEquity);
    var seenNo = Object.create(null), idx = applyIndex(book);
    Object.keys(book.docs).forEach(function (id) {
      var d = book.docs[id];
      if (!d) return;
      if (d.id !== id) problems.push('مستند رقمه الداخلي غلط: ' + id);
      if (d.no) { if (seenNo[d.no]) problems.push('رقم مستند مكرر: ' + d.no); seenNo[d.no] = 1; }
      if (d.void) return;
      var ps = docPostings(d, book, idx);
      var D = 0, C = 0;
      ps.forEach(function (p) { D = r2(D + p.dr); C = r2(C + p.cr); if (!A[p.acct]) problems.push((d.no || id) + ': حساب مش موجود ' + p.acct); });
      if (D !== C) problems.push((d.no || id) + ': قيوده مش موزونة');
      if (!APPLY_TYPES[d.type] && d.applies && d.applies.length) problems.push((d.no || id) + ': فيه تطبيق على فواتير وهو مش سند');
      if (APPLY_TYPES[d.type]) (d.applies || []).forEach(function (ap) {
        var tg = own(book.docs, ap.docId);
        if (!tg) { problems.push((d.no || id) + ': مطبّق على مستند مش موجود'); return; }
        if (tg.void) problems.push((d.no || id) + ': مطبّق على ' + (tg.no || '') + ' وهي ملغاة');
        var want = (d.type === 'receipt' || d.type === 'credit') ? 'ar' : 'ap';
        if (itemKind(tg) !== want) problems.push((d.no || id) + ': مطبّق على مستند من نوع غلط');
        if (tg.partyId !== d.partyId) problems.push((d.no || id) + ': مطبّق على ' + (tg.no || '') + ' وهي لطرف تاني');
        if ((tg.currency || book.base) !== (d.currency || book.base)) problems.push((d.no || id) + ': مطبّق على ' + (tg.no || '') + ' بعملة تانية');
        if (ap.fx !== undefined && Math.abs(Number(ap.fx) - docFx(tg, book)) > 1e-9) problems.push((d.no || id) + ': سعر صرف ' + (tg.no || '') + ' تغيّر بعد ما انطبق عليها');
      });
    });
    var am = appliedMap(book);
    Object.keys(book.docs).forEach(function (id) {
      var d = book.docs[id]; if (!d || d.void || !itemKind(d)) return;
      if (r2(itemTotal(d, book) - (am[id] || 0)) < -0.004) problems.push((d.no || id) + ': مدفوع أكتر من قيمته');
    });
    // رصيد الذمم = مجموع أرصدة الفواتير المفتوحة (بعملة الدفتر) - الدفعات المقدمة
    return problems;
  }

  /* --------------------------- أدوات للواجهة --------------------------- */
  function nextNo(book, type, date) {
    var def = DOC_TYPES[type];
    var y = (date || '').slice(0, 4) || String(new Date().getFullYear());
    var key = type + '-' + y;
    var n = (book.seq[key] || 0) + 1;
    return { key: key, n: n, no: (BOOKS[book.book] ? BOOKS[book.book].prefix : '') + def.prefix + '-' + y + '-' + String(n).padStart(4, '0') };
  }
  function fmt(n, cur) {
    var v = r2(n);
    var s = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return (v < 0 ? '-' : '') + s + (cur ? ' ' + (CURRENCY_LABEL[cur] || cur) : '');
  }

  return {
    VERSION: VERSION, BOOKS: BOOKS, CURRENCY_LABEL: CURRENCY_LABEL, TYPES: TYPES, TYPE_LABEL: TYPE_LABEL, DOC_TYPES: DOC_TYPES, SYS: SYS,
    r2: r2, num: num, isDate: isDate, debitNormal: debitNormal,
    defaultChart: defaultChart, newBook: newBook, acctMap: acctMap, sysAccts: sysAccts, isMoneyAcct: isMoneyAcct,
    docFx: docFx, docTotals: docTotals, itemKind: itemKind, itemTotal: itemTotal, APPLY_TYPES: APPLY_TYPES, appliedMap: appliedMap, applyIndex: applyIndex, docPostings: docPostings, validateDoc: validateDoc, openBalanceOf: openBalanceOf, dependents: dependents,
    ledger: ledger, balances: balances, trialBalance: trialBalance, profitLoss: profitLoss, balanceSheet: balanceSheet,
    accountLedger: accountLedger, partyStatement: partyStatement, openItems: openItems, aging: aging, projectProfit: projectProfit,
    vatReport: vatReport, moneyAccounts: moneyAccounts, reconView: reconView, integrity: integrity, nextNo: nextNo, fmt: fmt,
  };
});
