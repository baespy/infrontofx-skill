(async function () {
  'use strict';
  const S = window.SPEC, R = window.RENDER;
  if (!S || !R) { console.log('POSTER-ERROR no spec loaded'); return; }
  const W = R.w, H = R.h, U = Math.min(W, H) / 1000;
  const warn = m => console.log('POSTER-WARN ' + m);

  const gpu = (() => {
    const gl = document.createElement('canvas').getContext('webgl2', { failIfMajorPerformanceCaveat: true });
    if (!gl) return null;
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    return gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER);
  })();
  if (!gpu || /swiftshader|llvmpipe|basic render|software|warp/i.test(gpu)) { console.log('POSTER-ERROR no hardware GPU (renderer: ' + gpu + ')'); return; }
  console.log('POSTER-GPU ' + gpu);

  const THEMES = {
    crimson: { a: '#ff1a2e', a2: '#ff6a3a', bg: ['#040102', '#25030a', '#8a0714'], soft: '#ffc2c8', glow: 'rgba(255,20,40,.7)', cardmid: '#4a050c', cardend: '#160205', badge: '#a30f1e', pill: '#a30f1e' },
    cobalt: { a: '#2f86ec', a2: '#a8d8ff', bg: ['#04080f', '#0b2345', '#1a64bd'], soft: '#c5dfff', glow: 'rgba(60,150,255,.7)', cardmid: '#123d75', cardend: '#0a1a33', badge: '#1a5cae', pill: '#5a9be0' },
    violet: { a: '#b63cff', a2: '#ffb52e', bg: ['#07030e', '#280a48', '#7220bb'], soft: '#e6c8ff', glow: 'rgba(180,60,255,.7)', cardmid: '#3c1270', cardend: '#160630', badge: '#6d1fb0', pill: '#8a2ed0' },
    toxic: { a: '#27ff5c', a2: '#d8ff42', bg: ['#010503', '#05260e', '#10702c'], soft: '#c6ffd4', glow: 'rgba(40,255,90,.65)', cardmid: '#0d4a1e', cardend: '#04160a', badge: '#128a35', pill: '#27a84a' },
    ember: { a: '#ffc94a', a2: '#ff7a1f', bg: ['#0b0603', '#3a2208', '#9a6216'], soft: '#ffe6ae', glow: 'rgba(255,170,40,.65)', cardmid: '#5a3a0c', cardend: '#1c1104', badge: '#a8701a', pill: '#b57a1f' },
    rose: { a: '#ff2e9a', a2: '#ffa8dc', bg: ['#0c030a', '#38092a', '#942068'], soft: '#ffd0ea', glow: 'rgba(255,46,154,.7)', cardmid: '#5e1042', cardend: '#1e0516', badge: '#ad1d74', pill: '#c9328a' },
    haunt: { a: '#d06cff', a2: '#ff8ad2', bg: ['#100a1e', '#38205c', '#8245b4'], soft: '#ecd3ff', glow: 'rgba(200,100,255,.65)', cardmid: '#4a2878', cardend: '#1a0e30', badge: '#7a3bb0', pill: '#9050c8' },
    teal: { a: '#22b8e6', a2: '#86f1ff', bg: ['#031219', '#0a3a4e', '#127a98'], soft: '#c9f3ff', glow: 'rgba(40,190,235,.65)', cardmid: '#0e4f68', cardend: '#061e2a', badge: '#127a98', pill: '#1f94b8' },
    pastel: { a: '#ff7fb0', a2: '#ffd26b', bg: ['#fff4f7', '#f7dfe9', '#dcc9ee'], soft: '#ffe3ee', glow: 'rgba(255,127,176,.45)', cardmid: '#ffd9e6', cardend: '#f4c6da', badge: '#e0487f', pill: '#e0487f', light: true },
    ocean: { a: '#12a9e0', a2: '#fff0b8', bg: ['#e6f9ff', '#8ee3f7', '#1aa4d8'], soft: '#e0f7ff', glow: 'rgba(20,170,225,.45)', cardmid: '#a9e8f7', cardend: '#62c9e6', badge: '#0b7fb5', pill: '#0b7fb5', light: true }
  };
  const T = Object.assign({}, THEMES[S.theme] || THEMES.crimson);
  if (!THEMES[S.theme]) warn('unknown theme "' + S.theme + '", using crimson');
  if (S.accent) T.a = S.accent;
  if (S.accent2) T.a2 = S.accent2;

  const LAYOUTS = {
    'hero-right': { hero: [{ x: .72, y: 1.03, h: 1.04 }, { x: .52, y: 1.03, h: .8 }], column: { x: .05, w: .41, top: .08, bottom: .88, justify: 'center', align: 'left' }, itemsIn: true, footer: { x: .05, y: .945, align: 'left' }, logo: 'tr', shade: 'left' },
    'hero-left': { hero: [{ x: .28, y: 1.03, h: 1.04 }, { x: .48, y: 1.03, h: .8 }], column: { x: .54, w: .41, top: .08, bottom: .88, justify: 'center', align: 'right' }, itemsIn: true, footer: { x: .95, y: .945, align: 'right' }, logo: 'tl', shade: 'right' },
    'hero-center': { hero: [{ x: .5, y: 1.02, h: 1 }, { x: .3, y: 1.02, h: .86 }, { x: .7, y: 1.02, h: .86 }], column: { x: .18, w: .64, top: .5, bottom: .915, justify: 'flex-end', align: 'center' }, itemsIn: true, footer: { x: .5, y: .955, align: 'center' }, logo: 'tr', shade: 'bottom' },
    'square-support': { hero: [{ x: .34, y: .86, h: .86, fade: { bottom: .28 } }, { x: .68, y: .78, h: .6, fade: { bottom: .28 } }], column: { x: .57, w: .38, top: .16, bottom: .6, justify: 'center', align: 'center' }, items: { x: .08, y: .655, w: .84, band: [.62, .925] }, footer: { x: .5, y: .955, align: 'center' }, logo: 'tr', shade: 'bottom', frontShade: [.6, .34] },
    'gun-support': { hero: [{ x: .74, y: 1.04, h: 1.1 }], column: { x: .04, w: .44, top: .26, bottom: .625, justify: 'center', align: 'center' }, items: { x: .07, y: .655, w: .56, band: [.64, .9] }, footer: { x: .5, y: .955, align: 'center' }, logo: 'tr', shade: 'none' },
    'pack-grid': { hero: [{ x: .27, y: 1.02, h: 1 }, { x: .12, y: 1.02, h: .72 }], column: { x: .5, w: .44, top: .66, bottom: .93, justify: 'center', align: 'center' }, items: { x: .47, y: .05, w: .49 }, footer: { style: 'slash' }, logo: null, shade: 'none' },
    'product': { hero: [{ x: .68, y: .92, h: .78 }, { x: .42, y: .95, h: .5 }], column: { x: .05, w: .36, top: .1, bottom: .88, justify: 'center', align: 'left' }, itemsIn: true, footer: { x: .05, y: .945, align: 'left' }, logo: 'tr', shade: 'left' }
  };
  const L = LAYOUTS[S.layout] || LAYOUTS['hero-right'];
  if (!LAYOUTS[S.layout]) warn('unknown layout "' + S.layout + '", using hero-right');

  let seed = (S.seed || 7) >>> 0;
  const rnd = () => { seed = (seed + 0x6D2B79F5) >>> 0; let t = seed; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const rr = (a, b) => a + (b - a) * rnd();

  const url = p => {
    if (/^(file|https?|data):/i.test(p)) return p;
    if (/^[a-z]:[\\/]/i.test(p)) return 'file:///' + p.replace(/\\/g, '/').split('/').map(encodeURIComponent).join('/').replace('%3A', ':');
    return new URL(p.replace(/\\/g, '/').split('/').map(encodeURIComponent).join('/'), R.base).href;
  };
  const load = p => new Promise(res => { const i = new Image(); i.onload = () => res(i); i.onerror = () => { warn('image not found: ' + p); res(null); }; i.src = url(p); });
  const mk = (w, h) => { const c = document.createElement('canvas'); c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h)); return c; };
  const el = (tag, cls, parent) => { const e = document.createElement(tag); if (cls) e.className = cls; if (parent) parent.appendChild(e); return e; };
  const hexA = (hex, a) => { const n = parseInt(hex.slice(1), 16); return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')'; };

  const root = document.getElementById('poster');
  root.style.cssText = 'width:' + W + 'px;height:' + H + 'px';
  Object.entries({ '--u': U + 'px', '--a': T.a, '--a2': T.a2, '--soft': T.soft, '--glow': T.glow, '--cardmid': T.cardmid, '--cardend': T.cardend, '--badge': T.badge, '--pill': T.pill, '--scriptc': (S.title && S.title.scriptColor) || T.a }).forEach(([k, v]) => root.style.setProperty(k, v));

  await Promise.all(['400 40px Anton', '400 40px Bebas', '400 40px Russo', '400 40px Michroma', '400 40px Signature', '400 40px Titan', '700 40px Mitr', '500 40px Kanit', '700 40px Kanit', 'italic 900 40px Kanit']
    .map(f => document.fonts.load(f, 'Aก').catch(() => warn('font failed: ' + f))));

  /* ---------- background ---------- */
  function paintBackground(g, bgImg, b) {
    const grad = g.createRadialGradient(W * (b.lightX ?? .68), H * (b.lightY ?? .4), 0, W * (b.lightX ?? .68), H * (b.lightY ?? .4), Math.hypot(W, H) * .72);
    grad.addColorStop(0, T.bg[2]); grad.addColorStop(.48, T.bg[1]); grad.addColorStop(1, T.bg[0]);
    g.fillStyle = grad; g.fillRect(0, 0, W, H);
    if (bgImg) {
      const s = Math.max(W / bgImg.width, H / bgImg.height), m = (b.blur || 0) * U * 2;
      g.save(); g.filter = 'blur(' + (b.blur || 0) * U + 'px) brightness(' + (b.brightness ?? (T.light ? 1 : .62)) + ') saturate(1.1)';
      g.drawImage(bgImg, (W - bgImg.width * s) / 2 - m, (H - bgImg.height * s) / 2 - m, bgImg.width * s + 2 * m, bgImg.height * s + 2 * m);
      g.restore();
      if (b.tint !== 0) { g.save(); g.globalAlpha = b.tint ?? .28; g.globalCompositeOperation = 'color'; g.fillStyle = T.a; g.fillRect(0, 0, W, H); g.restore(); }
    }
    const shape = b.shape ?? (bgImg ? 'none' : 'diagonal');
    g.save();
    if (shape === 'diagonal') {
      [[.46, .0, .78, .0, .34, 1, .02, 1, .15], [.72, 0, .9, 0, .56, 1, .38, 1, .22], [.92, 0, 1.08, 0, .8, 1, .64, 1, .12]].forEach(p => {
        const lg = g.createLinearGradient(W * p[0], 0, W * p[4], H);
        lg.addColorStop(0, hexA(T.a, p[8] * 2.1)); lg.addColorStop(.75, hexA(T.a, 0));
        g.fillStyle = lg; g.beginPath(); g.moveTo(W * p[0], 0); g.lineTo(W * p[2], 0); g.lineTo(W * p[4], H); g.lineTo(W * p[6], H); g.closePath(); g.fill();
      });
    } else if (shape === 'triangle') {
      g.globalCompositeOperation = T.light ? 'source-over' : 'lighter';
      [[.62, .1, .62], [.8, .2, .4], [.42, .28, .3]].forEach((t, i) => {
        const s = H * t[2] * 1.15, cx = W * t[0], cy = H * t[1] + s * .6;
        const lg = g.createLinearGradient(cx, cy - s, cx, cy + s * .6);
        lg.addColorStop(0, hexA(T.a, .34 - i * .07)); lg.addColorStop(1, hexA(T.a, 0));
        g.fillStyle = lg; g.beginPath(); g.moveTo(cx, cy - s); g.lineTo(cx + s * .95, cy + s * .62); g.lineTo(cx - s * .95, cy + s * .62); g.closePath(); g.fill();
      });
    } else if (shape === 'burst') {
      g.globalCompositeOperation = 'lighter'; g.filter = 'blur(' + 15 * U + 'px)';
      const cx = W * (b.lightX ?? .62), cy = H * (b.lightY ?? .42);
      for (let i = 0; i < 16; i++) {
        const ang = rr(0, Math.PI * 2), len = Math.hypot(W, H) * rr(.2, .55), wid = rr(.03, .1);
        const lg = g.createRadialGradient(cx, cy, 0, cx, cy, len);
        lg.addColorStop(0, hexA(T.a, .42)); lg.addColorStop(1, hexA(T.a, 0));
        g.fillStyle = lg; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(ang - wid) * len, cy + Math.sin(ang - wid) * len); g.lineTo(cx + Math.cos(ang + wid) * len, cy + Math.sin(ang + wid) * len); g.closePath(); g.fill();
      }
    }
    g.restore();
    if (!bgImg && !T.light) {
      g.save(); g.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 26; i++) {
        const x = rr(0, W), y = rr(0, H), r = rr(.1, .3) * Math.max(W, H);
        const rg = g.createRadialGradient(x, y, 0, x, y, r);
        rg.addColorStop(0, hexA(T.a, rr(.015, .05))); rg.addColorStop(1, hexA(T.a, 0));
        g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2);
      }
      g.restore();
    }
    if (!bgImg && b.clouds !== 0) {
      [[5, .42], [12, .16], [34, .05]].forEach(([cells, alpha]) => {
        const n = mk(cells * W / Math.max(W, H) + 2, cells * H / Math.max(W, H) + 2), x = n.getContext('2d'), d = x.createImageData(n.width, n.height);
        for (let i = 0; i < d.data.length; i += 4) { const v = rnd() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
        x.putImageData(d, 0, 0);
        g.save(); g.globalCompositeOperation = 'overlay'; g.globalAlpha = alpha * (b.clouds ?? 1) * (T.light ? .25 : 1); g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high'; g.filter = 'blur(' + 1100 / cells * U * .22 + 'px)'; g.drawImage(n, 0, 0, W, H); g.restore();
      });
    }
    if (b.darken) { g.save(); g.fillStyle = 'rgba(2,3,8,' + b.darken + ')'; g.fillRect(0, 0, W, H); g.restore(); }
    if (b.ghost) {
      g.save(); g.font = '400 ' + H * (b.ghostSize ?? 1.1) + 'px Anton'; g.textAlign = 'center'; g.textBaseline = 'alphabetic';
      g.globalAlpha = b.ghostAlpha ?? .22; g.fillStyle = T.soft; g.filter = 'blur(' + 1.5 * U + 'px)';
      g.fillText(b.ghost, W * (b.ghostX ?? .42), H * (b.ghostY ?? .95)); g.restore();
    }
    if (b.texture) {
      const tile = mk(7, 7), tg = tile.getContext('2d');
      tg.strokeStyle = 'rgba(255,255,255,.9)'; tg.lineWidth = 1.2; tg.beginPath(); tg.moveTo(-1, 8); tg.lineTo(8, -1); tg.stroke();
      tg.strokeStyle = 'rgba(0,0,0,.7)'; tg.beginPath(); tg.moveTo(-1, 4.5); tg.lineTo(4.5, -1); tg.stroke();
      g.save(); g.globalCompositeOperation = 'overlay'; g.globalAlpha = b.texture === true ? .3 : b.texture; g.fillStyle = g.createPattern(tile, 'repeat'); g.fillRect(0, 0, W, H); g.restore();
    }
    if (b.weave) {
      const tile = mk(6, 6), tg = tile.getContext('2d');
      tg.fillStyle = 'rgba(255,255,255,.55)'; tg.fillRect(0, 0, 3, 3); tg.fillRect(3, 3, 3, 3);
      tg.fillStyle = 'rgba(0,0,0,.6)'; tg.fillRect(3, 0, 3, 3); tg.fillRect(0, 3, 3, 3);
      g.save(); g.globalCompositeOperation = 'overlay'; g.globalAlpha = b.weave === true ? .32 : b.weave; g.fillStyle = g.createPattern(tile, 'repeat'); g.fillRect(0, 0, W, H); g.restore();
    }
    if (b.swirl) paintSwirl(g, b);
    if (b._wm) {
      const wm = b._wm, ww = H * (b.wmSize ?? .95), wh = ww * wm.height / wm.width;
      g.save(); g.globalCompositeOperation = 'screen'; g.globalAlpha = b.wmAlpha ?? .07; g.filter = 'grayscale(1) brightness(1.5)';
      g.translate(W * (b.wmX ?? .62), H * (b.wmY ?? .42)); g.rotate((b.wmRotate ?? -8) * Math.PI / 180); g.drawImage(wm, -ww / 2, -wh / 2, ww, wh); g.restore();
    }
    if (b.grid) {
      const gv = b.grid === true ? 1 : b.grid;
      g.save(); g.globalCompositeOperation = 'screen';
      [[22, .07], [110, .16]].forEach(([step, al]) => {
        const s = step * U; g.strokeStyle = hexA(T.a, al * gv); g.lineWidth = (step > 50 ? 1.6 : 1) * U; g.beginPath();
        for (let x = 0; x <= W; x += s) { g.moveTo(x, 0); g.lineTo(x, H); }
        for (let y = 0; y <= H; y += s) { g.moveTo(0, y); g.lineTo(W, y); }
        g.stroke();
      });
      g.strokeStyle = hexA('#ffffff', .05 * gv); g.lineWidth = 1 * U; g.beginPath();
      for (let k = -H; k < W; k += 44 * U) { g.moveTo(k, H); g.lineTo(k + H, 0); }
      g.stroke();
      for (let i = 0; i < 70 * gv; i++) { const cx = Math.round(rr(0, W) / (110 * U)) * 110 * U, cy = Math.round(rr(0, H) / (110 * U)) * 110 * U; g.fillStyle = hexA(T.a2, rr(.3, .8)); g.fillRect(cx - 2.5 * U, cy - 2.5 * U, 5 * U, 5 * U); }
      g.restore();
    }
    if (b.graffiti) paintGraffiti(g, b);
    if (b.ground) {
      const top = H * (b.groundY ?? .8);
      const lg = g.createLinearGradient(0, top, 0, H);
      lg.addColorStop(0, 'rgba(0,0,0,0)'); lg.addColorStop(.25, 'rgba(14,12,13,.9)'); lg.addColorStop(1, 'rgba(32,28,29,1)');
      g.fillStyle = lg; g.beginPath(); g.moveTo(0, top + H * .07); g.lineTo(W, top - H * .05); g.lineTo(W, H); g.lineTo(0, H); g.closePath(); g.fill();
    }
  }

  /* spray-paint graffiti: soft clouds, stippled overspray, splatter, fat tag strokes, drips, outlined tag word */
  function paintGraffiti(g, b) {
    const gf = typeof b.graffiti === 'number' ? b.graffiti : 1;
    const cols = [T.a, T.a2, T.a, '#ffffff'], gauss = () => (rnd() + rnd() + rnd() - 1.5) / 1.5, M = Math.max(W, H);
    g.save(); g.globalCompositeOperation = T.light ? 'source-over' : 'screen';
    for (let i = 0; i < 8 * gf; i++) {
      const x = rr(0, W), y = rr(0, H), r = rr(.1, .28) * M, c = cols[i % 3];
      const rg = g.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, hexA(c, rr(.16, .3))); rg.addColorStop(1, hexA(c, 0));
      g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2);
      for (let k = 0; k < 260; k++) { const a = rnd() * 6.283, d = Math.abs(gauss()) * r * .95; g.fillStyle = hexA(c, rr(.12, .5)); g.beginPath(); g.arc(x + Math.cos(a) * d, y + Math.sin(a) * d, rr(.5, 2.2) * U, 0, 7); g.fill(); }
    }
    for (let i = 0; i < 14 * gf; i++) {
      const cx = rr(0, W), cy = rr(0, H), spread = rr(40, 140) * U, c = cols[Math.floor(rnd() * cols.length)];
      for (let k = 0, n = rr(50, 140); k < n; k++) { const d = Math.abs(gauss()) * spread, a = rnd() * 6.283; g.fillStyle = hexA(c, rr(.25, .8)); g.beginPath(); g.arc(cx + Math.cos(a) * d, cy + Math.sin(a) * d, (rr(.8, 4.6) * (1.2 - d / spread * .8)) * U, 0, 7); g.fill(); }
      g.fillStyle = hexA(c, .7); for (let k = 0; k < 3; k++) { g.beginPath(); g.arc(cx + gauss() * spread * .5, cy + gauss() * spread * .5, rr(6, 20) * U, 0, 7); g.fill(); }
    }
    g.lineCap = 'round'; g.lineJoin = 'round';
    for (let i = 0; i < 5 * gf; i++) {
      const x0 = rr(-.1, 1) * W, y0 = rr(0, 1) * H, c = cols[i % 4];
      const p = [x0, y0, x0 + rr(-.4, .4) * W, y0 + rr(-.3, .3) * H, x0 + rr(-.4, .4) * W, y0 + rr(-.3, .3) * H, x0 + rr(-.5, .5) * W, y0 + rr(-.4, .4) * H];
      [[1, 26, .18], [1, 5, .35]].forEach(([_, blur, al], pass) => {
        g.save(); g.filter = 'blur(' + blur * U * (pass ? .12 : .5) + 'px)'; g.strokeStyle = hexA(c, al); g.lineWidth = rr(26, 70) * U * (pass ? 1 : 1.5);
        g.beginPath(); g.moveTo(p[0], p[1]); g.bezierCurveTo(p[2], p[3], p[4], p[5], p[6], p[7]); g.stroke(); g.restore();
      });
    }
    for (let i = 0; i < 6 * gf; i++) {
      const x = rr(0, W), y = rr(0, H * .85), len = rr(40, 130) * U, w = rr(3, 8) * U, c = cols[i % 4];
      g.strokeStyle = hexA(c, rr(.4, .7)); g.fillStyle = g.strokeStyle; g.lineWidth = w;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + len); g.stroke(); g.beginPath(); g.arc(x, y + len, w * 1.3, 0, 7); g.fill();
    }
    if (b.tag) {
      g.save(); g.font = '400 ' + H * (b.tagSize ?? .5) + 'px Signature'; g.textAlign = 'center'; g.translate(W * (b.tagX ?? .38), H * (b.tagY ?? .58)); g.rotate((b.tagRot ?? -8) * Math.PI / 180);
      g.lineWidth = 5 * U; g.strokeStyle = hexA(T.a2, .5); g.filter = 'blur(' + 1.2 * U + 'px)'; g.strokeText(b.tag, 0, 0);
      g.lineWidth = 16 * U; g.strokeStyle = hexA(T.a, .18); g.filter = 'blur(' + 9 * U + 'px)'; g.strokeText(b.tag, 0, 0); g.restore();
    }
    g.restore();
  }
  function bolt(g, x1, y1, x2, y2, spread, depth) {
    const pts = [[x1, y1], [x2, y2]];
    for (let d = 0; d < 8; d++) {
      for (let i = pts.length - 1; i > 0; i--) {
        const a = pts[i - 1], b = pts[i], off = rr(-spread, spread) / Math.pow(2.05, d);
        const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
        pts.splice(i, 0, [(a[0] + b[0]) / 2 - dy / l * off, (a[1] + b[1]) / 2 + dx / l * off]);
      }
    }
    const stroke = (w, c, blur) => { g.lineWidth = w; g.strokeStyle = c; g.shadowColor = T.a; g.shadowBlur = blur; g.beginPath(); pts.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.stroke(); };
    stroke((8 - depth * 3) * U, hexA(T.a, .5), 46 * U);
    stroke((2.6 - depth) * U, hexA(T.a2, .9), 12 * U);
    stroke(1.1 * U, '#fff', 3 * U);
    if (depth < 1) for (let i = 0; i < 3; i++) {
      const p = pts[Math.floor(rr(.25, .9) * pts.length)], ang = Math.atan2(y2 - y1, x2 - x1) + rr(-.9, .9), len = Math.hypot(x2 - x1, y2 - y1) * rr(.12, .3);
      bolt(g, p[0], p[1], p[0] + Math.cos(ang) * len, p[1] + Math.sin(ang) * len, spread * .4, depth + 1);
    }
  }

  /* soft out-of-focus light discs in three depths: tiny and sharp, medium, large and very blurred. front=true keeps them to the poster edges so faces stay clean */
  function bokehDisc(g, x, y, r, col, a, blur) {
    g.save(); if (blur > .3) g.filter = 'blur(' + blur + 'px)';
    const rg = g.createRadialGradient(x, y, r * .15, x, y, r);
    rg.addColorStop(0, hexA(col, a * .5)); rg.addColorStop(.8, hexA(col, a * .75)); rg.addColorStop(.93, hexA(col, Math.min(1, a * 1.15))); rg.addColorStop(1, hexA(col, 0));
    g.fillStyle = rg; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); g.restore();
  }
  function paintBokeh(g, n, front) {
    g.save(); g.globalCompositeOperation = T.light ? 'source-over' : 'lighter';
    for (let i = 0; i < n; i++) {
      const t = rnd(), col = rnd() < .62 ? T.a : rnd() < .6 ? T.a2 : '#ffffff';
      let r, blur, a;
      if (t < .46) { r = rr(5, 15) * U; blur = rr(0, 1.2) * U; a = rr(.2, .55); }
      else if (t < .82) { r = rr(18, 46) * U; blur = rr(2, 5) * U; a = rr(.12, .3); }
      else { r = rr(60, 150) * U; blur = rr(10, 24) * U; a = rr(.09, .24); }
      let x = rr(0, W), y = rr(0, H);
      if (front) { r *= 1.15; a *= .8; x = rnd() < .5 ? rr(-.05, .16) * W : rr(.84, 1.05) * W; }
      bokehDisc(g, x, y, r, col, a, blur);
    }
    g.restore();
  }
  /* glowing energy arcs: smooth wavy streaks with a hot core and spark clusters (reference look: orange streaks sweeping through the scene) */
  function paintArcs(g, n, yr) {
    yr = yr || [.5, .66];
    g.save(); g.globalCompositeOperation = 'lighter'; g.lineCap = 'round'; g.lineJoin = 'round';
    for (let i = 0; i < n; i++) {
      const fromLeft = i % 2 === 0, x1 = (fromLeft ? -.05 : 1.05) * W, y1 = rr(yr[0], yr[1]) * H, x2 = (fromLeft ? 1.05 : -.05) * W, y2 = rr(yr[0] - .04, yr[1] - .02) * H;
      const c1 = [W * rr(.25, .4), H * rr(yr[0] - .08, yr[1] + .08)], c2 = [W * rr(.6, .78), H * rr(yr[0] - .08, yr[1] + .08)], ph = [rr(0, 7), rr(0, 7), rr(0, 7)];
      const pts = [];
      for (let k = 0; k <= 160; k++) {
        const t = k / 160, u = 1 - t;
        let x = u * u * u * x1 + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * x2, y = u * u * u * y1 + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * y2;
        const env = Math.sin(t * Math.PI), j = (Math.sin(t * 13 + ph[0]) * 12 + Math.sin(t * 29 + ph[1]) * 5 + Math.sin(t * 7 + ph[2]) * 16) * U * env;
        y += j; pts.push([x, y]);
      }
      const path = () => { g.beginPath(); pts.forEach((p, k) => k ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); };
      g.shadowColor = T.a2; g.shadowBlur = 60 * U; g.strokeStyle = hexA(T.a2, .22); g.lineWidth = 26 * U; path(); g.stroke();
      g.shadowBlur = 22 * U; g.strokeStyle = hexA(T.a2, .9); g.lineWidth = 6 * U; path(); g.stroke();
      g.shadowBlur = 6 * U; g.strokeStyle = 'rgba(255,255,255,.95)'; g.lineWidth = 2.2 * U; path(); g.stroke();
      g.shadowBlur = 0;
      for (let s = 0; s < 14; s++) {
        const p = pts[Math.floor(rr(.05, .95) * pts.length)], r = rr(1.4, 3.6) * U, ang = rr(-2.6, -.5), len = rr(3, 11) * U;
        const rg = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], r * 5); rg.addColorStop(0, 'rgba(255,255,255,.9)'); rg.addColorStop(.3, hexA(T.a2, .6)); rg.addColorStop(1, hexA(T.a2, 0));
        g.fillStyle = rg; g.beginPath(); g.arc(p[0], p[1], r * 5, 0, 7); g.fill();
        g.strokeStyle = hexA('#ffffff', .8); g.lineWidth = Math.max(1, r * .5); g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(p[0] + Math.cos(ang) * len, p[1] + Math.sin(ang) * len); g.stroke();
      }
    }
    g.restore();
  }
  /* concentric fingerprint-like light rings behind the subject */
  function paintSwirl(g, b) {
    const cx = W * (b.swirlX ?? .34), cy = H * (b.swirlY ?? .36), gv = typeof b.swirl === 'number' ? b.swirl : 1, M = Math.max(W, H);
    g.save(); g.globalCompositeOperation = 'screen'; g.filter = 'blur(' + .7 * U + 'px)';
    const ph = rr(0, 7), ph2 = rr(0, 7);
    for (let r = .05 * M, k = 0; r < .85 * M; r *= 1.034, k++) {
      g.strokeStyle = hexA(k % 5 === 0 ? T.soft : T.a, (k % 5 === 0 ? .2 : .1) * gv * (1 - r / (.95 * M) * .6)); g.lineWidth = (k % 5 === 0 ? 3 : 1.6) * U;
      g.beginPath();
      for (let s = 0; s <= 120; s++) {
        const ang = s / 120 * Math.PI * 2, wob = 1 + .018 * Math.sin(ang * 3 + ph + r * .01) + .01 * Math.sin(ang * 7 + ph2 + r * .02);
        const x = cx + Math.cos(ang) * r * wob * 1.08, y = cy + Math.sin(ang) * r * wob * .92;
        s ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.stroke();
    }
    g.restore();
  }

  function paintFxBack(g, fx, focus) {
    g.save(); g.globalCompositeOperation = T.light ? 'source-over' : 'lighter'; g.lineCap = 'round'; g.lineJoin = 'round';
    if (fx.bokeh) paintBokeh(g, fx.bokeh, false);
    if (fx.arcs) paintArcs(g, fx.arcs, fx.arcsY);
    for (let i = 0; i < (fx.streaks || 0); i++) {
      const y = rr(-.1, 1.1) * H, x = rr(-.1, 1) * W, len = rr(.12, .42) * W, slope = rr(.28, .36);
      const lg = g.createLinearGradient(x, y, x + len, y - len * slope);
      lg.addColorStop(0, hexA(T.a, 0)); lg.addColorStop(.5, hexA(T.a, rr(.18, .5))); lg.addColorStop(1, hexA(T.a, 0));
      g.strokeStyle = lg; g.lineWidth = rr(1.5, 9) * U; g.beginPath(); g.moveTo(x, y); g.lineTo(x + len, y - len * slope); g.stroke();
    }
    for (let i = 0; i < (fx.spikes || 0); i++) {
      const ang = rr(-Math.PI * .98, -Math.PI * .02), rad = rr(.2, .46) * Math.min(W, H) * 1.25, wid = rr(.02, .055);
      const cx = W * focus[0], cy = H * focus[1], tip = [cx + Math.cos(ang) * rad, cy + Math.sin(ang) * rad];
      const lg = g.createRadialGradient(cx, cy, 0, cx, cy, rad);
      lg.addColorStop(0, hexA(T.a, .9)); lg.addColorStop(.6, hexA(T.a2, .55)); lg.addColorStop(1, hexA(T.a, .05));
      g.fillStyle = lg; g.shadowColor = T.a; g.shadowBlur = 30 * U;
      g.beginPath(); g.moveTo(cx + Math.cos(ang - wid) * rad * .3, cy + Math.sin(ang - wid) * rad * .3); g.lineTo(tip[0], tip[1]); g.lineTo(cx + Math.cos(ang + wid) * rad * .3, cy + Math.sin(ang + wid) * rad * .3); g.closePath(); g.fill();
      g.shadowBlur = 0;
    }
    for (let i = 0; i < (fx.beams || 0); i++) {
      const x = rr(-.1, 1.1) * W, w = rr(60, 190) * U, c = i % 3 === 2 ? T.a2 : T.a, ang = rr(14, 28) * Math.PI / 180 * (focus[0] > .5 ? 1 : -1);
      g.save(); g.translate(x, -.1 * H); g.rotate(ang); g.filter = 'blur(' + rr(14, 34) * U + 'px)';
      const lg = g.createLinearGradient(0, 0, 0, 1.4 * H); lg.addColorStop(0, hexA(c, rr(.22, .42))); lg.addColorStop(.8, hexA(c, 0));
      g.fillStyle = lg; g.fillRect(-w / 2, 0, w, 1.4 * H); g.restore();
    }
    for (let i = 0; i < (fx.lightning || 0); i++) {
      const col = L.column, mid = col.x + col.w / 2, central = Math.abs(mid - .5) < .08;
      const left = central ? i % 2 === 0 : mid > .5;
      const x1 = (left ? rr(-.02, .04) : rr(.96, 1.02)) * W, y1 = rr(central ? .12 : .3, central ? col.top : .92) * H;
      const x2 = W * focus[0] + rr(-.08, .08) * W, y2 = H * focus[1] + rr(-.05, .25) * H;
      bolt(g, x1, y1, x2, y2, Math.hypot(x2 - x1, y2 - y1) * .13, 0);
    }
    g.restore();
  }

  function paintFxFront(g, fx, focus) {
    g.save(); g.globalCompositeOperation = T.light ? 'source-over' : 'lighter';
    for (let i = 0; i < (fx.sparks || 0); i++) {
      const x = rr(0, W), y = rr(0, H), r = rr(.5, 2.8) * U, len = rr(1, 9);
      g.strokeStyle = hexA(rnd() < .6 ? T.a2 : T.a, rr(.4, 1)); g.lineWidth = r; g.shadowColor = T.a; g.shadowBlur = 9 * U;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + len * U * rr(-1, 1), y - len * U * 2); g.stroke();
    }
    g.shadowBlur = 0;
    for (let i = 0; i < (fx.leaks || 0); i++) {
      const edge = i % 4, x = edge === 0 ? rr(-.1, .1) * W : edge === 1 ? rr(.9, 1.1) * W : rr(0, 1) * W, y = edge === 2 ? rr(-.1, .1) * H : edge === 3 ? rr(.9, 1.1) * H : rr(0, 1) * H, r = rr(.18, .4) * Math.max(W, H);
      const c = [T.a, T.a2, '#ff4fd8', '#36d6ff'][i % 4], rg = g.createRadialGradient(x, y, 0, x, y, r);
      rg.addColorStop(0, hexA(c, rr(.28, .5))); rg.addColorStop(1, hexA(c, 0)); g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2);
    }
    if (fx.bokehFront) paintBokeh(g, fx.bokehFront, true);
    if (fx.flare) {
      const x = W * (fx.flare[0] ?? focus[0]), y = H * (fx.flare[1] ?? focus[1]), r = (fx.flare[2] ?? .4) * Math.max(W, H);
      const rg = g.createRadialGradient(x, y, 0, x, y, r);
      rg.addColorStop(0, 'rgba(255,255,255,.95)'); rg.addColorStop(.1, hexA(T.a2, .65)); rg.addColorStop(.42, hexA(T.a, .2)); rg.addColorStop(1, hexA(T.a, 0));
      g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2);
    }
    g.restore();
  }

  /* ---------- subjects: composite-only canvas work, so file:// images never need a pixel read ---------- */
  function subjectCanvas(img, w, h, o) {
    const c = mk(w, h), g = c.getContext('2d');
    g.drawImage(img, 0, 0, c.width, c.height);
    /* soften: feather the cut edge a little (blurred silhouette multiplied into the alpha) so a hard matte never shows */
    if (o.soften !== 0) {
      const px = (o.soften ?? 1) * 1.1 * U, m = mk(c.width, c.height), mg = m.getContext('2d');
      mg.filter = 'blur(' + px + 'px)'; mg.drawImage(img, 0, 0, m.width, m.height);
      g.save(); g.globalCompositeOperation = 'destination-in'; g.drawImage(m, 0, 0); g.restore();
    }
    const sil = (color) => { const t = mk(c.width, c.height), x = t.getContext('2d'); x.fillStyle = color; x.fillRect(0, 0, t.width, t.height); x.globalCompositeOperation = 'destination-in'; x.drawImage(img, 0, 0, t.width, t.height); return t; };

    if (o.grade !== 0) {
      g.save(); g.globalCompositeOperation = 'soft-light'; g.globalAlpha = o.grade ?? .32; g.drawImage(sil(T.a), 0, 0); g.restore();
    }
    if (o.rim !== false && o.rim !== 0) {
      const strength = typeof o.rim === 'number' ? o.rim : .9;
      const rim = (color, dx, dy, blur) => {
        const t = sil(color), x = t.getContext('2d');
        x.globalCompositeOperation = 'destination-out'; x.drawImage(img, dx, dy, t.width, t.height);
        g.save(); g.globalCompositeOperation = 'lighter'; g.globalAlpha = strength; g.filter = 'blur(' + blur + 'px)'; g.drawImage(t, 0, 0); g.restore();
      };
      const k = Math.max(c.height / 150, 3);
      rim(T.a, k, k * .35, k * .55);
      rim(T.a2, -k * .7, k * .25, k * .5);
    }
    const f = o.fade || {}, cw = c.width, ch = c.height;
    Object.entries({ bottom: s => [0, ch, 0, ch * (1 - s)], top: s => [0, 0, 0, ch * s], left: s => [0, 0, cw * s, 0], right: s => [cw, 0, cw * (1 - s), 0] }).forEach(([side, line]) => {
      if (!f[side]) return;
      const lg = g.createLinearGradient.apply(g, line(f[side]));
      lg.addColorStop(0, 'rgba(0,0,0,1)'); lg.addColorStop(1, 'rgba(0,0,0,0)');
      g.save(); g.globalCompositeOperation = 'destination-out'; g.fillStyle = lg; g.fillRect(0, 0, c.width, c.height); g.restore();
    });
    return c;
  }

  async function addSubjects(list, defaults, parent) {
    for (let i = 0; i < list.length; i++) {
      const o = Object.assign({}, defaults ? defaults[Math.min(i, defaults.length - 1)] : {}, list[i]);
      const img = await load(o.src); if (!img) continue;
      const ar = img.width / img.height;
      let h = o.h ? o.h * H : (o.w ? o.w * W / ar : H * .5), w = h * ar;
      if (w / img.width > 1.6) warn('low-res subject ' + o.src + ' (' + img.width + 'x' + img.height + ') is enlarged ' + (w / img.width).toFixed(1) + 'x and will look soft');
      const c = subjectCanvas(img, w, h, o);
      c.className = 'subject';
      const x = (o.x ?? .5) * W - w / 2, y = (o.y ?? 1) * H - h;
      const filters = [];
      if (o.blur) filters.push('blur(' + o.blur * U + 'px)');
      if (o.bright) filters.push('brightness(' + o.bright + ')');
      if (o.contrast) filters.push('contrast(' + o.contrast + ')');
      if (o.saturate) filters.push('saturate(' + o.saturate + ')');
      if (o.glow !== false && o.glow !== 0 && !T.light) filters.push('drop-shadow(0 0 ' + (o.glowSize ?? 34) * U + 'px ' + T.glow + ')');
      if (T.light) filters.push('drop-shadow(0 ' + 12 * U + 'px ' + 26 * U + 'px rgba(110,60,110,.3))');
      c.style.cssText = 'left:' + x + 'px;top:' + y + 'px;width:' + w + 'px;height:' + h + 'px;opacity:' + (o.opacity ?? 1) + ';filter:' + (filters.join(' ') || 'none') + ';transform:' + (o.flip ? 'scaleX(-1) ' : '') + 'rotate(' + (o.rotate || 0) + 'deg)';
      parent.appendChild(c);
    }
  }

  /* ---------- title and text ---------- */
  function fitLine(span, target, maxH) {
    span.style.fontSize = '200px';
    const r = span.getBoundingClientRect();
    return Math.min(200 * target / r.width, maxH ? 200 * maxH / r.height : 1e9);
  }

  function buildTitle(t, column, colW) {
    const box = el('div', 'title t-' + (t.style || 'stack'), column);
    const lines = (t.lines || []).map(l => typeof l === 'string' ? { t: l } : l);
    if (t.textAlign) box.style.alignItems = { left: 'flex-start', right: 'flex-end', center: 'center' }[t.textAlign];
    if (t.kicker) { const k = el('div', 'kicker', box); k.textContent = t.kicker; k.style.fontSize = (t.kickerSize ?? 34) * U + 'px'; }
    const target = colW * (t.width ?? 1), maxH = (t.maxLine ?? (L.column.bottom - L.column.top) * .42) * H;
    const spans = lines.map((l, idx) => { const d = el('div', 'line ' + (idx % 2 ? 'l-even' : 'l-odd') + (idx === 0 ? ' l-first' : '') + (idx === lines.length - 1 ? ' l-last' : ''), box), s = el('span', null, d); s.textContent = l.t; if (l.color) { s.style.background = 'none'; s.style.color = T[l.color] || l.color; } return { s, l }; });
    const sizes = spans.map(({ s, l }) => fitLine(s, target * (l.scale ?? 1), maxH));
    const equal = t.justify === false || ['racing', 'gold', 'neon', 'bubble'].includes(t.style);
    const common = Math.min.apply(null, sizes);
    spans.forEach(({ s, l }, i) => s.style.fontSize = (equal ? common * (l.scale ?? 1) : sizes[i]) + 'px');
    if (t.sub) { const d = el('div', 'sub', box); d.textContent = t.sub; d.style.fontSize = fitLine(d, target * (t.subWidth ?? .78), 60 * U) + 'px'; }
    if (t.note) { const d = el('div', 'note', box); d.textContent = t.note; d.style.fontSize = Math.min(fitLine(d, target, 60 * U), (t.noteSize ?? 44) * U) + 'px'; }
    if (t.script) {
      const d = el('div', 'script', box); d.textContent = t.script;
      d.style.position = 'absolute'; d.style.left = (t.scriptX ?? 50) + '%'; d.style.top = (t.scriptY ?? 56) + '%';
      const size = fitLine(d, target * (t.scriptWidth ?? .95), box.getBoundingClientRect().height * 1.0);
      d.style.fontSize = size + 'px';
    }
  }

  async function buildItems(it, parent, areaW, fixed) {
    const style = it.style || ({ crimson: 'chamfer', cobalt: 'stripe', pastel: 'glass', ocean: 'glass', ember: 'dark' }[S.theme] || 'stripe');
    const n = it.list.length;
    const cols = it.cols || (n <= 3 ? n : n === 4 ? (fixed ? 2 : 4) : n <= 6 ? 3 : n <= 8 ? 4 : 5);
    const gap = areaW * (it.gap ?? .025);
    const cw = (areaW - gap * (cols - 1)) / cols;
    const g = el('div', 'cards c-' + style + (it.cardLogo ? ' has-logo' : ''), parent);
    g.style.cssText ='grid-template-columns:repeat(' + cols + ',' + cw + 'px);gap:' + gap + 'px;width:' + areaW + 'px;--c:' + cw + 'px;' + (fixed ? 'position:absolute;left:' + fixed.x * W + 'px;top:' + fixed.y * H + 'px;' : 'margin-top:' + 26 * U + 'px;');
    if (it.aspect) g.style.setProperty('--ar', it.aspect);
    /* items.opacity < 1: translucent glass cards. The solid edge becomes a ring (evenodd path in px) and the face fill gets that alpha */
    if (style === 'tag' && it.opacity !== undefined && it.opacity < 1) {
      g.classList.add('glass'); g.style.setProperty('--fa', Math.round(it.opacity * 100)); g.style.setProperty('--fan', it.opacity);
      const ch = cw * (it.aspect ?? .74), d = cw * .012, o = cw * .1, q = cw * .105, f = v => v.toFixed(2);
      g.style.setProperty('--ring', 'path(evenodd, "M' + f(o) + ' 0 L' + f(cw) + ' 0 L' + f(cw) + ' ' + f(ch - o) + ' L' + f(cw - o) + ' ' + f(ch) + ' L0 ' + f(ch) + ' L0 ' + f(o) + ' Z M' + f(q) + ' ' + f(d) + ' L' + f(cw - d) + ' ' + f(d) + ' L' + f(cw - d) + ' ' + f(ch - q) + ' L' + f(cw - q) + ' ' + f(ch - d) + ' L' + f(d) + ' ' + f(ch - d) + ' L' + f(d) + ' ' + f(q) + ' Z")');
    }
    if (it.cardLogo) g.style.setProperty('--logo', 'url("' + url(it.cardLogo) + '")');
    for (const c of it.list) {
      const card = el('div', 'card', g);
      el('div', 'face', card);
      const art = el('div', 'art', card);
      if (c.img) { const img = await load(c.img); if (img) { img.alt = ''; art.appendChild(img); if (cw * .7 / img.width > 2.5) warn('low-res item ' + c.img + ' (' + img.width + 'px) on a ' + Math.round(cw) + 'px card'); } }
      const rowHost = style === 'tag' ? el('div', 'row', card) : card;
      if (c.name) { const d = el('div', 'name', rowHost); d.textContent = c.name; }
      if (c.qty) { const d = el('div', 'qty', rowHost); d.textContent = c.qty; }
    }
    if (fixed && fixed.band) g.style.top = fixed.band[0] * H + ((fixed.band[1] - fixed.band[0]) * H - g.offsetHeight) / 2 + 'px';
    g.querySelectorAll('.row').forEach(r => {
      let fs = cw * .105; r.style.fontSize = fs + 'px';
      for (let k = 0; k < 14 && r.scrollWidth > r.clientWidth + 1; k++) { fs *= .93; r.style.fontSize = fs + 'px'; }
      const nm = r.querySelector('.name'); while (nm && nm.scrollWidth > nm.clientWidth + 1 && fs > 6) { fs *= .96; r.style.fontSize = fs + 'px'; }
    });
    { const rows = [...g.querySelectorAll('.row')]; if (rows.length) { const m = Math.min(...rows.map(r => parseFloat(r.style.fontSize))); rows.forEach(r => { r.style.fontSize = m + 'px'; }); } }
    g.querySelectorAll('.card > .name,.card > .qty').forEach(d => {
      const avail = d.clientWidth * .92; if (!avail) return;
      const m = document.createElement('span'); m.textContent = d.textContent; m.style.whiteSpace = 'nowrap'; d.textContent = ''; d.appendChild(m);
      const w = m.getBoundingClientRect().width;
      if (w > avail) d.style.fontSize = parseFloat(getComputedStyle(d).fontSize) * avail / w + 'px';
    });
  }

  const ICONS = {
    facebook: 'M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z',
    discord: 'M20.317 4.37a19.79 19.79 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.865-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.74 19.74 0 0 0 3.677 4.37a.07.07 0 0 0-.032.028C.533 9.046-.32 13.58.099 18.058a.082.082 0 0 0 .031.056 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.1 13.1 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.094.252-.192.372-.291a.074.074 0 0 1 .078-.01c3.927 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .079.009c.12.1.246.198.373.292a.077.077 0 0 1-.007.128 12.3 12.3 0 0 1-1.873.891.077.077 0 0 0-.041.107c.36.698.772 1.363 1.225 1.993a.076.076 0 0 0 .084.029 19.84 19.84 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z',
    tiktok: 'M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z'
  };

  function buildFooter(f, parent) {
    const layout = Object.assign({}, L.footer, f);
    const style = layout.style || 'chips';
    const size = (layout.size ?? (style === 'slash' ? 15 : 22)) * U;
    const box = el('div', 'footer f-' + style, parent);
    box.style.fontSize = size + 'px'; box.style.gap = size * 1.1 + 'px';
    if (style === 'slash') { box.style.padding = size * .55 + 'px ' + size * 3.2 + 'px ' + size * .55 + 'px ' + size * 1.2 + 'px'; }
    else {
      box.style.top = layout.y * H + 'px';
      if (layout.align === 'center') { box.style.left = layout.x * W + 'px'; box.style.transform = 'translate(-50%,-50%)'; }
      else if (layout.align === 'right') { box.style.right = (1 - layout.x) * W + 'px'; box.style.transform = 'translateY(-50%)'; }
      else { box.style.left = layout.x * W + 'px'; box.style.transform = 'translateY(-50%)'; }
    }
    if (T.light && style !== 'pill' && style !== 'slash') box.style.color = '#5a3a55';
    (layout.socials || []).forEach(s => {
      const chip = el('span', 'chip', box);
      if (ICONS[s.type]) { const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg'), p = document.createElementNS(ns, 'path'); svg.setAttribute('viewBox', '0 0 24 24'); svg.style.cssText = 'width:' + size * 1.05 + 'px;height:' + size * 1.05 + 'px;margin-right:' + size * .4 + 'px'; p.setAttribute('d', ICONS[s.type]); p.style.fill = ({ facebook: '#1877F2', discord: '#5865F2' })[s.type] || ''; svg.appendChild(p); chip.appendChild(svg); }
      chip.appendChild(document.createTextNode(s.text || ''));
    });
  }

  /* ---------- assemble, back to front ---------- */
  const bg = S.background || {};
  const fx = S.fx || {};
  const bgImg = bg.image ? await load(bg.image) : null;
  if (bg.watermark) bg._wm = await load(bg.watermark);
  const focus = fx.focus || [(L.hero[0].x), .46];

  const base = mk(W, H); base.className = 'layer'; root.appendChild(base);
  const bx = base.getContext('2d');
  paintBackground(bx, bgImg, bg);

  const shadeKind = S.shade ?? L.shade;
  if (shadeKind !== 'none' && !T.light) {
    const lg = shadeKind === 'left' ? bx.createLinearGradient(0, 0, W * .62, 0) : shadeKind === 'right' ? bx.createLinearGradient(W, 0, W * .38, 0) : bx.createLinearGradient(0, H, 0, H * .35);
    lg.addColorStop(0, 'rgba(0,0,0,.72)'); lg.addColorStop(1, 'rgba(0,0,0,0)');
    bx.fillStyle = lg; bx.fillRect(0, 0, W, H);
  }
  paintFxBack(bx, fx, focus);

  const heroLayer = el('div', 'layer', root);
  const props = (S.props || []);
  await addSubjects(props.filter(p => p.behind), null, heroLayer);
  await addSubjects(S.heroes || [], L.hero, heroLayer);
  await addSubjects(props.filter(p => !p.behind), null, heroLayer);

  const front = mk(W, H); front.className = 'layer'; root.appendChild(front);
  paintFxFront(front.getContext('2d'), fx, focus);

  if (!T.light && S.vignette !== 0) {
    const v = el('div', 'layer', root);
    v.style.background = 'radial-gradient(ellipse at 50% 45%, transparent 58%, rgba(0,0,0,' + (S.vignette ?? .55) + ') 100%)';
  }

  const frontShade = S.frontShade !== undefined ? S.frontShade : L.frontShade;   /* [fadeTop, solidBottom] as fractions from the bottom edge; false = off */
  if (frontShade && !T.light) {
    const v = el('div', 'layer', root);
    v.style.background = 'linear-gradient(to top, rgba(2,3,6,.96) ' + frontShade[1] * 100 + '%, rgba(2,3,6,0) ' + frontShade[0] * 100 + '%)';
  }

  /* bloom / dreamy haze: a blurred, brightened copy of everything painted so far is screened back over it */
  if (S.bloom && !T.light) {
    const bl = S.bloom === true ? {} : S.bloom, d = el('div', 'layer', root);
    d.style.backdropFilter = 'blur(' + (bl.blur ?? 18) * U + 'px) brightness(' + (bl.bright ?? 1.45) + ') saturate(' + (bl.saturate ?? 1.25) + ')';
    d.style.mixBlendMode = 'screen'; d.style.opacity = bl.alpha ?? .38;
  }

  if (S.grain !== 0) {
    const size = 512, tile = mk(size, size), x = tile.getContext('2d'), d = x.createImageData(size, size);
    for (let i = 0; i < d.data.length; i += 4) { const v = 128 + (rnd() - .5) * 150; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
    x.putImageData(d, 0, 0);
    const g = el('div', 'layer grain', root);
    g.style.backgroundImage = 'url(' + tile.toDataURL() + ')';
    g.style.opacity = S.grain ?? .22;
  }

  const col = Object.assign({}, L.column, S.column || {});
  L.column = col;
  const colW = col.w * W;
  const column = el('div', 'column a-' + col.align, root);
  column.dataset.align = col.align;
  column.style.cssText = 'left:' + col.x * W + 'px;top:' + col.top * H + 'px;height:' + (col.bottom - col.top) * H + 'px;width:' + colW + 'px;justify-content:' + col.justify;

  if (S.title) buildTitle(S.title, column, colW);
  if (S.badge) { const d = el('div', 'badge', column); d.textContent = S.badge; d.style.fontSize = (S.badgeSize ?? 30) * U + 'px'; d.style.marginTop = 16 * U + 'px'; }
  const panelRect = S.panel === false ? null : (S.panel || L.panel);
  if (panelRect) {
    const pn = el('div', 'panel', root), [px, py, pw, ph] = panelRect;
    pn.style.cssText = 'position:absolute;left:' + px * W + 'px;top:' + py * H + 'px;width:' + pw * W + 'px;height:' + ph * H + 'px;border-radius:' + 16 * U + 'px;background:linear-gradient(180deg,rgba(0,0,0,.34),rgba(0,0,0,.5));box-shadow:inset 0 0 0 ' + 1.2 * U + 'px ' + hexA(T.a, .22);
  }
  if (S.items && S.items.list && S.items.list.length) {
    const itemsArea = Object.assign({}, L.items || {}, S.items);
    if (L.itemsIn && !S.items.x) await buildItems(S.items, column, colW * (S.items.w ?? 1), null);
    else await buildItems(S.items, root, itemsArea.w * W, { x: itemsArea.x, y: itemsArea.y, band: S.items.y === undefined ? itemsArea.band : null });
  }
  if (S.title && S.title.behindHero) root.insertBefore(column, heroLayer);
  if (S.footer) buildFooter(S.footer, root);
  if (S.logo && S.logo.src) {
    const img = await load(S.logo.src);
    if (img) {
      const corner = S.logo.corner || L.logo || 'tr', m = 32 * U, w = (S.logo.w ?? .09) * W;
      img.className = 'logo'; img.style.width = w + 'px';
      img.style[corner[0] === 't' ? 'top' : 'bottom'] = m + 'px';
      img.style[corner[1] === 'l' ? 'left' : 'right'] = m + 'px';
      root.appendChild(img);
    }
  }

  /* grainTop: film grain over EVERYTHING (title, cards, footer) so text sits in the same grain as the photo, like the reference posters */
  if (S.grainTop) {
    const size = 512, tile = mk(size, size), x = tile.getContext('2d'), d = x.createImageData(size, size);
    for (let i = 0; i < d.data.length; i += 4) { const v = 128 + (rnd() - .5) * 170; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
    x.putImageData(d, 0, 0);
    const gt = el('div', 'layer grain', root);
    gt.style.backgroundImage = 'url(' + tile.toDataURL() + ')'; gt.style.opacity = S.grainTop; gt.style.mixBlendMode = 'overlay'; gt.style.pointerEvents = 'none';
  }

  /* shrink the title when the column content does not fit */
  const titleBox = column.querySelector('.title');
  for (let pass = 0; pass < 5 && titleBox && column.scrollHeight > column.clientHeight + 2; pass++) {
    const over = column.scrollHeight - column.clientHeight, th = titleBox.getBoundingClientRect().height;
    const k = Math.max(.45, (th - over - 6 * U) / th);
    titleBox.querySelectorAll('.line > span, .kicker, .sub, .note, .script').forEach(e => { e.style.fontSize = parseFloat(getComputedStyle(e).fontSize) * k + 'px'; });
  }

  /* warn about text the fit step could not keep inside the poster */
  document.querySelectorAll('.column, .cards, .footer').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.left < -1 || r.top < -1 || r.right > W + 1 || r.bottom > H + 1) warn(e.className + ' overflows the poster');
  });
  const c = column.getBoundingClientRect();
  if (column.scrollHeight > column.clientHeight + 2) warn('column content is taller than its area (' + Math.round(column.scrollHeight) + ' > ' + Math.round(c.height) + 'px): reduce items or enlarge column');
  document.title = 'ready';
})().catch(e => console.log('POSTER-ERROR ' + (e && e.stack || e)));








