// No-JS render check via raw CDP: Emulation.setScriptExecutionDisabled(true), then full-page-ish screenshot.
// usage: node _nojs_shot.mjs <port> <file.html> <out.png> <viewportW> <viewportH>
import fs from 'node:fs';
const [port, file, out, W = '1920', H = '1080'] = process.argv.slice(2);
const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const ws = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send('Page.enable');
await send('Emulation.setScriptExecutionDisabled', { value: true });
await send('Emulation.setDeviceMetricsOverride', { width: +W, height: +H, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url: 'file://' + file });
await new Promise(r => setTimeout(r, 4000));
const ev = await send('Runtime.evaluate', { expression: "document.documentElement.className + '|' + getComputedStyle(document.querySelector('.slide')).visibility + '|' + getComputedStyle(document.querySelector('.reveal')).opacity + '|' + document.documentElement.scrollHeight" });
console.log('state', JSON.stringify(ev.result?.result?.value ?? ev));
const shot = await send('Page.captureScreenshot', { format: 'png' });
fs.writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
console.log('wrote', out);
ws.close(); process.exit(0);
