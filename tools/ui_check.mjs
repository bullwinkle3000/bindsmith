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
const PROFILE = mkdtempSync(join(tmpdir(), 'bs-ui-'));
const fails = [];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function check(label, cond, detail = '') {
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${label}${detail ? '  — ' + detail : ''}`);
  if (!cond) fails.push(label);
}

let chrome = null;
function cleanup() {
  try { if (chrome) chrome.kill('SIGKILL'); } catch (_) { /* already gone */ }
  try { rmSync(PROFILE, { recursive: true, force: true }); } catch (_) { /* best effort */ }
}
// A crashed run must never leave a browser behind: a leftover instance holding
// a fixed debug port is invisible to the next run, which then silently drives
// a stale page. Hence port 0 (see below) plus these handlers.
process.on('exit', cleanup);
process.on('uncaughtException', (e) => { console.error(e); process.exit(1); });

chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  '--disable-dev-shm-usage', '--remote-debugging-port=0',
  `--user-data-dir=${PROFILE}`, '--window-size=1400,1000', URL_,
], { stdio: ['ignore', 'ignore', 'pipe'] });

// Ask Chrome to choose a free port, then read the port it actually chose from
// its own stderr and talk to that — never a port we guessed.
let chromeErr = '';
const devtoolsUrl = await new Promise((res, rej) => {
  const t = setTimeout(() => rej(new Error('no devtools endpoint:\n'
    + chromeErr.slice(-400))), 25000);
  chrome.stderr.on('data', (d) => {
    chromeErr += d.toString();
    const m = chromeErr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
    if (m) { clearTimeout(t); res(m[1]); }
  });
});
const DEV = new URL(devtoolsUrl).host;      // 127.0.0.1:<the port it picked>

async function targets() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://${DEV}/json/list`)).json();
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
  const det = r.result?.exceptionDetails;
  if (det) {
    const ex = det.exception || {};
    const frames = (det.stackTrace?.callFrames || [])
      .map((f) => `  at ${f.functionName || '(anon)'} :${f.lineNumber + 1}:${f.columnNumber + 1}`)
      .join('\n');
    throw new Error(`${ex.description || det.text}\n${frames}`);
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
  panels: [...document.querySelectorAll('#tab-status .panel h2')].map(h=>h.textContent.trim()),
}))()`);
console.log('status:', JSON.stringify(status));
check('page title', /bindsmith/i.test(status.title || ''), status.title);
check('version chip populated', /^v\d/.test(status.version || ''), status.version);
check('status chips rendered', status.chips.length >= 5, status.chips.join(' | '));
check('editor explains itself', status.panels.some(p => /how this works/i.test(p)),
  status.panels.join(' | '));

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

/* ── create / copy / delete a profile, and edit assignments ─────────── */
// Unique per run: a profile left behind by an interrupted run must not make
// this one fail with a duplicate-name error (which would look like a bug in
// the app rather than a dirty workspace).
const TESTPROF = 'zz_ui_' + Date.now().toString(36);
// Clear anything an earlier interrupted run left behind, so the workspace is
// self-healing and a dirty directory can never be mistaken for an app bug.
const APIBASE = URL_.replace(/\/$/, '');
try {
  const existing = await (await fetch(`${APIBASE}/api/presets`)).json();
  for (const p of existing.filter((p) => (p.name || '').startsWith('zz_ui_'))) {
    await fetch(`${APIBASE}/api/profiles/${encodeURIComponent(p.name)}`,
                { method: 'DELETE' });
    console.log('cleaned stale test profile:', p.name);
  }
} catch (_) { /* not fatal: the run just may collide */ }
await evaluate(`window.confirm = () => true;  // headless: auto-accept dialogs`);
await evaluate(`tab('presets'); loadPresets();`);
await sleep(1000);
await evaluate(`showCreateForm()`);
await sleep(600);
const form = await evaluate(`(() => ({
  hasName: !!document.getElementById('np-name'),
  hasGo: !!document.getElementById('np-go'),
  modes: [...document.querySelectorAll('input[name=npmode]')].map(r=>r.value),
  srcHidden: !!document.getElementById('np-src-wrap').hidden,
}))()`);
check('create form renders', form.hasName && form.hasGo, JSON.stringify(form));
check('create form offers three modes',
  ['blank','copy','ed'].every(m => form.modes.includes(m)), form.modes.join(','));
check('blank mode hides the source picker', form.srcHidden === true);

// switch modes -> the right pickers appear
await evaluate(`npMode('copy')`);
await sleep(400);
const copyMode = await evaluate(`({ srcHidden: !!document.getElementById('np-src-wrap').hidden,
  srcOptions: [...document.querySelectorAll('#np-src option')].map(o=>o.value) })`);
check('copy mode shows project sources', copyMode.srcHidden === false,
  copyMode.srcOptions.join(', '));
await evaluate(`npMode('ed')`);
await sleep(600);
const edMode = await evaluate(`({ src: [...document.querySelectorAll('#np-src option')].map(o=>o.value),
  dev: [...document.querySelectorAll('#np-dev option')].map(o=>o.value) })`);
check('ED mode lists game configs', edMode.src.length > 0, edMode.src.join(', '));
check('ED mode offers devices for role reading',
  edMode.dev.some(v => v === '231D0200'), `${edMode.dev.length} options`);

// actually create a blank profile through the UI
await evaluate(`(() => { npMode('blank');
  document.getElementById('np-name').value = '${TESTPROF}'; })()`);
await evaluate(`doCreate()`);
await sleep(2500);
const created = await evaluate(`(() => ({
  out: ((document.getElementById('np-out')||{}).innerText || '').replace(/\\n/g,' '),
  panelTitle: ((document.querySelector('#pre-main .panel h2')||{}).innerText || '')
    .replace(/\\n/g,' '),
  inList: [...document.querySelectorAll('#pre-list li')].some(li =>
    (li.dataset.name||'').startsWith('${TESTPROF}')),
  addBar: !!document.getElementById('add-action'),
  hint: (document.getElementById('add-hint')||{}).textContent,
  dlSize: document.querySelectorAll('#all-actions option').length,
}))()`);
// On success the form is replaced by the new profile's detail view, so the
// evidence is the list entry + the opened panel, not the form's own output.
check('creating a blank profile works',
  created.inList === true && created.panelTitle.includes(TESTPROF),
  `panel: ${created.panelTitle} | form output: ${created.out || '(form replaced)'}`);
check('new profile appears in the list', created.inList === true);
check('new profile opens with the add-action bar', created.addBar === true);
check('action picker populated', created.dlSize > 300,
  `${created.dlSize} unassigned — ${created.hint}`);

// add an assignment, then remove it
await evaluate(`(() => { document.getElementById('add-action').value = 'PitchAxisRaw';
  document.getElementById('add-role').value = 'pitch'; })()`);
await evaluate(`addAssignment()`);
await sleep(2200);
const added = await evaluate(`(() => ({
  rows: document.querySelectorAll('#pre-main tbody tr').length,
  hasPitch: [...document.querySelectorAll('#pre-main tbody tr td.a')]
    .some(td => td.textContent === 'PitchAxisRaw'),
}))()`);
check('assignment added through the UI', added.hasPitch === true,
  `${added.rows} rows`);

await evaluate(`removeAssignment('PitchAxisRaw')`);
await sleep(2200);
const removed = await evaluate(`(() => ({
  hasPitch: [...document.querySelectorAll('#pre-main tbody tr td.a')]
    .some(td => td.textContent === 'PitchAxisRaw'),
  rows: document.querySelectorAll('#pre-main tbody tr').length,
}))()`);
check('assignment removed through the UI', removed.hasPitch === false,
  `${removed.rows} rows left`);

// delete the throwaway profile
await evaluate(`deleteProfile()`);
await sleep(2200);
const deleted = await evaluate(`({ inList: [...document.querySelectorAll('#pre-list li')]
  .some(li => (li.dataset.name||'').startsWith('${TESTPROF}')) })`);
check('profile deleted through the UI', deleted.inList === false);

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
cleanup();
process.exit(fails.length ? 1 : 0);
