/* فحص PDF المسودة الحقيقي: quote-render.js (من مستودع السيرفر) بيفتح أداة العروض المحلية بمتصفح مخفي ويطبع.
   تشغيل: node render_pdf.js <مسار السيرفر> <رابط الأداة المحلي> <ملف الإخراج> */
'use strict';
const path = require('path'), fs = require('fs');
const [SERVER_DIR, TOOL_URL, OUT] = process.argv.slice(2);
const { createQuoteRenderer } = require(path.join(SERVER_DIR, 'quote-render.js'));
const THREE_STUB = process.env.THREE_STUB || '';
const r = createQuoteRenderer({ playwright: require('playwright'), toolUrl: TOOL_URL, serverOrigin: 'https://merzona-server-production.up.railway.app', log: { error: (...a) => console.error(...a) },
  routeExtra: (route, u) => (/^https?:\/\/127\.0\.0\.1/.test(u) ? route.continue() : (/fonts\.googleapis|fonts\.gstatic|cdnjs|jsdelivr|unpkg/.test(u) ? route.continue() : route.abort())) });
const draft = { id: 'x', by: 'المالك', branch: 'syria', currency: 'usd', client: 'أبو سمير', phone: '0944000111', project: 'فيلا المزة', location: 'دمشق', notes: '',
  items: [{ name: 'Handrail (Hidden Glass)', w: 12000, h: 1000, qty: 1, price: 95 }, { name: 'Aluminum Door with Glass', w: 2000, h: 1000, qty: 2, price: 150 }, { name: 'Glass Curtain wall', w: 3000, h: 2500, qty: 1, price: '' }] };
r.render(draft).then((x) => { fs.writeFileSync(OUT, x.pdf); console.log('INFO ' + JSON.stringify(x.info)); process.exit(0); }).catch((e) => { console.log('FAIL ' + (e && e.stack || e)); process.exit(1); });
