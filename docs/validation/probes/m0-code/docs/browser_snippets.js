// Probe: the exact JavaScript run in the built-in browser pane (Chromium) via javascript_exec,
// on the page https://cdn.jsdelivr.net/npm/mermaid@11.4.1/package.json. Paste each block into a console.

// (1) Claim 4.4 browser half: JSON.parse rejects NaN / Infinity with SyntaxError. Controls must parse.
const out = {}; for (const [k, src] of [['NaN', 'NaN'], ['objNaN', '{"x": NaN}'], ['Infinity', 'Infinity']]) {
  try { JSON.parse(src); out[k] = 'NO THROW' } catch (e) { out[k] = `${e.constructor.name}: ${e.message}` } }
out.ua = navigator.userAgent; out
const ctl = {}; for (const src of ['null', '{"x": null}', '1e308']) {
  try { ctl[src] = 'parsed: ' + JSON.stringify(JSON.parse(src)) } catch (e) { ctl[src] = 'THREW ' + e.name } }; ctl

// (2) Milestone page section 2.6: fetch cache:'no-cache' = store, then revalidate with a conditional request.
// transferSize ~ headers only (a 304) for 'no-cache'; 0 for 'force-cache' (no request); full size for 'no-store'.
const u = 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/README.md'; const res = [];
for (const [label, mode] of [['prime', 'default'], ['nc1', 'no-cache'], ['nc2', 'no-cache'], ['fc', 'force-cache'], ['ns', 'no-store']]) {
  const r = await fetch(u, { cache: mode }); await r.text(); const e = performance.getEntriesByName(u).pop();
  res.push({ label, mode, status: r.status, transferSize: e && e.transferSize, encodedBodySize: e && e.encodedBodySize });
  performance.clearResourceTimings() }
res
