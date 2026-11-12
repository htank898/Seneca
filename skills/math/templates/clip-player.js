// Seneca clip player: draw a Manim clip (transparent PNG sequence from render-math.mjs --clip)
// inside any renderFrame(t) page: gif-create, video-create, interactive guides.
//
//   <canvas id="eq"></canvas>
//   <script src="proof.clip/clip.js"></script>          <!-- manifest: window.CLIPS["proof"] -->
//   <script src="proof.clip/clip-player.js"></script>   <!-- this file -->
//   <script>
//     const proof = SenecaClip.mount("proof", document.getElementById("eq"), { base: "proof.clip/" });
//     window.renderFrame = (t) => {
//       proof.draw(t * MOTION.seconds);        // gif-create: t is 0..1, so convert to seconds
//       // video-create: proof.draw(t - s.from)    // t is already seconds; offset to the scene start
//     };
//   </script>
//
// Deterministic: draw(seconds) always shows frame floor(seconds * fps), clamped to the clip
// (or wrapped with { loop: true }). Every frame is preloaded as an <img> in the document,
// which holds the page's load event, so headless renderers never capture a missing frame.
// Keep clips short and at the host's fps (e.g. --fps 30 --quality m) to bound memory.
(function () {
  function mount(name, canvas, opts) {
    opts = opts || {};
    const meta = (window.CLIPS || {})[name];
    if (!meta) throw new Error(`SenecaClip: no manifest for "${name}". Load ${name}.clip/clip.js first.`);
    const base = opts.base != null ? opts.base : `${name}.clip/`;
    canvas.width = meta.width;
    canvas.height = meta.height;
    const ctx = canvas.getContext("2d");

    const shelf = document.createElement("div");
    shelf.style.cssText = "position:absolute;width:0;height:0;overflow:hidden;visibility:hidden";
    const frames = [];
    for (let i = 0; i < meta.frames; i++) {
      const img = document.createElement("img");
      img.decoding = "sync";
      img.src = base + meta.pattern.replace("%05d", String(i).padStart(5, "0"));
      shelf.appendChild(img);
      frames.push(img);
    }
    (document.body || document.documentElement).appendChild(shelf);

    let last = -1;
    return {
      meta,
      canvas,
      ready: Promise.all(frames.map((f) => (f.complete ? 0 : new Promise((r) => { f.onload = f.onerror = r; })))),
      frameAt(seconds) {
        const n = meta.frames;
        let i = Math.floor(seconds * meta.fps + 1e-6);
        i = opts.loop ? ((i % n) + n) % n : Math.max(0, Math.min(n - 1, i));
        return i;
      },
      draw(seconds) {
        const i = this.frameAt(seconds);
        if (i === last) return i;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(frames[i], 0, 0);
        last = i;
        return i;
      },
    };
  }
  window.SenecaClip = { mount };
})();
