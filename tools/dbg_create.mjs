#!/usr/bin/env node
/** Reproduce the doCreate failure in-page and print the real stack. */
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8770/';
const CHROME = '/home/andy/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome';
const PORT = 9336;
const PROFILE = mkdtempSync(join(tmpdir(), 'bs-dbg2-'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`, URL_],
  { stdio: ['ignore', 'ignore', 'ignore'] });

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
await new Promise((res) => { ws.onopen = res; });
let id = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => { const n = ++id;
  ws.send(JSON.stringify({ id: n, method, params }));
  return new Promise((res) => pending.set(n, res)); };
const evaluate = async (expression) => (await send('Runtime.evaluate',
  { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;

await send('Runtime.enable');
await sleep(2500);

console.log('--- state before ---');
console.log(await evaluate(`({ presets: [...document.querySelectorAll('#pre-list li')]
  .map(li=>li.dataset.name) })`).then(JSON.stringify));

console.log('--- run doCreate end to end ---');
console.log(await evaluate(`(async () => {
  try {
    tab('presets'); await loadPresets();
    showCreateForm(); await new Promise(r=>setTimeout(r,300));
    npMode('blank');
    document.getElementById('np-name').value = 'zz_dbg_profile';
    await doCreate();
    await new Promise(r=>setTimeout(r,1500));
    return 'RESOLVED. panel now shows: '
      + (document.querySelector('#pre-main .panel h2')||{}).textContent;
  } catch (e) {
    return 'REJECTED: ' + e.message + '\\nSTACK:\\n' + e.stack;
  }
})()`));

console.log('--- did the profile get created? ---');
console.log(await evaluate(`fetch('/api/presets').then(r=>r.json())
  .then(d=>d.map(p=>p.name).join(', '))`));

ws.close(); chrome.kill('SIGKILL');
rmSync(PROFILE, { recursive: true, force: true });
