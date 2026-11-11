/* ---------- sound engine (do not edit) ----------
   Synthesizes sound effects with the browser's Web Audio API: no audio files, no network.
   The preview plays cues live (press M); render-gif renders them offline into the MP4. */
window.SFX = (function () {
  // Seeded PRNG so noise-based sounds come out identical on every render.
  const rng = (seed) => () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
  const noiseBuffers = new WeakMap();
  function noise(ctx) {
    if (!noiseBuffers.has(ctx)) {
      const buf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
      const d = buf.getChannelData(0), r = rng(7);
      for (let i = 0; i < d.length; i++) d[i] = r() * 2 - 1;
      noiseBuffers.set(ctx, buf);
    }
    return noiseBuffers.get(ctx);
  }

  // Gain envelope: silence -> peak over `a` s -> exponential decay to silence over `d` s.
  function env(ctx, at, peak, a, d) {
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, at);
    g.gain.linearRampToValueAtTime(peak, at + a);
    g.gain.exponentialRampToValueAtTime(0.0001, at + a + d);
    return g;
  }
  // An oscillator with an optional pitch glide from f0 to f1.
  function tone(ctx, out, at, { type = "sine", f0, f1 = f0, glide = 0.05, peak = 0.5, a = 0.004, d = 0.15, lowpass }) {
    const o = ctx.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(f0, at);
    if (f1 !== f0) o.frequency.exponentialRampToValueAtTime(f1, at + glide);
    let node = o;
    if (lowpass) { const f = ctx.createBiquadFilter(); f.frequency.value = lowpass; node = node.connect(f); }
    node.connect(env(ctx, at, peak, a, d)).connect(out);
    o.start(at); o.stop(at + a + d + 0.05);
  }
  // Filtered noise with an optional filter sweep from f0 to f1.
  function hiss(ctx, out, at, { filter = "bandpass", f0 = 2000, f1 = f0, glide, q = 1, peak = 0.4, a = 0.002, d = 0.05, offset = 0 }) {
    const s = ctx.createBufferSource();
    s.buffer = noise(ctx); s.loop = true;
    const bq = ctx.createBiquadFilter();
    bq.type = filter; bq.Q.value = q;
    bq.frequency.setValueAtTime(f0, at);
    if (f1 !== f0) bq.frequency.exponentialRampToValueAtTime(f1, at + (glide ?? a + d));
    s.connect(bq).connect(env(ctx, at, peak, a, d)).connect(out);
    s.start(at, offset); s.stop(at + a + d + 0.05);
  }

  // Presets: (ctx, out, at, opts). opts.p is the pitch multiplier; other opts come from the cue.
  const presets = {
    pop: (c, out, at, o) => tone(c, out, at, { f0: 620 * o.p, f1: 180 * o.p, glide: 0.07, peak: 0.6, d: 0.11 }),
    bloop: (c, out, at, o) => tone(c, out, at, { f0: 260 * o.p, f1: 880 * o.p, glide: 0.09, peak: 0.45, d: 0.14 }),
    click: (c, out, at, o) => hiss(c, out, at, { f0: 3200 * o.p, q: 1.2, peak: 0.7, d: 0.018 }),
    tick: (c, out, at, o) => tone(c, out, at, { f0: 2400 * o.p, peak: 0.18, a: 0.001, d: 0.035 }),
    type: (c, out, at, o) => {
      const r = rng(o.seed ?? 3);
      for (let i = 0; i < (o.count ?? 6); i++) {
        hiss(c, out, at + i * (o.gap ?? 0.075) + r() * 0.02,
          { f0: (2200 + r() * 1800) * o.p, q: 2, peak: 0.35 + r() * 0.2, d: 0.02, offset: r() * 1.5 });
      }
    },
    whoosh: (c, out, at, o) => {
      const d = o.dur ?? 0.45, lo = 350 * o.p, hi = 3200 * o.p, up = o.dir !== "down";
      hiss(c, out, at, { f0: up ? lo : hi, f1: up ? hi : lo, glide: d, q: 0.9, peak: 0.5, a: d * 0.45, d: d * 0.55 });
    },
    impact: (c, out, at, o) => {
      tone(c, out, at, { f0: 140 * o.p, f1: 42 * o.p, glide: 0.3, peak: 0.9, d: 0.45 });
      hiss(c, out, at, { filter: "lowpass", f0: 900 * o.p, f1: 200 * o.p, peak: 0.5, d: 0.12 });
    },
    riser: (c, out, at, o) => {
      const d = o.dur ?? 1;
      const s = c.createOscillator(); s.type = "sawtooth";
      s.frequency.setValueAtTime(180 * o.p, at);
      s.frequency.exponentialRampToValueAtTime(1400 * o.p, at + d);
      const f = c.createBiquadFilter();
      f.frequency.setValueAtTime(600, at);
      f.frequency.exponentialRampToValueAtTime(6000, at + d);
      const g = c.createGain();
      g.gain.setValueAtTime(0.0001, at);
      g.gain.exponentialRampToValueAtTime(0.22, at + d);
      g.gain.linearRampToValueAtTime(0.0001, at + d + 0.04);
      s.connect(f).connect(g).connect(out);
      s.start(at); s.stop(at + d + 0.05);
      hiss(c, out, at, { filter: "highpass", f0: 1000, f1: 6000, glide: d, peak: 0.15, a: d, d: 0.06 });
    },
    ding: (c, out, at, o) => {
      tone(c, out, at, { f0: 1318.5 * o.p, peak: 0.3, d: 1 });
      tone(c, out, at, { f0: 2637 * o.p, peak: 0.08, d: 0.6 });
    },
    chime: (c, out, at, o) => {
      // Inharmonic partials give a bell rather than a beep.
      [[1, 0.3, 1.6], [2.76, 0.12, 1], [5.4, 0.06, 0.6], [8.93, 0.03, 0.4]].forEach(([k, peak, d]) =>
        tone(c, out, at, { f0: 1046.5 * k * o.p, peak, d }));
    },
    notify: (c, out, at, o) => {
      tone(c, out, at, { type: "triangle", f0: 880 * o.p, peak: 0.3, d: 0.25 });
      tone(c, out, at + 0.11, { type: "triangle", f0: 1320 * o.p, peak: 0.3, d: 0.35 });
    },
    success: (c, out, at, o) => [523.25, 659.25, 783.99, 1046.5].forEach((f, i) =>
      tone(c, out, at + i * 0.07, { type: "triangle", f0: f * o.p, peak: 0.28, d: 0.35 })),
    error: (c, out, at, o) => [196, 165].forEach((f, i) =>
      tone(c, out, at + i * 0.13, { type: "square", f0: f * o.p, peak: 0.18, d: 0.12, lowpass: 1200 })),
    sparkle: (c, out, at, o) => {
      const r = rng(o.seed ?? 11);
      for (let i = 0; i < (o.count ?? 6); i++) tone(c, out, at + i * 0.045, { f0: (2200 + r() * 2600) * o.p, peak: 0.12, d: 0.25 });
    },
  };

  function play(ctx, out, cue, at) {
    const fn = typeof cue.sfx === "function" ? cue.sfx : presets[cue.sfx];
    if (!fn) { console.warn(`[sfx] unknown sound "${cue.sfx}"`); return; }
    const g = ctx.createGain(); g.gain.value = cue.gain ?? 1;
    const pan = ctx.createStereoPanner(); pan.pan.value = cue.pan ?? 0;
    g.connect(pan).connect(out);
    fn(ctx, g, at, { ...cue, p: cue.pitch ?? 1 });
  }
  // Master bus: volume -> limiter -> output, so stacked cues never clip.
  function bus(ctx, volume = 0.8) {
    const v = ctx.createGain(); v.gain.value = volume;
    const lim = ctx.createDynamicsCompressor();
    lim.threshold.value = -6; lim.knee.value = 0; lim.ratio.value = 20;
    lim.attack.value = 0.002; lim.release.value = 0.1;
    v.connect(lim).connect(ctx.destination);
    return v;
  }
  const cues = () => (window.SOUND && window.SOUND.cues) || [];
  // Seconds into the loop where a cue starts. A negative `delay` starts it early (a riser that lands on the beat).
  const startOf = (cue, seconds) => cue.t * seconds + (cue.delay ?? 0);

  // Render `loops` back-to-back loops offline (works headless) and return a 16-bit WAV as base64.
  async function render({ seconds, loops = 1, sampleRate = 48000 }) {
    const total = seconds * loops;
    const ctx = new OfflineAudioContext(2, Math.ceil(total * sampleRate), sampleRate);
    const out = bus(ctx, window.SOUND && window.SOUND.volume);
    // Loop k+1's early-starting cues fall inside loop k, so tails and pre-rolls carry across the seam.
    for (let k = 0; k <= loops; k++) {
      for (const cue of cues()) {
        const at = k * seconds + startOf(cue, seconds);
        if (at >= 0 && at < total) play(ctx, out, cue, at);
      }
    }
    out.gain.setValueAtTime(out.gain.value, Math.max(0, total - 0.03));
    out.gain.linearRampToValueAtTime(0, total);
    return wav(await ctx.startRendering());
  }
  function wav(buf) {
    const ch = buf.numberOfChannels, n = buf.length, size = 44 + n * ch * 2;
    const dv = new DataView(new ArrayBuffer(size));
    const str = (o, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); };
    str(0, "RIFF"); dv.setUint32(4, size - 8, true); str(8, "WAVE");
    str(12, "fmt "); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, ch, true);
    dv.setUint32(24, buf.sampleRate, true); dv.setUint32(28, buf.sampleRate * ch * 2, true);
    dv.setUint16(32, ch * 2, true); dv.setUint16(34, 16, true);
    str(36, "data"); dv.setUint32(40, n * ch * 2, true);
    const data = Array.from({ length: ch }, (_, c) => buf.getChannelData(c));
    for (let i = 0, o = 44; i < n; i++) {
      for (let c = 0; c < ch; c++, o += 2) {
        const s = Math.max(-1, Math.min(1, data[c][i]));
        dv.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      }
    }
    const u8 = new Uint8Array(dv.buffer);
    let bin = "";
    for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    return btoa(bin);
  }

  // Live preview. Browsers only allow sound after a key press or click, so it starts muted.
  function live(seconds) {
    let ctx, out, on = false;
    return {
      get on() { return on; },
      toggle() {
        if (!ctx) { ctx = new AudioContext(); out = bus(ctx, window.SOUND && window.SOUND.volume); }
        on = !on;
        on ? ctx.resume() : ctx.suspend();
        return on;
      },
      // Fire every cue whose start falls in (t0, t1], wrapping at the loop point.
      advance(t0, t1) {
        if (!on) return;
        for (const cue of cues()) {
          const f = (((startOf(cue, seconds) / seconds) % 1) + 1) % 1;
          if (t1 >= t0 ? f > t0 && f <= t1 : f > t0 || f <= t1) play(ctx, out, cue, ctx.currentTime + 0.01);
        }
      },
    };
  }

  return { presets, tone, hiss, rng, play, render, live };
})();
