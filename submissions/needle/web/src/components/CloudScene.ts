// The landing page's WebGL scene: 26,183 public advisories as points (real embeddings, PCA to 3D), a needle for
// the question, the rows a given identity may see, and a faint nearest-neighbour graph that search pulses walk
// toward the question, the way DiskANN searches its graph (an illustration of the method, not Db2's own graph).
// Light comes from the scene: a bloom pass on emissive points and pulses, depth fog for atmosphere.
// Data: /cloud/cloud.{json,bin} from scripts/build_hero_cloud.py. Reduced motion gets a still frame.
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";

export interface CloudQuery {
  key: string; text: string; pos: [number, number, number];
  top10: number[]; top10_ids: string[]; batch: number[]; batch_visible_p10: number;
  p10_top10: number[]; p10_top10_ids: string[];
}
export interface CloudInfo {
  n: number; excluded_embargoed: number; p10_max_bucket: number; p10_visible: number; batch: number;
  pca_explained: number[]; generated: string; source: string; queries: CloudQuery[];
}
export type Lens = "all" | "p10-shared" | "p10-router";

const POINT_VERT = /* glsl */ `
attribute float aBucket;
attribute float aRole;
uniform float uMax, uPrevMax, uFade, uSize, uPixelRatio, uCamDist;
varying float vAlpha;
varying vec3 vColor;
void main() {
  float vis = mix(aBucket < uPrevMax ? 1.0 : 0.0, aBucket < uMax ? 1.0 : 0.0, uFade);
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float near = smoothstep(uCamDist + 2.4, uCamDist - 1.8, -mv.z);
  vec3 col = mix(vec3(0.22, 0.34, 0.42), vec3(0.62, 0.74, 0.77), near);
  float a = mix(0.03, 0.24, vis) * mix(0.32, 1.0, near);
  if (aRole > 0.5) a = 0.0;
  vColor = col; vAlpha = a;
  gl_PointSize = uSize * uPixelRatio * (3.2 / -mv.z) * mix(0.75, 1.15, near);
  gl_Position = projectionMatrix * mv;
}`;
const POINT_FRAG = /* glsl */ `
varying float vAlpha;
varying vec3 vColor;
void main() {
  float d = length(gl_PointCoord - 0.5);
  if (d > 0.5) discard;
  gl_FragColor = vec4(vColor, vAlpha * smoothstep(0.5, 0.05, d));
}`;
const HL_VERT = /* glsl */ `
attribute vec3 aColor;
attribute float aSize;
uniform float uPixelRatio;
varying vec3 vColor;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vColor = aColor;
  gl_PointSize = aSize * uPixelRatio * (3.2 / -mv.z);
  gl_Position = projectionMatrix * mv;
}`;
const HL_FRAG = /* glsl */ `
varying vec3 vColor;
void main() {
  float d = length(gl_PointCoord - 0.5);
  if (d > 0.5) discard;
  vec3 ring = vec3(0.03, 0.04, 0.045);
  gl_FragColor = vec4(mix(vColor * 1.25, ring, smoothstep(0.30, 0.36, d)), 1.0 - smoothstep(0.46, 0.5, d));
}`;
const HALO_FRAG = /* glsl */ `
varying vec3 vColor;
void main() {
  float d = length(gl_PointCoord - 0.5);
  if (d > 0.5) discard;
  float g = pow(1.0 - d * 2.0, 2.4);
  gl_FragColor = vec4(vColor * g, g * 0.32);
}`;
const PULSE_VERT = /* glsl */ `
uniform float uTime, uPixelRatio;
varying float vT;
void main() {
  vT = fract(uTime / 2.6);
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = (14.0 + vT * 120.0) * uPixelRatio * (3.2 / -mv.z);
  gl_Position = projectionMatrix * mv;
}`;
const PULSE_FRAG = /* glsl */ `
varying float vT;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float ring = smoothstep(0.5, 0.44, d) * smoothstep(0.36, 0.44, d);
  float a = ring * 0.6 * pow(1.0 - vT, 1.6);
  gl_FragColor = vec4(vec3(0.72, 0.95, 0.97) * a, a);
}`;
const EDGE_VERT = /* glsl */ `
uniform float uCamDist;
varying float vNear;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vNear = smoothstep(uCamDist + 2.4, uCamDist - 1.8, -mv.z);
  gl_Position = projectionMatrix * mv;
}`;
const EDGE_FRAG = /* glsl */ `
varying float vNear;
void main() { gl_FragColor = vec4(vec3(0.30, 0.62, 0.68), 0.04 * mix(0.3, 1.0, vNear)); }`;
const WALK_VERT = /* glsl */ `
attribute float aT;
varying float vT;
void main() { vT = aT; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const WALK_FRAG = /* glsl */ `
uniform float uHead, uFade;
varying float vT;
void main() {
  if (vT > uHead) discard;
  float tail = smoothstep(uHead - 0.28, uHead, vT);
  float a = (0.10 + 0.9 * tail) * uFade;
  gl_FragColor = vec4(vec3(0.45, 0.95, 1.0) * (0.5 + 1.0 * tail), a * 0.85);
}`;

export async function loadCloud(): Promise<{ info: CloudInfo; pos: Float32Array; bucket: Float32Array }> {
  const get = async (url: string) => {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`cloud data missing: HTTP ${r.status}`);
    return r;
  };
  const [info, buf] = await Promise.all([
    get("/cloud/cloud.json").then((r) => r.json() as Promise<CloudInfo>),
    get("/cloud/cloud.bin").then((r) => r.arrayBuffer()),
  ]);
  const n = info.n;
  if (buf.byteLength < n * 7) throw new Error(`cloud data incomplete: cloud.bin has ${buf.byteLength} bytes, expected ${n * 7}`);
  const q = new Int16Array(buf, 0, n * 3);
  const b = new Uint8Array(buf, n * 6, n);
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n * 3; i++) pos[i] = (q[i] / 32767) * 1.6;
  return { info, pos, bucket: Float32Array.from(b) };
}

/** A k-nearest-neighbour graph over a sample of the points (3D grid hash), plus the query neighbours. */
function buildGraph(pos: Float32Array, n: number, extra: number[], every = 6, k = 4) {
  const nodes: number[] = [];
  for (let i = 0; i < n; i += every) nodes.push(i);
  for (const i of extra) if (i % every) nodes.push(i);
  const cell = 0.14, grid = new Map<string, number[]>();
  const key = (x: number, y: number, z: number) => `${Math.floor(x / cell)},${Math.floor(y / cell)},${Math.floor(z / cell)}`;
  nodes.forEach((i, j) => {
    const kk = key(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
    const a = grid.get(kk); if (a) a.push(j); else grid.set(kk, [j]);
  });
  const nbr: number[][] = [];
  nodes.forEach((i) => {
    const x = pos[i * 3], y = pos[i * 3 + 1], z = pos[i * 3 + 2];
    const cx = Math.floor(x / cell), cy = Math.floor(y / cell), cz = Math.floor(z / cell);
    const cand: [number, number][] = [];
    for (let r = 1; r <= 3 && cand.length < k + 1; r++) {
      cand.length = 0;
      for (let a = -r; a <= r; a++) for (let b = -r; b <= r; b++) for (let c = -r; c <= r; c++) {
        for (const m of grid.get(`${cx + a},${cy + b},${cz + c}`) ?? []) {
          const o = nodes[m]; if (o === i) continue;
          const dx = pos[o * 3] - x, dy = pos[o * 3 + 1] - y, dz = pos[o * 3 + 2] - z;
          cand.push([m, dx * dx + dy * dy + dz * dz]);
        }
      }
    }
    cand.sort((p, q) => p[1] - q[1]);
    nbr.push(cand.slice(0, k).map((c) => c[0]));
  });
  return { nodes, nbr };
}

interface Walk { line: THREE.Line; mat: THREE.ShaderMaterial; start: number; dur: number }

export class CloudScene {
  private renderer: THREE.WebGLRenderer;
  private composer: EffectComposer;
  private bloom: UnrealBloomPass;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(32, 1, 0.1, 60);
  private group = new THREE.Group();
  private mat: THREE.ShaderMaterial;
  private edgeMat: THREE.ShaderMaterial;
  private role: THREE.BufferAttribute;
  private lines: THREE.LineSegments;
  private needle: THREE.Line;
  private tip: THREE.Points;
  private hl: THREE.Points;
  private halo: THREE.Points;
  private pulse: THREE.Points;
  private graph: { nodes: number[]; nbr: number[][] };
  private walks: Walk[] = [];
  private raf = 0;
  private running = true;
  private auto = true;
  private fadeT = 1;
  private rotY = -0.6;
  private rotX = 0.18;
  private velY = 0;
  private dragging = false;
  private lastX = 0;
  private lastY = 0;
  private needlePos = new THREE.Vector3();
  private needleTarget = new THREE.Vector3();
  private t0 = performance.now();
  private focus = 0;          // 0 wide .. 1 close to the question (scroll story)
  private focusTarget = 0;
  private showQuery = true;
  private baseDist = 5.6;
  private seed = 11;
  private ro: ResizeObserver;
  onFrame?: (screen: { x: number; y: number } | null) => void;

  constructor(private host: HTMLElement, private data: { info: CloudInfo; pos: Float32Array; bucket: Float32Array },
              private still: boolean) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x0a0c0d, 1);
    host.appendChild(this.renderer.domElement);
    this.renderer.domElement.style.cssText = "display:block;width:100%;height:100%;touch-action:pan-y;cursor:grab";
    this.scene.background = this.backdrop();
    const pr = this.renderer.getPixelRatio();

    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(data.pos, 3));
    g.setAttribute("aBucket", new THREE.BufferAttribute(data.bucket, 1));
    this.role = new THREE.BufferAttribute(new Float32Array(data.info.n), 1);
    g.setAttribute("aRole", this.role);
    this.mat = new THREE.ShaderMaterial({
      vertexShader: POINT_VERT, fragmentShader: POINT_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: { uMax: { value: 100 }, uPrevMax: { value: 100 }, uFade: { value: 1 }, uSize: { value: 5.0 },
                  uPixelRatio: { value: pr }, uCamDist: { value: 5.6 } },
    });
    this.group.add(new THREE.Points(g, this.mat));

    const extra = [...new Set(data.info.queries.flatMap((q) => [...q.top10, ...q.p10_top10, ...q.batch]))];
    this.graph = buildGraph(data.pos, data.info.n, extra);
    const seg: number[] = [];
    this.graph.nbr.forEach((ns, j) => ns.forEach((m) => {
      if (m < j && this.graph.nbr[m].includes(j)) return;
      const a = this.graph.nodes[j], b = this.graph.nodes[m];
      seg.push(data.pos[a * 3], data.pos[a * 3 + 1], data.pos[a * 3 + 2], data.pos[b * 3], data.pos[b * 3 + 1], data.pos[b * 3 + 2]);
    }));
    const eg = new THREE.BufferGeometry();
    eg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(seg), 3));
    this.edgeMat = new THREE.ShaderMaterial({ vertexShader: EDGE_VERT, fragmentShader: EDGE_FRAG, transparent: true,
      depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uCamDist: { value: 5.6 } } });
    this.group.add(new THREE.LineSegments(eg, this.edgeMat));

    this.lines = new THREE.LineSegments(new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0x7fe9f0, transparent: true, opacity: 0.45, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.group.add(this.lines);
    this.needle = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.7 }));
    this.group.add(this.needle);
    const tg = new THREE.BufferGeometry();
    tg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3), 3));
    this.tip = new THREE.Points(tg, new THREE.PointsMaterial({ color: 0xffffff, size: 0.1, transparent: true, depthWrite: false }));
    this.group.add(this.tip);

    this.halo = new THREE.Points(new THREE.BufferGeometry(), new THREE.ShaderMaterial({
      vertexShader: HL_VERT, fragmentShader: HALO_FRAG, transparent: true, depthTest: false, depthWrite: false,
      blending: THREE.AdditiveBlending, uniforms: { uPixelRatio: { value: pr } } }));
    this.halo.renderOrder = 2;
    this.hl = new THREE.Points(new THREE.BufferGeometry(), new THREE.ShaderMaterial({
      vertexShader: HL_VERT, fragmentShader: HL_FRAG, transparent: true, depthTest: false, depthWrite: false,
      uniforms: { uPixelRatio: { value: pr } } }));
    this.hl.renderOrder = 3;
    const pg = new THREE.BufferGeometry();
    pg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3), 3));
    this.pulse = new THREE.Points(pg, new THREE.ShaderMaterial({
      vertexShader: PULSE_VERT, fragmentShader: PULSE_FRAG, transparent: true, depthTest: false, depthWrite: false,
      blending: THREE.AdditiveBlending, uniforms: { uTime: { value: 0 }, uPixelRatio: { value: pr } } }));
    this.pulse.renderOrder = 4;
    this.pulse.visible = !still;
    this.group.add(this.halo, this.hl, this.pulse);
    this.scene.add(this.group);

    for (let w = 0; w < 4; w++) {
      const mat = new THREE.ShaderMaterial({ vertexShader: WALK_VERT, fragmentShader: WALK_FRAG, transparent: true,
        depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uHead: { value: still ? 1 : 0 }, uFade: { value: 1 } } });
      const line = new THREE.Line(new THREE.BufferGeometry(), mat);
      line.renderOrder = 1;
      this.group.add(line);
      this.walks.push({ line, mat, start: 0, dur: 2.2 });
    }

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.42, 0.38, 0.7);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.resize();
    this.bindDrag();
    document.addEventListener("visibilitychange", this.onVis);
    this.loop();
  }

  /** The stage's backdrop: a low key light from the upper right falling off to near-black, drawn once. */
  private backdrop() {
    const c = document.createElement("canvas");
    c.width = 512; c.height = 512;
    const x = c.getContext("2d")!;
    const g = x.createRadialGradient(330, 210, 10, 300, 260, 420);
    g.addColorStop(0, "#121c21"); g.addColorStop(0.45, "#0c1214"); g.addColorStop(1, "#070809");
    x.fillStyle = g; x.fillRect(0, 0, 512, 512);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }

  private rnd() { this.seed = (this.seed * 16807) % 2147483647; return this.seed / 2147483647; }

  /** A greedy walk over the graph from a far entry node toward the question (long edges when it stalls). */
  private planWalk(w: Walk, now: number) {
    const { pos } = this.data, { nodes, nbr } = this.graph, q = this.needleTarget;
    const d2 = (j: number) => {
      const i = nodes[j];
      return (pos[i * 3] - q.x) ** 2 + (pos[i * 3 + 1] - q.y) ** 2 + (pos[i * 3 + 2] - q.z) ** 2;
    };
    let cur = 0;
    for (let tries = 0; tries < 20; tries++) { cur = Math.floor(this.rnd() * nodes.length); if (d2(cur) > 1.0) break; }
    const path = [cur];
    for (let s = 0; s < 80; s++) {
      let best = cur, bd = d2(cur);
      for (const m of nbr[cur]) { const dm = d2(m); if (dm < bd) { bd = dm; best = m; } }
      if (best === cur) {
        let jump = -1;
        for (let t = 0; t < 40; t++) { const r = Math.floor(this.rnd() * nodes.length); if (d2(r) < bd * 0.6) { jump = r; break; } }
        if (jump < 0) break;
        best = jump;
      }
      path.push(best); cur = best;
      if (d2(cur) < 0.004) break;
    }
    const pts: number[] = [], ts: number[] = [];
    let len = 0, px = 0, py = 0, pz = 0;
    path.forEach((j, k) => {
      const i = nodes[j], x = pos[i * 3], y = pos[i * 3 + 1], z = pos[i * 3 + 2];
      if (k) len += Math.hypot(x - px, y - py, z - pz);
      pts.push(x, y, z); ts.push(len); px = x; py = y; pz = z;
    });
    len += Math.hypot(q.x - px, q.y - py, q.z - pz);
    pts.push(q.x, q.y, q.z); ts.push(len);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
    geo.setAttribute("aT", new THREE.BufferAttribute(new Float32Array(ts.map((t) => t / (len || 1))), 1));
    w.line.geometry.dispose();
    w.line.geometry = geo;
    w.start = now;
    w.dur = 1.8 + this.rnd() * 1.4;
  }

  private onVis = () => { this.running = !document.hidden; if (this.running) this.loop(); };

  /** Pause / resume the idle motion: turn, needle pulse and search walks (the stage's "Pause motion"). */
  setAuto(on: boolean) {
    this.auto = on;
    this.pulse.visible = on && !this.still && this.showQuery;
  }

  /** Scroll story: how close the camera sits to the question, and whether the question is shown at all. */
  setStory(focus: number, showQuery: boolean) {
    this.focusTarget = focus;
    if (this.still) this.focus = focus;
    this.showQuery = showQuery;
    for (const o of [this.needle, this.tip, this.lines, this.hl, this.halo, ...this.walks.map((w) => w.line)]) o.visible = showQuery;
    this.pulse.visible = showQuery && this.auto && !this.still;
    this.render();
  }

  setRunning(on: boolean) {
    if (on === this.running) return;
    this.running = on;
    if (on) this.loop();
  }

  private resize() {
    const w = this.host.clientWidth, h = this.host.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.composer.setSize(w, h);
    this.bloom.resolution.set(w / 2, h / 2);
    this.camera.aspect = w / h;
    const wide = w / h > 1.25;
    const dist = wide ? 5.6 : 6.6;
    this.baseDist = dist;
    this.camera.position.set(0, 0, dist);
    this.mat.uniforms.uCamDist.value = dist;
    this.edgeMat.uniforms.uCamDist.value = dist;
    this.group.position.x = wide ? Math.min(1.05, (w / h - 1) * 0.8) : 0;
    this.group.position.y = wide ? 0.05 : 0.2;
    this.group.scale.setScalar(wide ? 1.32 : 1.1);
    this.camera.updateProjectionMatrix();
    this.render();
  }

  private bindDrag() {
    const el = this.renderer.domElement;
    el.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "touch") return;
      this.dragging = true; this.lastX = e.clientX; this.lastY = e.clientY; this.velY = 0;
      el.setPointerCapture(e.pointerId); el.style.cursor = "grabbing";
    });
    el.addEventListener("pointermove", (e) => {
      if (!this.dragging) return;
      const dx = e.clientX - this.lastX, dy = e.clientY - this.lastY;
      this.lastX = e.clientX; this.lastY = e.clientY;
      this.rotY += dx * 0.006; this.velY = dx * 0.006;
      this.rotX = Math.max(-0.8, Math.min(0.8, this.rotX + dy * 0.004));
      if (this.still) this.render();
    });
    const up = () => { this.dragging = false; el.style.cursor = "grab"; };
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
  }

  /** Show what an identity sees for a query. Points: 0 plain, 1 lit, 2 fetched then removed by the permission. */
  setState(q: CloudQuery, lens: Lens) {
    const { info, pos, bucket } = this.data;
    const roles = this.role.array as Float32Array;
    roles.fill(0);
    let lit: number[] = [];
    if (lens === "all") lit = q.top10;
    else if (lens === "p10-router") lit = q.p10_top10;
    else for (const i of q.batch) { if (bucket[i] < info.p10_max_bucket) lit.push(i); else roles[i] = 2; }
    for (const i of lit) roles[i] = 1;
    this.role.needsUpdate = true;

    const marks = [...lit.map((i) => [i, 1] as const), ...Array.from(roles.keys()).filter((i) => roles[i] === 2).map((i) => [i, 2] as const)];
    const hp = new Float32Array(marks.length * 3), hc = new Float32Array(marks.length * 3);
    const hs = new Float32Array(marks.length), hz = new Float32Array(marks.length);
    marks.forEach(([i, r], k) => {
      hp.set([pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]], k * 3);
      hc.set(r === 1 ? [0.37, 0.86, 0.89] : [1.0, 0.36, 0.31], k * 3);
      hs[k] = r === 1 ? 17 : 13; hz[k] = r === 1 ? 64 : 42;
    });
    for (const [layer, size] of [[this.hl, hs], [this.halo, hz]] as const) {
      layer.geometry.setAttribute("position", new THREE.BufferAttribute(hp.slice(), 3));
      layer.geometry.setAttribute("aColor", new THREE.BufferAttribute(hc.slice(), 3));
      layer.geometry.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
      layer.geometry.computeBoundingSphere();
    }

    const max = lens === "all" ? 100 : info.p10_max_bucket;
    const u = this.mat.uniforms;
    if (u.uMax.value !== max) { u.uPrevMax.value = u.uMax.value; u.uMax.value = max; this.fadeT = this.still ? 1 : 0; }

    const moved = this.needleTarget.x !== q.pos[0] || this.needleTarget.y !== q.pos[1];
    this.needleTarget.set(...q.pos);
    if (this.still || this.needlePos.lengthSq() === 0) this.needlePos.copy(this.needleTarget);
    const segs = new Float32Array(lit.length * 6);
    lit.forEach((i, k) => segs.set([q.pos[0], q.pos[1], q.pos[2], pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]], k * 6));
    this.lines.geometry.setAttribute("position", new THREE.BufferAttribute(segs, 3));
    this.lines.geometry.computeBoundingSphere();
    if (moved) { const now = this.now(); this.walks.forEach((w, k) => this.planWalk(w, now - k * 0.7)); }
    this.updateNeedle();
    this.render();
  }

  private now() { return (performance.now() - this.t0) / 1000; }

  private updateNeedle() {
    const p = this.needlePos;
    const far = p.clone().addScaledVector(new THREE.Vector3(0.35, 1, 0.55).normalize(), 2.6);
    this.needle.geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array([far.x, far.y, far.z, p.x, p.y, p.z]), 3));
    for (const pts of [this.tip, this.pulse]) {
      (pts.geometry.getAttribute("position") as THREE.BufferAttribute).set([p.x, p.y, p.z]);
      pts.geometry.getAttribute("position").needsUpdate = true;
    }
  }

  private render() {
    this.group.rotation.set(this.rotX, this.rotY, 0);
    this.group.updateMatrixWorld();
    if (this.focus > 0.001) {
      const nw = this.needlePos.clone().applyMatrix4(this.group.matrixWorld);
      const f = this.focus * this.focus * (3 - 2 * this.focus);
      this.camera.position.set(nw.x * f, nw.y * f, this.baseDist + (nw.z + this.baseDist * 0.42 - this.baseDist) * f);
      this.camera.lookAt(nw.x * f, nw.y * f, nw.z * f);
    } else {
      this.camera.position.set(0, 0, this.baseDist);
      this.camera.lookAt(0, 0, 0);
    }
    (this.pulse.material as THREE.ShaderMaterial).uniforms.uTime.value = this.now();
    this.composer.render();
    if (this.onFrame) {
      const v = this.needlePos.clone().applyMatrix4(this.group.matrixWorld).project(this.camera);
      const w = this.host.clientWidth, h = this.host.clientHeight;
      this.onFrame(v.z < 1 && this.showQuery ? { x: (v.x * 0.5 + 0.5) * w, y: (-v.y * 0.5 + 0.5) * h } : null);
    }
  }

  private loop = () => {
    cancelAnimationFrame(this.raf);
    if (!this.running) return;
    if (!this.still) {
      const now = this.now();
      if (!this.dragging) { this.velY *= 0.94; this.rotY += this.velY + (this.auto ? 0.0011 * (1 - 0.7 * this.focus) : 0); }
      this.focus += (this.focusTarget - this.focus) * 0.06;
      if (this.fadeT < 1) { this.fadeT = Math.min(1, this.fadeT + 1 / 42); this.mat.uniforms.uFade.value = 1 - (1 - this.fadeT) ** 3; }
      if (this.needlePos.distanceToSquared(this.needleTarget) > 1e-6) { this.needlePos.lerp(this.needleTarget, 0.12); this.updateNeedle(); }
      for (const w of this.walks) {
        if (!this.auto) continue;
        const t = (now - w.start) / w.dur;
        if (t > 1.45) { this.planWalk(w, now + this.rnd() * 0.6); continue; }
        w.mat.uniforms.uHead.value = Math.max(0, Math.min(1, t)) * 1.0001;
        w.mat.uniforms.uFade.value = t < 1 ? 1 : Math.max(0, 1 - (t - 1) / 0.45);
      }
    } else {
      this.mat.uniforms.uFade.value = 1;
      this.focus = this.focusTarget;
    }
    this.render();
    if (!this.still) this.raf = requestAnimationFrame(this.loop);
  };

  dispose() {
    this.running = false;
    cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    document.removeEventListener("visibilitychange", this.onVis);
    this.composer.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
