#!/usr/bin/env node
// Photo analysis: photo.jpg -> landmarks.json + masks.png
//
// Runs MediaPipe Face Landmarker (478 3D landmarks + blendshapes + head pose) and the
// multiclass selfie segmenter (hair / face skin / body skin / clothes / background)
// inside headless Chromium, launched through the ai-gif skill's _browser.mjs.
//
//   node experiments/obama-3d/track-photo.mjs
import { createServer } from "node:http";
import { existsSync, writeFileSync, createReadStream, statSync } from "node:fs";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch } from "../../skills/ai-gif/scripts/_browser.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const C = join(HERE, ".cache");
const MIME = { ".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm", ".jpg": "image/jpeg" };
const routes = {
  "/vision.mjs": join(HERE, "node_modules/@mediapipe/tasks-vision/vision_bundle.mjs"),
  "/face.task": join(C, "face_landmarker.task"),
  "/seg.tflite": join(C, "segmenter.tflite"),
  "/photo.jpg": join(C, "photo.jpg"),
};
const PAGE = `<!doctype html><body><script type="module">
import { FilesetResolver, FaceLandmarker, ImageSegmenter } from "/vision.mjs";
const img = new Image(); img.src = "/photo.jpg"; await img.decode();
const fs = await FilesetResolver.forVisionTasks("/wasm");
const lm = await FaceLandmarker.createFromOptions(fs, {
  baseOptions: { modelAssetPath: "/face.task", delegate: "CPU" }, runningMode: "IMAGE", numFaces: 1,
  outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true });
const f = lm.detect(img);
const seg = await ImageSegmenter.createFromOptions(fs, {
  baseOptions: { modelAssetPath: "/seg.tflite", delegate: "CPU" }, runningMode: "IMAGE",
  outputConfidenceMasks: true, outputCategoryMask: false });
const s = seg.segment(img);
// Pack confidences into one RGBA PNG: R = person (1 - background), G = hair, B = face skin, A = 255.
const m = s.confidenceMasks, w = m[0].width, h = m[0].height;
const bg = m[0].getAsFloat32Array(), hair = m[1].getAsFloat32Array(), face = m[3].getAsFloat32Array();
const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
const ctx = cv.getContext("2d"), id = ctx.createImageData(w, h);
for (let i = 0; i < w * h; i++) {
  id.data[4*i] = 255 * (1 - bg[i]); id.data[4*i+1] = 255 * hair[i]; id.data[4*i+2] = 255 * face[i]; id.data[4*i+3] = 255;
}
ctx.putImageData(id, 0, 0);
window.RESULT = {
  width: img.naturalWidth, height: img.naturalHeight,
  landmarks: f.faceLandmarks[0].map(p => [p.x, p.y, p.z]),
  blendshapes: Object.fromEntries(f.faceBlendshapes[0].categories.map(c => [c.categoryName, +c.score.toFixed(3)])),
  matrix: Array.from(f.facialTransformationMatrixes[0].data),
  maskSize: [w, h], mask: cv.toDataURL("image/png"),
};
</script>`;

const server = createServer((req, res) => {
  const url = req.url.split("?")[0];
  if (url === "/") { res.writeHead(200, { "content-type": "text/html" }); return res.end(PAGE); }
  let p = routes[url];
  if (!p && url.startsWith("/wasm/")) p = join(HERE, "node_modules/@mediapipe/tasks-vision", url);
  if (!p || !existsSync(p)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "content-type": MIME[extname(p)] || "application/octet-stream", "content-length": statSync(p).size });
  createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, "127.0.0.1", r));
const browser = await launch();
const page = await browser.newPage();
page.on("console", m => m.type() === "error" && console.error("[page]", m.text()));
await page.goto(`http://127.0.0.1:${server.address().port}/`);
await page.waitForFunction(() => window.RESULT, null, { timeout: 120000 });
const r = await page.evaluate(() => window.RESULT);
await browser.close(); server.close();

writeFileSync(join(C, "masks.png"), Buffer.from(r.mask.split(",")[1], "base64"));
delete r.mask;
writeFileSync(join(C, "landmarks.json"), JSON.stringify(r));
console.log(`[track] ${r.landmarks.length} landmarks, mask ${r.maskSize.join("x")}, smile ${r.blendshapes.mouthSmileLeft}`);
