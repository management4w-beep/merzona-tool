/* 📴 2026-11-22: صفحة الكشف بالموقع بتفتح بلا نت.
   بس لصفحة survey.html (ونطاقها survey بس)، وبس لملفات الصفحة نفسها. أي طلب تاني (السيرفر، باقي السيستم) ما منلمسه.
   دايماً منجيب من النت أول (أحدث نسخة)، والمحفوظ بس إذا ما في نت. */
'use strict';
const CACHE = 'mz-survey-v1';
const MINE = /\/(survey\.html|company\.js|mz-i18n\.js|i18n-en-[a-z]+\.js|version\.json)$/;
self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  let u; try { u = new URL(req.url); } catch (_) { return; }
  if (u.origin !== self.location.origin || !MINE.test(u.pathname)) return;
  e.respondWith(fetch(req).then((r) => {
    if (r && r.ok) { const c = r.clone(); caches.open(CACHE).then((cache) => cache.put(u.origin + u.pathname, c)).catch(() => {}); }
    return r;
  }).catch(() => caches.open(CACHE).then((cache) => cache.match(u.origin + u.pathname)).then((hit) => hit || Response.error())));
});
