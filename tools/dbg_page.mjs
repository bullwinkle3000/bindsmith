#!/usr/bin/env node
/** Ask the browser what it is actually running. */
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8770/';
const CHROME = '/home/andy/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome';
const PORT = 9335;
const PROFILE = mkdtempSync(join(tmpdir(), 'bs-dbg-'));
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

console.log('--- how many doCreate definitions in the DOM-visible source? ---');
console.log(await evaluate(`(() => {
  const t = document.documentElement.innerHTML;
  return (t.match(/function doCreate/g) || []).length;
})()`));

console.log('--- the running doCreate source ---');
console.log(await evaluate(`typeof doCreate === 'function' ? doCreate.toString() : 'MISSING'`));

console.log('--- served line 355 as the browser fetches it ---');
console.log(await evaluate(`fetch('/').then(r=>r.text()).then(t=>t.split('\\n')[354])`));

console.log('--- disabled-set sites the browser sees ---');
console.log(await evaluate(`fetch('/').then(r=>r.text()).then(
  t=>t.split('\\n').map((l,i)=>[i+1,l]).filter(([,l])=>/disabled/.test(l))
      .map(([n,l])=>n+': '+l.trim()).join(' || '))`));

ws.close(); chrome.kill('SIGKILL');
rmSync(PROFILE, { recursive: true, force: true });
