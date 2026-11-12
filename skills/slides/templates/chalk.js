/* chalk.js: hand-drawn writing and doodles for SVG, driven by progress (0..1).
 *
 * Text is written stroke by stroke with single-stroke handwriting fonts, so it looks
 * like someone writing it, not an outline being traced. Doodles are any SVG path data,
 * roughened and drawn in order. Every mark is a pure function of progress, so it works
 * inside renderFrame(t) (gif-create), and .play() / Chalk.auto() animate it live (decks, guides).
 *
 *   const board = Chalk.board(svg, { look: "chalk" });
 *   const city  = board.write("St. Louis, Missouri", { x: 540, y: 420, size: 120, anchor: "middle" });
 *   const arch  = board.doodle("M 380 760 C 420 420, 660 420, 700 760", { rough: 2 });
 *   city.draw(p); arch.draw(p); board.erase(p);
 *
 * Fonts: EMS Allure ("script") and EMS Readability ("print") by Sheldon B. Michaels,
 * derived from Allura and Source Sans Pro, under the SIL Open Font License 1.1.
 * Full license: chalk-fonts-OFL.txt next to this file, or https://openfontlicense.org
 */
(function (root) {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));

  const LOOKS = {
    chalk: { color: "#f2efe4", width: 7, texture: "chalk" },
    marker: { color: "#1c2026", width: 6, texture: "none" },
    pen: { color: "#1c2026", width: 3.5, texture: "none" },
  };

  function rng(seed) {
    let a = (seed >>> 0) || 1;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const hash = (s) => [...String(s)].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619), 2166136261) >>> 0;

  // Smooth value noise in 1D, for wobble that drifts instead of jittering per point.
  function noise1(r) {
    const k = Array.from({ length: 64 }, () => r() * 2 - 1);
    return (x) => {
      const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
      return k[((i % 64) + 64) % 64] * (1 - u) + k[(((i + 1) % 64) + 64) % 64] * u;
    };
  }

  // Catmull-Rom through the points, as cubic Bezier path data.
  function smooth(pts) {
    if (pts.length < 2) return "";
    const f = (n) => Math.round(n * 10) / 10;
    if (pts.length === 2) return `M${f(pts[0][0])} ${f(pts[0][1])}L${f(pts[1][0])} ${f(pts[1][1])}`;
    let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      d += `C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
    }
    return d;
  }

  // Glyph path data ("M x y L x y ... M ...") to an array of point lists.
  function glyphStrokes(d) {
    return d.split("M").filter(Boolean).map((s) => s.split("L").map((p) => p.trim().split(/\s+/).map(Number)));
  }

  // Sample arbitrary path data into point lists (one per subpath that starts with an absolute M).
  let scratch = null;
  function samplePath(d, step) {
    if (!scratch) {
      const s = document.createElementNS(NS, "svg");
      s.setAttribute("width", "0"); s.setAttribute("height", "0");
      s.style.cssText = "position:absolute;visibility:hidden";
      scratch = document.createElementNS(NS, "path");
      s.appendChild(scratch); document.body.appendChild(s);
    }
    return d.split(/(?=M)/).map((sub) => sub.trim()).filter(Boolean).map((sub) => {
      scratch.setAttribute("d", sub);
      const L = scratch.getTotalLength(), n = Math.max(2, Math.ceil(L / step));
      const pts = [];
      for (let i = 0; i <= n; i++) { const p = scratch.getPointAtLength((L * i) / n); pts.push([p.x, p.y]); }
      return pts;
    });
  }

  function roughen(strokes, amount, seed, freq = 0.02) {
    if (!amount) return strokes;
    const r = rng(seed), nx = noise1(r), ny = noise1(r);
    let s = 0;
    return strokes.map((pts) => pts.map(([x, y], i) => {
      if (i) s += Math.hypot(x - pts[i - 1][0], y - pts[i - 1][1]);
      return [x + nx(s * freq) * amount, y + ny(s * freq + 17) * amount];
    }));
  }

  function measure(text, o = {}) {
    const F = Chalk.fonts[o.font || "script"], k = (o.size || 100) / F.em;
    return Math.max(...String(text).split("\n").map((line) =>
      [...line].reduce((w, ch) => w + ((F.glyphs[ch] || F.glyphs["?"])[0] * k) + (o.tracking || 0), 0)));
  }

  // Lay out text as stroke point lists in user space. Baseline at y.
  function layout(text, o) {
    const F = Chalk.fonts[o.font] || Chalk.fonts.script;
    const k = o.size / F.em, r = rng(o.seed), j = o.jitter;
    const lines = String(text).split("\n"), out = [];
    lines.forEach((line, li) => {
      const w = measure(line, o);
      let x = o.x - (o.anchor === "middle" ? w / 2 : o.anchor === "end" ? w : 0);
      const y = o.y + li * o.size * o.lineHeight;
      const drift = (r() - 0.5) * 0.02 * j; // a slightly uphill or downhill line
      for (const ch of line) {
        const g = F.glyphs[ch] || F.glyphs["?"];
        const rot = (r() - 0.5) * 0.05 * j, sc = 1 + (r() - 0.5) * 0.06 * j, dy = (r() - 0.5) * o.size * 0.035 * j;
        const ox = x, oy = y + dy + (x - o.x) * drift;
        if (g[1]) {
          for (const s of glyphStrokes(g[1])) {
            out.push(s.map(([gx, gy]) => {
              const px = (gx + gy * o.slant) * k * sc, py = -gy * k * sc;
              return [ox + px * Math.cos(rot) - py * Math.sin(rot), oy + px * Math.sin(rot) + py * Math.cos(rot)];
            }));
          }
        }
        x += g[0] * k + o.tracking;
      }
    });
    return out;
  }

  /* ---------- texture filters, one set per <svg> ---------- */
  function ensureDefs(svg) {
    const id = svg.__chalkId || (svg.__chalkId = "chalk" + Math.random().toString(36).slice(2, 7));
    if (svg.querySelector(`#${id}-tex`)) return id;
    const vb = svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width ? svg.viewBox.baseVal : { x: 0, y: 0, width: 4000, height: 4000 };
    const region = `filterUnits="userSpaceOnUse" x="${vb.x - 50}" y="${vb.y - 50}" width="${vb.width + 100}" height="${vb.height + 100}"`;
    const defs = document.createElementNS(NS, "defs");
    defs.innerHTML = `
      <filter id="${id}-tex" ${region} color-interpolation-filters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency="0.62" numOctaves="2" seed="11" result="n"/>
        <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -3.4 0 0 0 2.75" result="grain"/>
        <feComposite in="SourceGraphic" in2="grain" operator="in" result="grained"/>
        <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="4" result="warp"/>
        <feDisplacementMap in="grained" in2="warp" scale="3.5" xChannelSelector="R" yChannelSelector="G" result="rough"/>
        <feGaussianBlur in="rough" stdDeviation="2.2" result="dust"/>
        <feComponentTransfer in="dust" result="dust2"><feFuncA type="linear" slope="0.35"/></feComponentTransfer>
        <feMerge><feMergeNode in="dust2"/><feMergeNode in="rough"/></feMerge>
      </filter>
      <filter id="${id}-slate" ${region} color-interpolation-filters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency="0.006 0.012" numOctaves="3" seed="8" result="n"/>
        <feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  1.1 0 0 0 -0.48"/>
        <feComposite in2="SourceGraphic" operator="in"/>
      </filter>`;
    svg.insertBefore(defs, svg.firstChild);
    return id;
  }

  /* ---------- a mark: one piece of writing or one doodle ---------- */
  class Mark {
    constructor(board, strokes, o) {
      this.board = board;
      this.strokes = strokes.filter((s) => s.length > 1);
      const g = (this.el = document.createElementNS(NS, "g"));
      g.setAttribute("class", "chalk-mark");
      g.setAttribute("fill", "none");
      g.setAttribute("stroke", o.color);
      g.setAttribute("stroke-width", o.width);
      g.setAttribute("stroke-linecap", "round");
      g.setAttribute("stroke-linejoin", "round");
      (o.parent || board.el).appendChild(g);
      this.paths = this.strokes.map((pts) => {
        const p = document.createElementNS(NS, "path");
        p.setAttribute("d", smooth(pts));
        g.appendChild(p);
        return p;
      });
      // Pen lifts take time too: each stroke starts after a gap measured in path length.
      let at = 0;
      this.spans = this.paths.map((p, i) => {
        const len = p.getTotalLength();
        p.style.strokeDasharray = `${len + 1} ${len + 1}`;
        const s = { start: at + (i ? o.lift : 0), len };
        at = s.start + len;
        return s;
      });
      this.total = at || 1;
      if (o.nib) {
        this.nib = document.createElementNS(NS, "circle");
        this.nib.setAttribute("r", o.width * 0.9);
        this.nib.setAttribute("fill", o.color);
        this.nib.setAttribute("stroke", "none");
        g.appendChild(this.nib);
      }
      this.draw(0);
    }
    // Reveal up to progress p (0..1). Call it with an eased value if you want acceleration.
    draw(p) {
      const target = clamp(p) * this.total;
      let tip = null;
      this.spans.forEach((s, i) => {
        const shown = clamp(target - s.start, 0, s.len), path = this.paths[i];
        path.style.strokeDashoffset = s.len + 1 - shown;
        path.style.visibility = shown > 0 ? "visible" : "hidden";
        if (shown > 0 && shown < s.len) tip = path.getPointAtLength(shown);
      });
      if (this.nib) {
        this.nib.style.visibility = tip ? "visible" : "hidden";
        if (tip) { this.nib.setAttribute("cx", tip.x); this.nib.setAttribute("cy", tip.y); }
      }
      this.progress = clamp(p);
      return this;
    }
    // Fade the mark away like a quick wipe of the eraser (0 = untouched, 1 = gone).
    erase(p) { this.el.style.opacity = 1 - clamp(p); return this; }
    // Live playback for decks and guides. Resolves when finished.
    play(ms, { delay = 0, ease = (x) => x } = {}) {
      cancelAnimationFrame(this._raf);
      if (root.__CHALK_INSTANT__) { this.draw(1); return Promise.resolve(); }
      return new Promise((done) => {
        const t0 = performance.now() + delay;
        const tick = (now) => {
          const k = clamp((now - t0) / ms);
          this.draw(ease(k));
          k < 1 ? (this._raf = requestAnimationFrame(tick)) : done();
        };
        this.draw(0);
        this._raf = requestAnimationFrame(tick);
      });
    }
    stop() { cancelAnimationFrame(this._raf); return this; }
    // Bounding box of the finished mark, for circling or underlining it.
    get box() {
      const xs = this.strokes.flat().map((p) => p[0]), ys = this.strokes.flat().map((p) => p[1]);
      const x = Math.min(...xs), y = Math.min(...ys);
      return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y, cx: (x + Math.max(...xs)) / 2, cy: (y + Math.max(...ys)) / 2 };
    }
  }

  /* ---------- a board: a layer of marks inside an <svg> ---------- */
  class Board {
    constructor(svg, o = {}) {
      this.svg = svg;
      const look = LOOKS[o.look || "chalk"] || LOOKS.chalk;
      this.o = { look: o.look || "chalk", color: o.color || look.color, width: o.width || look.width, texture: o.texture || look.texture, seed: o.seed || 7 };
      this.id = ensureDefs(svg);
      this.el = document.createElementNS(NS, "g");
      this.el.setAttribute("class", "chalk-board");
      if (this.o.texture === "chalk") this.el.setAttribute("filter", `url(#${this.id}-tex)`);
      (o.parent || svg).appendChild(this.el);
      this.n = 0;
    }
    opts(o) {
      return {
        color: o.color || this.o.color, width: o.width || this.o.width, parent: o.parent,
        nib: o.nib ?? false, seed: o.seed ?? this.o.seed * 101 + ++this.n,
      };
    }
    // Handwrite text. y is the baseline. size is the em size in user units.
    // maxWidth shrinks the size until the longest line fits.
    write(text, o = {}) {
      let size = o.size || 100;
      const base = this.opts(o);
      if (o.maxWidth) size = Math.min(size, size * o.maxWidth / measure(text, { font: o.font, size, tracking: o.tracking }));
      const strokes = layout(text, {
        x: o.x || 0, y: o.y || 0, size, font: o.font || "script", anchor: o.anchor || "start",
        tracking: o.tracking || 0, slant: o.slant || 0, lineHeight: o.lineHeight || 1.05,
        jitter: o.jitter ?? 1, seed: base.seed,
      });
      return new Mark(this, roughen(strokes, o.rough ?? 0, base.seed), {
        ...base, width: o.width || Math.max(2.5, size * 0.055), lift: o.lift ?? size * 0.35,
      });
    }
    // Draw SVG path data (string or array). Each absolute M starts a new stroke, drawn in order.
    doodle(d, o = {}) {
      const base = this.opts(o);
      const strokes = [].concat(d).flatMap((s) => samplePath(s, 5));
      return new Mark(this, roughen(strokes, o.rough ?? 2, base.seed, o.wobble || 0.02), { ...base, lift: o.lift ?? 40 });
    }
    underline(mark, o = {}) {
      const b = mark.box || mark, y = b.y + b.h + (o.gap ?? 14);
      return this.doodle(Chalk.shape.underline(b.x - 10, b.x + b.w + 16, y, o.double), o);
    }
    circle(mark, o = {}) {
      const b = mark.box || mark, pad = o.pad ?? 24;
      return this.doodle(Chalk.shape.loop(b.cx, b.cy, b.w / 2 + pad, b.h / 2 + pad), o);
    }
    arrow(x1, y1, x2, y2, o = {}) { return this.doodle(Chalk.shape.arrow(x1, y1, x2, y2, o.bend ?? 0.2), o); }
    // A slate (chalkboard) or paper panel to write on. Returns the <g> so you can move or fade it.
    panel(x, y, w, h, o = {}) {
      const g = document.createElementNS(NS, "g");
      g.setAttribute("class", "chalk-panel");
      const kind = o.kind || (this.o.look === "chalk" ? "slate" : "paper");
      const fill = o.fill || (kind === "slate" ? "#26332e" : "#fbfaf6");
      const r = o.radius ?? 10, frame = o.frame ?? (kind === "slate" ? 22 : 0);
      g.innerHTML =
        (frame ? `<rect x="${x - frame}" y="${y - frame}" width="${w + frame * 2}" height="${h + frame * 2}" rx="${r + frame / 2}" fill="${o.frameColor || "#8a5b36"}"/>` : "") +
        `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}"/>` +
        (kind === "slate" ? `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="#ffffff" filter="url(#${this.id}-slate)" opacity="${o.smudge ?? 0.3}"/>` : "");
      this.el.parentNode.insertBefore(g, this.el);
      return g;
    }
    erase(p) { this.el.style.opacity = 1 - clamp(p); return this; }
    clear() { this.el.replaceChildren(); return this; }
  }

  /* ---------- hand-drawn shape helpers (return path data for board.doodle) ---------- */
  const shape = {
    underline: (x1, x2, y, double) => {
      const a = `M ${x1} ${y + 3} Q ${(x1 + x2) / 2} ${y - 6} ${x2} ${y}`;
      return double ? [a, `M ${x1 + 20} ${y + 16} Q ${(x1 + x2) / 2} ${y + 9} ${x2 - 10} ${y + 15}`] : a;
    },
    // A loop that overshoots its start, like circling something by hand.
    loop: (cx, cy, rx, ry) => {
      let d = "";
      for (let i = 0; i <= 44; i++) {
        const a = -2.4 + (i / 44) * (Math.PI * 2 + 0.55), k = 1 + 0.06 * Math.sin(i / 4);
        d += (i ? " L " : "M ") + (cx + Math.cos(a) * rx * k).toFixed(1) + " " + (cy + Math.sin(a) * ry * k).toFixed(1);
      }
      return d;
    },
    arrow: (x1, y1, x2, y2, bend = 0.2) => {
      const mx = (x1 + x2) / 2 - (y2 - y1) * bend, my = (y1 + y2) / 2 + (x2 - x1) * bend;
      const ang = Math.atan2(y2 - my, x2 - mx), L = Math.min(38, Math.hypot(x2 - x1, y2 - y1) * 0.25);
      const h = (s) => `${(x2 - Math.cos(ang + s) * L).toFixed(1)} ${(y2 - Math.sin(ang + s) * L).toFixed(1)}`;
      return [`M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`, `M ${h(0.5)} L ${x2} ${y2} L ${h(-0.5)}`];
    },
    strike: (x1, x2, y) => `M ${x1} ${y + 4} L ${x2} ${y - 4}`,
    box: (x, y, w, h) => `M ${x + 6} ${y} L ${x + w} ${y + 3} L ${x + w - 3} ${y + h} L ${x - 2} ${y + h - 2} L ${x + 2} ${y - 6}`,
    check: (x, y, s = 60) => `M ${x} ${y} L ${x + s * 0.35} ${y + s * 0.4} L ${x + s} ${y - s * 0.55}`,
    star: (cx, cy, r) => {
      const p = [0, 2, 4, 1, 3, 0].map((i) => { const a = -Math.PI / 2 + (i * Math.PI * 2) / 5; return `${(cx + Math.cos(a) * r).toFixed(1)} ${(cy + Math.sin(a) * r).toFixed(1)}`; });
      return "M " + p.join(" L ");
    },
  };

  /* ---------- time: pause a scene, draw, then carry on ---------- */
  // sceneSeconds: how long the underlying scene (or footage) runs.
  // holds: [{ at: sceneSecond, dur: seconds, name }], where the scene freezes while you draw.
  // at(sec) maps output time to { scene, hold, p } where hold is the hold's name (or null) and p its 0..1 progress.
  function timeline(sceneSeconds, holds = []) {
    const hs = holds.map((h, i) => ({ name: h.name ?? i, at: h.at, dur: h.dur })).sort((a, b) => a.at - b.at);
    let shift = 0;
    hs.forEach((h) => { h.out = h.at + shift; shift += h.dur; });
    return {
      seconds: sceneSeconds + shift,
      holds: hs,
      at(sec) {
        let s = sec;
        for (const h of hs) {
          if (sec < h.out) break;
          if (sec < h.out + h.dur) return { scene: h.at, hold: h.name, p: (sec - h.out) / h.dur };
          s -= h.dur;
        }
        return { scene: Math.min(s, sceneSeconds), hold: null, p: 0 };
      },
      // Source ranges of the scene's audio and where each lands in the output; holds are silent.
      audioSegments() {
        const segs = []; let from = 0, at = 0;
        for (const h of hs) { segs.push({ from, to: h.at, at }); at = h.out + h.dur; from = h.at; }
        segs.push({ from, to: sceneSeconds, at });
        return segs.filter((s) => s.to > s.from);
      },
    };
  }

  // Show footage frames (made by scripts/prepare-footage.mjs) in an <img> or SVG <image>.
  function footage(el, F) {
    const pad = (n) => String(n).padStart(5, "0");
    const attr = el instanceof SVGElement ? "href" : "src";
    let last = -1;
    return {
      show(sceneSec) {
        const i = clamp(Math.floor(sceneSec * F.fps + 1e-6), 0, F.frames - 1);
        if (i === last) return Promise.resolve();
        last = i;
        el.setAttribute(attr, `${F.dir}/f${pad(i + 1)}.jpg`);
        if (el.decode) return el.decode().catch(() => {});
        return new Promise((r) => { el.onload = r; el.onerror = r; });
      },
    };
  }

  /* ---------- declarative mode for decks and guides ---------- */
  // <svg viewBox="..."><text data-chalk x=".." y=".." font-size="90">St. Louis</text><path data-chalk d="..."/></svg>
  // Marks in one <svg> play in order whenever the svg becomes visible, and reset when it's hidden.
  // data-chalk on <text> may name the font ("script" or "print"); data-chalk-ms sets the duration.
  // Chalk.auto(), Chalk.auto(options), or Chalk.auto(rootElement, options).
  function auto(a, b) {
    const scope = a && a.querySelectorAll ? a : document;
    const o = (a && !a.querySelectorAll ? a : b) || {};
    const groups = [...scope.querySelectorAll("svg")].filter((s) => s.querySelector("[data-chalk]")).map((svg) => {
      const board = new Board(svg, { look: svg.dataset.chalkLook || o.look, color: svg.dataset.chalkColor || o.color });
      const marks = [...svg.querySelectorAll("[data-chalk]")].map((el) => {
        const ms = +el.dataset.chalkMs || 0, num = (a, d = 0) => +(el.getAttribute(a) ?? d);
        let m;
        if (el.tagName.toLowerCase() === "text") {
          const anchor = el.getAttribute("text-anchor") || "start";
          m = board.write(el.textContent.trim(), {
            x: num("x"), y: num("y"), size: num("font-size", 80), anchor,
            font: el.dataset.chalk || "script", color: el.getAttribute("fill") || undefined,
          });
        } else {
          m = board.doodle(el.getAttribute("d"), { color: el.getAttribute("stroke") || undefined, width: +el.getAttribute("stroke-width") || undefined, rough: +(el.dataset.chalkRough ?? 2) });
        }
        el.remove();
        m.ms = ms || Math.min(2600, 500 + m.total * 1.6);
        return m;
      });
      return { svg, marks, shown: false };
    });
    const run = async (g) => {
      const token = (g.token = {});
      for (const m of g.marks) { if (g.token !== token) return; await m.play(m.ms); }
    };
    const check = () => {
      for (const g of groups) {
        const vis = g.svg.checkVisibility ? g.svg.checkVisibility({ opacityProperty: true, visibilityProperty: true }) : g.svg.getClientRects().length > 0;
        if (vis && !g.shown) { g.shown = true; run(g); }
        else if (!vis && g.shown) { g.shown = false; g.token = null; g.marks.forEach((m) => m.stop().draw(0)); }
      }
    };
    if (root.__CHALK_INSTANT__ || matchMedia("print, (prefers-reduced-motion: reduce)").matches) { groups.forEach((g) => g.marks.forEach((m) => m.draw(1))); return groups; }
    // Slides and states change visibility through classes and CSS transitions, so check on both.
    let timer;
    new MutationObserver(() => { check(); clearTimeout(timer); timer = setTimeout(check, 900); })
      .observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ["class", "style", "hidden"] });
    addEventListener("transitionend", check, true);
    addEventListener("beforeprint", () => groups.forEach((g) => g.marks.forEach((m) => m.stop().draw(1))));
    requestAnimationFrame(check);
    return groups;
  }

  const Chalk = { board: (svg, o) => new Board(svg, o), measure, timeline, footage, auto, shape, looks: LOOKS, fonts: null };
  root.Chalk = Chalk;

  /* ---------- font data (generated; do not edit by hand) ---------- */
  Chalk.fonts = {"script":{"em":1000,"asc":800,"xh":300,"cap":500,"glyphs":{"0":[662,"M466 583L432 608L343 611L293 589L189 520L132 463L85 387L47 265L41 164L82 63L151 16L230 -6L318 9L422 63L520 161L576 268L608 384L608 479L583 558L532 608L479 649L425 665L350 668"],"1":[378,"M170 450L261 523L315 589L356 646L384 646L287 428L192 211L154 101L145 38M6 9L69 32L132 32L205 38L284 35"],"2":[702,"M198 491L195 501L195 536L287 602L372 630L472 643L573 621L621 586L649 510L617 432L539 346L435 265L350 205L261 148L198 113L170 98L123 66L104 47L57 16L57 47L82 82L120 95L186 91L255 66L299 38L403 -3L513 -6L570 19L617 57L630 85"],"3":[665,"M239 498L255 567L321 617L406 639L479 643L558 624L605 564L608 498L589 460L545 422L510 394L438 378L362 365L312 346L299 356L293 384L369 378L482 356L536 337L567 290L576 208L554 145L495 79L428 32L353 0L220 -19L148 -9L104 19L76 72L85 110L101 132"],"4":[558,"M243 -6L268 95L321 249L419 463L504 636L372 526L239 422L104 340L38 284L-3 224L50 252L88 268L183 268L261 265L334 249L410 249L491 280L529 306L554 337"],"5":[643,"M318 608L220 460L164 362L220 397L312 428L387 432L460 416L523 378L548 321L548 255L523 183L457 101L378 50L284 13L192 -3L117 -3L50 9L3 32L-25 79L-35 129L-16 154M280 614L422 624L570 630L652 624"],"6":[602,"M551 507L554 576L523 624L450 636L337 614L214 520L145 432L88 312L60 186L69 98L120 32L195 6L274 6L334 35L406 91L454 154L479 252L463 324L406 365L337 372L271 359L227 321"],"7":[501,"M110 507L148 592L208 630L318 636L447 621L523 617L576 611L617 633L435 438L293 261L189 139L126 32L113 25"],"8":[592,"M384 662L268 611L195 536L202 460L227 406L293 375L359 375L435 350L482 280L479 195L444 145L343 76L255 25L173 16L95 22L38 54L25 132L69 214L170 290L422 428L501 469L554 513L573 589L548 643L491 668L384 662"],"9":[605,"M369 328L318 293L243 284L164 309L126 359L126 454L170 551L239 611L299 643L403 658L485 630L539 558L551 482L529 369L498 284L435 183L359 110L284 50L227 22L158 9L104 9L47 54L35 88L38 158"]," ":[378],"!":[359,"M444 665L403 592L295 362L232 214M204 63L182 41"],"\"":[302,"M95 548L79 403M233 548L211 400"],"#":[926,"M410 743L167 41M693 737L460 38M95 469L825 472M13 192L753 192"],"$":[592,"M372 403L447 463L479 532L463 586L419 608L328 608L205 576L126 513L98 457L91 422L98 375L246 198L274 151L249 117L192 101L142 107L88 117L63 129M432 658L403 633L239 359L63 13"],"%":[548,"M189 649L120 621L66 558L66 479L104 444L164 450L211 495L243 545L246 602L233 633L205 646L271 624L413 630L476 662L410 573L211 280L57 19M306 202L261 132L255 60L296 22L340 22L400 66L432 113L441 202L410 233L353 236L306 202"],"&":[828,"M602 658L573 646L542 595L526 561L526 520M548 621L510 662L457 690L359 680L280 652L249 567L274 488L321 410L387 340L274 328L164 315L66 239L25 145L57 60L120 3L224 -16L343 -3L450 25L539 72L598 142L636 214L646 280L639 321L621 375M728 491L728 463L696 428L570 350L472 309L384 265L340 192L343 154L372 110"],"'":[173,"M98 551L79 400"],"(":[447,"M501 684L293 573L148 444L73 315L25 154L19 19L38 -98L66 -161"],")":[617,"M372 684L428 554L425 362L356 158L246 9L139 -76L41 -123L-50 -158"],"*":[762,"M236 602L243 598L400 261M457 617L186 271M554 438L117 428"],"+":[731,"M101 243L586 243M435 432L249 16"],",":[211,"M104 57L123 22L101 -9L28 -117"],"-":[444,"M161 236L387 243"],".":[224,"M145 63L129 38"],"/":[564,"M482 655L252 356L126 183L25 22"],":":[246,"M195 252L183 230M139 63L126 41"],";":[224,"M189 252L173 230M101 60L120 41L117 19L101 -9L32 -101"],"<":[450,"M391 561L101 277L167 186L208 132L252 60"],"=":[646,"M189 318L573 328M145 139L189 154L548 151"],">":[472,"M252 554L328 438L391 375L293 280L173 164L85 79"],"?":[564,"M139 561L151 602L173 624L246 665L309 696L413 693L469 652L498 561L466 476L422 413L362 365L315 337L246 280L214 236L202 205M129 57L107 32"],"@":[895,"M602 517L510 551L381 501L284 428L220 356L186 293L183 236L208 202L249 186L309 202L362 252L450 340L554 463L576 463L529 369L507 299L501 214L529 183L598 189L680 255L750 359L788 447L797 554L759 649L658 712L539 724L406 709L265 646L132 542L54 438L-3 284L6 170L41 98L132 19L258 -16L410 -13L570 28L580 35L715 123L788 202L816 258L822 312L816 378"],"A":[1062,"M-9 41L9 -16L66 -57L154 -66L274 -25L406 79L529 205L662 359L737 463L813 558L882 636L939 699L958 706L876 570L797 346L753 189L750 98L775 19L819 3L910 54L986 126L1030 180M129 161L132 246L167 302L249 331L324 334L441 312L513 296L652 280L813 261L901 261L929 274L958 293"],"B":[860,"M95 328L22 369L3 419L25 510L117 583L328 680L548 712L696 709L781 677L819 627L816 561L788 520L737 479L598 435L529 425L469 416L428 410L542 324L633 246L668 158L652 72L605 13L532 -38L438 -44L375 -44L318 -25L290 32L277 82L208 32L161 0L148 25L186 148L324 406L372 510L419 561L479 573L517 570"],"C":[690,"M296 362L403 372L526 441L617 526L658 608L639 680L564 712L375 662L249 576L110 419L41 280L13 132L60 25L189 -31L346 -16L476 35L595 113L668 189"],"D":[1033,"M652 554L545 507L472 403L454 334L387 186L350 107L302 9L265 -44L236 -38L205 32L202 113L214 208L233 145L375 35L510 -9L728 25L863 113L976 220L1033 372L1021 532L951 627L828 680L608 706L413 671L261 614L154 548L95 460L85 384L126 321L189 293"],"E":[850,"M662 580L668 504L589 662L501 718L400 706L324 621L328 526L365 428L406 372L444 321L504 306L507 337L466 350L359 346L180 321L41 217L-3 107L44 9L170 -50L318 -47L498 -22L643 38L756 113L803 180L810 205L806 252"],"F":[624,"M517 576L435 551L369 479L331 384L277 296L217 170L164 76L158 25L176 0L224 9L252 47L268 66M73 372L25 403L-6 476L44 589L145 652L346 690L513 674L630 658L709 658L791 655L828 677L813 680L740 605L718 554L721 507M230 309L195 287L570 331"],"G":[951,"M825 639L781 696L731 718L621 718L454 677L328 608L208 517L135 419L88 337L66 246L79 161L126 95L214 44L324 32L472 72L580 142L699 233L753 284L775 312L835 353L854 372L822 362L769 271L677 -41L573 -208L466 -353L365 -406L271 -413L227 -375L227 -302L265 -220L365 -117L495 -31L608 28L731 69L762 76L847 91"],"H":[939,"M290 539L302 539L400 592L447 652L482 699L444 589M444 589L324 255L211 57L110 -72L6 -126L-50 -126L-123 -94L-129 -72M939 680L854 643L810 567L759 447L712 337L665 211L633 107L643 41L671 9L728 6L794 57L869 132L907 183M41 198L32 293L82 353L236 372L315 359L441 343L614 306L759 290L832 306L850 321"],"I":[548,"M501 693L410 413L334 224L280 126L220 50L167 28L98 19L9 25L-6 50L22 72L66 41L117 32L447 38M233 450L176 523L202 602L277 665L394 684L523 677L598 674L665 649"],"J":[687,"M643 715L614 687L567 586L501 400L428 202L328 41L258 -35L145 -94L54 -72L28 9L82 110L214 243L309 302L428 356L529 384L624 403M268 438L217 476L211 567L265 633L397 674L523 684L636 668L684 646"],"K":[759,"M132 532L255 592L334 699L208 359L154 208L110 132L41 32L-25 -50L-126 -120L-211 -129L-258 -113L-293 -57M756 699L564 583L381 435L236 293L145 180M296 403L350 189L435 41L529 -9L595 3L624 50L611 72L595 98"],"L":[617,"M230 126L239 126L425 202L589 337L687 510L702 624M709 624L671 702L605 721L498 680L410 567L346 369L249 88L214 -6L176 -69L145 -107L126 -120M123 82L6 50L19 82L135 41L302 -76L435 -151L583 -211L750 -202L819 -151L838 -120L841 -57"],"M":[1351,"M224 536L302 570L343 605L378 646L406 693L428 699L365 529L287 315L205 148L129 19L63 -41L0 -60L-38 -16L-19 47L95 186L249 356L447 542L570 614L649 633L721 605L756 513L740 315L721 189L687 76L712 82L784 198L961 463L1036 570L1106 621L1156 614L1175 589L1188 539L1150 428L1112 350L1068 255L1046 180L1046 101L1084 22L1181 38L1285 129L1320 183"],"N":[932,"M-230 -38L-211 -91L-154 -126L-66 -107L38 -35L129 107L214 271L274 432L321 561L350 658L359 328L381 189L447 35L507 -19L573 -35L643 0L731 129L788 274L825 472L832 589L819 646L797 709L844 643L873 605L898 586L926 570M158 513L170 517L258 558L293 595L328 658M158 513L170 517L258 558L293 595L328 658"],"O":[850,"M38 328L38 334L88 491L186 598L334 680L444 715L551 712L652 696L737 627L778 526L791 454L775 324L728 198L636 79L542 0L447 -44L290 -53L180 0L117 129L129 296L183 400L268 501L353 545L419 576L460 576L504 570"],"P":[639,"M504 576L441 561L387 526L346 479L331 416L306 362L246 265L198 173L170 98L161 63L154 32L170 0L205 13L243 57M101 359L41 394L22 463L44 545L132 611L230 658L324 687L450 702L624 693L740 649L803 595L810 523L775 441L718 378L639 340L504 296L375 274L299 261L214 271"],"Q":[800,"M699 715L775 680L816 608L813 463L759 287L646 123L532 35L447 -3L337 -25L211 -3L113 54L54 167L50 353L117 513L214 614L296 668L384 715L479 740L573 724L646 677L684 595L687 469L668 356L598 239L513 151L438 104L384 85L274 47L230 63L236 85L296 79L397 32L498 -38L605 -107L734 -183L898 -214M895 -214L1036 -189L1080 -132L1084 -104L1080 -38"],"R":[639,"M498 573L419 564L356 501L340 438L293 334L208 198L154 85L142 35L161 3L198 19L220 38L227 44M82 369L28 419L22 495L54 561L161 636L274 671L406 696L558 693L671 680L772 617L813 536L788 447L677 365L554 321L432 284L334 280L202 293L198 315L312 230L381 117L498 -22L627 -117L762 -176L882 -176L945 -139L970 -101L976 -66"],"S":[706,"M693 580L721 621L721 668L665 709L520 690L350 636L268 558L265 485L362 438L517 391L617 337L658 277L652 224L617 170L523 98L372 35L167 -6L63 9L28 47L19 129L54 202L117 255L189 293L293 324"],"T":[554,"M57 378L9 425L-3 501L38 592L113 646L198 677L287 690L466 687L639 665L806 662L860 674L825 690L743 580L734 539L728 485L743 463M529 570L450 539L391 476L324 353L239 205L180 66L180 25L198 0L230 22L268 63"],"U":[671,"M9 476L19 482L104 520L167 570L233 630L249 662L280 662L208 558L104 331L54 220L35 117L57 32L129 9L224 41L343 123L504 277L621 419L702 548L743 646L737 709L696 731L646 712L595 684L548 602L513 498L479 359L444 186L422 47L425 -57L441 -139L463 -180L498 -195L529 -198L558 -183"],"V":[737,"M54 454L0 529L25 611L73 646L189 668L302 677L391 677L447 655L469 649M331 718L337 586L299 482L258 410L211 290L164 167L142 82L145 -9L186 -38L277 -38L400 32L532 154L677 343L784 507L844 598L895 662L939 696L983 724L1002 724"],"W":[1206,"M69 444L35 476L9 545L47 614L145 662L265 680L391 677L460 665L488 652M416 709L387 592L328 501L220 353L135 217L91 145L54 66L41 6L47 -38L63 -57L98 -66L148 -60L233 -28L328 28L394 85L495 167L586 268L684 394L712 469L721 529L712 586L677 570L665 507L668 416L662 299L687 176L731 91L788 41L876 3L939 13L986 32L1052 126L1096 224L1118 324L1128 387L1115 517L1084 598L1017 649L945 668L898 662L876 643"],"X":[806,"M66 457L16 491L3 554L25 621L104 665L195 687L268 696L378 684L441 674L469 665L485 662M419 699L397 561L410 410L432 284L488 148L558 54L621 16L702 50L775 113L816 158M778 696L696 583L570 419L469 287L350 173L243 63L135 -16L32 -88L-101 -132L-192 -120L-246 -101L-268 -60L-271 -41"],"Y":[627,"M28 482L35 485L120 523L195 583L252 646L277 665L287 668L230 554L142 394L69 230L57 154L50 76L85 16L158 16L233 54L334 145L403 220L463 306L542 416L595 510L621 586L662 649L715 674L759 680L684 633L633 576L583 400L526 205L457 -6L406 -113L346 -211L296 -284L233 -346L148 -400L69 -413L32 -400L3 -350L6 -296L38 -233L107 -151L205 -60L331 9L416 41L570 91L598 91"],"Z":[627,"M145 554L135 611L180 662L255 693L381 699L501 690L595 674L674 649L734 633L788 649L822 668L835 702L803 709L759 684L721 646L595 539L457 400L362 290L302 224L227 148L164 104L107 63L57 38L19 28L0 54L16 72L63 54L145 22L243 -50L378 -135L513 -205L671 -205L747 -167L781 -98L775 -69L769 -41M239 340L236 321L621 340"],"[":[526,"M570 652L444 652L318 469L180 236L95 76L69 13L202 13"],"\\":[381,"M44 652L148 447L214 277L258 161L309 28"],"]":[510,"M428 655L554 649L479 476L362 277L280 148L186 13L54 19"],"^":[791,"M186 662L378 765L485 658"],"_":[709,"M-28 -35L674 -35"],"`":[406,"M73 523L202 444"],"a":[526,"M495 183L457 132L406 79L331 32L271 19L243 63L255 142L296 274L277 243L176 145L69 57L-19 19L-63 66L-57 154L35 261L148 331L230 356L312 356L324 343"],"b":[416,"M-31 183L47 252L132 328L233 406L312 476L394 583L416 674L372 721L284 680L195 564L98 359L38 202L28 72L38 54L50 145L132 243L249 315L334 334L365 296L369 252L328 183L287 120L189 41L135 19L-13 -9"],"c":[346,"M243 306L239 350L198 365L101 328L-16 208L-47 170L-72 110L-66 66L-47 25L57 16L186 57L268 123L315 183"],"d":[381,"M328 312L302 356L258 369L151 334L47 265L-38 176L-63 107L-57 50L13 16L79 63L176 148L277 252L387 334L532 457L668 592L693 668L690 709L639 721L561 684L510 633L441 523L387 425L293 217L246 66L233 -44L258 -98L302 -113L340 -101"],"e":[346,"M66 170L148 211L217 249L252 306L239 350L180 356L63 287L16 252L-35 192L-66 139L-72 88L-50 44L32 9L170 44L214 82L277 135L315 183"],"f":[334,"M-110 -365L-60 -321L9 -94L104 154L198 369L277 517L328 617L419 696L466 718L523 696L507 598L406 444L290 321L220 261L173 220L117 192L25 183L28 208L208 205L306 217"],"g":[469,"M306 350L195 353L69 287L-16 205L-57 164L-79 110L-60 57L-19 19L91 69L176 158L265 252L287 274L318 274L164 -85L35 -331L-22 -381L-72 -410L-117 -416L-167 -381L-148 -280L-79 -220L22 -132L85 -88L258 22L369 110L438 183"],"h":[561,"M-31 183L113 315L343 482L447 605L469 702L394 718L324 662L255 586L180 457L101 309L13 32L110 148L192 252L287 315L328 334L350 312L340 261L290 183L261 76L284 19L350 19L413 63L482 129L529 183"],"i":[249,"M-31 183L38 236L60 328L-38 85L-19 22L54 6L132 69L183 129L217 183M123 476L95 438"],"j":[258,"M-31 183L66 287L104 312L113 299L-82 -145L-173 -309L-243 -391L-306 -416L-365 -406L-387 -353L-359 -287L-252 -183L-69 -60L57 32L151 107L227 183M205 482L167 444L186 428"],"k":[356,"M-31 183L32 252L98 337M73 356L158 356L271 428L381 542L438 627L450 696L406 728L318 696L249 617L183 498L126 394L19 139L-19 13L25 54L113 173L214 284L290 343L340 346M139 249L186 44L258 -85L362 -148L428 -148L457 -120L460 -101L457 -66"],"l":[261,"M-25 176L91 265L239 428L346 589L394 662L381 709L312 718L243 674L148 532L41 340L-28 198L-50 85L-22 25L44 19L120 54L195 132L230 183"],"m":[687,"M-31 183L47 255L76 321L-35 28L38 104L167 252L233 309L280 337L302 340L309 312L296 274L208 107L318 195L403 261L491 293L447 230L400 95L413 38L472 19L561 69L655 183"],"n":[580,"M148 328L41 25L183 186L271 280L334 318L381 337L394 312L331 195L290 101L293 47L328 16L387 25L450 69L513 132L548 183"],"o":[391,"M195 337L142 365L66 315L-6 233L-41 161L-57 76L13 9L101 41L183 110L230 208L239 246L239 284L220 284M167 158L183 101L214 72L255 76L296 110L359 183"],"p":[356,"M25 359L-72 57L-176 -192L-227 -350L-255 -369L-91 38L-44 13L85 63L208 135L258 227L268 299L227 346L139 321L73 274L16 198L-25 148L-91 32"],"q":[542,"M324 334L224 359L88 293L-35 180L-60 120L-54 69L-31 28L35 25L120 76L186 154L315 284L422 416L372 406L255 91L139 -205L129 -350L161 -403L246 -403L280 -356L293 -249L280 -110L246 35L321 28L413 79L476 135L507 183"],"r":[369,"M-31 183L35 287L154 463L47 391L47 365L60 356L258 353L145 214L82 101L98 22L186 28L296 132L337 183"],"s":[302,"M-31 183L9 217L35 261L66 328L117 394L249 447L293 454L343 444L350 413L343 381L328 365M54 274L73 233L161 183L198 135L195 88L151 35L79 -6L32 -28L-25 -31L-35 -19L-35 16L-16 35"],"t":[290,"M-31 183L19 224L54 261L110 337L183 457L217 510L183 517L9 151L-6 66L19 22L98 28L192 110L258 183M54 346L258 356"],"u":[495,"M47 309L-19 217L-54 123L-57 57L-9 28L79 54L145 139L227 239L293 353L324 343L214 164L205 98L202 54L255 22L321 41L413 120L463 183"],"v":[321,"M-31 183L57 274L73 312L69 337L35 356L0 356M41 334L28 170L0 85L0 9L126 186L224 299L318 381L403 432L447 419"],"w":[554,"M69 346L-13 227L-57 120L-63 69L-50 32L-3 19L57 41L120 113L195 227L236 290L265 287L205 176L195 85L224 32L280 16L391 82L501 205L551 312L551 369L529 422L476 435"],"x":[488,"M-31 183L60 306L126 321L142 277L158 202L180 117L202 41L271 13L340 41L397 101L457 183M400 346L362 343L227 236L110 135L-3 6L-82 -101L-98 -132L-117 -183"],"y":[488,"M88 312L3 233L-31 186L-47 132L-54 85L-38 47L13 32L69 47L176 151L280 277L334 334L369 331L274 139L183 -98L107 -230L28 -346L-28 -397L-135 -394L-167 -346L-123 -252L-16 -167L123 -66L265 9L406 123L457 183"],"z":[551,"M35 202L85 277L145 331L214 340L302 315L384 296L447 318L457 340L432 356L397 334L340 280L126 85L60 22L3 9L-13 38L19 66L66 66L117 41L220 -16L315 -19L384 28L469 117L520 183"],"{":[488,"M432 668L299 643L233 545L227 444L189 384L132 369L63 362L126 328L154 274L123 208L76 158L35 72L73 -3L113 -19L158 -28"],"|":[296,"M132 684L126 -28"],"}":[558,"M372 674L447 665L482 627L472 567L432 510L397 444L369 384L419 362L482 356L375 315L324 274L302 227L293 145L255 76L161 -19L120 -28L28 -31"],"~":[491,"M161 463L195 498L246 498L321 472L384 447L406 469L422 482"],"·":[268,"M249 340L231 310"],"é":[346,"M66 170L148 211L217 249L252 306L239 350L180 356L63 287L16 252L-35 192L-66 139L-72 88L-50 44L32 9L170 44L214 82L277 135L315 183M274 608L144 529"],"–":[666,"M241 236L581 243"],"—":[888,"M321 236L775 243"],"“":[366,"M103 669L162 598M245 669L303 598"],"”":[366,"M147 612L89 541M289 612L231 541"]}},"print":{"em":1000,"asc":800,"xh":300,"cap":500,"glyphs":{"0":[501,"M246 19L306 32L369 95L397 161L410 236L416 340L410 438L387 532L356 592L306 630L261 646L224 643L164 608L123 551L95 460L85 365L82 271L95 183L126 95L164 54L202 22L246 19"],"1":[504,"M265 598L161 595L268 636L268 32L110 32L422 32"],"2":[504,"M76 558L117 598L167 630L230 646L284 636L340 608L375 561L391 491L387 432L356 359L299 277L230 192L167 126L110 63L82 32L438 32"],"3":[498,"M88 576L139 614L205 643L258 643L315 627L362 589L384 539L394 479L378 425L324 384L265 353L214 343L176 343L224 343L274 337L324 318L378 277L403 239L413 195L410 148L400 110L369 66L324 38L268 22L208 22L151 38L95 69L60 101"],"4":[504,"M340 16L340 630L47 220L444 220"],"5":[501,"M60 98L101 63L145 38L195 19L243 16L315 35L365 76L406 135L422 205L413 287L378 350L306 391L233 397L180 384L126 356L120 365L139 630L397 630"],"6":[498,"M85 265L132 315L189 359L246 378L309 378L356 356L391 324L416 265L425 195L410 123L375 63L321 25L258 16L202 35L151 72L110 135L91 224L85 318L98 438L120 510L148 567L195 614L255 639L315 643L372 624L413 589"],"7":[504,"M224 19L236 186L261 306L296 410L340 491L387 567L435 633L73 633"],"8":[501,"M296 321L359 372L397 428L406 482L403 539L362 605L299 639L249 643L173 621L123 570L110 513L126 435L176 387L265 340L346 296L400 255L425 198L419 129L400 79L340 32L265 16L205 25L142 54L95 104L79 158L85 236L135 306L176 334L230 359"],"9":[501,"M88 76L123 41L180 22L239 16L302 47L362 107L397 198L413 309L413 413L391 510L353 586L293 630L224 643L151 617L107 573L82 517L76 460L79 397L113 331L176 290L252 280L334 315L384 362L416 403"]," ":[378],"!":[280,"M195 674L195 192M173 69L173 19L220 19L220 69L173 69"],"\"":[381,"M117 693L120 491M255 693L261 491"],"#":[501,"M202 649L123 16M381 649L302 16M73 447L450 447M54 246L428 246"],"$":[501,"M391 580L340 624L287 636L255 639L255 747L255 639L189 627L139 580L120 526L123 460L148 413L198 375L309 318L353 284L387 249L406 192L406 145L391 85L337 41L271 19L255 19L255 -85L255 19L205 25L142 50L95 88"],"%":[828,"M192 284L239 293L277 324L302 375L315 444L318 495L302 564L277 617L246 649L208 665L167 662L120 633L91 589L79 536L76 428L85 372L107 328L139 299L164 287L192 284M633 13L680 22L715 57L743 104L753 173L756 224L743 296L718 350L687 381L646 397L605 391L561 365L529 321L520 268L513 161L526 101L548 60L576 32L605 16L633 13M233 9L592 671"],"&":[598,"M558 22L485 54L406 120L324 198L271 265L205 369L173 444L164 542L173 598L208 643L258 662L318 652L353 621L369 570L359 517L328 463L287 428L167 337L126 299L88 249L69 195L79 135L110 69L173 32L252 16L312 32L381 72L432 132L476 192L510 271L536 340"],"'":[249,"M117 693L123 491"],"(":[302,"M239 -148L189 -53L145 69L129 145L120 255L120 359L135 450L158 539L192 633L220 687L243 718"],")":[302,"M63 -151L117 -50L158 57L176 161L189 290L173 416L161 498L139 573L101 649L63 721"],"*":[422,"M139 488L208 589L321 627L208 589L208 709L208 589L95 627L208 589L287 485"],"+":[501,"M249 554L249 123M57 340L450 340"],",":[249,"M142 25L104 25L104 76L142 76L158 19L154 -28L135 -69L110 -94L82 -120"],"-":[328,"M57 261L261 261"],".":[249,"M98 72L98 22L148 22L148 72L98 72"],"/":[381,"M44 -142L343 709"],":":[249,"M98 454L98 406L145 406L145 454L98 454M98 72L98 25L145 25L145 72L98 72"],";":[246,"M98 454L98 403L148 403L148 454L98 454M142 25L104 25L104 76L142 76L158 19L154 -28L139 -69L110 -94L82 -120"],"<":[504,"M450 183L54 343L450 504"],"=":[504,"M50 441L450 441M50 239L450 239"],">":[498,"M57 183L450 346L57 504"],"?":[428,"M170 72L170 22L220 22L220 72L170 72M189 202L195 261L220 324L290 419L331 485L340 542L328 598L296 643L258 668L205 674L151 665L107 643L69 608"],"@":[832,"M545 413L504 173L454 123L403 98L343 95L290 135L274 202L293 302L346 381L419 419L482 406L513 378L532 340L504 167L510 129L564 88L636 95L696 145L737 211L750 293L747 378L721 469L677 536L621 586L529 617L432 624L346 608L249 558L180 491L132 419L95 324L82 243L82 173L104 79L142 3L220 -66L290 -98L387 -117L479 -113L564 -69"],"A":[548,"M41 16L277 662L416 255L132 255L416 255L501 16"],"B":[602,"M129 28L129 646L312 646L365 643L419 621L463 580L476 532L476 476L454 425L406 391L365 372L309 362L135 362L312 362L365 353L428 337L479 302L507 271L517 227L517 164L491 104L447 66L369 35L312 28L135 28"],"C":[589,"M520 98L454 47L365 16L277 28L195 72L132 148L101 227L91 346L101 457L142 548L205 617L277 652L359 658L432 643L482 611L498 592"],"D":[627,"M132 32L132 646L309 646L381 627L435 598L472 561L517 488L532 406L532 356L529 290L520 214L495 161L450 95L381 54L315 35L265 32L135 32"],"E":[539,"M466 32L132 32L132 356L410 356L132 356L132 643L454 643"],"F":[501,"M132 19L132 346L413 346L132 346L132 643L454 643"],"G":[624,"M346 315L520 315L520 82L479 54L391 22L328 19L265 32L208 63L142 139L98 233L88 343L101 450L142 545L208 617L274 649L350 662L432 649L482 621L517 592"],"H":[668,"M132 22L132 652L132 359L532 359L532 649L532 22"],"I":[268,"M132 19L132 652"],"J":[488,"M79 101L110 63L148 35L198 16L261 25L321 66L350 126L356 173L356 655"],"K":[583,"M132 19L132 655M491 649L142 255M293 425L529 19"],"L":[491,"M132 655L132 32L447 32"],"M":[731,"M129 16L129 655L161 655L365 98L570 652L592 652L592 19"],"N":[655,"M126 22L126 649L148 649L523 22L523 652"],"O":[677,"M334 22L416 35L498 88L554 173L583 284L583 387L567 472L536 542L485 608L416 649L346 662L287 652L220 627L158 573L110 482L95 410L91 302L104 220L135 145L180 85L230 44L284 25L334 22"],"P":[580,"M135 16L135 649L359 649L416 633L457 602L488 561L501 498L498 441L472 378L425 340L359 315L284 312L132 312"],"Q":[674,"M331 16L400 32L472 69L532 132L567 220L580 296L580 384L567 476L542 539L485 608L413 649L346 665L277 652L211 624L154 567L120 507L98 413L88 340L95 271L117 189L151 120L195 72L249 38L302 22L331 19L359 -38L400 -79L444 -104L501 -120L551 -123L598 -113"],"R":[580,"M129 19L129 649L340 649L391 633L447 605L488 542L488 488L479 428L441 375L394 346L318 328L132 328L312 328L495 19"],"S":[545,"M79 107L132 63L183 38L246 25L318 22L397 54L450 101L469 164L466 220L432 277L359 324L230 381L158 428L120 479L117 542L142 608L214 652L284 662L350 655L400 630L447 595"],"T":[548,"M274 22L274 649L57 649L495 649"],"U":[662,"M135 655L135 217L145 161L173 101L211 60L268 28L321 16L387 25L454 60L501 117L523 167L529 236L529 652"],"V":[513,"M44 655L255 19L466 652"],"W":[791,"M66 655L214 19L227 22L391 652L403 652L570 19L583 19L724 655"],"X":[507,"M57 19L435 655M76 658L447 19"],"Y":[472,"M44 655L236 274L236 22L236 277L425 652"],"Z":[561,"M101 649L479 649L79 28L491 28"],"[":[306,"M261 -123L129 -123L129 699L261 699"],"\\":[384,"M41 706L340 -142"],"]":[306,"M44 -120L176 -120L176 702L44 702"],"^":[504,"M101 312L249 674L400 302"],"_":[529,"M28 -82L501 -82"],"`":[558,"M220 709L312 586"],"a":[520,"M117 428L183 466L239 482L296 488L340 472L378 438L403 387L406 318L406 107L406 22L403 107L362 79L318 47L268 25L211 16L164 32L126 57L98 98L98 158L120 205L170 246L220 265L280 284L337 293L372 296L400 296"],"b":[564,"M123 718L123 16L123 101L158 72L211 38L268 22L324 19L391 57L432 101L463 164L476 243L472 321L457 394L410 454L369 476L312 488L252 476L192 444L129 394"],"c":[472,"M413 72L362 35L287 19L217 28L145 76L104 142L88 220L88 302L113 378L164 438L224 472L290 482L346 472L384 454L400 435"],"d":[567,"M438 715L438 22L438 117L394 72L334 32L274 16L224 25L173 47L123 101L91 173L85 261L107 365L161 444L236 482L296 488L359 466L400 441L441 403"],"e":[504,"M88 265L435 265L435 321L419 394L372 450L324 482L258 485L192 466L135 419L113 372L88 312L82 249L98 173L126 104L183 47L236 22L302 16L359 32L413 60"],"f":[290,"M135 19L135 472L60 472L255 472L132 472L132 611L142 658L173 706L220 724L261 718L290 706"],"g":[510,"M170 41L123 -3L91 -57L85 -113L129 -161L202 -192L287 -202L362 -183L438 -132L466 -85L463 -31L435 19L365 38L173 38L132 66L113 110L123 151L176 211L211 189L265 180L331 202L378 246L400 299L400 362L375 419L356 444L312 472L463 472L312 472L265 482L192 476L142 435L113 378L110 315L123 265L148 233L176 208"],"h":[554,"M126 22L126 715L126 365L173 416L214 454L274 479L334 485L403 447L428 403L441 331L441 19"],"i":[252,"M126 16L126 479M98 671L98 621L148 621L148 671L98 671"],"j":[261,"M-9 -186L-3 -186L32 -195L79 -192L120 -164L132 -113L132 482M104 668L104 621L154 621L154 668L104 668"],"k":[485,"M123 16L123 718M400 479L126 148M255 306L435 16"],"l":[265,"M129 715L129 63L135 41L145 28L161 19L183 19"],"m":[835,"M123 16L123 479L123 375L167 413L208 447L246 472L293 485L334 479L362 466L394 435L416 381L422 315L422 16L422 365L435 391L501 450L551 476L592 488L636 476L665 460L699 419L715 337L715 19"],"n":[558,"M126 16L126 482L126 369L170 413L211 450L243 469L290 482L321 485L369 472L397 454L419 422L438 378L438 16"],"o":[561,"M287 19L290 19L353 35L413 76L450 139L466 208L469 274L460 334L438 387L406 428L362 466L315 482L271 485L220 476L173 447L132 400L110 356L91 290L91 239L98 180L113 126L151 76L195 41L243 22L287 19"],"p":[567,"M123 -195L123 482L123 381L176 435L239 469L293 479L359 479L410 450L454 387L476 315L476 233L466 164L432 91L381 44L343 25L284 22L236 32L183 60L132 95"],"q":[558,"M438 -192L438 479L438 410L381 450L321 476L246 482L176 454L129 397L98 328L85 271L88 214L95 154L120 95L161 54L205 28L265 16L331 35L391 72L435 110"],"r":[340,"M129 19L129 482L129 340L158 397L202 454L249 476L293 482L321 479"],"s":[428,"M66 79L123 41L186 22L236 16L299 38L346 76L362 132L350 189L293 236L214 268L142 299L101 340L91 387L107 432L158 476L220 485L284 472L337 441"],"t":[334,"M299 38L265 22L220 22L180 35L145 76L139 145L139 469L47 469L290 469L139 469L139 611"],"u":[554,"M425 476L425 19L425 139L391 98L350 57L293 25L239 16L183 32L145 63L123 104L120 183L120 476"],"v":[460,"M54 485L227 16L239 16L413 485"],"w":[702,"M60 482L198 9L211 9L343 482L362 482L495 9L507 9L643 482"],"x":[435,"M50 9L365 485M69 485L387 9"],"y":[460,"M54 479L243 3M406 476L211 -79L189 -126L158 -161L120 -183L54 -183"],"z":[425,"M79 466L359 466L63 32L381 32"],"{":[309,"M265 -123L217 -126L167 -101L145 -50L158 214L145 249L120 274L98 284L57 287L107 299L145 321L151 362L148 627L158 671L202 699L265 699"],"|":[255,"M120 -220L120 740"],"}":[309,"M44 -123L104 -120L148 -98L161 -38L154 208L167 255L192 277L230 290L246 290L208 302L173 315L158 350L158 441L167 630L139 684L98 702L47 702"],"~":[504,"M76 324L110 365L151 384L202 384L249 343L302 302L334 290L372 296L400 321L428 350"],"·":[328,"M193 389L193 329L253 329L253 389L193 389"],"é":[504,"M88 265L435 265L435 321L419 394L372 450L324 482L258 485L192 466L135 419L113 372L88 312L82 249L98 173L126 104L183 47L236 22L302 16L359 32L413 60M387 766L261 596"],"–":[491,"M85 261L392 261"],"—":[655,"M113 261L523 261"],"“":[326,"M128 695L169 584M269 695L310 584"],"”":[326,"M126 695L85 584M268 695L227 584"]}}};
})(typeof window !== "undefined" ? window : globalThis);
