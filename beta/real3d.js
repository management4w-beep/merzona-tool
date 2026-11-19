/* =====================================================================================
   ✨ ميرزونا - عرض ثري دي واقعي (2026-11-18)
   طلب حمدي: "الثري دي ماعم يطلع مرندر واقعي ماعم يبين حقيقي... منقدر نوصل فيه بالتطوير لدرجة يصير حقيقي؟"
   - مشهد WebGL حقيقي (three.js r128 المحمّل أصلاً بالصفحة): ألمنيوم بلمعة ومعدن حقيقي، زجاج بيعكس البيئة،
     حواف البروفيلات مشطوفة، جوان أسود، ظلال ناعمة، إضاءة بيئة (انعكاسات) + Tone mapping سينمائي.
   - البند بينحط بحيط حقيقي (لياسة + عتبة رخام للشبابيك / أرضية للأبواب) والسما مبينة من ورا الزجاج.
   - السحّاب: الدرف على سكتين (قدّام/ورا) وبتركب فوق بعض متل الواقع. المفصلي: درفة بإطارها ومسكة.
   - كل شي بيطلع من نفس بيانات المصمم (المقاسات، التقسيمات، سماكات البروفيل) - ما في أي تخمين بالمقاس.
   - إذا الجهاز ما بيدعم WebGL أو صار أي خطأ ← بيضل العرض القديم (الرسمة) متل ما هو.
   ===================================================================================== */
(function(){
'use strict';

const COLORS = {
  black:      { ar:'أسود مطفي',   hex:0x1b1c1f, rough:0.52, metal:0.3, env:0.5 },
  anthracite: { ar:'رمادي فحمي',  hex:0x383c41, rough:0.45, metal:0.45, env:0.6 },
  silver:     { ar:'فضي',         hex:0xaeb3b8, rough:0.3, metal:0.9, env:0.9 },
  white:      { ar:'أبيض',        hex:0xe9e9e6, rough:0.45, metal:0.05, env:0.5 },
  champagne:  { ar:'شامبين',      hex:0xa58e66, rough:0.32, metal:0.85, env:0.85 },
  bronze:     { ar:'برونزي',      hex:0x4a3729, rough:0.4, metal:0.7, env:0.7 },
  wood:       { ar:'خشبي',        hex:0x8a5a35, rough:0.6,  metal:0.05, wood:true }
};
const GLASS = {
  clear:      { ar:'شفاف',     hex:0x9fb7b2, opacity:0.24, rough:0.0, refl:0.16 },
  tinted:     { ar:'فاميه',    hex:0x26343a, opacity:0.7, rough:0.0, refl:0.14 },
  reflective: { ar:'عاكس',     hex:0x3a5060, opacity:0.92, rough:0.0, refl:0.42 },
  frosted:    { ar:'مغبّش',    hex:0xe4e9e8, opacity:0.85, rough:0.5, refl:0.08 }
};

let ST = null; // { renderer, pmrem, env }
function T(){ return window.THREE; }
function supported(){
  const t = T();
  if(!t || typeof t.WebGLRenderer !== 'function' || typeof t.PMREMGenerator !== 'function' || typeof t.ExtrudeGeometry !== 'function') return false;
  try{ const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); }catch(e){ return false; }
}

/* بيئة إضاءة (غرفة استوديو) - مقتبسة من RoomEnvironment تبع three.js / model-viewer (MIT) */
function envScene(){
  const THREE = T();
  const scene = new THREE.Scene();
  const geometry = new THREE.BoxGeometry();
  geometry.deleteAttribute('uv');
  const roomMaterial = new THREE.MeshStandardMaterial({ side: THREE.BackSide });
  const boxMaterial = new THREE.MeshStandardMaterial();
  const mainLight = new THREE.PointLight(0xffffff, 5.0, 28, 2);
  mainLight.position.set(0.418, 16.199, 0.300); scene.add(mainLight);
  const room = new THREE.Mesh(geometry, roomMaterial); room.position.set(-0.757, 13.219, 0.717); room.scale.set(31.713, 28.305, 28.591); scene.add(room);
  [[-10.906,2.009,1.846,-0.195,2.328,7.905,4.651],[-5.607,-0.754,-0.758,0.994,1.970,1.534,3.955],[6.167,0.857,7.803,0.561,3.927,6.285,3.687],
   [-2.017,0.018,6.124,0.333,2.002,4.566,2.064],[2.291,-0.756,-2.621,-0.286,1.546,1.552,1.496],[-2.193,-0.369,-5.547,0.516,3.875,3.487,2.986]].forEach(b=>{
    const m = new THREE.Mesh(geometry, boxMaterial); m.position.set(b[0], b[1], b[2]); m.rotation.set(0, b[3], 0); m.scale.set(b[4], b[5], b[6]); scene.add(m);
  });
  const area = (i)=>{ const m = new THREE.MeshBasicMaterial(); m.color.setScalar(i); return m; };
  [[50,-16.116,14.37,8.208,0.1,2.428,2.739],[50,-16.109,18.021,-8.207,0.1,2.425,2.751],[17,14.904,12.198,-1.832,0.15,4.265,6.331],
   [43,-0.462,8.89,14.520,4.38,5.441,0.088],[20,3.235,11.486,-12.541,2.5,2.0,0.1],[100,0,20,0,1,0.1,1]].forEach(l=>{
    const m = new THREE.Mesh(geometry, area(l[0])); m.position.set(l[1], l[2], l[3]); m.scale.set(l[4], l[5], l[6]); scene.add(m);
  });
  return scene;
}

// بيئة سما حقيقية (للواجهة): سما زرقا → أفق فاتح → أرض، مع شمس - الزجاج والألمنيوم بيعكسوها متل الواقع
function skyEnvScene(){
  const THREE = T();
  const scene = new THREE.Scene();
  const c = document.createElement('canvas'); c.width = 8; c.height = 512;
  const x = c.getContext('2d'), g = x.createLinearGradient(0, 0, 0, 512);
  g.addColorStop(0, '#2f6db3'); g.addColorStop(0.32, '#7fb0df'); g.addColorStop(0.47, '#e8f0f4'); g.addColorStop(0.5, '#c9c2b3'); g.addColorStop(0.56, '#8b8172'); g.addColorStop(1, '#4e463c');
  x.fillStyle = g; x.fillRect(0, 0, 8, 512);
  const t = new THREE.CanvasTexture(c); t.encoding = THREE.sRGBEncoding;
  const sky = new THREE.Mesh(new THREE.SphereGeometry(50, 32, 24), new THREE.MeshBasicMaterial({ map:t, side:THREE.BackSide }));
  sky.material.map.flipY = true;
  scene.add(sky);
  const sunM = new THREE.MeshBasicMaterial(); sunM.color.setScalar(40);
  const sun = new THREE.Mesh(new THREE.SphereGeometry(2.2, 16, 12), sunM); sun.position.set(-22, 28, 26); scene.add(sun);
  // مباني وشجر بعيدين حوالين (بالانعكاس بيبينوا متل صورة حقيقية لشارع)
  const r = rnd(9);
  const facade = (tone)=>{
    const fc = document.createElement('canvas'); fc.width = 64; fc.height = 128; const f = fc.getContext('2d');
    f.fillStyle = tone; f.fillRect(0, 0, 64, 128);
    for(let yy=6; yy<122; yy+=14) for(let xx=5; xx<60; xx+=12){ const v = 40 + Math.floor(r()*60); f.fillStyle = `rgb(${v},${v+8},${v+18})`; f.fillRect(xx, yy, 7, 8); }
    const tx = new THREE.CanvasTexture(fc); tx.encoding = THREE.sRGBEncoding; return new THREE.MeshBasicMaterial({ map:tx });
  };
  const tones = ['#d8cfbf', '#c9bba4', '#e6e1d6', '#b5a58c', '#9c9a95'];
  const fm = tones.map(facade);
  for(let i=0;i<22;i++){
    const a = i/22*Math.PI*2 + r()*0.12, d = 30 + r()*8, h = 6 + r()*16, w = 7 + r()*7;
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, 5), fm[i % fm.length]);
    b.position.set(Math.cos(a)*d, h/2 - 2, Math.sin(a)*d); b.lookAt(0, h/2 - 2, 0); scene.add(b);
  }
  const tm = new THREE.MeshBasicMaterial({ color:0x2f4526 });
  for(let i=0;i<30;i++){
    const a = r()*Math.PI*2, d = 20 + r()*6, rad = 1.5 + r()*2;
    const t = new THREE.Mesh(new THREE.SphereGeometry(rad, 10, 8), tm); t.position.set(Math.cos(a)*d, rad*0.8 + 0.5, Math.sin(a)*d); t.scale.y = 1.3; scene.add(t);
  }
  return scene;
}
function getState(){
  const THREE = T();
  if(ST && ST.renderer) return ST;
  const renderer = new THREE.WebGLRenderer({ antialias:true, preserveDrawingBuffer:true, alpha:false });
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.85;
  renderer.physicallyCorrectLights = false;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromScene(envScene(), 0.04).texture;
  let skyEnv = env; try{ skyEnv = pmrem.fromScene(skyEnvScene(), 0.02).texture; }catch(e){}
  ST = { renderer, pmrem, env, skyEnv };
  return ST;
}

/* ---------- خامات ---------- */
function canvasTex(w, h, draw, repeat){
  const THREE = T();
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.encoding = THREE.sRGBEncoding; t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if(repeat) t.repeat.set(repeat[0], repeat[1]);
  t.anisotropy = 4;
  return t;
}
function rnd(seed){ let s = seed >>> 0; return ()=>{ s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
function plasterTex(){
  return canvasTex(256, 256, (x, w, h)=>{
    x.fillStyle = '#ddd5c7'; x.fillRect(0, 0, w, h);
    const r = rnd(7);
    for(let i=0;i<5200;i++){ const v = 185 + Math.floor(r()*55); x.fillStyle = `rgba(${v},${v-6},${v-16},${0.12 + r()*0.15})`; x.fillRect(r()*w, r()*h, 1 + r()*2.2, 1 + r()*2.2); }
  }, [3, 3]);
}
function marbleTex(){
  return canvasTex(512, 128, (x, w, h)=>{
    x.fillStyle = '#e4ded3'; x.fillRect(0, 0, w, h);
    const r = rnd(11);
    for(let k=0;k<9;k++){
      x.strokeStyle = `rgba(150,140,125,${0.12 + r()*0.18})`; x.lineWidth = 0.6 + r()*1.6; x.beginPath();
      let px = r()*w, py = 0; x.moveTo(px, py);
      while(py < h){ px += (r()-0.5)*40; py += 6 + r()*10; x.lineTo(px, py); }
      x.stroke();
    }
  }, [1, 1]);
}
function tileTex(){
  return canvasTex(512, 512, (x, w, h)=>{
    const r = rnd(3), n = 4, s = w / n;
    for(let i=0;i<n;i++) for(let j=0;j<n;j++){
      const v = 188 + Math.floor(r()*16); x.fillStyle = `rgb(${v},${v-7},${v-16})`; x.fillRect(i*s, j*s, s, s);
      for(let k=0;k<5;k++){ x.strokeStyle = `rgba(160,150,135,${0.08+r()*0.1})`; x.lineWidth = 1; x.beginPath(); x.moveTo(i*s + r()*s, j*s); x.bezierCurveTo(i*s + r()*s, j*s + s*0.4, i*s + r()*s, j*s + s*0.6, i*s + r()*s, j*s + s); x.stroke(); }
    }
    x.strokeStyle = 'rgba(120,112,100,0.55)'; x.lineWidth = 2;
    for(let i=0;i<=n;i++){ x.beginPath(); x.moveTo(i*s, 0); x.lineTo(i*s, h); x.stroke(); x.beginPath(); x.moveTo(0, i*s); x.lineTo(w, i*s); x.stroke(); }
  }, [1, 1]);
}
function woodTex(){
  return canvasTex(128, 512, (x, w, h)=>{
    x.fillStyle = '#8a5a35'; x.fillRect(0, 0, w, h);
    const r = rnd(5);
    for(let i=0;i<60;i++){ x.strokeStyle = `rgba(${60 + r()*40},${35 + r()*25},${18 + r()*15},${0.25 + r()*0.35})`; x.lineWidth = 0.5 + r()*2; const xx = r()*w; x.beginPath(); x.moveTo(xx, 0); x.bezierCurveTo(xx + (r()-0.5)*20, h*0.3, xx + (r()-0.5)*20, h*0.7, xx + (r()-0.5)*14, h); x.stroke(); }
  }, [1, 1]);
}
function skyTex(mode){
  return canvasTex(16, 512, (x, w, h)=>{
    const g = x.createLinearGradient(0, 0, 0, h);
    if(mode === 'studio'){ g.addColorStop(0, '#f4f5f6'); g.addColorStop(1, '#d9dcdf'); }
    else { g.addColorStop(0, '#6f9fd0'); g.addColorStop(0.55, '#b9d4ea'); g.addColorStop(0.78, '#e9eff2'); g.addColorStop(0.8, '#9aa98a'); g.addColorStop(1, '#7b8a6b'); }
    x.fillStyle = g; x.fillRect(0, 0, w, h);
  });
}

// انعكاس الزجاج (متل صور المعماريين): سما فاتحة فوق وبتغمق لتحت + خطوط ضو مايلة ناعمة. منقسوم على كل الفتحة (مش كل لوح لحالو)
function reflTex(mode){
  return canvasTex(512, 512, (x, w, h)=>{
    const g = x.createLinearGradient(0, 0, 0, h);
    if(mode === 'studio'){ g.addColorStop(0, '#ffffff'); g.addColorStop(0.5, '#8a8f94'); g.addColorStop(1, '#2a2d30'); }
    else { g.addColorStop(0, '#b4cde2'); g.addColorStop(0.45, '#6f8ea9'); g.addColorStop(0.66, '#3f5163'); g.addColorStop(0.68, '#2a3326'); g.addColorStop(1, '#101410'); }
    x.fillStyle = g; x.fillRect(0, 0, w, h);
    x.globalCompositeOperation = 'lighter';
    [[0.18, 0.11, 0.35], [0.42, 0.05, 0.2], [0.7, 0.16, 0.28]].forEach(b=>{
      const cx = b[0]*w, bw = b[1]*w;
      const gg = x.createLinearGradient(cx - bw, 0, cx + bw, 0);
      gg.addColorStop(0, 'rgba(255,255,255,0)'); gg.addColorStop(0.5, `rgba(255,255,255,${b[2]})`); gg.addColorStop(1, 'rgba(255,255,255,0)');
      x.save(); x.translate(cx, h/2); x.transform(1, 0, -0.55, 1, 0, 0); x.translate(-cx, -h/2); x.fillStyle = gg; x.fillRect(cx - bw, -h, bw*2, h*3); x.restore();
    });
  });
}
function makeMats(opts){
  const THREE = T();
  const env = opts.bg === 'studio' ? getState().env : getState().skyEnv;
  const c = COLORS[opts.color] || COLORS.black;
  const g = GLASS[opts.glass] || GLASS.clear;
  const alu = new THREE.MeshStandardMaterial({ color:c.hex, roughness:c.rough, metalness:c.metal, envMap:env, envMapIntensity:(c.env == null ? 0.8 : c.env) });
  if(c.wood){ alu.map = woodTex(); alu.color.set(0xffffff); }
  const glass = new THREE.MeshPhysicalMaterial({ color:g.hex, transparent:true, opacity:g.opacity, roughness:g.rough, metalness:g.metal || 0,
    reflectivity:0.3, envMap:env, envMapIntensity:0.5, side:THREE.DoubleSide, depthWrite:false });
  // طبقة انعكاس (بتنضاف فوق الزجاج): الزجاج الحقيقي من برّا بيعكس السما والبنايات والشجر
  const rv = g.refl == null ? 0.3 : g.refl;
  const glassRefl = new THREE.MeshBasicMaterial({ map:reflTex(opts.bg), color:new THREE.Color(rv, rv, rv), transparent:true, blending:THREE.AdditiveBlending, depthWrite:false });
  const glassEdge = new THREE.MeshStandardMaterial({ color:0x6f9c94, transparent:true, opacity:0.55, roughness:0.1, envMap:env });
  const gasket = new THREE.MeshStandardMaterial({ color:0x0d0e10, roughness:0.85, metalness:0, envMap:env, envMapIntensity:0.4 });
  const steel = new THREE.MeshStandardMaterial({ color:0xc9ccd0, roughness:0.22, metalness:1, envMap:env, envMapIntensity:1.3 });
  const plaster = new THREE.MeshStandardMaterial({ map:plasterTex(), roughness:0.95, metalness:0, envMap:env, envMapIntensity:0.18 });
  const marble = new THREE.MeshStandardMaterial({ map:marbleTex(), roughness:0.25, metalness:0, envMap:env, envMapIntensity:0.8 });
  const floor = new THREE.MeshStandardMaterial({ map:tileTex(), roughness:0.75, metalness:0, envMap:env, envMapIntensity:0.2 });
  return { alu, glass, glassRefl, glassEdge, gasket, steel, plaster, marble, floor };
}

/* ---------- هندسة ---------- */
const geoCache = new Map();
function bevelBoxGeo(w, h, d, b){
  const THREE = T();
  w = Math.max(0.004, w); h = Math.max(0.004, h); d = Math.max(0.004, d);
  b = Math.max(0.0004, Math.min(b, w/3, h/3, d/3));
  const key = [w,h,d,b].map(v=>v.toFixed(4)).join('|');
  if(geoCache.has(key)) return geoCache.get(key);
  const s = new THREE.Shape();
  const x0 = -w/2 + b, x1 = w/2 - b, y0 = -h/2 + b, y1 = h/2 - b;
  s.moveTo(x0, y0); s.lineTo(x1, y0); s.lineTo(x1, y1); s.lineTo(x0, y1); s.lineTo(x0, y0);
  const geo = new THREE.ExtrudeGeometry(s, { depth: d - 2*b, bevelEnabled:true, bevelThickness:b, bevelSize:b, bevelSegments:2, curveSegments:1 });
  geo.translate(0, 0, -(d - 2*b)/2);
  geo.computeVertexNormals();
  if(geoCache.size > 600) geoCache.clear();
  geoCache.set(key, geo);
  return geo;
}

function isOpeningSupported(it, H){
  if(!it || !(it.width > 0) || !(it.height > 0) || !it.layout) return false;
  if(H.isHandrail(it) || H.isMirror(it) || H.isShowerDoor(it) || H.isRoom(it) || H.isPergola(it) || H.isGableRoof(it)) return false;
  if(it.archTop) return false;
  return true;
}

// بيبني الشباك/الباب (مجموعة بمركزها تحت-يسار = 0,0، الوجه الخارجي باتجاه +Z)
function buildOpening(it, M, H){
  const THREE = T();
  const W = it.width/1000, Hh = it.height/1000;
  const g = new THREE.Group();
  const door = H.isDoorLike(it), sliding = H.isSlidingType(it);
  const mm = v => Math.max(0, +v || 0) / 1000;
  const ofw = Math.max(0.025, sliding ? mm(it.frameThickness ?? H.DEFAULT_FRAME_THICKNESS) : mm(it.profileThickness || 50));
  const lw  = Math.max(0.03, sliding ? mm(it.leafThickness ?? H.DEFAULT_LEAF_THICKNESS) * 0.62 : ofw * 0.95);
  const D   = sliding ? 0.10 : (door ? 0.075 : 0.065);
  const SD  = sliding ? 0.036 : D * 0.9;
  const mbw = Math.max(0.05, ofw * 1.25); // عرض القاطع (المولّيون)
  const BEV = 0.0022;

  function bar(cx, cy, w, h, d, z, mat, parent){
    const m = new THREE.Mesh(bevelBoxGeo(w, h, d, BEV), mat);
    m.position.set(cx, cy, z || 0); m.castShadow = true; m.receiveShadow = true;
    (parent || g).add(m); return m;
  }
  function frame(x, y, w, h, bw, d, z, parent){
    bw = Math.max(0.012, Math.min(bw, w/2 - 0.004, h/2 - 0.004));
    bar(x + w/2, y + h - bw/2, w, bw, d, z, M.alu, parent);
    bar(x + w/2, y + bw/2, w, bw, d, z, M.alu, parent);
    bar(x + bw/2, y + h/2, bw, h - 2*bw, d, z, M.alu, parent);
    bar(x + w - bw/2, y + h/2, bw, h - 2*bw, d, z, M.alu, parent);
    // جوان أسود رفيع جوّا الإطار
    const gk = 0.006, gd = d * 0.55;
    if(w - 2*bw > 0.03 && h - 2*bw > 0.03){
      bar(x + w/2, y + h - bw - gk/2, w - 2*bw, gk, gd, z, M.gasket, parent);
      bar(x + w/2, y + bw + gk/2, w - 2*bw, gk, gd, z, M.gasket, parent);
      bar(x + bw + gk/2, y + h/2, gk, h - 2*bw - 2*gk, gd, z, M.gasket, parent);
      bar(x + w - bw - gk/2, y + h/2, gk, h - 2*bw - 2*gk, gd, z, M.gasket, parent);
    }
  }
  function glassPane(x, y, w, h, z, parent){
    if(w < 0.01 || h < 0.01) return;
    const t = 0.008;
    const geo = new THREE.BoxGeometry(w, h, t);
    const mats = [M.glassEdge, M.glassEdge, M.glassEdge, M.glassEdge, M.glass, M.glass];
    const m = new THREE.Mesh(geo, mats); m.position.set(x + w/2, y + h/2, z || 0); m.renderOrder = 2;
    (parent || g).add(m);
    const pg = new THREE.PlaneGeometry(w, h);
    { const uv = pg.attributes.uv; for(let i=0;i<uv.count;i++){ uv.setXY(i, (x + uv.getX(i)*w) / W, (y + uv.getY(i)*h) / Hh); } uv.needsUpdate = true; }
    const rf = new THREE.Mesh(pg, M.glassRefl); rf.position.set(x + w/2, y + h/2, (z || 0) + t/2 + 0.0006); rf.renderOrder = 3;
    (parent || g).add(rf);
  }
  function leverHandle(x, y, z, vertical){
    // مسكة شباك: قاعدة + ذراع
    bar(x, y, 0.028, 0.075, 0.012, z + 0.006, M.alu);
    const lever = bar(x, y - (vertical ? 0.045 : 0), vertical ? 0.016 : 0.11, vertical ? 0.1 : 0.016, 0.016, z + 0.026, M.alu);
    if(!vertical) lever.position.x = x + 0.045;
  }
  function pullHandle(x, y, h, zFace, sgn){
    const len = Math.min(0.5, Math.max(0.28, h * 0.3));
    const so = 0.05;
    [len/2 - 0.02, -(len/2 - 0.02)].forEach(dy=>{
      const c = new THREE.Mesh(new THREE.CylinderGeometry(0.009, 0.009, so, 16), M.steel);
      c.rotation.x = Math.PI/2; c.position.set(x, y + dy, zFace + sgn*so/2); c.castShadow = true; g.add(c);
    });
    const r = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.014, len, 24), M.steel);
    r.position.set(x, y, zFace + sgn*(so + 0.004)); r.castShadow = true; g.add(r);
  }
  function lockAt(x, y, zFace, sgn){
    bar(x, y, 0.03, 0.09, 0.008, zFace + sgn*0.004, M.steel);
    const k = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 0.012, 20), M.steel);
    k.rotation.x = Math.PI/2; k.position.set(x, y - 0.02, zFace + sgn*0.012); g.add(k);
  }
  const handleSide = (type)=> !type || type === 'fold' ? null : (type.indexOf('left') !== -1 ? 'right' : (type.indexOf('right') !== -1 ? 'left' : 'right'));

  function leaf(type, x, y, w, h, slideIdx){
    type = type || 'plain';
    if(type === 'plain'){
      glassPane(x, y, w, h, 0);
      // خرزة الزجاج (الكبّاس) من برّا
      const kb = 0.014;
      frame(x, y, w, h, kb, 0.02, D*0.22);
      return;
    }
    if(type.indexOf('louver') === 0){
      frame(x, y, w, h, lw*0.7, SD, 0);
      const ix = x + lw*0.7, iw = w - lw*1.4, iy = y + lw*0.7, ih = h - lw*1.4;
      const step = 0.055;
      for(let yy = iy + step/2; yy < iy + ih - 0.01; yy += step){
        const s = new THREE.Mesh(bevelBoxGeo(iw, 0.05, 0.006, 0.001), M.alu);
        s.position.set(ix + iw/2, yy, 0); s.rotation.x = -0.55; s.castShadow = true; g.add(s);
      }
      return;
    }
    if(/^slide_/.test(type)){
      const z = (slideIdx % 2 === 0 ? 1 : -1) * 0.022;
      frame(x, y, w, h, lw, SD, z);
      glassPane(x + lw, y + lw, w - 2*lw, h - 2*lw, z);
      const side = handleSide(type), hx = side === 'right' ? x + w - lw/2 : x + lw/2;
      // مسكة سحاب رفيعة على طرف الدرفة
      bar(hx, y + Math.min(h*0.5, 1.05), 0.014, Math.min(0.32, h*0.25), 0.012, z + SD/2 + 0.006, M.alu);
      if(door) bar(hx, y + Math.min(h*0.5, 1.05), 0.014, Math.min(0.32, h*0.25), 0.012, z - SD/2 - 0.006, M.alu);
      return;
    }
    // مفصلي / قلّاب / فولد: درفة بإطار خاص فيها
    const z = 0.006;
    frame(x, y, w, h, lw, SD, z);
    glassPane(x + lw, y + lw, w - 2*lw, h - 2*lw, z);
    const side = handleSide(type);
    if(door){
      if(side){
        const hx = side === 'right' ? x + w - Math.max(0.06, lw*0.6) : x + Math.max(0.06, lw*0.6);
        const hy = y + Math.min(h - 0.2, 1.05);
        pullHandle(hx, hy, h, z + SD/2, 1); pullHandle(hx, hy, h, z - SD/2, -1);
        lockAt(hx, hy - 0.32, z + SD/2, 1);
        // مفصلات
        const px = side === 'right' ? x + 0.004 : x + w - 0.004;
        [0.12, 0.5, 0.88].forEach(f=>{ const c = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 0.09, 16), M.alu); c.position.set(px, y + h*f, z + SD/2 + 0.006); c.castShadow = true; g.add(c); });
      }
    } else {
      const zf = z + SD/2;
      if(type === 'tri_up') leverHandle(x + w/2, y + lw/2 + 0.02, zf, false);
      else if(type === 'tri_down') leverHandle(x + w/2, y + h - lw/2 - 0.02, zf, false);
      else if(side) leverHandle(side === 'right' ? x + w - lw/2 : x + lw/2, y + h/2, zf, true);
    }
  }

  const inner = { x0: ofw, y0: ofw, x1: W - ofw, y1: Hh - ofw };
  const EPS = 1e-6;
  let slideCounter = 0;
  function walk(node, x, y, w, h, eL, eR, eB, eT){
    if(!node) return;
    if(node.kind === 'leaf'){
      // حواف داخلية: نص القاطع، أو تداخل للسحّاب
      const isSlide = /^slide_/.test(node.type || '');
      const ov = isSlide ? 0.018 : 0;
      const lx0 = eL === 'out' ? inner.x0 : (eL === 'slide' ? x - ov : x + mbw/2);
      const lx1 = eR === 'out' ? inner.x1 : (eR === 'slide' ? x + w + ov : x + w - mbw/2);
      const ly0 = eB === 'out' ? inner.y0 : y + mbw/2;
      const ly1 = eT === 'out' ? inner.y1 : y + h - mbw/2;
      leaf(node.type, lx0, ly0, Math.max(0.02, lx1 - lx0), Math.max(0.02, ly1 - ly0), isSlide ? slideCounter++ : 0);
      return;
    }
    const kids = node.children || [];
    const row = node.direction === 'row';
    const total = row ? w : h;
    let cum = 0;
    const slideKid = (k)=> k && k.node && k.node.kind === 'leaf' && /^slide_/.test(k.node.type || '');
    kids.forEach((ch, i)=>{
      const size = ch.frac / 100 * total;
      const cx = row ? x + cum : x, cy = row ? y : y + cum;
      const cw = row ? size : w, chh = row ? h : size;
      const slideL = row && i > 0 && slideKid(kids[i-1]) && slideKid(ch);
      const slideR = row && i < kids.length - 1 && slideKid(kids[i+1]) && slideKid(ch);
      const L = row ? (i === 0 ? eL : (slideL ? 'slide' : 'in')) : eL;
      const R = row ? (i === kids.length - 1 ? eR : (slideR ? 'slide' : 'in')) : eR;
      const B = row ? eB : (i === 0 ? eB : 'in');
      const Tt = row ? eT : (i === kids.length - 1 ? eT : 'in');
      walk(ch.node, cx, cy, cw, chh, L, R, B, Tt);
      cum += size;
      if(i < kids.length - 1 && !(row && slideKid(ch) && slideKid(kids[i+1]))){
        const lo = row ? Math.max(y, inner.y0) : Math.max(x, inner.x0);
        const hi = row ? Math.min(y + h, inner.y1) : Math.min(x + w, inner.x1);
        if(row) bar(x + cum, (lo + hi)/2, mbw, hi - lo, D * 0.96, 0, M.alu);
        else bar((lo + hi)/2, y + cum, hi - lo, mbw, D * 0.96, 0, M.alu);
      }
    });
  }
  walk(it.layout, 0, 0, W, Hh, 'out', 'out', 'out', 'out');
  frame(0, 0, W, Hh, ofw, D, 0);
  if(sliding){
    // سكة السحّاب تحت (ظاهرة)
    bar(W/2, ofw*0.55, W - 2*ofw, 0.006, 0.004, 0.022, M.steel);
    bar(W/2, ofw*0.55, W - 2*ofw, 0.006, 0.004, -0.022, M.steel);
  }
  return { group: g, W, H: Hh, D, door };
}

/* ---------- المشهد ---------- */
function buildScene(it, opts, H){
  const THREE = T();
  const st = getState();
  const M = makeMats(opts);
  const scene = new THREE.Scene();
  scene.environment = opts.bg === 'studio' ? st.env : st.skyEnv;
  scene.background = skyTex(opts.bg);
  const op = buildOpening(it, M, H);
  const W = op.W, Hh = op.H;
  const WT = 0.22;            // سماكة الحيط
  const setback = 0.07;       // الفريم داخل الحيط شوي (الكشف ظاهر)
  const sillH = op.door ? 0 : Math.min(1.0, Math.max(0.5, 0.9));
  const wallMat = M.plaster;
  const grp = new THREE.Group(); scene.add(grp);
  const box = (cx, cy, cz, w, h, d, mat)=>{ const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(cx, cy, cz); m.receiveShadow = true; m.castShadow = true; grp.add(m); return m; };
  const y0 = sillH, y1 = sillH + Hh;
  // الحيط: قطعة وحدة مع فتحة (الخامة مكمّلة بلا فواصل)، الوجه الخارجي عند z=0
  const L = -Math.max(3.5, W), R = W + Math.max(3.5, W), TOP = y1 + Math.max(2.2, Hh * 0.8);
  const shp = new THREE.Shape();
  if(y0 <= 0.0001){
    shp.moveTo(L, 0); shp.lineTo(0, 0); shp.lineTo(0, y1); shp.lineTo(W, y1); shp.lineTo(W, 0); shp.lineTo(R, 0); shp.lineTo(R, TOP); shp.lineTo(L, TOP); shp.lineTo(L, 0);
  } else {
    shp.moveTo(L, 0); shp.lineTo(R, 0); shp.lineTo(R, TOP); shp.lineTo(L, TOP); shp.lineTo(L, 0);
    const hole = new THREE.Path(); hole.moveTo(0, y0); hole.lineTo(0, y1); hole.lineTo(W, y1); hole.lineTo(W, y0); hole.lineTo(0, y0); shp.holes.push(hole);
  }
  const wg = new THREE.ExtrudeGeometry(shp, { depth: WT, bevelEnabled:false, curveSegments:1 });
  wg.translate(0, 0, -WT);
  wallMat.map.repeat.set(0.7, 0.7);
  const wall = new THREE.Mesh(wg, wallMat); wall.receiveShadow = true; wall.castShadow = true; grp.add(wall);
  if(sillH > 0){
    // عتبة رخام بارزة
    box(W/2, sillH - 0.015, 0.02, W + 0.08, 0.03, WT + 0.06, M.marble);
  }
  // أرضية
  const fl = new THREE.Mesh(new THREE.PlaneGeometry(40, 15), M.floor);
  fl.rotation.x = -Math.PI/2; fl.position.set(W/2, 0, 7.5); fl.receiveShadow = true;
  M.floor.map.repeat.set(40/0.6, 15/0.6);
  grp.add(fl);
  // جوّا (ورا الحيط): غرفة أعتم من برّا - متل الواقع لما تشوف شباك من الشارع، الزجاج بيعكس السما وجوّا مبيّن خفيف
  const inMat = new THREE.MeshBasicMaterial({ color:0x2f2b26, side:THREE.BackSide });
  const RD = 4.5, RW = W + 4, RH = Math.max(3, y1 + 0.6);
  const room = new THREE.Mesh(new THREE.BoxGeometry(RW, RH, RD), inMat); room.position.set(W/2, RH/2, -WT - RD/2 + 0.001); grp.add(room);
  const curtainMat = new THREE.MeshBasicMaterial({ color:0x6f675b });
  [-0.35, W + 0.05].forEach(cx=>{ const c = new THREE.Mesh(new THREE.BoxGeometry(0.3, RH - 0.1, 0.06), curtainMat); c.position.set(cx + 0.15, RH/2, -WT - 0.25); grp.add(c); });
  op.group.position.set(0, y0, -setback - op.D/2);
  scene.add(op.group);
  // إضاءة: شمس بظل ناعم + سما
  const sun = new THREE.DirectionalLight(0xfff1dc, 1.7);
  sun.position.set(W/2 - 3.2, y1 + 2.6, 3.2); sun.target.position.set(W/2, y0 + Hh/2, 0);
  sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.radius = 4;
  const sc = sun.shadow.camera, span = Math.max(W, Hh) + 2; sc.left = -span; sc.right = span; sc.top = span; sc.bottom = -span; sc.near = 0.5; sc.far = 20;
  scene.add(sun); scene.add(sun.target);
  scene.add(new THREE.HemisphereLight(0xdfeaf5, 0x7a6f60, 0.22));
  // ضو من ورا (السما) حتى الزجاج يبين
  const back = new THREE.DirectionalLight(0xdbe8ff, 0.35); back.position.set(W/2, y1, -5); scene.add(back);
  return { scene, focus: new THREE.Vector3(W/2, y0 + Hh/2, -setback), W, H: Hh, mats: M };
}

/* ---------- ⛱️ البيرغولا (2026-11-19) ----------
   حمدي: "عملت عرض سعر وتصميم وفيه بيرغولا بس ما ظهرت عالثري دي وما اعطاني خيار انو السقف يكون مغلق بساندويتش بانل".
   كل شي من بيانات المصمم (pgCalc): الطول والعمق والارتفاع، عدد الأعمدة وأماكنها حسب طريقة التركيب (أعمدة قدام وورا / عالحيط / كابولي)،
   مقاسات العمود والجسر والشريحة، المسافة بين الشرائح، ونوع السقف: شرائح مفتوحة · لوفر متحرك · بولي كاربونيت · زجاج · ساندويتش بانل (مسكّر). */
const PG_ROOFS = { slats:'شرائح مفتوحة', louver:'لوفر متحرك', poly:'بولي كاربونيت', glass:'زجاج', sandwich:'ساندويتش بانل (مسكّر)' };
function isPergolaSupported(it, H){ return !!(it && H.isPergola && H.isPergola(it) && typeof H.pgCalc === 'function' && it.width > 0 && it.height > 0); }
function buildPergolaScene(it, opts, H){
  const THREE = T();
  const st = getState();
  const M = makeMats(opts);
  const c = H.pgCalc(it);
  const mm = (v)=> v / 1000;
  const L = mm(c.L), D = mm(c.D), Hh = mm(c.H);
  const sz = (v, d)=>{ const m = String(v || '').match(/(\d{2,3})\s*[x×*]\s*(\d{2,3})/i); return m ? [mm(+m[1]), mm(+m[2])] : d; };
  const post = sz(it.pgPost, [0.15, 0.15]), beam = sz(it.pgBeam, [0.15, 0.15]), slat = sz(it.pgSlat, [0.05, 0.05]);
  const scene = new THREE.Scene();
  scene.environment = opts.bg === 'studio' ? st.env : st.skyEnv;
  scene.background = skyTex(opts.bg);
  const grp = new THREE.Group(); scene.add(grp);
  const metal = it.pgMaterial === 'steel' && !it.r3dColor ? new THREE.MeshStandardMaterial({ color:0x8f969b, roughness:0.45, metalness:0.75, envMap:M.alu.envMap, envMapIntensity:0.8 }) : M.alu;
  const add = (geo, mat, x, y, z, cast)=>{ const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = cast !== false; m.receiveShadow = true; grp.add(m); return m; };
  const bx = (w, h, d, mat, x, y, z)=> add(bevelBoxGeo(w, h, d, 0.003), mat, x, y, z);
  // الأرضية: بلاط حوالين البيرغولا
  const fl = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), M.floor); fl.rotation.x = -Math.PI/2; fl.position.set(L/2, 0, -D/2); fl.receiveShadow = true;
  M.floor.map.repeat.set(60/0.6, 60/0.6); grp.add(fl);
  // حيط البيت (تركيب عالحيط) ورا البيرغولا
  const WT = 0.25;
  if(it.pgMount === 'wall'){
    M.plaster.map.repeat.set(0.7, 0.7);
    const wh = Hh + 1.6, ww = L + 6;
    const wg = new THREE.BoxGeometry(ww, wh, WT);
    add(wg, M.plaster, L/2, wh/2, -D - WT/2, true);
  }
  // الأعمدة حسب تصميمها (عادي / مزدوج / زاوية) + القطع الصغيرة بيناتهم - من pgPostLayout بالمصمم (نفس الحساب والرسمة)
  if(typeof H.pgPostLayout === 'function'){
    const ly = H.pgPostLayout(it);
    ly.posts.forEach((q)=>{ bx(mm(q.w), Hh, mm(q.d), metal, mm(q.x), Hh/2, -mm(q.z)); bx(mm(q.w) + 0.08, 0.012, mm(q.d) + 0.08, metal, mm(q.x), 0.006, -mm(q.z)); });
    const iw = mm(ly.iw), ih = mm(ly.ih);
    ly.rungs.forEach((r)=>{
      const dx = mm(r.x2 - r.x1), dz = mm(r.z2 - r.z1), len = Math.hypot(dx, dz); if(len < 0.005) return;
      const along = Math.abs(dx) >= Math.abs(dz);
      const cx = mm((r.x1 + r.x2) / 2), cz = -mm((r.z1 + r.z2) / 2);
      ly.ys.forEach((y)=>{ bx(along ? len : iw, ih, along ? iw : len, metal, cx, mm(y), cz); });
    });
  } else {
    const rowsZ = it.pgMount === 'free' ? [-post[1]/2, -D + post[1]/2] : it.pgMount === 'wall' ? [-post[1]/2] : [-D + post[1]/2];
    rowsZ.forEach((z)=>{ for(let i=0;i<c.per;i++){ const x = c.per === 1 ? L/2 : post[0]/2 + i * (L - post[0]) / (c.per - 1); bx(post[0], Hh, post[1], metal, x, Hh/2, z); bx(post[0] + 0.08, 0.012, post[1] + 0.08, metal, x, 0.006, z); } });
  }
  // الجسور (الإطار فوق): الارتفاع = آخر قياس بالجسر
  const bw = beam[0], bh = Math.max(beam[1], beam[0]);
  const yB = Hh - bh/2;
  bx(L, bh, bw, metal, L/2, yB, -bw/2);
  bx(L, bh, bw, metal, L/2, yB, -D + bw/2);
  bx(bw, bh, D - 2*bw, metal, bw/2, yB, -D/2);
  bx(bw, bh, D - 2*bw, metal, L - bw/2, yB, -D/2);
  // الشرائح (ماشية بالعمق، موزّعة عالطول)
  const roof = PG_ROOFS[it.pgRoof] ? it.pgRoof : 'slats';
  const n = Math.max(2, c.slats), sw = slat[0], sh = slat[1];
  const sp = n > 1 ? (L - 2*bw - sw) / (n - 1) : 0;
  const yS = Hh - sh/2;
  for(let i=0;i<n;i++){
    const x = bw + sw/2 + i*sp;
    if(roof === 'louver'){
      // شفرات لوفر عريضة ومايلة شوي (مفتوحة)
      const bl = Math.min(Math.max(sp * 0.92, 0.12), 0.25);
      const m = add(bevelBoxGeo(bl, 0.022, D - 2*bw, 0.004), metal, x, Hh - 0.07, -D/2); m.rotation.z = 0.55;
    } else {
      bx(sw, sh, D - 2*bw, metal, x, yS, -D/2);
    }
  }
  // تغطية السقف
  const yTop = Hh + 0.004;
  if(roof === 'poly'){
    const pm = new THREE.MeshPhysicalMaterial({ color:0xeef6f8, transparent:true, opacity:0.55, roughness:0.35, metalness:0, envMap:M.alu.envMap, envMapIntensity:0.6, side:THREE.DoubleSide, depthWrite:false });
    const m = add(new THREE.BoxGeometry(L, 0.01, D), pm, L/2, yTop + 0.005, -D/2, false); m.renderOrder = 2;
    // خطوط البولي (قنوات)
    const lm = new THREE.MeshStandardMaterial({ color:0xdde8ec, transparent:true, opacity:0.5, roughness:0.4 });
    for(let x = 0.25; x < L; x += 0.5) add(new THREE.BoxGeometry(0.008, 0.012, D), lm, x, yTop + 0.012, -D/2, false);
  } else if(roof === 'glass'){
    const m = add(new THREE.BoxGeometry(L, 0.01, D), M.glass, L/2, yTop + 0.005, -D/2, false); m.renderOrder = 2;
    const rf = new THREE.Mesh(new THREE.PlaneGeometry(L, D), M.glassRefl); rf.rotation.x = -Math.PI/2; rf.position.set(L/2, yTop + 0.011, -D/2); rf.renderOrder = 3; grp.add(rf);
  } else if(roof === 'sandwich'){
    // ساندويتش بانل: لوح مسكّر بسماكة + أضلاع (ribs) فوق، لونه أبيض/رمادي فاتح، ومن تحت أملس
    const thk = 0.05;
    const top = new THREE.MeshStandardMaterial({ color:0xe6e4df, roughness:0.55, metalness:0.25, envMap:M.alu.envMap, envMapIntensity:0.5 });
    const under = new THREE.MeshStandardMaterial({ color:0xf1f0ec, roughness:0.7, metalness:0.1, envMap:M.alu.envMap, envMapIntensity:0.3 });
    const pan = add(new THREE.BoxGeometry(L + 0.06, thk, D + 0.06), [top, top, top, under, top, top], L/2, Hh + thk/2, -D/2);
    pan.castShadow = true;
    for(let x = 0.17; x < L; x += 0.333) add(bevelBoxGeo(0.035, 0.03, D + 0.06, 0.004), top, x, Hh + thk + 0.015, -D/2);
    // فلاشينغ عالأطراف
    bx(L + 0.1, 0.06, 0.02, top, L/2, Hh + thk/2 + 0.005, 0.04);
  }
  // إضاءة
  const span = Math.max(L, D, Hh) + 3;
  const sun = new THREE.DirectionalLight(0xfff1dc, 1.8);
  sun.position.set(L/2 - span*0.6, Hh + span*0.9, span*0.5); sun.target.position.set(L/2, 0, -D/2);
  sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0005; sun.shadow.radius = 3;
  const sc = sun.shadow.camera; sc.left = -span; sc.right = span; sc.top = span; sc.bottom = -span; sc.near = 0.5; sc.far = span * 4;
  scene.add(sun); scene.add(sun.target);
  scene.add(new THREE.HemisphereLight(0xdfeaf5, 0x7a6f60, 0.35));
  const W = Math.max(L, D * 0.9) + 0.6, HH = Hh + 0.4;
  return { scene, focus: new THREE.Vector3(L/2, Hh * 0.5, -D/2), W, H: HH, mats: M, pergola: true };
}
function sceneFor(it, opts, H){ return isPergolaSupported(it, H) ? buildPergolaScene(it, opts, H) : buildScene(it, opts, H); }
function canRender(it, H){ return isPergolaSupported(it, H) || isOpeningSupported(it, H); }

function placeCamera(cam, info, aspect, yawDeg, pitchDeg){
  const THREE = T();
  const fov = cam.fov * Math.PI / 180;
  const needH = info.H * 1.3 + 0.35, needW = info.W * 1.3 + 0.35;
  const dist = Math.max(needH / (2*Math.tan(fov/2)), needW / (2*Math.tan(fov/2)*aspect)) + 0.3;
  const yaw = (yawDeg == null ? 16 : yawDeg) * Math.PI/180, pitch = (pitchDeg == null ? 4 : pitchDeg) * Math.PI/180;
  cam.position.set(info.focus.x + dist*Math.sin(yaw)*Math.cos(pitch), info.focus.y + dist*Math.sin(pitch), info.focus.z + dist*Math.cos(yaw)*Math.cos(pitch));
  cam.lookAt(info.focus);
  cam.near = 0.05; cam.far = 120; cam.updateProjectionMatrix();
}

function disposeScene(scene){
  scene.traverse(o=>{
    if(o.geometry && !Array.from(geoCache.values()).includes(o.geometry)) o.geometry.dispose();
    const ms = o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : [];
    ms.forEach(m=>{ if(m.map) m.map.dispose(); m.dispose(); });
  });
  if(scene.background && scene.background.dispose) scene.background.dispose();
}

function optsFor(it, o){
  return Object.assign({ color: (it && it.r3dColor) || 'black', glass: (it && it.r3dGlass) || 'clear', bg: (it && it.r3dBg) || 'facade' }, o || {});
}

// صورة ثابتة (dataURL) لبطاقة العرض
function renderImage(it, H, o){
  if(!supported() || !canRender(it, H)) return null;
  const THREE = T();
  const opts = optsFor(it, o);
  const w = (o && o.w) || 900, h = (o && o.h) || 680;
  const st = getState(), r = st.renderer;
  r.setPixelRatio(1); r.setSize(w, h, false);
  const info = sceneFor(it, opts, H);
  const cam = new THREE.PerspectiveCamera(30, w/h, 0.05, 120);
  placeCamera(cam, info, w/h, opts.yaw != null ? opts.yaw : (info.pergola ? 28 : null), opts.pitch != null ? opts.pitch : (info.pergola ? 20 : null));
  r.render(info.scene, cam);
  const url = r.domElement.toDataURL('image/png');
  disposeScene(info.scene);
  return url;
}

/* ---------- العارض التفاعلي (دوّر وشوف) ---------- */
let VW = null;
function openViewer(it, H, onSave){
  if(!supported() || !canRender(it, H)) return false;
  const isPg = isPergolaSupported(it, H);
  const THREE = T();
  closeViewer();
  const ov = document.createElement('div'); ov.id = 'mzR3dOverlay';
  ov.style.cssText = 'position:fixed;inset:0;z-index:10700;background:#111;display:flex;flex-direction:column;direction:rtl;font-family:Tajawal,Tahoma,Arial,sans-serif;';
  const chip = (k, v, ar, cur, extra)=> `<button data-k="${k}" data-v="${v}" style="font:inherit;font-size:13px;padding:6px 10px;border-radius:16px;cursor:pointer;border:1px solid ${cur ? '#00B8D4' : '#556'};background:${cur ? '#00B8D4' : 'rgba(255,255,255,0.06)'};color:#fff;display:inline-flex;gap:6px;align-items:center;">${extra || ''}${ar}</button>`;
  const opts = optsFor(it);
  const sw = (hex)=> `<span style="width:14px;height:14px;border-radius:50%;background:#${hex.toString(16).padStart(6,'0')};border:1px solid #999;display:inline-block"></span>`;
  ov.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#1b1f24;color:#fff;flex-wrap:wrap;">
      <b style="font-size:15px;">✨ ${String(it.label || '').replace(/[<>&]/g,'')} — عرض واقعي</b>
      <span style="font-size:12px;color:#9ab;">اسحب لتدوّر · قرّب بإصبعين أو بالعجلة</span>
      <span style="flex:1"></span>
      <button id="mzR3dShot" style="font:inherit;font-size:14px;padding:7px 12px;border-radius:8px;border:0;background:#2e7d32;color:#fff;cursor:pointer;">📸 نزّل صورة</button>
      <button id="mzR3dClose" style="font:inherit;font-size:14px;padding:7px 12px;border-radius:8px;border:1px solid #556;background:transparent;color:#fff;cursor:pointer;">✕ إغلاق</button>
    </div>
    <div id="mzR3dStage" style="flex:1;position:relative;min-height:0;"></div>
    <div id="mzR3dBar" style="display:flex;flex-wrap:wrap;gap:6px 8px;padding:10px 14px;background:#1b1f24;color:#cfd8dc;font-size:13px;align-items:center;">
      <span>لون الألمنيوم:</span>${Object.keys(COLORS).map(k=> chip('color', k, COLORS[k].ar, opts.color === k, sw(COLORS[k].hex))).join('')}
      ${isPg ? `<span style="margin-inline-start:10px">السقف:</span>${Object.keys(PG_ROOFS).map(k=> chip('roof', k, PG_ROOFS[k], (it.pgRoof || 'slats') === k)).join('')}` : ''}
      <span style="margin-inline-start:10px">الزجاج:</span>${Object.keys(GLASS).map(k=> chip('glass', k, GLASS[k].ar, opts.glass === k)).join('')}
      <span style="margin-inline-start:10px">الخلفية:</span>${chip('bg', 'facade', 'واجهة', opts.bg === 'facade')}${chip('bg', 'studio', 'استوديو', opts.bg === 'studio')}
    </div>`;
  document.body.appendChild(ov);
  const stage = ov.querySelector('#mzR3dStage');
  const st = getState(), r = st.renderer;
  stage.appendChild(r.domElement);
  r.domElement.style.cssText = 'width:100%;height:100%;display:block;touch-action:none;';
  const cam = new THREE.PerspectiveCamera(30, 1, 0.05, 120);
  let info = null, controls = null, raf = 0, dirty = true;
  function rebuild(keepView){
    const prev = keepView && info ? { p: cam.position.clone(), t: controls ? controls.target.clone() : null } : null;
    if(info) disposeScene(info.scene);
    info = sceneFor(it, opts, H);
    size();
    if(prev){ cam.position.copy(prev.p); if(controls && prev.t) controls.target.copy(prev.t); }
    else { placeCamera(cam, info, cam.aspect, info.pergola ? 30 : 22, info.pergola ? 22 : 5); if(controls){ controls.target.copy(info.focus); } }
    if(controls) controls.update();
    dirty = true;
  }
  function size(){
    const w = Math.max(50, stage.clientWidth), h = Math.max(50, stage.clientHeight);
    r.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); r.setSize(w, h, false);
    cam.aspect = w / h; cam.updateProjectionMatrix(); dirty = true;
  }
  if(THREE.OrbitControls){
    controls = new THREE.OrbitControls(cam, r.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.08;
    controls.minPolarAngle = 0.25; controls.maxPolarAngle = Math.PI/2 - 0.02;
    if(!isPg){ controls.minAzimuthAngle = -1.25; controls.maxAzimuthAngle = 1.25; }
    controls.addEventListener('change', ()=>{ dirty = true; });
  }
  rebuild(false);
  function loop(){ raf = requestAnimationFrame(loop); if(controls && controls.update()) dirty = true; if(dirty && info){ r.render(info.scene, cam); dirty = false; } }
  loop();
  const onResize = ()=> size();
  window.addEventListener('resize', onResize);
  ov.querySelector('#mzR3dBar').addEventListener('click', (e)=>{
    const b = e.target.closest('button[data-k]'); if(!b) return;
    if(b.dataset.k === 'roof'){ it.pgRoof = b.dataset.v; } else opts[b.dataset.k] = b.dataset.v;
    ov.querySelectorAll(`button[data-k="${b.dataset.k}"]`).forEach(x=>{ const on = x.dataset.v === b.dataset.v; x.style.background = on ? '#00B8D4' : 'rgba(255,255,255,0.06)'; x.style.borderColor = on ? '#00B8D4' : '#556'; });
    it.r3dColor = opts.color; it.r3dGlass = opts.glass; it.r3dBg = opts.bg;
    try{ if(onSave) onSave(it); }catch(err){}
    rebuild(true);
  });
  ov.querySelector('#mzR3dShot').addEventListener('click', ()=>{
    r.render(info.scene, cam);
    const a = document.createElement('a'); a.href = r.domElement.toDataURL('image/png');
    a.download = (String(it.label || 'design').replace(/[\\/:*?"<>|]+/g, '_')) + ' - 3D.png'; document.body.appendChild(a); a.click(); a.remove();
  });
  ov.querySelector('#mzR3dClose').addEventListener('click', closeViewer);
  VW = { ov, stop(){ cancelAnimationFrame(raf); window.removeEventListener('resize', onResize); if(controls) controls.dispose(); if(info) disposeScene(info.scene); } };
  return true;
}
function closeViewer(){
  if(!VW) return;
  try{ VW.stop(); }catch(e){}
  try{ VW.ov.remove(); }catch(e){}
  VW = null;
}

window.MzReal3D = { _state: ()=> getState(), supported, canRender, isPergolaSupported, PG_ROOFS, isOpeningSupported, renderImage, openViewer, closeViewer, COLORS, GLASS, _buildOpening: buildOpening };
})();
