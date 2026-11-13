/* =====================================================================================
   🏢 إعدادات الشركة (2026-11-11) - طلب حمدي: "عندي شركة تانية بدي اعطيهم اشتراك فبدي ضيف اللوغو وتفاصيلهم".
   كل الصفحات بتقرا اسم الشركة ولوغوها وعنوانها وأرقامها وحسابها البنكي من هون.
   القيم الافتراضية = ميرزونا متل ما هي بالضبط. إذا الإعدادات المحفوظة عالسيرفر نفس الافتراضي (ميرزونا)
   ما بيتغيّر ولا حرف بالصفحات. التبديل بيصير بس بنسخة شركة تانية (إعداداتها محفوظة على سيرفرها).
   ===================================================================================== */
(function (root) {
  'use strict';
  var DEFAULT = {
    nameEn: 'Merzona',
    nameAr: 'ميرزونا',
    fullNameEn: 'Merzona for Aluminum & Glass Works',
    taglineEn: 'Aluminum & Glass Works',
    logo: '', // فاضي = اللوغو المبني بالصفحات (لوغو ميرزونا)
    email: 'Info@Merzona.com',
    website: 'www.Merzona.ae',
    phone: '+971508471158',
    cities: 'دمشق · دبي · الشارقة',
    colors: { accent: '#0f88cd', text: '#333333' },
    branches: {
      uae: {
        enabled: true, labelEn: 'United Arab Emirates', labelAr: 'الإمارات', flag: '🇦🇪', refPrefix: 'M', currency: 'AED',
        addressHtml: 'United Arab Emirates / Sharjah, Abu Dhabi &nbsp; Tel: +971508471158 &nbsp; e: Info@Merzona.com &nbsp; Web: www.Merzona.ae',
        hasVat: true, trn: '104252457700003',
        jurisdictionEn: 'Sharjah courts shall have exclusive jurisdiction over any dispute arising from this contract.',
        jurisdictionAr: 'الاختصاص القضائي لحل أي نزاع ناتج عن هذا العقد ينعقد لمحاكم إمارة الشارقة.',
        bank: { nameEn: 'Mashreq Bank', nameAr: 'بنك المشرق', account: '19101374683', accountName: 'Merzona', iban: 'AE060330000019101374683' },
      },
      syria: {
        enabled: true, labelEn: 'Damascus, Syria', labelAr: 'دمشق، سوريا', flag: '🇸🇾', refPrefix: 'S', currency: 'USD',
        addressHtml: 'Damascus, Syria &nbsp; — &nbsp; دمشق، سوريا',
        hasVat: false, trn: '',
        jurisdictionEn: 'Damascus courts shall have exclusive jurisdiction over any dispute arising from this contract.',
        jurisdictionAr: 'الاختصاص القضائي لحل أي نزاع ناتج عن هذا العقد ينعقد لمحاكم مدينة دمشق.',
        bank: null,
      },
    },
  };
  var KEY = 'mz-company-profile-v1';
  var isObj = function (v) { return v && typeof v === 'object' && !Array.isArray(v); };
  function merge(base, over) {
    if (!isObj(over)) return JSON.parse(JSON.stringify(base));
    var out = {};
    Object.keys(base).forEach(function (k) {
      var b = base[k], o = over[k];
      if (o === undefined) out[k] = JSON.parse(JSON.stringify(b === undefined ? null : b));
      else if (isObj(b) && isObj(o)) out[k] = merge(b, o);
      else if (b === null && isObj(o)) out[k] = JSON.parse(JSON.stringify(o));
      else out[k] = o;
    });
    return out;
  }
  var profile = null, isDefault = true;
  function set(p) {
    profile = merge(DEFAULT, p || {});
    isDefault = JSON.stringify(profile) === JSON.stringify(merge(DEFAULT, {}));
    return profile;
  }
  function get() {
    if (!profile) {
      var c = null; try { c = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) {}
      // نسخة شركة تانية (رابطها لحاله): إعداداتها مبنية بالصفحة، فأول ظهور بيكون باسمها ولوغوها مباشرة
      var boot = null; try { boot = root.MZ_COMPANY_BOOT || null; } catch (e) {}
      var p = c && c.profile; if (boot && !(p && p.nameEn)) p = boot;
      if (boot && p && !p.logo && boot.logo) p = Object.assign({}, p, { logo: boot.logo });
      set(p);
    }
    return profile;
  }
  function serverUrl() {
    try { if (root.MZ_COMPANY_SERVER) return root.MZ_COMPANY_SERVER; } catch (e) {}
    return 'https://merzona-server-production.up.railway.app';
  }
  // من السيرفر (بدون تسجيل دخول - صفحة التوقيع للزبون بتحتاجها). الصفحة بتشتغل فوراً من النسخة المخزّنة.
  function load() {
    if (typeof fetch !== 'function') return Promise.resolve(get());
    return fetch(serverUrl() + '/company/public', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (!j) return get();
      var before = JSON.stringify(get());
      set(j.profile || {});
      try { localStorage.setItem(KEY, JSON.stringify({ profile: j.profile || null, rev: j.rev || 0, at: Date.now() })); } catch (e) {}
      if (JSON.stringify(profile) !== before) { try { root.dispatchEvent(new CustomEvent('mz-company', { detail: profile })); } catch (e) {} applyAll(); }
      return profile;
    }).catch(function () { return get(); });
  }

  /* ---------- التبديل بالصفحات ---------- */
  // جدول "نص ميرزونا الأصلي ← نص الشركة" (الأطول أول حتى ما يتكسر نص جوّا نص)
  function replacements() {
    var p = get(), d = DEFAULT, list = [];
    var add = function (from, to) { if (from && to != null && String(from) !== String(to)) list.push([String(from), String(to)]); };
    ['uae', 'syria'].forEach(function (b) {
      var pb = p.branches[b] || {}, db = d.branches[b];
      add(db.addressHtml.replace(/&nbsp;/g, ' '), String(pb.addressHtml || '').replace(/&nbsp;/g, ' '));
      add(db.jurisdictionEn, pb.jurisdictionEn); add(db.jurisdictionAr, pb.jurisdictionAr);
      if (db.trn) add(db.trn, pb.trn || '');
      if (db.bank && pb.bank) { add(db.bank.iban, pb.bank.iban); add(db.bank.account, pb.bank.account); add(db.bank.nameEn, pb.bank.nameEn); add(db.bank.nameAr, pb.bank.nameAr); }
      if (db.bank && pb.bank) { add('Account Name: ' + db.bank.accountName, 'Account Name: ' + (pb.bank.accountName || p.nameEn)); add('اسم الحساب: ' + db.bank.accountName, 'اسم الحساب: ' + (pb.bank.accountName || p.nameEn)); }
    });
    add('United Arab Emirates / Sharjah, Abu Dhabi', p.branches.uae.labelEn && p.branches.uae.addressHtml ? String(p.branches.uae.addressHtml).split('&nbsp;')[0].trim() : '');
    add(d.fullNameEn, p.fullNameEn); add(d.cities, p.cities);
    add(d.email, p.email); add('info@merzona.com', p.email); add(d.website, p.website); add('www.merzona.ae', p.website);
    add(d.phone, p.phone);
    add('شركة ميرزونا (Merzona)', 'شركة ' + p.nameAr + (p.nameEn && p.nameEn !== p.nameAr ? ' (' + p.nameEn + ')' : ''));
    add('MERZONA', String(p.nameEn || '').toUpperCase()); add('Merzona', p.nameEn); add('ميرزونا', p.nameAr); add('مرزونا', p.nameAr);
    list.sort(function (a, b) { return b[0].length - a[0].length; });
    return list;
  }
  function brand(s) {
    get(); if (isDefault || s == null) return s;
    var out = String(s);
    replacements().forEach(function (r) { if (out.indexOf(r[0]) >= 0) out = out.split(r[0]).join(r[1]); });
    return out;
  }
  var SKIP = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, CODE: 1 };
  // كل نص بيتبدّل مرة وحدة بس (لو اسم الشركة الجديد فيه كلمة Merzona ما بيصير تبديل ورا تبديل)
  var done = typeof WeakMap !== 'undefined' ? new WeakMap() : null;
  function fixText(t, fix) {
    var v = t.nodeValue; if (!v || !/\S/.test(v)) return;
    if (done && done.get(t) === v) return;
    var n = fix(v); if (n !== v) t.nodeValue = n;
    if (done) done.set(t, n);
  }
  function applyNode(node, withValues) {
    if (!node) return;
    var reps = replacements(); if (!reps.length) return;
    var fix = function (s) { var o = s; for (var i = 0; i < reps.length; i++) if (o.indexOf(reps[i][0]) >= 0) o = o.split(reps[i][0]).join(reps[i][1]); return o; };
    if (node.nodeType === 3) { fixText(node, fix); return; }
    if (node.nodeType !== 1 || SKIP[node.tagName]) return;
    var walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, { acceptNode: function (t) { var p = t.parentNode; return p && SKIP[p.tagName] ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; } });
    var t; while ((t = walker.nextNode())) fixText(t, fix);
    var els = node.querySelectorAll ? [node].concat([].slice.call(node.querySelectorAll('img,[title],[placeholder],textarea,input'))) : [];
    var logo = get().logo;
    els.forEach(function (el) {
      if (el.tagName === 'IMG') {
        var alt = el.getAttribute('alt') || '';
        if (/Merzona logo/i.test(alt) || el.hasAttribute('data-co-logo')) {
          if (logo && el.getAttribute('src') !== logo) {
            el.src = logo;
            // لوغو عريض (أفقي): منكبّر العرض شوي حتى ما يطلع صغير مكان لوغو ميرزونا
            el.onload = function () { try { var w = parseFloat(el.style.width) || 0; if (w && el.naturalWidth / el.naturalHeight > 2.4 && !el.__mzW) { el.__mzW = 1; el.style.width = Math.round(w * 1.35) + 'px'; } } catch (e) {} };
          }
          el.setAttribute('alt', get().nameEn + ' logo'); el.setAttribute('data-co-logo', '1');
        }
      }
      if (el.title) { var tt = fix(el.title); if (tt !== el.title) el.title = tt; }
      if (el.placeholder) { var pp = fix(el.placeholder); if (pp !== el.placeholder) el.placeholder = pp; }
      if (withValues && !el.__mzCo && (el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && /^(text|)$/i.test(el.type || '')))) { el.__mzCo = 1; var vv = el.value; if (vv) { var vn = fix(vv); if (vn !== vv) el.value = vn; } }
    });
  }
  // ألوان عرض السعر والطباعة (اللون الأساسي ولون النص)
  function hexA(h, a) { var n = parseInt(String(h).slice(1), 16); return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')'; }
  function applyTheme() {
    try {
      var c = get().colors || {}, d = DEFAULT.colors, r = document.documentElement;
      if (!r) return;
      if (c.accent && c.accent.toLowerCase() !== d.accent) { r.style.setProperty('--aux1', c.accent); r.style.setProperty('--aux1-tint', hexA(c.accent, 0.14)); r.style.setProperty('--aux1-mid', hexA(c.accent, 0.30)); }
      if (c.text && c.text.toLowerCase() !== d.text) r.style.setProperty('--main', c.text);
    } catch (e) {}
  }
  var observer = null;
  function applyAll() {
    get();
    applyTheme();
    if (isDefault || typeof document === 'undefined' || !document.documentElement) return;
    try { document.title = fix1(document.title); } catch (e) {}
    // كل الصفحة (مش بس body): شاشة القفل قبل الدخول بتنضاف برّا body
    applyNode(document.documentElement, true);
    if (!observer && typeof MutationObserver !== 'undefined') {
      observer = new MutationObserver(function (muts) {
        if (isDefault) return;
        muts.forEach(function (m) {
          if (m.type === 'characterData') applyNode(m.target, false);
          else m.addedNodes.forEach(function (n) { applyNode(n, false); });
        });
      });
      observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
    }
  }
  function fix1(s) { return brand(s); }

  /* 💵 شريط سعر صرف الدولار (2026-11-13) - طلب حمدي: "يكون مكتوب سعر الصرف فوق دائما ويكون ابديتيت كل يوم".
     السعر من السيرفر (/fx/usd-syp) يلي بيجيبه من sp-today.com مرة باليوم. صفحات الزبون (التوقيع والكتالوج) ما فيها الشريط. */
  var FX_KEY = 'mz-fx-usd-syp-v1';
  function fxNum(n) { return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function fxWhen(iso) {
    try { var d = new Date(iso); return d.toLocaleDateString('en-GB', { timeZone: 'Asia/Damascus', day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString('en-GB', { timeZone: 'Asia/Damascus', hour: '2-digit', minute: '2-digit' }); } catch (e) { return ''; }
  }
  function fxPage() {
    try { var p = (location.pathname.split('/').pop() || 'index.html').toLowerCase(); return !/^(sign|catalog|about|privacy)\.html$/.test(p); } catch (e) { return false; }
  }
  function fxRender(r) {
    if (!r || !r.sell || typeof document === 'undefined' || !document.body) return;
    var bar = document.getElementById('mzFxBar');
    if (!bar) {
      if (!document.getElementById('mzFxCss')) {
        var st = document.createElement('style'); st.id = 'mzFxCss';
        st.textContent = '#mzFxBar{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;justify-content:center;padding:4px 10px;font:600 12.5px/1.5 Tajawal,Cairo,system-ui,sans-serif;direction:rtl;background:#0f2336;color:#fff;text-decoration:none;position:relative;z-index:5}' +
          '#mzFxBar b{font-variant-numeric:tabular-nums;color:#9fe0ff}#mzFxBar .o{opacity:.7;font-weight:500}#mzFxBar .up{color:#ff9b9b}#mzFxBar .dn{color:#8be0a4}@media print{#mzFxBar{display:none!important}}';
        (document.head || document.documentElement).appendChild(st);
      }
      bar = document.createElement('a'); bar.id = 'mzFxBar'; bar.href = (r.source && r.source.url) || 'https://sp-today.com/currency/us-dollar'; bar.target = '_blank'; bar.rel = 'noopener';
      bar.title = 'سعر صرف الدولار بالليرة السورية - المصدر sp-today.com (بيتحدّث كل يوم)';
      document.body.insertBefore(bar, document.body.firstChild);
      // بعض الصفحات إلها هامش حوالين الـ body: الشريط بيلغيه ليلزق بأعلى الشاشة وبعرضها كلها
      try {
        var cs = getComputedStyle(document.body), px = function (k) { return parseFloat(cs[k]) || 0; };
        var t = px('marginTop') + px('paddingTop'), l = px('marginLeft') + px('paddingLeft'), rr = px('marginRight') + px('paddingRight');
        bar.style.margin = (-t) + 'px ' + (-rr) + 'px ' + t + 'px ' + (-l) + 'px';
      } catch (e) {}
    }
    var arrow = r.prevSell && r.prevSell !== r.sell ? (r.sell > r.prevSell ? ' <span class="up">▲</span>' : ' <span class="dn">▼</span>') : '';
    bar.innerHTML = '💵 <span>الدولار:</span> <span>شراء <b>' + fxNum(r.buy) + '</b></span> <span>مبيع <b>' + fxNum(r.sell) + '</b>' + arrow + '</span> <span>ل.س جديدة</span>' +
      ' <span class="o">(' + Math.round(r.sell * 100).toLocaleString('en-US') + ' قديمة)</span> <span class="o">· ' + fxWhen(r.fetchedAt || r.at) + ' · sp-today</span>';
  }
  function fxStart() {
    if (!fxPage() || typeof fetch !== 'function') return;
    try { fxRender(JSON.parse(localStorage.getItem(FX_KEY) || 'null')); } catch (e) {}
    var pull = function () {
      fetch(serverUrl() + '/fx/usd-syp').then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
        if (!j || !j.sell) return;
        try { localStorage.setItem(FX_KEY, JSON.stringify(j)); } catch (e) {}
        fxRender(j);
      }).catch(function () {});
    };
    pull(); setInterval(pull, 30 * 60 * 1000);
  }

  function onReady() {
    get(); applyAll(); load(); fxStart();
  }
  var api = { DEFAULT: DEFAULT, get: get, set: set, load: load, brand: brand, applyAll: applyAll, applyNode: applyNode, isDefault: function () { get(); return isDefault; }, _merge: merge, _replacements: replacements, _fxRender: fxRender };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else {
    root.MzCompany = api;
    applyTheme(); // الألوان فوراً (قبل ما تنرسم الصفحة)
    if (typeof document !== 'undefined') {
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', onReady); else onReady();
    }
  }
})(typeof window !== 'undefined' ? window : this);
