#!/usr/bin/env node
/**
 * Headless UI check for the bindsmith editor.
 *
 *   node tools/ui_check.mjs [url] [chromePath]
 *
 * Launches Chromium with the DevTools protocol, loads the page, drives the
 * real interaction path (status -> devices -> role menu -> preset -> bindings
 * -> audit -> port preview) and reports console errors. Exits non-zero on
 * failure. Uses only Node built-ins (WebSocket is global in Node >= 22).
 */
import { spawn } from 'node:child_process';
import { rmSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8770/';
const CHROME = process.argv[3] ||
  '/home/andy/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome';
const PORT = 9333;
const PROFILE = mkdtempSync(join(tmpdir(), 'bs-ui-'));
const fails = [];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function check(label, cond, detail = '') {
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${label}${detail ? '  — ' + detail : ''}`);
  if (!cond) fails.push(label);
}

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  '--disable-dev-shm-usage', `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${PROFILE}`, '--window-size=1400,1000', URL_,
], { stdio: ['ignore', 'ignore', 'pipe'] });

let chromeErr = '';
chrome.stderr.on('data', (d) => { chromeErr += d.toString(); });

async function targets() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const page = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page;
    } catch (_) { /* not up yet */ }
    await sleep(250);
  }
  throw new Error('chrome devtools never came up:\n' + chromeErr.slice(-500));
}

const page = await targets();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let msgId = 0;
const pending = new Map();
const consoleErrors = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === 'Runtime.exceptionThrown') {
    consoleErrors.push(m.params?.exceptionDetails?.exception?.description
      || m.params?.exceptionDetails?.text || 'exception');
  }
  if (m.method === 'Runtime.consoleAPICalled' && m.params?.type === 'error') {
    consoleErrors.push((m.params.args || []).map((a) =>
      a.value ?? a.description ?? '').join(' '));
  }
};

function send(method, params = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((res) => pending.set(id, res));
}

async function evaluate(expr) {
  const r = await send('Runtime.evaluate', {
    expression: expr, awaitPromise: true, returnByValue: true,
  });
  if (r.result?.exceptionDetails) {
    throw new Error(r.result.exceptionDetails.exception?.description
      || 'evaluate failed');
  }
  return r.result?.result?.value;
}

await send('Runtime.enable');
await send('Page.enable');

async function boot() {
  for (let i = 0; i < 40; i++) {
    const ready = await evaluate(
      `document.readyState === 'complete' && !!document.getElementById('hdr-version')`);
    if (ready) return;
    await sleep(250);
  }
}

await boot();
await sleep(1500);   // let the initial fetches land

/* ── status tab ─────────────────────────────────────────────────────── */
const status = await evaluate(`(() => ({
  title: document.title,
  version: (document.getElementById('hdr-version')||{}).textContent,
  chips: [...document.querySelectorAll('#status-facts .chip')].map(c=>c.textContent.trim()),
  seedSrc: [...document.querySelectorAll('#seed-src option')].map(o=>o.textContent),
  seedDevices: document.getElementById('seed-dev')?.options.length ?? -1,
}))()`);
console.log('status:', JSON.stringify(status));
check('page title', /bindsmith/i.test(status.title || ''), status.title);
check('version chip populated', /^v\d/.test(status.version || ''), status.version);
check('status chips rendered', status.chips.length >= 5, status.chips.join(' | '));
check('seed form lists ED binds', (status.seedSrc || []).length > 0,
  (status.seedSrc || []).join(', '));
check('seed form lists devices', status.seedDevices > 0, `${status.seedDevices} options`);

/* ── devices tab ────────────────────────────────────────────────────── */
const devList = await evaluate(`(() => {
  tab('devices');
  return { items: document.querySelectorAll('#dev-list li').length,
           count: (document.getElementById('dev-count')||{}).textContent };
})()`);
await sleep(800);
check('device list rendered', devList.items > 10, `${devList.items} devices`);

await evaluate(`selectDevice('231D0200')`);
await sleep(2500);
const devView = await evaluate(`(() => {
  const sels = [...document.querySelectorAll('#dev-body select[data-ckey]')];
  const y = document.querySelector('#dev-body select[data-ckey="Joy_YAxis"]');
  const p = document.querySelector('#dev-body select[data-ckey="Joy_POV1Up"]');
  return {
    title: (document.getElementById('dev-title')||{}).textContent,
    rows: document.querySelectorAll('#dev-body tbody tr').length,
    selects: sels.length,
    populated: sels.filter(s=>s.options.length>1).length,
    yAxisRole: y ? y.value : null,
    yAxisOptions: y ? [...y.options].map(o=>o.value) : null,
    povOptions: p ? [...p.options].map(o=>o.value) : null,
    hasInvToggle: document.querySelectorAll('#dev-body input[data-inv]').length,
    hasDeadzone: document.querySelectorAll('#dev-body input[data-dz]').length,
  };
})()`);
console.log('device view:', JSON.stringify(devView));
check('control table rendered', devView.rows > 40, `${devView.rows} rows`);
check('role menus populated from API', devView.populated > 40,
  `${devView.populated}/${devView.selects} selects have options`);
check('axis role menu offers rotation + thrust',
  (devView.yAxisOptions || []).includes('pitch')
  && (devView.yAxisOptions || []).includes('thrust_fwd'),
  `current=${devView.yAxisRole}`);
check('pov role menu offered', (devView.povOptions || []).length > 1,
  (devView.povOptions || []).slice(0, 3).join(', '));
check('axis tuning widgets present',
  devView.hasInvToggle > 0 && devView.hasDeadzone > 0,
  `${devView.hasInvToggle} invert, ${devView.hasDeadzone} deadzone`);

/* ── presets tab ────────────────────────────────────────────────────── */
await evaluate(`tab('presets'); loadPresets();`);
await sleep(1200);
const preList = await evaluate(
  `[...document.querySelectorAll('#pre-list li')].map(li=>li.textContent.replace(/\\s+/g,' ').trim())`);
check('preset list rendered', preList.length > 0, preList.join(' | '));

await evaluate(`selectPreset('vkb_gladiator_seed.json')`);
await sleep(1500);
const preView = await evaluate(`(() => ({
  h2: (document.querySelector('#pre-main .panel h2')||{}).innerText,
  rows: document.querySelectorAll('#pre-main tbody tr').length,
  roleInputs: document.querySelectorAll('#pre-main input[data-role]').length,
  details: [...document.querySelectorAll('#pre-main details summary')].map(s=>s.textContent),
  bindDev: document.getElementById('bind-dev')?.options.length ?? -1,
}))()`);
console.log('preset view:', JSON.stringify(preView));
check('preset assignments table', preView.rows > 10, `${preView.rows} rows`);
check('assignment inputs rendered', preView.roleInputs > 10,
  `${preView.roleInputs} role inputs`);
check('panels present (bindings/audit/port)', preView.details.length >= 3,
  preView.details.join(' | '));
check('device picker populated', preView.bindDev > 0,
  `${preView.bindDev} devices`);

/* ── bindings resolve ───────────────────────────────────────────────── */
await evaluate(`(() => { const s=document.getElementById('bind-dev');
  s.value='231D0200'; return loadBindings(); })()`);
await sleep(2500);
const bindOut = await evaluate(
  `({ rows: document.querySelectorAll('#bind-out tbody tr').length,
     text: (document.getElementById('bind-out')||{}).innerText.slice(0,120) })`);
check('bindings resolved in UI', bindOut.rows > 100, `${bindOut.rows} rows`);

/* ── audit ──────────────────────────────────────────────────────────── */
await evaluate(`loadAudit()`);
await sleep(2500);
const auditOut = await evaluate(
  `({ hasPre: !!document.querySelector('#audit-out pre'),
     text: (document.getElementById('audit-out')||{}).innerText.slice(0,160) })`);
check('audit rendered', auditOut.hasPre, auditOut.text.replace(/\n/g, ' / '));

/* ── port preview ───────────────────────────────────────────────────── */
await evaluate(`(() => { const f=document.getElementById('port-from'),
  t=document.getElementById('port-to'); f.value='231D0200'; t.value='231D012C';
  return previewPort(); })()`);
await sleep(2500);
const portOut = await evaluate(`(() => ({
  chips: [...document.querySelectorAll('#port-out .chip')].map(c=>c.textContent.trim()),
  text: (document.getElementById('port-out')||{}).innerText.slice(0,160),
}))()`);
check('port preview rendered', portOut.chips.length >= 2, portOut.text.replace(/\n/g, ' / '));

/* ── console errors ─────────────────────────────────────────────────── */
check('no uncaught JS errors', consoleErrors.length === 0,
  consoleErrors.slice(0, 3).join(' ;; ') || 'clean');

console.log();
if (fails.length) {
  console.log(`FAILED (${fails.length}): ` + fails.join('; '));
} else {
  console.log('UI OK — all checks passed');
}

ws.close();
chrome.kill('SIGKILL');
rmSync(PROFILE, { recursive: true, force: true });
process.exit(fails.length ? 1 : 0);
