// Render the KT video: narration (tts.py) -> frames (composition.html via Playwright) -> ffmpeg mux.
//
//   npm run kt-video            full pipeline (regenerates only changed narration)
//   node render.mjs --preview   serve the composition for scrubbing in a browser
//   node render.mjs --skip-tts  reuse the existing audio and timing.json
//   node render.mjs --force     re-render every scene instead of reusing cached segments
//   node render.mjs --frames 12.5,40   write single PNG frames to out/ (for checking)
//
// Each scene is encoded as its own segment in out/segments/, named by a hash of everything that can change
// its frames (the scene's code, its timing, the shared page code and styles, the quoted source files and
// screenshots). Unchanged scenes are reused, so editing one scene re-renders only that scene.
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const OUT = join(HERE, "out");
const FPS = 30;
const MAX_BYTES = 20 * 1024 * 1024;
const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const option = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : null; };

const TYPES = { ".html": "text/html", ".json": "application/json", ".py": "text/plain", ".wav": "audio/wav", ".js": "text/javascript",
  ".png": "image/png" };
const SEGMENTS = join(OUT, "segments");
// Files the page reads besides itself; a change to any of them re-renders every scene.
const PAGE_INPUTS = ["onboarding/compiler.py", "onboarding/schema.py", "onboarding/validator.py", "onboarding/semantic.py",
  "onboarding/repairer.py", "docs/screenshots/1-practices.png", "docs/screenshots/2-packet-to-config.png",
  "docs/screenshots/3-exceptions.png", "docs/screenshots/4-smoke-test.png"];

// Serve the repo root so the page can read timing.json and the real source files it quotes.
function serve(port = 0) {
  const server = createServer((req, res) => {
    const path = normalize(join(REPO, decodeURIComponent(new URL(req.url, "http://x").pathname)));
    if (!path.startsWith(REPO + sep) || !existsSync(path) || statSync(path).isDirectory()) {
      res.writeHead(404); res.end(); return;
    }
    res.writeHead(200, { "Content-Type": TYPES[extname(path)] || "application/octet-stream" });
    res.end(readFileSync(path));
  });
  return new Promise((ok) => server.listen(port, "127.0.0.1", () => ok(server)));
}

function run(cmd, cmdArgs, opts = {}) {
  const r = spawnSync(cmd, cmdArgs, { stdio: "inherit", ...opts });
  if (r.status !== 0) throw new Error(`${cmd} ${cmdArgs.join(" ")} exited with ${r.status}`);
}

function python() {
  const win = join(HERE, ".venv", "Scripts", "python.exe");
  return existsSync(win) ? win : join(HERE, ".venv", "bin", "python");
}

function stamp(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

async function openPage(server) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => { throw e; });
  const { port } = server.address();
  await page.goto(`http://127.0.0.1:${port}/docs/kt-video/composition.html?render=1`);
  await page.waitForFunction(() => window.READY === true, null, { timeout: 30000 });
  const missing = await page.evaluate(() => window.MISSING);
  if (missing.length) throw new Error("beat phrases not found in timing.json:\n  " + missing.join("\n  "));
  return { browser, page, stage: await page.$("#stage") };
}

const sha = (...parts) => {
  const h = createHash("sha256");
  for (const part of parts) h.update(part);
  return h.digest("hex");
};

// Hash of everything shared by all scenes: the page minus its SCENES section, the files it reads, the encoder settings.
function sharedKey() {
  const html = readFileSync(join(HERE, "composition.html"), "utf8").replace(/\r/g, "");
  const start = html.indexOf("// ---------------------------------------------------------------- scenes");
  const end = html.indexOf("// ---------------------------------------------------------------- runtime");
  if (start < 0 || end < 0) throw new Error("composition.html is missing its scenes/runtime markers");
  return sha(html.slice(0, start), html.slice(end), ...PAGE_INPUTS.map((f) => readFileSync(join(REPO, f))),
    `fps=${FPS} crf=${process.env.CRF || "20"}`);
}

async function encodeScene(page, stage, scene, file) {
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "png", "-framerate", String(FPS), "-i", "-",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", process.env.CRF || "20", "-preset", "veryfast", "-r", String(FPS), file],
    { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((ok, fail) => ff.on("close", (c) => (c === 0 ? ok() : fail(new Error("ffmpeg video encode failed")))));
  const first = Math.round(scene.start * FPS);
  for (let j = 0; j < scene.frames; j++) {
    await page.evaluate((t) => window.renderAt(t), (first + j) / FPS);
    const png = await stage.screenshot({ type: "png" });
    if (!ff.stdin.write(png)) await new Promise((ok) => ff.stdin.once("drain", ok));
  }
  ff.stdin.end();
  await done;
}

async function renderVideo(server, timing) {
  const { browser, page, stage } = await openPage(server);
  const sources = await page.evaluate(() => window.SCENE_SOURCES);
  const shared = sharedKey();
  mkdirSync(SEGMENTS, { recursive: true });
  const list = [];
  for (const [k, scene] of timing.scenes.entries()) {
    const { start, ...rest } = scene;  // a scene's frames do not depend on where it starts
    const key = sha(shared, sources[k], JSON.stringify(rest), `index=${k} last=${k === timing.scenes.length - 1}`).slice(0, 12);
    const name = `scene_${String(k + 1).padStart(2, "0")}`;
    const file = join(SEGMENTS, `${name}-${key}.mp4`);
    if (existsSync(file) && !flag("--force")) {
      console.log(`${name}: unchanged, reusing segment`);
    } else {
      for (const old of readdirSync(SEGMENTS).filter((f) => f.startsWith(name + "-"))) rmSync(join(SEGMENTS, old));
      const started = Date.now();
      await encodeScene(page, stage, scene, file);
      console.log(`${name}: rendered ${scene.frames} frames in ${((Date.now() - started) / 1000).toFixed(0)} s`);
    }
    list.push(`file '${file.replace(/\\/g, "/")}'`);
  }
  await browser.close();
  const listFile = join(SEGMENTS, "list.txt");
  writeFileSync(listFile, list.join("\n") + "\n");
  const video = join(OUT, "video.mp4");
  run("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listFile, "-c", "copy", video]);
  return video;
}

function buildAudio(timing) {
  // Each scene's WAV padded with silence to exactly its scene duration, then concatenated.
  const inputs = timing.scenes.flatMap((s) => ["-i", join(HERE, "audio", s.audio)]);
  const pads = timing.scenes.map((s, i) => `[${i}:a]apad=whole_dur=${s.duration}[a${i}]`).join(";");
  const cat = timing.scenes.map((_, i) => `[a${i}]`).join("") + `concat=n=${timing.scenes.length}:v=0:a=1[out]`;
  const wav = join(OUT, "narration.wav");
  run("ffmpeg", ["-y", "-loglevel", "error", ...inputs, "-filter_complex", `${pads};${cat}`, "-map", "[out]", "-ar", "24000", wav]);
  return wav;
}

function srtToVtt(srt) {
  return "WEBVTT\n\n" + srt.replace(/\r/g, "").replace(/(\d\d:\d\d:\d\d),(\d\d\d)/g, "$1.$2");
}

function probe(file) {
  const r = spawnSync("ffprobe", ["-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", file], { encoding: "utf8" });
  return JSON.parse(r.stdout).streams;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  if (flag("--preview")) {
    const server = await serve(Number(option("--port") || 8765));
    console.log(`Preview: http://127.0.0.1:${server.address().port}/docs/kt-video/composition.html  (Ctrl+C to stop)`);
    return;
  }
  if (!flag("--skip-tts") && !option("--frames")) run(python(), [join(HERE, "tts.py")], { cwd: HERE });
  const timing = JSON.parse(readFileSync(join(HERE, "timing.json"), "utf8"));
  const server = await serve();

  if (option("--frames")) {
    const { browser, page, stage } = await openPage(server);
    for (const t of option("--frames").split(",").map(Number)) {
      await page.evaluate((x) => window.renderAt(x), t);
      await stage.screenshot({ path: join(OUT, `frame_${t.toFixed(2)}.png`) });
      console.log(`wrote out/frame_${t.toFixed(2)}.png`);
    }
    await browser.close(); server.close();
    return;
  }

  const audio = buildAudio(timing);
  const video = await renderVideo(server, timing);
  server.close();

  const final = join(OUT, "kt-video.mp4");
  const mux = (crf) => {
    let src = video;
    if (crf) {
      src = join(OUT, "video-recompressed.mp4");
      run("ffmpeg", ["-y", "-loglevel", "error", "-i", video, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", String(crf), "-preset", "veryfast", src]);
    }
    run("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
      "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", final]);
  };
  mux(null);
  for (let crf = 23; statSync(final).size > MAX_BYTES && crf <= 35; crf += 3) {
    console.log(`video is ${(statSync(final).size / 1e6).toFixed(1)} MB, re-encoding at CRF ${crf}`);
    mux(crf);
  }

  // side outputs
  const srt = readFileSync(join(HERE, "captions.srt"), "utf8");
  writeFileSync(join(OUT, "captions.srt"), srt);
  const chapters = timing.scenes.map((s) => `${stamp(s.start)} ${s.chapter.split(" / ")[1]}`).join("\n") + "\n";
  writeFileSync(join(OUT, "chapters.txt"), chapters);
  copyFileSync(final, join(HERE, "kt-video.mp4"));
  writeFileSync(join(HERE, "captions.vtt"), srtToVtt(srt));
  writeFileSync(join(HERE, "chapters.txt"), chapters);
  const posterAt = Math.max(0, timing.scenes[0].duration - 1.2);
  run("ffmpeg", ["-y", "-loglevel", "error", "-ss", String(posterAt), "-i", final, "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "3",
    join(HERE, "poster.jpg")]);

  const streams = probe(final);
  const v = Number(streams.find((s) => s.codec_type === "video").duration);
  const a = Number(streams.find((s) => s.codec_type === "audio").duration);
  console.log(`\n${final}\n  video ${v.toFixed(2)} s · audio ${a.toFixed(2)} s · diff ${Math.abs(v - a).toFixed(3)} s · ${(statSync(final).size / 1e6).toFixed(1)} MB`);
  console.log(chapters);
  if (Math.abs(v - a) > 0.2) throw new Error("audio and video durations differ by more than 0.2 s");
}

main().catch((e) => { console.error(e); process.exit(1); });
