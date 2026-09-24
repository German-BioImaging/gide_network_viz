// Pre-computes node positions once: graph{suffix}.json -> positions{suffix}.json (read by index.html, which never runs forces).
// `node layout.mjs` lays out every view; `node layout.mjs _ssbd` only that one ("" = all publishers, "_ssbd" = SSBD merged).
import { readFileSync, writeFileSync } from "node:fs";
import * as d3 from "d3-force";

const POLY_R = 600, OUT_R = 2.5;  // polygon radius; unique nodes are pulled to corner * OUT_R
const TICKS = 400, SEED = 42;

function layout(suffix) {
  const { publishers, nodes, links: rawLinks } = JSON.parse(readFileSync(`graph${suffix}.json`, "utf8"));
  const N = publishers.length, rot = -Math.PI / 2 + (N % 2 ? 0 : Math.PI / N);  // flat bottom edge
  const cornerAngle = i => 2 * Math.PI * i / N + rot;
  // distance from the centre to the polygon edge in direction θ
  const boundary = θ => POLY_R * Math.cos(Math.PI / N) / Math.max(...publishers.map((_, i) => Math.cos(θ - cornerAngle(i + .5))));
  const unique = n => n.p.length === 1;
  const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
  // where each node is attracted to: its corner (pushed out) if unique, else the centroid of its publishers' corners
  const target = n => {
    if (!n.p.length) return [0, 0];
    const a = n.p.map(cornerAngle), s = unique(n) ? POLY_R * OUT_R : POLY_R * .8;
    return [s * mean(a.map(Math.cos)), s * mean(a.map(Math.sin))];
  };
  const IN = .9, OUT = 1.15;  // hard constraint: shared nodes inside IN*edge, unique nodes outside OUT*edge
  function polygonForce() {
    let ns;
    const f = () => {
      for (const n of ns) {
        if (n.fx != null) continue;
        const d = Math.hypot(n.x, n.y) || 1e-6, b = boundary(Math.atan2(n.y, n.x));
        const lim = unique(n) ? b * OUT : b * IN;
        if (unique(n) ? d < lim : d > lim) { n.x *= lim / d; n.y *= lim / d; n.vx *= .5; n.vy *= .5; }
      }
    };
    f.initialize = x => ns = x;
    return f;
  }

  let seed = SEED;  // seeded LCG so the layout is reproducible
  const rand = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;
  for (const n of nodes) {
    if (n.pub !== undefined) {
      const a = cornerAngle(n.pub);
      n.fx = n.x = POLY_R * Math.cos(a); n.fy = n.y = POLY_R * Math.sin(a);
    } else {
      const [x, y] = target(n);
      n.x = x + (rand() - .5) * 300; n.y = y + (rand() - .5) * 300;
    }
  }
  const links = rawLinks.map(([source, target]) => ({ source, target }));
  const sim = d3.forceSimulation(nodes).randomSource(rand).stop()
    .force("link", d3.forceLink(links).id(n => n.id).distance(20).strength(l => 1 / Math.min(l.source.k, l.target.k)))
    .force("charge", d3.forceManyBody().strength(-12).theta(1.2).distanceMax(600))
    .force("x", d3.forceX(n => target(n)[0]).strength(.02)).force("y", d3.forceY(n => target(n)[1]).strength(.02))
    .force("polygon", polygonForce())
    .velocityDecay(.6);

  console.time(`layout${suffix}`);
  for (let i = 0; i < TICKS; i++) sim.tick();
  console.timeEnd(`layout${suffix}`);

  // self-check: the inside/outside rule holds
  for (const n of nodes) {
    if (n.pub !== undefined) continue;
    const d = Math.hypot(n.x, n.y), b = boundary(Math.atan2(n.y, n.x));
    if (unique(n) ? d < b * OUT - 1 : d > b * IN + 1) throw new Error(`node ${n.id} on the wrong side of the polygon`);
  }

  const r1 = v => Math.round(v * 10) / 10;
  writeFileSync(`positions${suffix}.json`, JSON.stringify({
    polygon: publishers.map((_, i) => [r1(POLY_R * Math.cos(cornerAngle(i))), r1(POLY_R * Math.sin(cornerAngle(i)))]),
    pos: nodes.map(n => [r1(n.x), r1(n.y)]),  // indexed by node id (ids are 0..n-1)
  }));
  console.log(`positions${suffix}.json: ${nodes.length} nodes`);
}

const VIEWS = ["", "_ssbd"];
for (const v of process.argv.length > 2 ? process.argv.slice(2) : VIEWS) layout(v);
