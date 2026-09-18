#!/usr/bin/env node
/**
 * Screenshot the bindsmith editor in a couple of meaningful states.
 *
 *   node tools/shot.mjs [url] [outDir]
 *
 * Writes PNGs to outDir (default /tmp) and prints their paths.
 */
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8770/';
const OUT = process.argv[3] || '/tmp';
const CHROME = '/home/andy/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome';
const PORT = 9334;
const PROFILE = mkdtempSync(join(tmpdir(), 'bs-shot-'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  '--disable-dev-shm-usage', `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`, '--window-size=1500,1100',
  '--force-device-scale-factor=1', URL_,
], { stdio: ['ignore', 'ignore', 'ignore'] });

async function target() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const p = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (p) return p;
    } catch (_) { /* wait */ }
    await sleep(250);
  }
  throw new Error('devtools never came up');
}

const page = await target();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let id = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
function send(method, params = {}) {
  const n = ++id;
  ws.send(JSON.stringify({ id: n, method, params }));
  return new Promise((res) => pending.set(n, res));
}
async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true,
                                             returnByValue: true });
  return r.result?.result?.value;
}
async function shot(name) {
  const r = await send('Page.captureScreenshot',
                       { format: 'png', captureBeyondViewport: true });
  const path = join(OUT, name);
  writeFileSync(path, Buffer.from(r.result.data, 'base64'));
  console.log(path);
}

await send('Runtime.enable');
await send('Page.enable');
for (let i = 0; i < 40; i++) {
  if (await evaluate(`document.readyState === 'complete'
                      && !!document.getElementById('hdr-version')`)) break;
  await sleep(250);
}
await sleep(2000);
await shot('bindsmith-status.png');

// devices view, Gladiator selected -> the role menu is the interesting part
await evaluate(`tab('devices'); selectDevice('231D0200');`);
await sleep(3000);
await shot('bindsmith-devices.png');

// presets view with bindings resolved
await evaluate(`tab('presets'); loadPresets();`);
await sleep(1200);
await evaluate(`selectPreset('vkb_gladiator_seed.json')`);
await sleep(1500);
await evaluate(`(() => { document.getElementById('bind-dev').value='231D0200';
                         return loadBindings(); })()`);
await sleep(2500);
await shot('bindsmith-presets.png');

ws.close();
chrome.kill('SIGKILL');
rmSync(PROFILE, { recursive: true, force: true });
