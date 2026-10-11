// The 3D stage: a procedural football in a studio, then the "time gap" tracks.
// Scroll progress p in [0,1] drives the camera through the story.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const SIG = 0xff4d1a, COLD = 0x7f93a6, BONE = 0xede8df, FLOOR = -1.12;
const ease = (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
const seg = (p, a, b) => ease((p - a) / (b - a));
const L = (a, b, t) => a + (b - a) * t;

// ---------- leather: pebbled normal map + mottled colour, generated on the fly
function leather(lowPower) {
  const W = lowPower ? 768 : 1024, H = Math.round(W * 0.625);
  const hgt = new Float32Array(W * H);
  const n = Math.round(W * H * 0.04);
  for (let k = 0; k < n; k++) {
    const cx = Math.random() * W, cy = Math.random() * H, r = 1.5 + Math.random() * 1.7, r2 = r * r;
    for (let dy = -3; dy <= 3; dy++) for (let dx = -3; dx <= 3; dx++) {
      const d2 = dx * dx + dy * dy; if (d2 > r2) continue;
      const y = (cy + dy) | 0; if (y < 0 || y >= H) continue;
      const x = (((cx + dx) | 0) + W) % W;
      hgt[y * W + x] += (1 - d2 / r2) * 0.55;
    }
  }
  // four panel seams (u = 0, .25, .5, .75) with stitching dimples
  const seams = [0, 0.25, 0.5, 0.75].map((u) => Math.round(u * W));
  for (let y = 0; y < H; y++) for (const sx of seams) {
    for (let d = -6; d <= 6; d++) {
      const x = (sx + d + W) % W, a = Math.abs(d);
      if (a <= 3) hgt[y * W + x] = -2.4 * (1 - a / 4);
      else if (a === 5 && y % 9 < 4) hgt[y * W + x] += 0.9;
    }
  }
  const nrm = new ImageData(W, H), col = new ImageData(W, H);
  // low-frequency mottling
  const GX = 24, GY = 16, grid = Array.from({ length: (GX + 1) * (GY + 1) }, () => Math.random());
  const mott = (x, y) => {
    const gx = (x / W) * GX, gy = (y / H) * GY, ix = gx | 0, iy = gy | 0, fx = gx - ix, fy = gy - iy;
    const g = (i, j) => grid[Math.min(GY, j) * (GX + 1) + (i % (GX + 1))];
    return L(L(g(ix, iy), g(ix + 1, iy), fx), L(g(ix, iy + 1), g(ix + 1, iy + 1), fx), fy);
  };
  const s = 2.4;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x;
    const hl = hgt[y * W + (x - 1 + W) % W], hr = hgt[y * W + (x + 1) % W];
    const hu = hgt[Math.max(0, y - 1) * W + x], hd = hgt[Math.min(H - 1, y + 1) * W + x];
    let nx = (hl - hr) * s, ny = (hd - hu) * s, nz = 1; const l = Math.hypot(nx, ny, nz); nx /= l; ny /= l; nz /= l;
    const o = i * 4;
    nrm.data[o] = (nx * 0.5 + 0.5) * 255; nrm.data[o + 1] = (ny * 0.5 + 0.5) * 255; nrm.data[o + 2] = (nz * 0.5 + 0.5) * 255; nrm.data[o + 3] = 255;
    const m = 0.82 + 0.3 * mott(x, y) + 0.05 * hgt[i];
    const groove = hgt[i] < -0.5 ? 0.45 : 1;
    col.data[o] = Math.min(255, 118 * m * groove); col.data[o + 1] = Math.min(255, 58 * m * groove); col.data[o + 2] = Math.min(255, 28 * m * groove); col.data[o + 3] = 255;
  }
  const mk = (img, srgb) => {
    const c = document.createElement('canvas'); c.width = W; c.height = H; c.getContext('2d').putImageData(img, 0, 0);
    const t = new THREE.CanvasTexture(c); t.wrapS = THREE.RepeatWrapping; t.anisotropy = 4;
    if (srgb) t.colorSpace = THREE.SRGBColorSpace; return t;
  };
  return { normal: mk(nrm, false), color: mk(col, true) };
}

const R = 0.61, HALF = 1.0, PEXP = 0.8;
const radiusAt = (x) => R * Math.pow(Math.max(0, 1 - (x / HALF) ** 2), PEXP);

function buildFootball(lowPower) {
  const pts = [];
  for (let i = 0; i <= 72; i++) { const t = -1 + (2 * i) / 72; pts.push(new THREE.Vector2(Math.max(1e-4, radiusAt(t * HALF)), t * HALF)); }
  const geo = new THREE.LatheGeometry(pts, lowPower ? 72 : 112);
  geo.rotateZ(Math.PI / 2); // long axis along x; phi = 90deg faces +y
  const tex = leather(lowPower);
  const mat = new THREE.MeshPhysicalMaterial({
    map: tex.color, normalMap: tex.normal, normalScale: new THREE.Vector2(0.9, 0.9),
    roughness: 0.58, clearcoat: 0.22, clearcoatRoughness: 0.55, sheen: 0.3, sheenColor: new THREE.Color(0x6a3a22),
  });
  const ball = new THREE.Mesh(geo, mat); ball.castShadow = true; ball.receiveShadow = true;
  const g = new THREE.Group(); g.add(ball);
  // laces: long lace under 8 cross laces along the top seam
  const laceMat = new THREE.MeshStandardMaterial({ color: 0xf2ece1, roughness: 0.62 });
  const curve = new THREE.CatmullRomCurve3(Array.from({ length: 11 }, (_, i) => {
    const x = -0.4 + (0.8 * i) / 10; return new THREE.Vector3(x, radiusAt(x) + 0.006, 0);
  }));
  const long = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, 0.014, 6, false), laceMat); long.castShadow = true; g.add(long);
  const cross = new THREE.CapsuleGeometry(0.019, 0.17, 4, 8); cross.rotateX(Math.PI / 2);
  for (let i = 0; i < 8; i++) {
    const x = -0.33 + (0.66 * i) / 7, r = radiusAt(x), slope = (radiusAt(x + 0.01) - radiusAt(x - 0.01)) / 0.02;
    const m = new THREE.Mesh(cross, laceMat); m.position.set(x, r + 0.016, 0); m.rotation.z = Math.atan(slope); m.castShadow = true; g.add(m);
  }
  return g;
}

export function createStage(canvas, labelsEl, opts = {}) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const lowPower = /iPhone|iPad|Android/i.test(navigator.userAgent) || innerWidth < 760;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, lowPower ? 1.75 : 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setClearColor(0x0a0a0b, 1);

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0a0a0b, 9, 30);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.32;
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 120);

  // lights: warm key spot, cold fill (the TV), hot rim (the market)
  const key = new THREE.SpotLight(0xfff0dc, 95, 0, 0.5, 0.85, 1.6);
  key.position.set(2.6, 5.4, 3.6); key.castShadow = true;
  key.shadow.mapSize.set(lowPower ? 1024 : 2048, lowPower ? 1024 : 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 6;
  scene.add(key, key.target);
  const fill = new THREE.DirectionalLight(COLD, 0.55); fill.position.set(-5, 1.5, 2.5); scene.add(fill);
  const rim = new THREE.DirectionalLight(SIG, 2.4); rim.position.set(-1.8, -0.35, -4.5); scene.add(rim);
  const rim2 = new THREE.DirectionalLight(0xffd2b8, 0.7); rim2.position.set(4, 0.15, -3); scene.add(rim2);
  scene.add(new THREE.HemisphereLight(0x30343a, 0x0a0a0b, 0.6));

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({ color: 0x0f0f11, roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = FLOOR; floor.receiveShadow = true; scene.add(floor);

  // football rig: holder (position/scale) > tilt (cursor) > spin (spiral about long axis)
  const holder = new THREE.Group(), tilt = new THREE.Group(), spinG = new THREE.Group();
  spinG.add(buildFootball(lowPower)); tilt.add(spinG); holder.add(tilt); scene.add(holder);

  // ---------- tracks (built in seconds along local x)
  const LEN = (opts.worst || 62) + 9;
  const tracks = new THREE.Group(); scene.add(tracks);
  const fadeMats = [];
  const M = (o) => { const m = new THREE.MeshStandardMaterial({ transparent: true, ...o }); fadeMats.push([m, o.opacity ?? 1]); return m; };
  const B = (o) => { const m = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, ...o }); fadeMats.push([m, o.opacity ?? 1]); return m; };
  const ZM = -0.62, ZS = 0.62, LD = 0.86;
  const box = (w, hh, d, mat, x, y, z) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, hh, d), mat); m.position.set(x, y, z); tracks.add(m); return m; };
  const laneMat = M({ color: 0x18181c, roughness: 0.85 });
  box(LEN + 2, 0.04, LD, laneMat, LEN / 2 - 1, 0.02, ZM); box(LEN + 2, 0.04, LD, laneMat, LEN / 2 - 1, 0.02, ZS);
  const edgeSig = B({ color: SIG, opacity: 0.55 }), edgeCold = B({ color: COLD, opacity: 0.45 });
  box(LEN + 2, 0.05, 0.02, edgeSig, LEN / 2 - 1, 0.03, ZM - LD / 2); box(LEN + 2, 0.05, 0.02, edgeSig, LEN / 2 - 1, 0.03, ZM + LD / 2);
  box(LEN + 2, 0.05, 0.02, edgeCold, LEN / 2 - 1, 0.03, ZS - LD / 2); box(LEN + 2, 0.05, 0.02, edgeCold, LEN / 2 - 1, 0.03, ZS + LD / 2);
  const tickMat = B({ color: BONE, opacity: 0.32 }), tickMatHi = B({ color: BONE, opacity: 0.7 });
  for (let t = 0; t <= LEN - 4; t += 5) for (const z of [ZM, ZS]) box(0.22, 0.05, LD, t % 10 === 0 ? tickMatHi : tickMat, t, 0.035, z);
  const fillM = box(1, 0.06, 0.2, B({ color: SIG }), 0, 0.06, ZM);
  const fillS = box(1, 0.06, 0.2, B({ color: COLD }), 0, 0.06, ZS);
  const pilM = box(0.5, 1, LD, B({ color: SIG, opacity: 0.5, blending: THREE.AdditiveBlending }), 0, 0.5, ZM);
  const pilS = box(0.5, 1, LD, B({ color: COLD, opacity: 0.45, blending: THREE.AdditiveBlending }), 0, 0.5, ZS);
  const gapBar = box(1, 0.035, 0.035, B({ color: BONE, opacity: 0.9 }), 0, 2.0, 0);
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.4, 0.5, 48), B({ color: BONE, opacity: 0.8, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2; ring.position.set(0, 0.08, 0); tracks.add(ring);
  // price step line on the market lane
  let priceTube = null; const priceMat = B({ color: SIG });
  function buildPrice(lag) {
    if (priceTube) { tracks.remove(priceTube); priceTube.geometry.dispose(); }
    const pts = [[-1, 0.3], [lag, 0.3], [lag, 1.05], [LEN - 2, 1.05]].map(([x, y]) => new THREE.Vector3(x, y, ZM));
    const path = new THREE.CurvePath(); for (let i = 0; i < 3; i++) path.add(new THREE.LineCurve3(pts[i], pts[i + 1]));
    priceTube = new THREE.Mesh(new THREE.TubeGeometry(path, 240, 0.035, 6, false), priceMat); tracks.add(priceTube);
  }

  // ---------- HTML labels anchored in 3D
  const labels = [];
  const lab = (cls, text, local) => {
    const el = document.createElement('div'); el.className = `gl-lab ${cls}`; el.innerHTML = text; labelsEl.appendChild(el);
    const o = { el, local: new THREE.Vector3(...local), op: 0 }; labels.push(o); return o;
  };
  const Lm = lab('gl-lane gl-sig', 'MARKET', [-1.2, 0.1, ZM]);
  const Ls = lab('gl-lane gl-cold', 'YOUR STREAM', [-1.2, 0.1, ZS]);
  const ticks = []; for (let t = 0; t <= 60; t += 10) ticks.push(lab('gl-tick', `${t}s`, [t, 0.05, ZS + LD / 2 + 0.45]));
  const Lplay = lab('gl-tag', 'THE PLAY · 0.0 s', [0, 2.1, 0]);
  const Lmk = lab('gl-tag gl-sig', 'KALSHI', [0, 1.35, ZM]);
  const Lst = lab('gl-tag gl-cold', 'YOUR STREAM', [0, 1.35, ZS]);
  const Lgap = lab('gl-gap', '0.0 s', [0, 2.35, 0]);

  let lag = opts.lag ?? 2.6, delay = opts.delay ?? 48;
  buildPrice(lag);

  // ---------- layout per aspect
  let W = 1, H = 1, portrait = false, k = 0.2;
  const v3 = new THREE.Vector3(), look = new THREE.Vector3(), camPos = new THREE.Vector3();
  function layout() {
    const r = canvas.parentElement.getBoundingClientRect();
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    renderer.setSize(W, H, false); camera.aspect = W / H; camera.updateProjectionMatrix();
    portrait = W / H < 0.95;
    k = portrait ? 9.5 / LEN : Math.min(15.5, 15.5 * Math.min(1, camera.aspect / 1.6)) / LEN;
    tracks.scale.set(k, 1, 1);
    tracks.rotation.y = portrait ? -Math.PI / 2 : 0;
    if (portrait) tracks.position.set(0, FLOOR, -(LEN * k) / 2 + 0.6); else tracks.position.set(-(LEN * k) / 2 + 0.7, FLOOR, 0);
  }
  const worldOf = (t, y = 0, z = 0) => tracks.localToWorld(v3.set(t, y, z)).clone();

  // ---------- interaction
  const ptr = { x: 0, y: 0, tx: 0, ty: 0 };
  addEventListener('pointermove', (e) => { ptr.tx = (e.clientX / innerWidth) * 2 - 1; ptr.ty = (e.clientY / innerHeight) * 2 - 1; }, { passive: true });
  addEventListener('deviceorientation', (e) => {
    if (e.gamma == null) return; ptr.tx = Math.max(-1, Math.min(1, e.gamma / 30)); ptr.ty = Math.max(-1, Math.min(1, (e.beta - 50) / 30));
  }, { passive: true });

  let p = 0, pT = 0, spin = 0, spinVel = 0, hop = 0, hopVel = 0, rimBoost = 0, t = 0;
  function kick() { if (reduce) { rimBoost = 1; return; } spinVel += 16; hopVel = 3.4; rimBoost = 1; }

  function update(dt) {
    t += dt;
    p += (pT - p) * Math.min(1, dt * (reduce ? 20 : 5));
    ptr.x += (ptr.tx - ptr.x) * Math.min(1, dt * 3); ptr.y += (ptr.ty - ptr.y) * Math.min(1, dt * 3);

    // ---- football
    spinVel *= Math.pow(0.35, dt); spin += (reduce ? 0 : 0.45 + spinVel) * dt;
    hopVel -= 9.8 * dt; hop += hopVel * dt; if (hop < 0) { hop = 0; hopVel = Math.abs(hopVel) > 1.2 ? -hopVel * 0.35 : 0; }
    spinG.rotation.x = spin;
    tilt.rotation.z = 0.42 + ptr.x * 0.22 + (reduce ? 0 : Math.sin(t * 0.7) * 0.03);
    tilt.rotation.y = -0.62 + ptr.x * 0.38;
    tilt.rotation.x = 0.12 + ptr.y * 0.18;
    const fly = seg(p, 0.05, 0.22);
    const playPos = worldOf(0, 1.0, 0);
    const heroPos = new THREE.Vector3(0, 0.05 + (reduce ? 0 : Math.sin(t * 1.1) * 0.05), 0);
    holder.position.lerpVectors(heroPos, playPos, fly);
    holder.position.y += Math.sin(Math.PI * fly) * 1.4 + hop;
    const sc = L(portrait ? 0.82 : 1, portrait ? 0.32 : 0.36, fly); holder.scale.setScalar(sc);
    rimBoost *= Math.pow(0.2, dt); rim.intensity = 2.4 + rimBoost * 6;

    // ---- tracks
    const fade = seg(p, 0.06, 0.2);
    tracks.visible = fade > 0.001;
    for (const [m, o] of fadeMats) m.opacity = o * fade;
    const pm = seg(p, 0.33, 0.49);       // market reacts (step 2 at p=.5)
    const ps = seg(p, 0.55, 0.78);       // stream catches up (step 3 at p=.75)
    const tm = lag * pm, ts = delay * ps;
    fillM.scale.x = Math.max(0.001, tm); fillM.position.x = tm / 2;
    fillS.scale.x = Math.max(0.001, ts); fillS.position.x = ts / 2;
    pilM.position.x = lag; pilM.scale.y = Math.max(0.001, 1.6 * pm); pilM.position.y = 0.8 * pm;
    pilS.position.x = ts; pilS.scale.y = Math.max(0.001, 1.6 * ps); pilS.position.y = 0.8 * ps;
    const gapA = lag, gapB = Math.max(lag, ts);
    gapBar.scale.x = Math.max(0.001, gapB - gapA); gapBar.position.x = (gapA + gapB) / 2; gapBar.visible = ps > 0.02;
    const rf = seg(p, 0.18, 0.32); ring.scale.setScalar(1 + rf * 5); ring.material.opacity = 0.8 * fade * (1 - rf);
    if (priceTube) { const idx = priceTube.geometry.index.count; const frac = 0.06 + 0.94 * pm; priceTube.geometry.setDrawRange(0, Math.floor((frac * idx) / 36) * 36); }

    // ---- camera
    const D0 = portrait ? 11.2 : 6.0;
    const heroLook = portrait ? new THREE.Vector3(0, -1.55, 0) : new THREE.Vector3(-1.25, 0.05, 0);
    const heroCam = portrait ? new THREE.Vector3(0, -1.0, D0) : new THREE.Vector3(-1.25, 0.42, D0);
    const mid = worldOf(LEN / 2 - 4, 0, 0);
    const half = (LEN * k) / 2 + (portrait ? 0.4 : 1.2);
    const tanH = Math.tan(THREE.MathUtils.degToRad(16));
    let D, dir;
    if (portrait) { D = (half * 0.92 + 1.4) / tanH; dir = new THREE.Vector3(0, 0.88, 0.47).normalize(); }
    else { D = half / (tanH * camera.aspect) + 1; dir = new THREE.Vector3(0, 0.6, 0.8).normalize(); }
    const ovLook = mid.clone().add(new THREE.Vector3(0, 0.3, portrait ? 0.4 : 0.35));
    const ovCam = ovLook.clone().addScaledVector(dir, D);
    const gapMid = worldOf((lag + delay) / 2, 0.6, 0);
    const endLook = ovLook.clone().lerp(gapMid, 0.35);
    const endCam = endLook.clone().addScaledVector(dir.clone().add(new THREE.Vector3(portrait ? 0 : -0.12, -0.08, 0)).normalize(), D * 0.9);
    const c1 = seg(p, 0.05, 0.24), c2 = seg(p, 0.8, 1);
    look.lerpVectors(heroLook, ovLook, c1).lerp(endLook, c2);
    camPos.lerpVectors(heroCam, ovCam, c1).lerp(endCam, c2);
    if (!reduce) { camPos.x += ptr.x * 0.12 * (1 - c1); camPos.y -= ptr.y * 0.08 * (1 - c1); }
    camera.position.copy(camPos); camera.lookAt(look);
    scene.fog.near = L(9, D * 0.85, c1); scene.fog.far = L(30, D * 2.4, c1);
    key.target.position.lerpVectors(new THREE.Vector3(0, 0, 0), mid, c1);
    key.angle = L(0.5, portrait ? 0.9 : 0.75, c1);
    key.position.lerpVectors(new THREE.Vector3(2.6, 5.4, 3.6), mid.clone().add(new THREE.Vector3(1, 9, 5)), c1);

    // ---- labels
    const setOp = (o, v) => { o.op = v; };
    setOp(Lm, fade); setOp(Ls, fade); ticks.forEach((o) => setOp(o, fade * 0.9));
    setOp(Lplay, fade * (1 - seg(p, 0.52, 0.6)));
    setOp(Lmk, pm); setOp(Lst, ps > 0.01 ? 1 : 0); setOp(Lgap, ps > 0.03 ? 1 : 0);
    Lmk.local.set(lag, 1.9, ZM); Lmk.el.textContent = `KALSHI +${lag.toFixed(1)}s`;
    Lst.local.set(ts, 1.9, ZS); Lst.el.textContent = `YOUR STREAM +${ts.toFixed(1)}s`;
    Lgap.local.set((gapA + gapB) / 2, 2.25, 0); Lgap.el.innerHTML = `<b>${Math.max(0, ts - lag).toFixed(1)}</b> s ahead`;
    for (const o of labels) {
      if (o.op < 0.01) { if (o.el.style.opacity !== '0') o.el.style.opacity = '0'; continue; }
      const w = tracks.localToWorld(v3.copy(o.local)); w.project(camera);
      const x = (w.x * 0.5 + 0.5) * W, y = (-w.y * 0.5 + 0.5) * H;
      o.el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      o.el.style.opacity = (w.z < 1 ? o.op : 0).toFixed(2);
    }
  }

  let running = false, last = 0, raf = 0;
  function frame(now) {
    if (!running) return;
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    update(dt); renderer.render(scene, camera);
  }
  function setActive(on) {
    if (on === running) return;
    running = on; last = 0;
    if (on) raf = requestAnimationFrame(frame); else cancelAnimationFrame(raf);
  }
  layout();
  addEventListener('resize', () => { layout(); if (!running) { update(0.016); renderer.render(scene, camera); } });
  document.addEventListener('visibilitychange', () => setActive(!document.hidden && stageVisible));
  let stageVisible = true;
  update(0.016); renderer.render(scene, camera); setActive(true);

  return {
    setProgress(v) { pT = Math.max(0, Math.min(1, v)); },
    setNumbers(o) { if (o.lag != null && o.lag !== lag) { lag = o.lag; buildPrice(lag); } if (o.delay != null) delay = o.delay; },
    kick,
    setVisible(v) { stageVisible = v; setActive(v && !document.hidden); },
  };
}
