/* 3D wiring viewer for the LoRa Campus Monitor.
 * Pin numbers match connections/*.txt, esp32-node/include/board_config.h
 * and raspberry-pi/config/config.toml. Units are arbitrary (~0.5 cm).
 */
(function () {
  'use strict';

  // Wire colour guide (FILE 2).
  const WIRE = {
    red: { hex: 0xd62828, name: 'Red · 5 V' },
    orange: { hex: 0xf77f00, name: 'Orange · 3.3 V' },
    black: { hex: 0x1f1f1f, name: 'Black · GND' },
    blue: { hex: 0x2563eb, name: 'Blue · I2C SDA' },
    cyan: { hex: 0x06b6d4, name: 'Cyan · I2C SCL' },
    yellow: { hex: 0xfacc15, name: 'Yellow · SPI SCK' },
    green: { hex: 0x16a34a, name: 'Green · SPI MISO' },
    purple: { hex: 0x7c3aed, name: 'Purple · SPI MOSI' },
    white: { hex: 0xf8fafc, name: 'White · SPI NSS/CS' },
    brown: { hex: 0x8b5a2b, name: 'Brown · RESET' },
    gray: { hex: 0x9ca3af, name: 'Gray · DIO0' },
    magenta: { hex: 0xd946ef, name: 'Magenta · Analog' },
  };

  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const LABEL_SCALE = 1.45;

  // ------------------------------------------------------------------ renderer
  const view = document.getElementById('view');
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  view.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xe9edf2);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 1000);
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotateSpeed = 0.8;

  scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 0.75);
  sun.position.set(25, 45, 30);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -45, right: 45, top: 45, bottom: -45, near: 1, far: 150 });
  scene.add(sun);

  const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshStandardMaterial({ color: 0xdfe4ea, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.6;
  ground.receiveShadow = true;
  scene.add(ground);

  // ------------------------------------------------------------------ helpers
  let root = null;          // group holding the current scene
  let wires = [];           // { mesh, info, color, row }
  let pinLabelSprites = [];
  let animations = [];

  function mat(color, opts = {}) {
    return new THREE.MeshStandardMaterial(Object.assign({ color, roughness: 0.55, metalness: 0.1 }, opts));
  }

  function box(w, h, d, color, x, y, z, opts) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color, opts));
    m.position.set(x, y + h / 2, z);
    m.castShadow = true;
    m.receiveShadow = true;
    root.add(m);
    return m;
  }

  function cyl(r, h, color, x, y, z, opts, axis) {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 24), mat(color, opts));
    if (axis === 'x') { m.rotation.z = Math.PI / 2; m.position.set(x, y, z); }
    else if (axis === 'z') { m.rotation.x = Math.PI / 2; m.position.set(x, y, z); }
    else m.position.set(x, y + h / 2, z);
    m.castShadow = true;
    root.add(m);
    return m;
  }

  function sprite(text, x, y, z, opts = {}) {
    const size = opts.size || 1;
    const fg = opts.color || '#111827';
    const bg = opts.bg === undefined ? 'rgba(255,255,255,0.92)' : opts.bg;
    const lines = String(text).split('\n');
    const fontPx = 64;
    const c = document.createElement('canvas');
    const ctx = c.getContext('2d');
    ctx.font = `${opts.bold ? '700' : '600'} ${fontPx}px system-ui, sans-serif`;
    const w = Math.max(...lines.map(l => ctx.measureText(l).width)) + 40;
    const h = lines.length * fontPx * 1.2 + 24;
    c.width = Math.ceil(w); c.height = Math.ceil(h);
    ctx.font = `${opts.bold ? '700' : '600'} ${fontPx}px system-ui, sans-serif`;
    if (bg) {
      ctx.fillStyle = bg;
      const r = 22;
      ctx.beginPath();
      ctx.moveTo(r, 0); ctx.arcTo(c.width, 0, c.width, c.height, r); ctx.arcTo(c.width, c.height, 0, c.height, r);
      ctx.arcTo(0, c.height, 0, 0, r); ctx.arcTo(0, 0, c.width, 0, r); ctx.fill();
      if (opts.border) { ctx.strokeStyle = opts.border; ctx.lineWidth = 6; ctx.stroke(); }
    }
    ctx.fillStyle = fg;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    lines.forEach((l, i) => ctx.fillText(l, c.width / 2, 12 + fontPx * 0.6 + i * fontPx * 1.2));
    const tex = new THREE.CanvasTexture(c);
    tex.anisotropy = 4;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthWrite: false, depthTest: opts.depthTest !== false }));
    const worldH = size * lines.length * 0.75 * LABEL_SCALE;
    s.scale.set(worldH * c.width / c.height, worldH, 1);
    s.position.set(x, y, z);
    s.renderOrder = 10;
    root.add(s);
    return s;
  }

  // Header pin: returns the world position of the pin tip (wire attachment point).
  function pin(x, y, z, label, opts = {}) {
    const h = opts.h || 0.7;
    const base = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.25, 0.42), mat(0x111111));
    base.position.set(x, y + 0.125, z);
    root.add(base);
    const p = new THREE.Mesh(new THREE.BoxGeometry(0.12, h, 0.12), mat(0xd4af37, { metalness: 0.8, roughness: 0.3 }));
    p.position.set(x, y + 0.25 + h / 2, z);
    root.add(p);
    if (label && opts.label !== false) {
      const off = opts.labelOffset || [0, 0, 0];
      const s = sprite(label, x + off[0], y + h + 0.9 + off[1], z + off[2], {
        size: opts.labelSize || 0.55, color: opts.labelColor || '#111827', bg: opts.labelBg,
      });
      pinLabelSprites.push(s);
    }
    return V(x, y + 0.25 + h, z);
  }

  function resistor(a, b, bands, label) {
    const dir = b.clone().sub(a);
    const len = dir.length();
    const mid = a.clone().add(b).multiplyScalar(0.5);
    const lead = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, len, 8), mat(0xbfbfbf, { metalness: 0.9 }));
    lead.position.copy(mid);
    lead.quaternion.setFromUnitVectors(V(0, 1, 0), dir.clone().normalize());
    root.add(lead);
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, len * 0.5, 16), mat(0xe8d3a5));
    body.position.copy(mid);
    body.quaternion.copy(lead.quaternion);
    body.castShadow = true;
    root.add(body);
    bands.forEach((c, i) => {
      const band = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, len * 0.05, 16), mat(c));
      band.quaternion.copy(lead.quaternion);
      band.position.copy(mid).add(dir.clone().normalize().multiplyScalar((i - (bands.length - 1) / 2) * len * 0.09));
      root.add(band);
    });
    if (label) sprite(label, mid.x, mid.y + 1.1, mid.z, { size: 0.55, bg: 'rgba(255,248,230,0.95)' });
  }

  function capacitor(a, b, kind, label) {
    const mid = a.clone().add(b).multiplyScalar(0.5);
    [a, b].forEach(p => {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 1.0, 6), mat(0xbfbfbf, { metalness: 0.9 }));
      leg.position.set(p.x, p.y + 0.5, p.z);
      root.add(leg);
    });
    if (kind === 'ceramic') {
      const disc = cyl(0.55, 0.22, 0xe7b416, mid.x, mid.y + 1.4, mid.z, {}, 'z');
      disc.castShadow = true;
    } else {
      cyl(0.5, 1.4, 0x1e3a8a, mid.x, mid.y + 0.9, mid.z);
      box(0.12, 1.4, 1.0, 0xcbd5e1, mid.x - 0.42, mid.y + 0.9, mid.z);
    }
    if (label) sprite(label, mid.x, mid.y + 3.0, mid.z, { size: 0.5, bg: 'rgba(255,248,230,0.95)' });
    return [V(a.x, a.y + 0.1, a.z), V(b.x, b.y + 0.1, b.z)];
  }

  function solderDot(p, color = 0xb0b0b0) {
    const s = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 12), mat(color, { metalness: 0.7, roughness: 0.3 }));
    s.position.copy(p);
    root.add(s);
    return p;
  }

  function antenna(x, y, z, height = 9) {
    cyl(0.18, 0.8, 0xc0c0c0, x, y, z, { metalness: 0.9 });
    cyl(0.35, height, 0x111111, x, y + 0.8, z);
    const tip = new THREE.Mesh(new THREE.SphereGeometry(0.38, 16, 16), mat(0x111111));
    tip.position.set(x, y + 0.8 + height, z);
    root.add(tip);
    return V(x, y + 0.8 + height, z);
  }

  // A coloured wire (tube) between two points with an arched route.
  function wire(a, b, color, info, opts = {}) {
    const dist = a.distanceTo(b);
    const lift = opts.lift !== undefined ? opts.lift : 1.0 + dist * 0.12;
    const up = Math.max(a.y, b.y) + lift;
    const pts = opts.points || [
      a,
      V(a.x, a.y + lift * 0.45, a.z),
      V(a.x + (b.x - a.x) * 0.25, up, a.z + (b.z - a.z) * 0.25),
      V(a.x + (b.x - a.x) * 0.75, up, a.z + (b.z - a.z) * 0.75),
      V(b.x, b.y + lift * 0.45, b.z),
      b,
    ];
    const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    const geo = new THREE.TubeGeometry(curve, Math.max(32, Math.round(dist * 4)), opts.radius || 0.11, 10, false);
    const w = WIRE[color];
    const m = new THREE.Mesh(geo, mat(w.hex, { roughness: 0.35, emissive: 0x000000 }));
    m.castShadow = true;
    m.userData.wireIndex = wires.length;
    root.add(m);
    wires.push({ mesh: m, info, color, group: opts.group || 'Connections', note: opts.note || '' });
    return m;
  }

  function rail(x1, x2, z, y, color, label) {
    const r = box(x2 - x1, 0.12, 0.55, color, (x1 + x2) / 2, y, z, { metalness: 0.6, roughness: 0.35 });
    if (label) sprite(label, x1 - 2.2, y + 0.7, z, { size: 0.55, bg: 'rgba(255,255,255,0.95)' });
    return (x) => V(x, y + 0.13, z);
  }

  function perfboard(w, d, color = 0x2f6f3e) {
    box(w, 0.25, d, color, 0, -0.25, 0, { roughness: 0.9 });
    // hole grid (visual only)
    const holes = new THREE.Group();
    const g = new THREE.CylinderGeometry(0.07, 0.07, 0.02, 6);
    const m = mat(0xc9a227, { metalness: 0.7 });
    for (let x = -w / 2 + 1; x < w / 2; x += 1.27)
      for (let z = -d / 2 + 1; z < d / 2; z += 1.27) {
        const h = new THREE.Mesh(g, m);
        h.position.set(x, 0.01, z);
        holes.add(h);
      }
    root.add(holes);
  }

  // ------------------------------------------------------------------ modules
  function ra02Module(cx, cz, rot) {
    // Adapter PCB + shielded Ra-02 + 8 pins along the edge facing +z (rot=0).
    box(6.2, 0.18, 5.4, 0x1d4ed8, cx, 0.6, cz);
    box(4.2, 0.5, 4.2, 0xcfd6de, cx - 0.4, 0.78, cz - 0.4, { metalness: 0.85, roughness: 0.25 });
    sprite('SX1278 · Ra-02\n433 MHz LoRa', cx - 0.4, 3.0, cz - 0.4, { size: 0.75, bold: true, bg: 'rgba(255,255,255,0.95)' });
    // pin standoffs
    box(6.2, 0.6, 0.6, 0x111111, cx, 0, cz + 2.35);
    const names = ['VCC', 'GND', 'SCK', 'MISO', 'MOSI', 'NSS', 'RST', 'DIO0'];
    const pins = {};
    names.forEach((n, i) => {
      const x = cx - 2.8 + i * 0.8;
      pins[n] = pin(x, 0.78, cz + 2.35, n, { labelOffset: [0, 0, 0.9 + (i % 2) * 1.0], labelSize: 0.42 });
    });
    // IPEX socket
    const ipex = V(cx + 2.4, 1.3, cz - 2.2);
    cyl(0.3, 0.3, 0xd4af37, ipex.x, 0.78, ipex.z, { metalness: 0.9 });
    pins.IPEX = ipex;
    return pins;
  }

  function antennaWithCable(fromPt, ax, az) {
    const top = antenna(ax, 0, az, 10);
    const cable = new THREE.CatmullRomCurve3([fromPt, V(fromPt.x, fromPt.y + 1.2, fromPt.z), V(ax, 1.2, az), V(ax, 0.4, az)]);
    const m = new THREE.Mesh(new THREE.TubeGeometry(cable, 40, 0.07, 8), mat(0x6b7280));
    root.add(m);
    sprite('433 MHz antenna\n(fit before power-on)', ax, top.y + 1.8, az, { size: 0.6, bg: 'rgba(255,255,255,0.95)' });
    return top;
  }

  function esp32(cx, cz) {
    // DevKit V1 30-pin. Row A (+z) = EN…VIN, Row B (-z) = GPIO23…3V3, USB at +x.
    box(13.0, 0.3, 6.0, 0x1f2937, cx, 0.9, cz);
    box(4.6, 0.6, 3.6, 0xb8c0c8, cx - 3.4, 1.2, cz, { metalness: 0.85, roughness: 0.25 }); // WROOM shield
    box(1.6, 0.5, 3.6, 0x1e3a8a, cx - 6.1, 1.2, cz); // PCB antenna area
    box(1.4, 0.7, 1.8, 0xc0c0c0, cx + 6.3, 1.2, cz, { metalness: 0.9 }); // micro-USB
    box(0.7, 0.3, 0.7, 0x111111, cx + 2.2, 1.2, cz - 1.3);
    box(0.5, 0.25, 0.5, 0xeeeeee, cx + 4.2, 1.2, cz + 1.2);
    box(0.5, 0.25, 0.5, 0xeeeeee, cx + 4.2, 1.2, cz - 1.2);
    sprite('ESP32 DevKit V1', cx - 3.4, 3.1, cz, { size: 0.8, bold: true });
    // headers
    box(11.6, 0.9, 0.6, 0x111111, cx, 0, cz + 2.6);
    box(11.6, 0.9, 0.6, 0x111111, cx, 0, cz - 2.6);
    const rowA = ['EN', 'VP', 'VN', '34', '35', '32', '33', '25', '26', '27', '14', '12', '13', 'GND', 'VIN'];
    const rowB = ['23', '22', 'TX0', 'RX0', '21', '19', '18', '5', 'TX2', 'RX2', '4', '2', '15', 'GND', '3V3'];
    const used = new Set(['34', '35', '32', '26', '14', 'GND', 'VIN', '23', '22', '21', '19', '18', '5', '3V3']);
    const pins = {};
    rowA.forEach((n, i) => {
      const x = cx - 5.25 + i * 0.75;
      const key = n === 'GND' ? 'GND_A' : n;
      pins[key] = pin(x, 1.2, cz + 2.6, n, {
        label: used.has(n), labelOffset: [0, 0, 1.1 + (i % 2) * 1.1], labelSize: 0.42, labelBg: 'rgba(254,249,195,0.95)',
      });
    });
    rowB.forEach((n, i) => {
      const x = cx - 5.25 + i * 0.75;
      const key = n === 'GND' ? 'GND_B' : n;
      pins[key] = pin(x, 1.2, cz - 2.6, n, {
        label: used.has(n), labelOffset: [0, 0, -1.1 - (i % 2) * 1.1], labelSize: 0.42, labelBg: 'rgba(254,249,195,0.95)',
      });
    });
    sprite('numbers = GPIO', cx + 2.0, 2.4, cz + 0.6, { size: 0.32, bg: null, color: '#e5e7eb' });
    return pins;
  }

  function smallModule(cx, cz, w, d, color, title, pinNames, opts = {}) {
    box(w, 0.18, d, color, cx, 0.9, cz);
    box(w, 0.9, 0.55, 0x111111, cx, 0, cz + (opts.pinsBack ? -d / 2 + 0.3 : d / 2 - 0.3));
    const pinsZ = cz + (opts.pinsBack ? -d / 2 + 0.3 : d / 2 - 0.3);
    const pins = {};
    const step = Math.min(0.75, (w - 0.6) / Math.max(1, pinNames.length - 1));
    pinNames.forEach((n, i) => {
      const x = cx - (step * (pinNames.length - 1)) / 2 + i * step;
      const off = 0.9 + (i % 2) * 0.95;
      pins[n] = pin(x, 0.9, pinsZ, n, { labelOffset: [0, 0, opts.pinsBack ? -off : off], labelSize: 0.38 });
    });
    sprite(title, cx, opts.titleY || 3.4, cz, { size: 0.65, bold: true });
    return pins;
  }

  // ------------------------------------------------------------------ scenes
  function buildFieldNode(nodeId) {
    perfboard(44, 34);
    sprite(`ESP32 FIELD NODE ${nodeId}  ·  NODE_ID = ${nodeId}`, -4, 2.5, 19.5,
      { size: 1.1, bold: true, color: '#ffffff', bg: 'rgba(17,24,39,0.92)' });

    // Power rails
    const r33b = rail(-19, 19, -13.2, 0, 0xf77f00, '3.3 V');
    const gndb = rail(-19, 19, -14.4, 0, 0x222222, 'GND');
    const r33f = rail(-19, 19, 12.0, 0, 0xf77f00, '3.3 V');
    const r5f = rail(-19, 19, 13.2, 0, 0xd62828, '5 V');
    const gndf = rail(-19, 19, 14.4, 0, 0x222222, 'GND');

    wire(r33b(19.6), r33f(19.6), 'orange', '3.3 V rail (back) ↔ 3.3 V rail (front)', { group: 'Power', lift: 1.2 });
    wire(gndb(20.3), gndf(20.3), 'black', 'GND rail (back) ↔ GND rail (front)', { group: 'Power', lift: 1.6 });

    // 5 V adapter jack
    box(2.4, 1.6, 2.0, 0x111111, 19.5, 0, 16.2);
    cyl(0.5, 1.6, 0x444444, 20.9, 0.8, 16.2, {}, 'x');
    const plug = new THREE.CatmullRomCurve3([V(21.6, 0.8, 16.2), V(25, 0.6, 16.5), V(29, 0.3, 18)]);
    root.add(new THREE.Mesh(new THREE.TubeGeometry(plug, 30, 0.22, 8), mat(0x111111)));
    sprite('5 V regulated adapter\n(≥ 1 A)', 27, 3.0, 18, { size: 0.7 });
    wire(V(19.0, 1.7, 15.6), r5f(17.5), 'red', '5 V adapter (+) → 5 V rail', { group: 'Power' });
    wire(V(20.0, 1.7, 15.6), gndf(18.5), 'black', '5 V adapter (−) → GND rail', { group: 'Power' });

    // ESP32
    const e = esp32(0, 0);
    wire(e.VIN, r5f(5.25), 'red', 'ESP32 VIN → 5 V rail', { group: 'Power' });
    wire(e.GND_A, gndf(4.5), 'black', 'ESP32 GND → GND rail (front)', { group: 'Power' });
    wire(e['3V3'], r33b(5.25), 'orange', 'ESP32 3V3 → 3.3 V rail (back)', { group: 'Power' });
    wire(e.GND_B, gndb(4.5), 'black', 'ESP32 GND → GND rail (back)', { group: 'Power' });

    // Ra-02 LoRa
    const r = ra02Module(10.5, -7.5);
    wire(r.VCC, r33b(7.7), 'orange', 'Ra-02 VCC → 3.3 V rail  (3.3 V ONLY!)', { group: 'LoRa SX1278 / Ra-02' });
    wire(r.GND, gndb(8.5), 'black', 'Ra-02 GND → GND rail', { group: 'LoRa SX1278 / Ra-02' });
    wire(e['18'], r.SCK, 'yellow', 'ESP32 GPIO18 → Ra-02 SCK', { group: 'LoRa SX1278 / Ra-02' });
    wire(e['19'], r.MISO, 'green', 'ESP32 GPIO19 → Ra-02 MISO', { group: 'LoRa SX1278 / Ra-02' });
    wire(e['23'], r.MOSI, 'purple', 'ESP32 GPIO23 → Ra-02 MOSI', { group: 'LoRa SX1278 / Ra-02' });
    wire(e['5'], r.NSS, 'white', 'ESP32 GPIO5 → Ra-02 NSS (CS)', { group: 'LoRa SX1278 / Ra-02' });
    wire(e['14'], r.RST, 'brown', 'ESP32 GPIO14 → Ra-02 RESET', { group: 'LoRa SX1278 / Ra-02', lift: 5.5 });
    wire(e['26'], r.DIO0, 'gray', 'ESP32 GPIO26 → Ra-02 DIO0', { group: 'LoRa SX1278 / Ra-02', lift: 6.5 });
    const [c1a, c1b] = capacitor(V(15.2, 0.0, -11.2), V(15.2, 0.0, -9.6), 'ceramic', '100 nF');
    const [c2a, c2b] = capacitor(V(17.0, 0.0, -11.2), V(17.0, 0.0, -9.6), 'electrolytic', '10 µF');
    wire(c1a, r33b(15.2), 'orange', '100 nF decoupling: Ra-02 VCC side → 3.3 V', { group: 'LoRa SX1278 / Ra-02', lift: 0.6 });
    wire(c1b, gndb(15.9), 'black', '100 nF decoupling: GND side', { group: 'LoRa SX1278 / Ra-02', lift: 0.9 });
    wire(c2a, r33b(17.0), 'orange', '10 µF decoupling: + → 3.3 V', { group: 'LoRa SX1278 / Ra-02', lift: 0.6 });
    wire(c2b, gndb(17.7), 'black', '10 µF decoupling: − → GND', { group: 'LoRa SX1278 / Ra-02', lift: 0.9 });
    antennaWithCable(r.IPEX, 12.0, -12.0);

    // BME280
    const b = smallModule(-13, -8, 3.6, 3.0, 0x6d28d9, 'BME280\n0x76', ['VCC', 'GND', 'SCL', 'SDA', 'CSB', 'SDO']);
    wire(b.VCC, r33b(-14.9), 'orange', 'BME280 VCC → 3.3 V rail', { group: 'BME280 (I2C 0x76)' });
    wire(b.GND, gndb(-14.2), 'black', 'BME280 GND → GND rail', { group: 'BME280 (I2C 0x76)' });
    wire(e['22'], b.SCL, 'cyan', 'ESP32 GPIO22 → BME280 SCL', { group: 'BME280 (I2C 0x76)' });
    wire(e['21'], b.SDA, 'blue', 'ESP32 GPIO21 → BME280 SDA', { group: 'BME280 (I2C 0x76)' });
    wire(b.CSB, r33b(-11.6), 'orange', 'BME280 CSB → 3.3 V (I2C mode)', { group: 'BME280 (I2C 0x76)' });
    wire(b.SDO, gndb(-11.0), 'black', 'BME280 SDO → GND (address 0x76)', { group: 'BME280 (I2C 0x76)' });

    // BH1750
    const l = smallModule(-4.5, -8, 3.4, 2.6, 0x0e7490, 'BH1750\n0x23', ['VCC', 'GND', 'SCL', 'SDA', 'ADDR']);
    const dome = new THREE.Mesh(new THREE.SphereGeometry(0.45, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2), mat(0xf8fafc));
    dome.position.set(-4.5, 1.08, -8.6);
    root.add(dome);
    wire(l.VCC, r33b(-6.0), 'orange', 'BH1750 VCC → 3.3 V rail', { group: 'BH1750 (I2C 0x23)' });
    wire(l.GND, gndb(-5.3), 'black', 'BH1750 GND → GND rail', { group: 'BH1750 (I2C 0x23)' });
    wire(e['22'], l.SCL, 'cyan', 'ESP32 GPIO22 → BH1750 SCL (shared bus)', { group: 'BH1750 (I2C 0x23)', lift: 2.6 });
    wire(e['21'], l.SDA, 'blue', 'ESP32 GPIO21 → BH1750 SDA (shared bus)', { group: 'BH1750 (I2C 0x23)', lift: 2.2 });
    wire(l.ADDR, gndb(-2.5), 'black', 'BH1750 ADDR → GND (address 0x23)', { group: 'BH1750 (I2C 0x23)' });

    // MQ-135 + divider
    const mq = smallModule(-15.5, 8, 3.6, 3.2, 0x1d4ed8, 'MQ-135\n(5 V heater)', ['VCC', 'GND', 'DO', 'AO'], { pinsBack: true, titleY: 4.6 });
    cyl(1.05, 1.6, 0x9ca3af, -15.5, 1.08, 8.3, { metalness: 0.8, roughness: 0.4 });
    cyl(0.9, 0.05, 0x6b7280, -15.5, 2.7, 8.3);
    wire(mq.VCC, r5f(-17.6), 'red', 'MQ-135 VCC → 5 V rail', { group: 'MQ-135 + divider → GPIO34' });
    wire(mq.GND, gndf(-16.6), 'black', 'MQ-135 GND → GND rail', { group: 'MQ-135 + divider → GPIO34' });
    sprite('DO: not connected', -14.0, 2.2, 5.0, { size: 0.4, color: '#6b7280' });

    const J = solderDot(V(-8.5, 0.35, 6.5));
    const r1a = V(-11.8, 0.35, 6.5);
    resistor(r1a, J, [0x8b4513, 0x111111, 0xff8c00, 0xd4af37], 'R1 10 kΩ');
    const r2b = V(-8.5, 0.35, 10.0);
    resistor(J, r2b, [0xd62828, 0x111111, 0xff8c00, 0xd4af37], 'R2 20 kΩ');
    const r3b = V(-8.5, 0.35, 3.8);
    resistor(J, r3b, [0x8b4513, 0x111111, 0xd62828, 0xd4af37], '1 kΩ series');
    const [cfa, cfb] = capacitor(V(-6.6, 0.35, 7.6), V(-6.6, 0.35, 9.4), 'ceramic', '100 nF filter');
    wire(mq.AO, r1a, 'magenta', 'MQ-135 AO → R1 10 kΩ', { group: 'MQ-135 + divider → GPIO34' });
    wire(J, cfa, 'magenta', 'Divider junction → 100 nF filter capacitor', { group: 'MQ-135 + divider → GPIO34', lift: 0.8 });
    wire(cfb, gndf(-6.6), 'black', '100 nF filter → GND', { group: 'MQ-135 + divider → GPIO34', lift: 0.8 });
    wire(r2b, gndf(-8.5), 'black', 'R2 20 kΩ → GND rail', { group: 'MQ-135 + divider → GPIO34', lift: 0.6 });
    wire(r3b, e['34'], 'magenta', '1 kΩ → ESP32 GPIO34 (≤ 3.3 V, measure first!)', { group: 'MQ-135 + divider → GPIO34' });
    sprite('junction ≈ AO × 0.667\n5 V → 3.33 V max', -8.5, 4.6, 6.5, { size: 0.42, bg: 'rgba(254,242,242,0.95)', color: '#991b1b' });

    // Sound sensor
    const s = smallModule(-0.5, 8.5, 3.6, 2.0, 0xb91c1c, 'Sound sensor\n(3.3 V)', ['AO', 'GND', 'VCC', 'DO'], { pinsBack: true, titleY: 3.6 });
    cyl(0.55, 0.9, 0x111111, 0.6, 1.08, 8.9);
    wire(s.VCC, r33f(0.5), 'orange', 'Sound VCC → 3.3 V rail', { group: 'Sound sensor → GPIO35' });
    wire(s.GND, gndf(-1.0), 'black', 'Sound GND → GND rail', { group: 'Sound sensor → GPIO35' });
    wire(s.AO, e['35'], 'magenta', 'Sound AO → ESP32 GPIO35', { group: 'Sound sensor → GPIO35' });

    // Supply monitor divider
    const Js = solderDot(V(8.5, 0.35, 7.0));
    const rt = V(8.5, 0.35, 10.6);
    resistor(rt, Js, [0x8b4513, 0x111111, 0xf5d000, 0xd4af37], '100 kΩ');
    const rb = V(12.0, 0.35, 7.0);
    resistor(Js, rb, [0x8b4513, 0x111111, 0xf5d000, 0xd4af37], '100 kΩ');
    wire(rt, r5f(8.5), 'red', '5 V rail → 100 kΩ (supply monitor)', { group: 'Supply monitor → GPIO32 (optional)', lift: 0.6 });
    wire(rb, gndf(12.0), 'black', '100 kΩ → GND', { group: 'Supply monitor → GPIO32 (optional)' });
    wire(Js, e['32'], 'magenta', 'Sense junction → ESP32 GPIO32 (≈2.5 V at 5 V)', { group: 'Supply monitor → GPIO32 (optional)' });
    sprite('Supply monitor\n(optional)', 10.3, 3.6, 7.5, { size: 0.5 });

    return {
      title: `Field node ${nodeId} — ESP32 DevKit V1`,
      intro: `Perfboard layout of ESP32 field node ${nodeId}. Flash with <code>pio run -e node${nodeId} -t upload</code>. ` +
        `Transmits every 60 s in slot +${nodeId === 1 ? 10 : 40} s. ` +
        'Same circuit for both nodes — only NODE_ID differs.',
      warn: 'Ra-02 VCC = 3.3 V only. ESP32 inputs ≤ 3.3 V: measure the MQ-135 divider junction before connecting GPIO34. Fit the antenna before power-on.',
      camera: [{ x: 2, y: 30, z: 24 }, { x: 0, y: 0, z: 0 }, 0.56],
    };
  }

  function buildMainNode() {
    // Raspberry Pi 3B+ board, 40-pin header along the back edge (pin 1 at -x, SD-card end).
    box(34, 0.3, 22.4, 0x1e7b3c, 0, 0, 0, { roughness: 0.8 });
    sprite('RASPBERRY PI 3 MODEL B+  ·  MAIN NODE', 2, 2.5, 15.5, { size: 1.1, bold: true, color: '#ffffff', bg: 'rgba(17,24,39,0.92)' });
    box(6, 0.6, 6, 0x222222, -3, 0.3, 1, {}); // SoC
    sprite('BCM2837B0', -3, 2.0, 1, { size: 0.55, bg: null, color: '#e5e7eb' });
    box(7, 6, 5.4, 0xd5dbe1, 14, 0.3, -6.5, { metalness: 0.3, roughness: 0.4 }); // USB stack
    box(7, 6, 5.4, 0xd5dbe1, 14, 0.3, -0.8, { metalness: 0.3, roughness: 0.4 });
    box(7.5, 6.2, 6.2, 0xd5dbe1, 14, 0.3, 6.5, { metalness: 0.3, roughness: 0.4 }); // Ethernet
    sprite('USB ×4', 14, 8, -3.6, { size: 0.7 });
    sprite('Ethernet', 14, 8, 6.5, { size: 0.7 });
    box(3.2, 1.2, 2.2, 0xd5dbe1, -11, 0.3, 10.6, { metalness: 0.3 }); // micro-USB power
    box(5.6, 1.8, 3, 0x9ca3af, -2.5, 0.3, 10.2, { metalness: 0.7 }); // HDMI
    cyl(1.0, 2.2, 0x111111, 6, 0.3, 10.3); // audio
    box(4.5, 0.5, 4.5, 0x111111, -15.5, -0.3, 2, {}); // SD card (underside)
    sprite('microSD (underside)', -15.5, 1.6, 4.8, { size: 0.4 });
    sprite('micro-USB power', -11, 3.2, 10.6, { size: 0.55 });

    // 40-pin header
    box(20.4, 0.9, 2.3, 0x111111, -5.9, 0.3, -9.6);
    const hp = {};
    const used = { 1: '1: 3.3V', 2: '2: 5V ✕', 4: '4: 5V ✕', 6: '6: GND', 18: '18: GPIO24', 19: '19: MOSI',
      21: '21: MISO', 22: '22: GPIO25', 23: '23: SCLK', 24: '24: CE0' };
    for (let n = 1; n <= 40; n++) {
      const col = Math.floor((n - 1) / 2);
      const odd = n % 2 === 1;
      const x = -15.4 + col * 1.0;
      const z = odd ? -9.1 : -10.1;
      const danger = n === 2 || n === 4;
      hp[n] = pin(x, 1.2, z, used[n], {
        label: !!used[n], labelSize: 0.42,
        labelOffset: [0, odd ? 0.0 : 1.0, (odd ? 1 : -1) * (1.5 + (col % 2) * 1.4)],
        labelColor: danger ? '#ffffff' : '#111827', labelBg: danger ? 'rgba(220,38,38,0.95)' : undefined,
      });
    }
    sprite('Pin 1 (square pad)', -15.4, 4.4, -7.0, { size: 0.45, bg: 'rgba(254,249,195,0.95)' });

    // Ra-02 on adapter, behind the header
    const r = ra02Module(-7.5, -19);
    const G = 'Raspberry Pi → SX1278 / Ra-02';
    wire(hp[1], r.VCC, 'orange', 'Pi pin 1 (3.3 V) → Ra-02 VCC   — never pin 2/4 (5 V)!', { group: G });
    wire(hp[6], r.GND, 'black', 'Pi pin 6 (GND) → Ra-02 GND', { group: G });
    wire(hp[23], r.SCK, 'yellow', 'Pi pin 23 (GPIO11 SCLK) → Ra-02 SCK', { group: G });
    wire(hp[21], r.MISO, 'green', 'Pi pin 21 (GPIO9 MISO) → Ra-02 MISO', { group: G });
    wire(hp[19], r.MOSI, 'purple', 'Pi pin 19 (GPIO10 MOSI) → Ra-02 MOSI', { group: G });
    wire(hp[24], r.NSS, 'white', 'Pi pin 24 (GPIO8 CE0) → Ra-02 NSS', { group: G });
    wire(hp[22], r.RST, 'brown', 'Pi pin 22 (GPIO25) → Ra-02 RESET', { group: G });
    wire(hp[18], r.DIO0, 'gray', 'Pi pin 18 (GPIO24) → Ra-02 DIO0', { group: G });

    const [c1a, c1b] = capacitor(V(-2.0, 0.6, -21.0), V(-2.0, 0.6, -19.4), 'ceramic', '100 nF');
    const [c2a, c2b] = capacitor(V(-0.2, 0.6, -21.0), V(-0.2, 0.6, -19.4), 'electrolytic', '10 µF');
    box(4.2, 0.18, 3.6, 0x1d4ed8, -1.1, 0.42, -20.2);
    wire(c1a, r.VCC, 'orange', '100 nF: Ra-02 VCC side', { group: 'Decoupling (at the Ra-02)', lift: 1.4 });
    wire(c1b, r.GND, 'black', '100 nF: GND side', { group: 'Decoupling (at the Ra-02)', lift: 1.2 });
    wire(c2a, r.VCC, 'orange', '10 µF: + → VCC', { group: 'Decoupling (at the Ra-02)', lift: 1.8 });
    wire(c2b, r.GND, 'black', '10 µF: − → GND', { group: 'Decoupling (at the Ra-02)', lift: 1.6 });
    antennaWithCable(r.IPEX, -4.0, -23.5);

    // Power adapter and network cable
    const pwr = new THREE.CatmullRomCurve3([V(-11, 0.9, 11.8), V(-11, 0.7, 16), V(-14, 0.4, 21), V(-18, 0.3, 24)]);
    root.add(new THREE.Mesh(new THREE.TubeGeometry(pwr, 40, 0.3, 8), mat(0x111111)));
    box(4.5, 3, 3.5, 0x111111, -20, -0.5, 25.5);
    sprite('5 V / 2.5 A\nmicro-USB adapter', -20, 4.8, 25.5, { size: 0.7 });
    const eth = new THREE.CatmullRomCurve3([V(17.8, 3.3, 6.5), V(22, 2.6, 6.5), V(27, 0.8, 8), V(31, 0.4, 10)]);
    root.add(new THREE.Mesh(new THREE.TubeGeometry(eth, 40, 0.3, 8), mat(0x2563eb)));
    box(6, 1.6, 4, 0xe5e7eb, 33, -0.5, 11);
    sprite('Router / switch\n→ laptop browser\nhttp://<pi-ip>:5000', 33, 4.4, 11, { size: 0.7 });

    return {
      title: 'Main node — Raspberry Pi 3B+ + SX1278',
      intro: 'GPIO header seen from above. Pin 1 is the square pad at the microSD-card end. ' +
        'NSS uses CE0 so <code>/dev/spidev0.0</code> drives chip-select. RESET = BCM25, DIO0 = BCM24 (config.toml).',
      warn: 'Ra-02 VCC goes to pin 1 (3.3 V). Pins 2 and 4 are 5 V (red labels) — connecting them destroys the module. Enable SPI before testing.',
      camera: [{ x: 0, y: 34, z: 22 }, { x: 0, y: 0, z: 0 }, 0.6],
    };
  }

  function buildSystem() {
    const unit = (x, z, color, title, sub) => {
      box(9, 1.2, 7, color, x, 0, z);
      box(2.6, 0.6, 2.6, 0xcfd6de, x + 2.2, 1.2, z - 1.6, { metalness: 0.85 });
      const top = antenna(x + 3.4, 1.2, z - 2.8, 9);
      sprite(title + '\n' + sub, x, 6.5, z + 1.5, { size: 0.9, bold: true });
      return top;
    };
    const a1 = unit(-28, -12, 0x1f2937, 'ESP32 NODE 1', 'BME280 · BH1750 · MQ-135 · Sound');
    const a2 = unit(-28, 14, 0x1f2937, 'ESP32 NODE 2', 'BME280 · BH1750 · MQ-135 · Sound');
    const ap = unit(14, 0, 0x1e7b3c, 'RASPBERRY PI 3B+', 'SQLite · Flask · Alerts');
    sprite('LoRa 433 MHz · SF7 · BW125 · CR4/5 · sync 0x12 · CRC', -6, 16, 0, { size: 0.9, bg: 'rgba(219,234,254,0.95)' });
    sprite('slot +10 s', -24, 13.5, -12, { size: 0.6 });
    sprite('slot +40 s', -24, 13.5, 14, { size: 0.6 });

    // Laptop
    box(8, 0.4, 5.5, 0x9ca3af, 34, 0, 0, { metalness: 0.6 });
    const scr = box(8, 5, 0.3, 0x111827, 34, 0.4, -2.6);
    scr.rotation.x = -0.25;
    sprite('Laptop / mobile\nbrowser :5000', 34, 8, 0, { size: 0.8 });
    const eth = new THREE.CatmullRomCurve3([V(18.5, 0.8, 1), V(24, 1.5, 3), V(29.8, 0.4, 1)]);
    root.add(new THREE.Mesh(new THREE.TubeGeometry(eth, 40, 0.25, 8), mat(0x2563eb)));
    sprite('Ethernet / Wi-Fi', 24, 3.4, 3, { size: 0.6 });
    sprite('No wires between units — each has its own 5 V supply and antenna.', -6, -0.2, 24, { size: 0.8, bg: 'rgba(254,249,195,0.95)' });

    // Animated radio pulses from each node to the Pi
    [a1, a2].forEach((from, k) => {
      const curve = new THREE.QuadraticBezierCurve3(from, V((from.x + ap.x) / 2, 15, (from.z + ap.z) / 2), ap);
      const line = new THREE.Mesh(new THREE.TubeGeometry(curve, 60, 0.05, 6), mat(0x60a5fa, { transparent: true, opacity: 0.6 }));
      root.add(line);
      for (let i = 0; i < 3; i++) {
        const p = new THREE.Mesh(new THREE.SphereGeometry(0.45, 16, 16), mat(0x2563eb, { emissive: 0x1d4ed8, emissiveIntensity: 0.8 }));
        root.add(p);
        animations.push(t => {
          const u = ((t * 0.25 + i / 3 + k * 0.5) % 1);
          p.position.copy(curve.getPoint(u));
        });
      }
      const ring = new THREE.Mesh(new THREE.TorusGeometry(1, 0.06, 8, 48), mat(0x3b82f6, { transparent: true, opacity: 0.8 }));
      ring.rotation.x = Math.PI / 2;
      ring.position.copy(from);
      root.add(ring);
      animations.push(t => {
        const u = (t * 0.6 + k * 0.5) % 1;
        ring.scale.setScalar(1 + u * 5);
        ring.material.opacity = 0.8 * (1 - u);
      });
    });

    return {
      title: 'System overview — star network',
      intro: 'Both ESP32 field nodes transmit one 33-byte packet per minute directly to the Raspberry Pi (no mesh). ' +
        'The Pi validates, stores and serves the dashboard.',
      warn: 'All three LoRa modules must use identical radio settings. Nodes 1 and 2 must have different NODE_IDs.',
      camera: [{ x: 0, y: 30, z: 42 }, { x: 0, y: 0, z: 0 }, 0.6],
      noWires: true,
    };
  }

  // ------------------------------------------------------------------ UI
  const panel = document.getElementById('panel');
  const tip = document.getElementById('tip');
  let selected = -1;

  function buildLegend() {
    const lg = document.getElementById('legend');
    lg.innerHTML = Object.values(WIRE).map(w =>
      `<span><i class="sw" style="background:#${w.hex.toString(16).padStart(6, '0')}"></i>${w.name}</span>`).join('');
  }

  function renderPanel(meta) {
    const groups = {};
    wires.forEach((w, i) => { (groups[w.group] = groups[w.group] || []).push(i); });
    let html = `<h2>${meta.title}</h2><p>${meta.intro}</p><div id="warn">⚠ ${meta.warn}</div>`;
    if (meta.noWires) {
      html += '<h3>Units</h3><p>Open <b>Main node</b>, <b>Field node 1</b> or <b>Field node 2</b> for the full wiring of each unit.</p>';
    }
    for (const [g, idx] of Object.entries(groups)) {
      html += `<h3>${g}</h3>`;
      idx.forEach(i => {
        const w = wires[i];
        html += `<div class="conn" data-i="${i}"><i class="sw" style="background:#${WIRE[w.color].hex.toString(16).padStart(6, '0')}"></i>` +
          `<span class="txt">${w.info}<div class="note">${WIRE[w.color].name}</div></span></div>`;
      });
    }
    panel.innerHTML = html;
    panel.querySelectorAll('.conn').forEach(el => el.addEventListener('click', () => select(Number(el.dataset.i))));
  }

  function select(i) {
    selected = selected === i ? -1 : i;
    wires.forEach((w, k) => {
      const on = selected === -1 || k === selected;
      w.mesh.material.transparent = !on;
      w.mesh.material.opacity = on ? 1 : 0.12;
      w.mesh.material.emissive.setHex(k === selected ? 0x444444 : 0x000000);
      w.mesh.scale.setScalar(1);
    });
    panel.querySelectorAll('.conn').forEach(el => el.classList.toggle('sel', Number(el.dataset.i) === selected));
  }

  // Frame the whole scene: keep the preset viewing direction, compute the distance.
  function fitCamera(preset) {
    const dir = V(preset[0].x - preset[1].x, preset[0].y - preset[1].y, preset[0].z - preset[1].z).normalize();
    const meshes = [];
    root.traverse(o => { if (o.isMesh) meshes.push(o); });
    const bbox = new THREE.Box3();
    meshes.forEach(m => bbox.expandByObject(m));
    const center = bbox.getCenter(V(0, 0, 0));
    const radius = bbox.getBoundingSphere(new THREE.Sphere()).radius;
    const vfov = THREE.MathUtils.degToRad(camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
    const dist = (radius / Math.sin(Math.min(vfov, hfov) / 2)) * (preset[2] || 0.78);
    controls.target.copy(center);
    camera.position.copy(center).addScaledVector(dir, dist);
    camera.near = dist / 100;
    camera.far = dist * 10;
    camera.updateProjectionMatrix();
    controls.update();
  }

  function clearRoot() {
    if (!root) return;
    root.traverse(o => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        if (o.material.map) o.material.map.dispose();
        o.material.dispose();
      }
    });
    scene.remove(root);
  }

  const builders = {
    system: buildSystem,
    main: buildMainNode,
    node1: () => buildFieldNode(1),
    node2: () => buildFieldNode(2),
  };

  function show(name) {
    clearRoot();
    root = new THREE.Group();
    scene.add(root);
    wires = []; pinLabelSprites = []; animations = []; selected = -1;
    const meta = builders[name]();
    pinLabelSprites.forEach(s => { s.visible = document.getElementById('pinLabels').checked; });
    fitCamera(meta.camera);
    renderPanel(meta);
    document.querySelectorAll('#topbar button').forEach(b => b.classList.toggle('active', b.dataset.scene === name));
    if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
  }

  // Hover tooltip
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  renderer.domElement.addEventListener('mousemove', ev => {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const hit = raycaster.intersectObjects(wires.map(w => w.mesh))[0];
    if (hit) {
      const w = wires[hit.object.userData.wireIndex];
      tip.innerHTML = `<b>${w.info}</b><br>${WIRE[w.color].name}`;
      tip.style.left = ev.clientX + 14 + 'px';
      tip.style.top = ev.clientY + 14 + 'px';
      tip.style.display = 'block';
      renderer.domElement.style.cursor = 'pointer';
    } else {
      tip.style.display = 'none';
      renderer.domElement.style.cursor = '';
    }
  });
  renderer.domElement.addEventListener('click', () => {
    raycaster.setFromCamera(mouse, camera);
    const hit = raycaster.intersectObjects(wires.map(w => w.mesh))[0];
    if (hit) {
      select(hit.object.userData.wireIndex);
      const row = panel.querySelector(`.conn[data-i="${hit.object.userData.wireIndex}"]`);
      if (row) row.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  });

  document.querySelectorAll('#topbar button').forEach(b => b.addEventListener('click', () => show(b.dataset.scene)));
  document.getElementById('pinLabels').addEventListener('change', e => pinLabelSprites.forEach(s => { s.visible = e.target.checked; }));
  document.getElementById('rotate').addEventListener('change', e => { controls.autoRotate = e.target.checked; });

  function resize() {
    const w = view.clientWidth, h = view.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);

  const clock = new THREE.Clock();
  function loop() {
    requestAnimationFrame(loop);
    const t = clock.getElapsedTime();
    animations.forEach(f => f(t));
    controls.update();
    renderer.render(scene, camera);
  }

  buildLegend();
  resize();
  const initial = location.hash.slice(1);
  show(initial in builders ? initial : 'system');
  loop();
  window.__show = show; // used by the screenshot script
  window.__cam = (x, y, z, tx, ty, tz) => { camera.position.set(x, y, z); controls.target.set(tx, ty, tz); controls.update(); };
})();
