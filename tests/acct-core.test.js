/* اختبارات قلب المحاسبة - شغّل: node tests/acct-core.test.js */
const C = require('../acct-core.js');
let pass = 0, fail = 0;
function eq(a, b, msg){ const ok = JSON.stringify(a) === JSON.stringify(b); if(ok) pass++; else { fail++; console.log('✗', msg, '\n   got:', JSON.stringify(a), '\n   want:', JSON.stringify(b)); } }
function ok(c, msg){ if(c) pass++; else { fail++; console.log('✗', msg); } }
let idc = 0;
function add(book, doc){
  doc.id = doc.id || ('d' + (++idc));
  if(doc.taxRate === undefined) doc.taxRate = ['invoice','credit','bill','vcredit','expense','deposit'].includes(doc.type) ? C.num(book.settings.vatRate) : 0;
  const errs = C.validateDoc(doc, book);
  if(errs.length) return errs;
  const n = C.nextNo(book, doc.type, doc.date); book.seq[n.key] = n.n; doc.no = n.no;
  book.docs[doc.id] = doc; return [];
}
function sane(book, label){
  const p = C.integrity(book); ok(!p.length, label + ' integrity: ' + p.join(' | '));
  const tb = C.trialBalance(book); ok(tb.balanced, label + ' TB balanced');
  const bs = C.balanceSheet(book); ok(bs.balanced, label + ' BS balanced ' + bs.totalAssets + ' vs ' + (bs.totalLiabilities + bs.totalEquity));
  // صافي الربح بالميزانية = صافي ربح قائمة الدخل
  const pl = C.profitLoss(book); const e = bs.equity.find(x=>x.computed); eq(e.amount, pl.netProfit, label + ' BS earnings = P&L');
}

/* ========== r2 ========== */
eq(C.r2(1.005), 1.01, 'r2 1.005'); eq(C.r2(-1.005), -1.01, 'r2 -1.005'); eq(C.r2(0.1+0.2), 0.3, 'r2 .1+.2'); eq(C.r2('x'), 0, 'r2 NaN'); eq(C.r2(2.675), 2.68, 'r2 2.675');
ok(C.isDate('2026-02-28') && !C.isDate('2026-02-30') && !C.isDate('2026-2-3'), 'isDate');

/* ========== UAE: فاتورة بضريبة + قبض جزئي + كامل ========== */
const U = C.newBook('uae');
U.parties.c1 = { id:'c1', kind:'customer', name:'Ahmad' };
U.parties.c2 = { id:'c2', kind:'customer', name:'Khalid' };
U.parties.v1 = { id:'v1', kind:'vendor', name:'Gulf Aluminium' };
eq(add(U, { id:'i1', type:'invoice', date:'2026-10-01', due:'2026-10-31', partyId:'c1', project:'Q-260120', lines:[{desc:'شبابيك', qty:10, price:1000, acct:'4000', tax:true},{desc:'تركيب', qty:1, price:500.5, acct:'4000', tax:true}] }), [], 'invoice ok');
const t1 = C.docTotals(U.docs.i1, U); eq(t1, { subtotal:10500.5, tax:525.03, total:11025.53 }, 'invoice totals with VAT');
const ps1 = C.docPostings(U.docs.i1, U);
eq(ps1.filter(p=>p.acct==='1100')[0].dr, 11025.53, 'AR debit'); eq(ps1.filter(p=>p.acct==='2200')[0].cr, 525.03, 'VAT out');
sane(U, 'after invoice');
eq(add(U, { type:'receipt', date:'2026-10-05', partyId:'c1', acct:'1010', amount:5000, applies:[{docId:'i1', amount:5000}] }), [], 'receipt partial');
eq(C.openBalanceOf(U, 'i1'), 6025.53, 'open after partial');
let e = add(U, { type:'receipt', date:'2026-10-06', partyId:'c1', acct:'1010', amount:7000, applies:[{docId:'i1', amount:7000}] });
ok(e.some(x=>x.includes('أكبر من المتبقي')), 'overpay blocked');
e = add(U, { type:'receipt', date:'2026-10-06', partyId:'c2', acct:'1010', amount:100, applies:[{docId:'i1', amount:100}] });
ok(e.some(x=>x.includes('مش لنفس الطرف')), 'other party blocked');
e = add(U, { id:'adv1', type:'receipt', date:'2026-09-01', partyId:'c1', acct:'1010', amount:100, applies:[{docId:'i1', amount:100}] });
ok(e.length === 0, 'advance receipt dated before invoice is allowed (review #5)'); U.docs.adv1.void = true;
e = add(U, { type:'receipt', date:'2026-10-06', partyId:'c1', acct:'4000', amount:100, applies:[] });
ok(e.length > 0, 'receipt into income acct blocked');
eq(add(U, { type:'receipt', date:'2026-10-20', partyId:'c1', acct:'1000', amount:6025.53, applies:[{docId:'i1', amount:6025.53}] }), [], 'receipt rest');
eq(C.openBalanceOf(U, 'i1'), 0, 'invoice closed');
eq(C.openItems(U, 'ar').length, 0, 'no open items');
eq(C.balances(U)['1100'].net, 0, 'AR zero');
sane(U, 'after receipts');

/* فاتورة مورد بضريبة + دفع + مصروف + ربح المشروع */
eq(add(U, { id:'b1', type:'bill', date:'2026-10-02', partyId:'v1', project:'Q-260120', lines:[{desc:'بروفايلات', qty:1, price:4000, acct:'5000', tax:true}] }), [], 'bill');
eq(C.docTotals(U.docs.b1, U).total, 4200, 'bill total');
eq(add(U, { type:'vpayment', date:'2026-10-03', partyId:'v1', acct:'1010', amount:4200, applies:[{docId:'b1', amount:4200}] }), [], 'vpayment');
eq(add(U, { type:'expense', date:'2026-10-04', acct:'1000', payee:'ADNOC', project:'Q-260120', lines:[{desc:'بنزين', amount:200, acct:'6300', tax:true}] }), [], 'expense');
e = add(U, { type:'expense', date:'2026-10-04', acct:'1000', lines:[{desc:'x', amount:200, acct:'1010'}] });
ok(e.some(x=>x.includes('صندوق/بنك بسطر')), 'expense to bank line blocked');
e = add(U, { type:'expense', date:'2026-10-04', acct:'4000', lines:[{desc:'x', amount:200, acct:'6300'}] });
ok(e.length>0, 'expense paid from income blocked');
const pp = C.projectProfit(U).find(r=>r.project==='Q-260120');
eq([pp.income, pp.cogs, pp.expense, pp.profit], [10500.5, 4000, 200, 6300.5], 'project profit');
const v = C.vatReport(U, {});
eq([v.outputVat, v.inputVat, v.net], [525.03, 210, 315.03], 'VAT report');
sane(U, 'after purchases');

/* إشعار دائن + إلغاء */
eq(add(U, { id:'i2', type:'invoice', date:'2026-10-10', partyId:'c2', lines:[{desc:'باب', qty:1, price:2000, acct:'4000', tax:true}] }), [], 'invoice 2');
eq(add(U, { id:'cn1', type:'credit', date:'2026-10-11', partyId:'c2', lines:[{desc:'خصم', qty:1, price:200, acct:'4000', tax:true}], applies:[{docId:'i2', amount:210}] }), [], 'credit note');
eq(C.openBalanceOf(U, 'i2'), 1890, 'invoice after credit');
e = add(U, { type:'credit', date:'2026-10-11', partyId:'c2', lines:[{desc:'خصم', qty:1, price:100, acct:'4000', tax:true}], applies:[{docId:'i2', amount:500}] });
ok(e.some(x=>x.includes('مجموع المطبّق')), 'credit apply > credit total blocked');
sane(U, 'after credit');
ok(C.dependents(U, 'i2').length === 1, 'dependents found');
U.docs.cn1.void = true; eq(C.openBalanceOf(U, 'i2'), 2100, 'void credit restores');
sane(U, 'after void');

/* قيد يومية: موزون / غير موزون / ذمم بدون طرف */
eq(add(U, { type:'journal', date:'2026-01-01', lines:[{acct:'1000', dr:10000},{acct:'3000', cr:10000}] }), [], 'opening capital');
e = add(U, { type:'journal', date:'2026-01-01', lines:[{acct:'1000', dr:100},{acct:'3000', cr:90}] });
ok(e.some(x=>x.includes('مش موزون')), 'unbalanced journal blocked');
e = add(U, { type:'journal', date:'2026-01-01', lines:[{acct:'1100', dr:100},{acct:'3900', cr:100}] });
ok(e.some(x=>x.includes('لازم معه')), 'AR without party blocked');
e = add(U, { type:'journal', date:'2026-01-01', lines:[{acct:'1000', dr:-5},{acct:'3000', cr:-5}] });
ok(e.some(x=>x.includes('سالبة')), 'negative blocked');
e = add(U, { type:'journal', date:'2026-01-01', lines:[{acct:'1000', dr:'abc'},{acct:'3000', cr:5}] });
ok(e.length>0, 'NaN blocked');
/* تحويل */
eq(add(U, { type:'transfer', date:'2026-10-21', from:'1000', to:'1010', amount:1000 }), [], 'transfer');
e = add(U, { type:'transfer', date:'2026-10-21', from:'1000', to:'1000', amount:1000 }); ok(e.length>0, 'self transfer blocked');
sane(U, 'after journals');
/* قفل الفترة */
U.settings.lockDate = '2026-10-31';
e = add(U, { type:'transfer', date:'2026-10-21', from:'1000', to:'1010', amount:1 }); ok(e.some(x=>x.includes('مقفلة')), 'lock date blocks');
U.settings.lockDate = '';
/* الأرقام التسلسلية */
const nos = Object.values(U.docs).map(d=>d.no); ok(new Set(nos).size === nos.length, 'unique numbers'); ok(nos.includes('INV-2026-0001') && nos.includes('INV-2026-0002'), 'invoice numbering');

/* ========== سوريا: دولار + ليرة بسعري صرف ========== */
const Sy = C.newBook('syria');
Sy.parties.s1 = { id:'s1', kind:'customer', name:'Tarek' };
Sy.parties.sv = { id:'sv', kind:'vendor', name:'Glass Co' };
e = add(Sy, { type:'invoice', date:'2026-10-01', partyId:'s1', lines:[{desc:'x', qty:1, price:100, acct:'4000', tax:true}], taxRate:5 });
ok(e.some(x=>x.includes('الضريبة مش مفعّلة')), 'no VAT in syria');
eq(add(Sy, { id:'si1', type:'invoice', date:'2026-10-01', partyId:'s1', currency:'SYP', fx:13000, lines:[{desc:'شبابيك', qty:1, price:1300000, acct:'4000'}] }), [], 'SYP invoice');
eq(C.docPostings(Sy.docs.si1, Sy).find(p=>p.acct==='1100').dr, 100, 'SYP→USD base');
// قبض بالليرة بسعر 14000 (الليرة نزلت) → خسارة فرق صرف
eq(add(Sy, { type:'receipt', date:'2026-10-15', partyId:'s1', acct:'1000', currency:'SYP', fx:14000, amount:1300000, applies:[{docId:'si1', amount:1300000}] }), [], 'SYP receipt other rate');
const bS = C.balances(Sy);
eq(bS['1100'].net, 0, 'AR closed exactly despite FX'); eq(bS['7900'].net, 7.14, 'FX loss 100-92.86');
e = add(Sy, { type:'receipt', date:'2026-10-15', partyId:'s1', acct:'1000', currency:'USD', amount:10, applies:[{docId:'si1', amount:1}] });
ok(e.some(x=>x.includes('عملة الفاتورة')), 'currency mismatch blocked');
e = add(Sy, { type:'receipt', date:'2026-10-15', partyId:'s1', acct:'1000', currency:'SYP', amount:10 });
ok(e.some(x=>x.includes('سعر الصرف')), 'missing fx blocked');
e = add(Sy, { type:'receipt', date:'2026-10-15', partyId:'s1', acct:'1000', currency:'AED', amount:10 });
ok(e.some(x=>x.includes('مش مسموحة')), 'AED not allowed in syria');
// فاتورة مورد بالليرة + دفعة جزئية بسعر تاني + إشعار مدين
eq(add(Sy, { id:'sb1', type:'bill', date:'2026-10-02', partyId:'sv', currency:'SYP', fx:13000, lines:[{desc:'زجاج', qty:2, price:650000, acct:'5010'}] }), [], 'SYP bill');
eq(add(Sy, { type:'vpayment', date:'2026-10-10', partyId:'sv', acct:'1000', currency:'SYP', fx:12500, amount:650000, applies:[{docId:'sb1', amount:650000}] }), [], 'SYP partial pay (gain? no: lira rose → loss)');
eq(add(Sy, { type:'vcredit', date:'2026-10-12', partyId:'sv', currency:'SYP', fx:13500, lines:[{desc:'مرتجع', qty:1, price:650000, acct:'5010'}], applies:[{docId:'sb1', amount:650000}] }), [], 'SYP vendor credit other rate');
eq(C.openBalanceOf(Sy, 'sb1'), 0, 'bill closed');
eq(C.balances(Sy)['2000'].net, 0, 'AP exactly zero after FX');
sane(Sy, 'syria');
// دفعة مقدمة بدون تطبيق
eq(add(Sy, { type:'receipt', date:'2026-10-20', partyId:'s1', acct:'1000', amount:50 }), [], 'advance receipt');
eq(C.balances(Sy)['1100'].net, -50, 'AR negative = advance');
sane(Sy, 'syria advance');

/* بنود افتتاحية منقولة (فواتير قديمة من QuickBooks) */
const O = C.newBook('uae'); O.parties.q = { id:'q', kind:'customer', name:'Old' }; O.parties.qv = { id:'qv', kind:'vendor', name:'OldV' };
eq(add(O, { id:'oi1', type:'journal', date:'2026-11-07', partyId:'q', openItem:{ kind:'ar', amount:1000, ref:'INV-77' }, lines:[{acct:'1100', dr:1000, party:'q'},{acct:'3900', cr:1000}] }), [], 'opening AR item');
eq(add(O, { id:'oi2', type:'journal', date:'2026-11-07', partyId:'qv', openItem:{ kind:'ap', amount:400 }, lines:[{acct:'3900', dr:400},{acct:'2000', cr:400, party:'qv'}] }), [], 'opening AP item');
e = add(O, { type:'journal', date:'2026-11-07', partyId:'q', openItem:{ kind:'ar', amount:5000 }, lines:[{acct:'1100', dr:1000, party:'q'},{acct:'3900', cr:1000}] });
ok(e.some(x=>x.includes('أكبر من قيده')), 'open item > line blocked');
eq(C.openItems(O, 'ar').length, 1, 'opening item listed');
eq(add(O, { type:'receipt', date:'2026-11-08', partyId:'q', acct:'1010', amount:600, applies:[{docId:'oi1', amount:600}] }), [], 'receipt on opening item');
eq(C.openBalanceOf(O, 'oi1'), 400, 'opening item partial');
e = add(O, { type:'receipt', date:'2026-11-08', partyId:'q', acct:'1010', amount:600, applies:[{docId:'oi1', amount:600}] });
ok(e.some(x=>x.includes('أكبر من المتبقي')), 'opening item overpay blocked');
eq(add(O, { type:'vpayment', date:'2026-11-08', partyId:'qv', acct:'1010', amount:400, applies:[{docId:'oi2', amount:400}] }), [], 'pay opening AP');
eq(C.balances(O)['2000'].net, 0, 'AP cleared'); eq(C.balances(O)['1100'].net, 400, 'AR left');
sane(O, 'opening items');

/* أعمار الذمم */
const U2 = C.newBook('uae'); U2.parties.c = { id:'c', kind:'customer', name:'X' };
add(U2, { id:'a1', type:'invoice', date:'2026-07-01', due:'2026-07-15', partyId:'c', lines:[{desc:'x', qty:1, price:1000, acct:'4000'}], taxRate:0 });
add(U2, { id:'a2', type:'invoice', date:'2026-10-25', due:'2026-11-30', partyId:'c', lines:[{desc:'x', qty:1, price:500, acct:'4000'}], taxRate:0 });
const ag = C.aging(U2, 'ar', '2026-11-07');
eq([ag.totals.current, ag.totals.d90p, ag.totals.total], [500, 1000, 1500], 'aging buckets');
eq(C.balances(U2)['1100'].net, ag.totals.total, 'AR = aging total');

/* كشف حساب */
const st = C.partyStatement(U, 'c1');
eq(st.ar.closing, 0, 'statement closing'); ok(st.ar.rows.length === 3, 'statement rows');
/* سجل الحساب مع رصيد افتتاحي */
const al = C.accountLedger(U, '1010', { from: '2026-10-04' });
eq(al.opening, -4200, 'ledger opening = vpayment on 10-03 only'); ok(al.rows.length >= 1, 'ledger rows');
/* مطابقة البنك */
const rv = C.reconView(U, '1010', 0); ok(rv.lines.length > 0 && rv.difference !== null, 'recon view');

/* اختبار عشوائي ضخم: 3000 مستند عشوائي - الدفتر لازم يضل موزون دايمًا */
function rnd(n){ return Math.floor(Math.random()*n); }
for(const bid of ['uae','syria']){
  const B = C.newBook(bid);
  for(let i=0;i<8;i++){ B.parties['c'+i] = { id:'c'+i, kind:'customer', name:'c'+i }; B.parties['v'+i] = { id:'v'+i, kind:'vendor', name:'v'+i }; }
  const cur = bid==='uae' ? ['AED','USD'] : ['USD','SYP'];
  const fxr = c => c===B.base ? 1 : (c==='USD' ? 3.6725 : 12000 + rnd(3000));
  let okN = 0, rej = 0;
  for(let i=0;i<1200;i++){
    const day = '2026-' + String(1+rnd(12)).padStart(2,'0') + '-' + String(1+rnd(28)).padStart(2,'0');
    const c = cur[rnd(2)], fx = fxr(c);
    const kinds = ['invoice','receipt','bill','vpayment','expense','deposit','transfer','journal','credit','vcredit'];
    const k = kinds[rnd(kinds.length)];
    const price = Math.round(Math.random()*100000)/100 + 0.01;
    let d;
    const tax = bid==='uae' && Math.random()<0.7;
    if(k==='invoice') d = { type:k, date:day, partyId:'c'+rnd(8), currency:c, fx, lines:[{desc:'x', qty:1+rnd(5), price, acct:'4000', tax},{desc:'y', qty:1, price:price/3, acct:'4100', tax:false}] };
    else if(k==='bill') d = { type:k, date:day, partyId:'v'+rnd(8), currency:c, fx, lines:[{desc:'x', qty:1+rnd(3), price, acct:['5000','5010','6100'][rnd(3)], tax}] };
    else if(k==='receipt' || k==='credit' || k==='vpayment' || k==='vcredit'){
      const cust = (k==='receipt'||k==='credit');
      const items = C.openItems(B, cust ? 'ar' : 'ap').filter(x=>x.currency===c && x.date <= day);
      const it = items[rnd(items.length||1)];
      const pid = it ? it.partyId : (cust ? 'c':'v')+rnd(8);
      const amt = it ? C.r2(Math.min(it.open, Math.random()*it.open*1.2 + 0.01)) : price;
      if(k==='receipt'||k==='vpayment') d = { type:k, date:day, partyId:pid, acct:['1000','1010'][rnd(2)], currency:c, fx, amount: C.r2(amt + (Math.random()<0.2 ? 10 : 0)), applies: it ? [{docId:it.id, amount:amt}] : [] };
      else d = { type:k, date:day, partyId:pid, currency:c, fx, lines:[{desc:'c', qty:1, price: amt, acct: cust ? '4000' : '5000'}], applies: it ? [{docId:it.id, amount: Math.min(amt, it.open)}] : [] };
    }
    else if(k==='expense') d = { type:k, date:day, acct:['1000','1010'][rnd(2)], currency:c, fx, lines:[{desc:'e', amount:price, acct:'6900', tax}] };
    else if(k==='deposit') d = { type:k, date:day, acct:'1000', currency:c, fx, lines:[{desc:'e', amount:price, acct:'4100'}] };
    else if(k==='transfer') d = { type:k, date:day, from:'1000', to:'1010', currency:c, fx, amount:price };
    else d = { type:k, date:day, lines:[{acct:'6100', dr:price},{acct:'1000', cr:price}] };
    const r = add(B, d); if(r.length) rej++; else okN++;
    if(i % 500 === 0 && Object.keys(B.docs).length){ const ids = Object.keys(B.docs); const vid = ids[rnd(ids.length)]; if(!C.dependents(B, vid).length) B.docs[vid].void = true; }
  }
  sane(B, 'random ' + bid + ' (' + okN + ' ok, ' + rej + ' rejected)');
  const ag2 = C.aging(B, 'ar'); const arNet = C.balances(B)['1100'].net;
  // الذمم = الفواتير المفتوحة - الدفعات/الإشعارات غير المطبّقة (بعملة الدفتر)
  let unapplied = 0; /* + بنود افتتاحية = صفر هون */
  Object.values(B.docs).forEach(d=>{ if(d.void) return; if(d.type==='receipt'){ const ap = (d.applies||[]).reduce((s,a)=>s+a.amount,0); unapplied += C.r2((d.amount - ap)/C.docFx(d,B)); } if(d.type==='credit'){ const ap = (d.applies||[]).reduce((s,a)=>s+a.amount,0); unapplied += C.r2((C.docTotals(d,B).total - ap)/C.docFx(d,B)); } });
  const openOnly = C.r2(ag2.totals.total - ag2.totals.credit);
  ok(Math.abs(C.r2(openOnly - unapplied) - arNet) < 0.05 * Object.keys(B.docs).length / 100 + 0.05, 'random ' + bid + ' AR subledger ties: ' + arNet + ' vs ' + C.r2(openOnly - unapplied));
  eq(ag2.totals.total, arNet, 'random ' + bid + ' AR aging total = control exactly');
  console.log('random', bid, 'docs', Object.keys(B.docs).length, 'ok', okN, 'rejected', rej);
}

// aging reconciles to control accounts (advances / overpayments show as unapplied credit, like QuickBooks)
for (const bid of ['uae','syria']) {
  const B = C.newBook(bid);
  B.parties.c = { id:'c', kind:'customer', name:'C' }; B.parties.v = { id:'v', kind:'vendor', name:'V' };
  const S = C.sysAccts(B), cash = C.moneyAccounts(B)[0].code;
  B.docs.i1 = { id:'i1', type:'invoice', date:'2026-10-01', due:'2026-10-01', partyId:'c', taxRate:0, lines:[{ desc:'x', qty:1, price:1000, acct:'4000' }], no:'I1' };
  B.docs.r1 = { id:'r1', type:'receipt', date:'2026-10-05', partyId:'c', acct:cash, amount:1500, applies:[{ docId:'i1', amount:1000 }], no:'R1' };
  B.docs.j1 = { id:'j1', type:'journal', date:'2026-10-06', lines:[{ acct:S.AP, dr:40, party:'v' }, { acct:cash, cr:40 }], no:'J1' };
  const bal = C.balances(B, {});
  const ar = C.aging(B, 'ar', '2026-11-08'), ap = C.aging(B, 'ap', '2026-11-08');
  eq(ar.totals.total, bal[S.AR].net, bid + ' AR aging total = AR control');
  eq(ar.totals.credit, -500, bid + ' AR unapplied advance shown');
  eq(ap.totals.total, bal[S.AP].net, bid + ' AP aging total = AP control');
  eq(ap.totals.credit, -40, bid + ' AP debit balance shown');
  eq(C.integrity(B), [], bid + ' aging book integrity');
}

console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
