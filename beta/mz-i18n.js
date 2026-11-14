/* =====================================================================================
   🌐 لغة الواجهة (2026-11-14) - طلب حمدي: "بدي ضيف موظف محاسب... تكون نسخة السيستم للمحاسب بالانكليزي"
   و"بشكل عام يكون فيه خيار لاختيار اللغة".
   - اللغة: اختيار هالجهاز (زر EN/ع) ← وإلا لغة المستخدم من السيرفر (الأدمن بيحددها بصفحة المستخدمين) ← وإلا عربي.
   - الترجمة بتصير عالشاشة بس (نصوص، أزرار، placeholders، رسائل التنبيه). البيانات نفسها (أسماء الزبائن،
     البيان، المبالغ) ما بتتغيّر ولا بتنحفظ مترجمة، وخانات الإدخال ما بتنلمس.
   - الأوراق الرسمية يلي بتنطبع (فواتير، سندات) بتضل متل ما هي (مأشّرة بـ data-no-i18n).
   - كل صفحة بتضيف قاموسها: MZ_I18N.add({ 'نص عربي': 'English' }).
   ===================================================================================== */
(function (root) {
  'use strict';
  if (root.MZ_I18N) return;
  var KEY = 'mz-lang', UKEY = 'mz-lang-user';
  function lsGet(k) { try { return root.localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { if (v == null) root.localStorage.removeItem(k); else root.localStorage.setItem(k, v); } catch (e) {} }
  // رابط فيه ?lang=en أو #lang=en (مثلاً رابط المحاسب) بيثبّت اللغة على هالجهاز
  try { var m = /[?#&]lang=(en|ar)\b/.exec(root.location.search + root.location.hash); if (m) lsSet(KEY, m[1]); } catch (e) {}
  function pick() { var l = lsGet(KEY) || lsGet(UKEY) || 'ar'; return l === 'en' ? 'en' : 'ar'; }
  var lang = pick();
  var dict = Object.create(null), phrases = [];
  var RUN = /[ء-يً-ْٱ-ۓ](?:[ء-يً-ْٱ-ۓـ ،؟]*[ء-يً-ْٱ-ۓ])?/g;
  var HAS_AR = /[ء-ي]/;
  function norm(s) { return String(s).replace(/\s+/g, ' ').trim(); }

  function add(map, phraseMap) {
    Object.keys(map || {}).forEach(function (k) { dict[norm(k)] = map[k]; });
    Object.keys(phraseMap || {}).forEach(function (k) { phrases.push([k, phraseMap[k]]); });
    phrases.sort(function (a, b) { return b[0].length - a[0].length; });
    if (lang === 'en' && started) translateTree(root.document.body);
  }
  function tr(text) {
    if (lang !== 'en' || text == null) return text;
    var s = String(text);
    if (!HAS_AR.test(s)) return s;
    var whole = norm(s);
    if (dict[whole] != null) return s.match(/^\s*/)[0] + dict[whole] + s.match(/\s*$/)[0];
    for (var i = 0; i < phrases.length; i++) if (s.indexOf(phrases[i][0]) !== -1) s = s.split(phrases[i][0]).join(phrases[i][1]);
    return s.replace(RUN, function (r) { var k = norm(r); return dict[k] != null ? dict[k] : greedy(k); });
  }
  // نص مركّب من كذا قطعة (مثلاً "إعدادات" + "فرع سوريا"): منطابق أطول تسلسل كلمات موجود بالقاموس
  function greedy(k) {
    var w = k.split(' '), out = [], i = 0, hit = false;
    while (i < w.length) {
      var j = w.length, found = null;
      for (; j > i; j--) { var p = w.slice(i, j).join(' '); if (dict[p] != null) { found = dict[p]; break; } }
      if (found != null) { out.push(found); i = j; hit = true; } else { out.push(w[i]); i++; }
    }
    return hit ? out.join(' ') : k;
  }

  // ---- ترجمة الصفحة ----
  var started = false, busy = false;
  var ATTRS = ['placeholder', 'title', 'aria-label', 'data-label'];
  function skip(el) {
    for (var e = el; e && e.nodeType === 1; e = e.parentNode) {
      if (e.hasAttribute && e.hasAttribute('data-no-i18n')) return true;
      var t = e.tagName; if (t === 'SCRIPT' || t === 'STYLE' || t === 'TEXTAREA' || t === 'CODE') return true;
      if (e.isContentEditable) return true;
    }
    return false;
  }
  function doText(n) { var v = n.nodeValue; if (!v || !HAS_AR.test(v) || skip(n.parentNode)) return; var t = tr(v); if (t !== v) n.nodeValue = t; }
  function doEl(el) {
    if (skip(el)) return;
    ATTRS.forEach(function (a) { var v = el.getAttribute && el.getAttribute(a); if (v && HAS_AR.test(v)) { var t = tr(v); if (t !== v) el.setAttribute(a, t); } });
    if (el.tagName === 'INPUT' && /^(button|submit|reset)$/i.test(el.type) && HAS_AR.test(el.value)) el.value = tr(el.value);
    if (el.tagName === 'OPTION' && HAS_AR.test(el.textContent || '')) { /* النص بيترجم كنص عادي؛ القيمة value ما بتنلمس */ }
  }
  function translateTree(node) {
    if (!node || lang !== 'en') return;
    busy = true;
    try {
      if (node.nodeType === 3) { doText(node); return; }
      if (node.nodeType !== 1 && node.nodeType !== 9 && node.nodeType !== 11) return;
      if (node.nodeType === 1) doEl(node);
      var w = root.document.createTreeWalker(node, 5 /* elements + text */, null), n;
      while ((n = w.nextNode())) { if (n.nodeType === 3) doText(n); else doEl(n); }
    } finally { busy = false; }
  }
  function start() {
    if (started || lang !== 'en') return; started = true;
    var d = root.document;
    d.documentElement.setAttribute('lang', 'en'); d.documentElement.setAttribute('dir', 'ltr');
    d.documentElement.classList.add('mz-en');
    if (d.title) d.title = tr(d.title);
    translateTree(d.body);
    new root.MutationObserver(function (muts) {
      if (busy) return;
      muts.forEach(function (m) {
        if (m.type === 'characterData') doText(m.target);
        else if (m.type === 'attributes') { if (m.target.nodeType === 1) doEl(m.target); }
        else m.addedNodes.forEach(function (x) { translateTree(x); });
      });
    }).observe(d.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS.concat(['value']) });
    // رسائل التنبيه والتأكيد
    var A = root.alert, C = root.confirm, P = root.prompt;
    root.alert = function (m) { return A.call(root, tr(m)); };
    root.confirm = function (m) { return C.call(root, tr(m)); };
    root.prompt = function (m, v) { return P.call(root, tr(m), v); };
  }

  // ---- زر اللغة ----
  function setLang(l) { lsSet(KEY, l === 'en' ? 'en' : 'ar'); root.location.reload(); }
  function toggleHtml() {
    return '<button type="button" class="mz-lang-btn" data-no-i18n onclick="MZ_I18N.setLang(\'' + (lang === 'en' ? 'ar' : 'en') + '\')" title="' + (lang === 'en' ? 'عربي' : 'English') + '">' + (lang === 'en' ? 'ع' : 'EN') + '</button>';
  }
  function mountToggle() {
    var d = root.document; if (d.getElementById('mzLangBtnWrap')) return;
    var css = d.createElement('style');
    css.textContent = '.mz-lang-btn{font:700 12px/1 system-ui,sans-serif;padding:6px 9px;border-radius:8px;border:1px solid rgba(0,0,0,.18);background:#fff;color:#0d4a6b;cursor:pointer}' +
      '#mzLangBtnWrap{position:fixed;bottom:12px;z-index:99990}html[dir=rtl] #mzLangBtnWrap{left:12px}html[dir=ltr] #mzLangBtnWrap{right:12px}@media print{#mzLangBtnWrap,.mz-lang-btn{display:none!important}}';
    d.head.appendChild(css);
    var slot = d.getElementById('mzLangSlot');
    if (slot) { slot.innerHTML = toggleHtml(); return; }
    var w = d.createElement('div'); w.id = 'mzLangBtnWrap'; w.setAttribute('data-no-i18n', ''); w.innerHTML = toggleHtml(); d.body.appendChild(w);
  }
  // لغة المستخدم من السيرفر (بعد تسجيل الدخول): إذا الجهاز ما اختار لغة بإيده، منمشي على لغة المستخدم
  function applyUser(l) {
    if (l !== 'en' && l !== 'ar') return;
    var prev = lsGet(UKEY); lsSet(UKEY, l);
    if (!lsGet(KEY) && l !== lang && prev !== l) root.location.reload();
  }

  root.MZ_I18N = { lang: function () { return lang; }, t: tr, add: add, setLang: setLang, applyUser: applyUser, toggleHtml: toggleHtml, _translateTree: translateTree };
  function boot() { start(); mountToggle(); }
  if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', boot); else boot();
})(window);
