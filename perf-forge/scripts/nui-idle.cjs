const http = require("http");
const fs = require("fs");
const path = require("path");
const root = path.resolve(process.argv[2]);
const port = Number(process.argv[3] || 5198);
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".wav": "audio/wav", ".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf", ".json": "application/json" };
function findFile(dir, re, depth = 0) {
  if (depth > 8) return null;
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return null;
  }
  for (const e of entries) if (e.isFile() && re.test(e.name)) return path.join(dir, e.name);
  for (const e of entries) {
    if (!e.isDirectory() || skip.has(e.name)) continue;
    const hit = findFile(path.join(dir, e.name), re, depth + 1);
    if (hit) return hit;
  }
  return null;
}
const skip = new Set(["node_modules", "_backup", "_dev", "cache", ".git", "html-dev", "stream"]);

function pages(dir, list = []) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return list;
  }
  if (entries.some((e) => e.isFile() && e.name === "fxmanifest.lua")) {
    const manifest = fs.readFileSync(path.join(dir, "fxmanifest.lua"), "utf8");
    const m = /^\s*ui_page\s*\(?\s*['"]([^'"]+)['"]/m.exec(manifest);
    if (m && !/^https?:/.test(m[1])) list.push({ resource: path.basename(dir), base: "/" + path.relative(root, dir).split(path.sep).map(encodeURIComponent).join("/"), url: "/" + path.relative(root, path.join(dir, m[1])).split(path.sep).map(encodeURIComponent).join("/") });
    return list;
  }
  for (const e of entries) if (e.isDirectory() && !skip.has(e.name)) pages(path.join(dir, e.name), list);
  return list;
}

function probe(resource) {
  return `<script>(()=>{const P=window.__perf={raf:0,ticks:0,intervals:0,errors:[]};const R=window.requestAnimationFrame.bind(window);window.requestAnimationFrame=(cb)=>{P.raf++;return R(cb)};const SI=window.setInterval.bind(window);window.setInterval=function(fn,ms,...a){P.intervals++;return SI(function(){P.ticks++;if(typeof fn==="function")return fn.apply(this,arguments)},ms,...a)};window.GetParentResourceName=()=>${JSON.stringify(resource)};window.invokeNative=()=>{};const F=window.fetch.bind(window);window.fetch=(u,o)=>{const s=String(u&&u.url||u);if(/^https?:\\/\\//.test(s)&&!s.startsWith(location.origin))return Promise.resolve(new Response("{}",{headers:{"content-type":"application/json"}}));return F(u,o)};const XO=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u,...a){const s=String(u);if(/^https?:\\/\\//.test(s)&&!s.startsWith(location.origin)){u="data:application/json,{}";m="GET"}return XO.call(this,m,u,...a)};window.addEventListener("error",(e)=>P.errors.push(String(e.message).slice(0,120)))})();</script>`;
}

const harness = `<!doctype html><html><head><meta charset="utf-8"><title>NUI idle</title><style>body{margin:0;background:#3a4a3a;font:12px monospace;color:#fff}iframe{position:fixed;inset:0;width:1920px;height:1080px;border:0;background:transparent}</style></head><body><script>
window.measure=async(urls,settle=3000,win=2000)=>{const out=[];for(const p of urls){const f=document.createElement("iframe");f.setAttribute("sandbox","allow-scripts allow-same-origin");f.src=p.url;document.body.appendChild(f);await new Promise(r=>setTimeout(r,settle));const w=f.contentWindow;const P=w.__perf||{raf:0,ticks:0,intervals:0,errors:[]};const r0=P.raf,t0=P.ticks;await new Promise(r=>setTimeout(r,win));let anims=[];try{anims=w.document.getAnimations().filter(a=>a.playState==="running")}catch(e){}const vis=anims.filter(a=>{const t=a.effect&&a.effect.target;return t&&t.checkVisibility&&t.checkVisibility({opacityProperty:true,visibilityProperty:true})});const desc=(a)=>{const t=a.effect&&a.effect.target;const id=t?(t.id?"#"+t.id:"")+(typeof t.className==="string"&&t.className?"."+t.className.trim().split(/\\s+/).slice(0,2).join("."):"")||t.tagName:"?";return (a.animationName||a.transitionProperty||"anim")+"@"+id};out.push({resource:p.resource,rafPerSec:Math.round((P.raf-r0)*1000/win),ticksPerSec:Math.round((P.ticks-t0)*1000/win),intervals:P.intervals,running:anims.length,visible:vis.length,hiddenButRunning:anims.length-vis.length,sample:anims.slice(0,6).map(desc),errors:P.errors.slice(0,2)});f.remove();}return out};
</script></body></html>`;

http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split("?")[0]);
  if (url === "/__list") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify(pages(root)));
  }
  if (url === "/__jquery.js") {
    res.writeHead(200, { "Content-Type": "text/javascript" });
    const jq = findFile(root, /^jquery(.min)?.js$/i);
    return res.end(jq ? fs.readFileSync(jq) : "");
  }
  if (url === "/__control.html") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(`<!doctype html><html><head>${probe("control")}<style>@keyframes s{to{transform:rotate(1turn)}}.a{width:20px;height:20px;background:red;animation:s 1s linear infinite}.b{opacity:0}.c{display:none}</style></head><body><div class="a"></div><div class="b"><div class="a"></div></div><div class="c"><div class="a"></div></div><script>(function l(){requestAnimationFrame(l)})();setInterval(()=>{},100)</script></body></html>`);
  }
  if (url === "/" || url === "/__harness") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(harness);
  }
  let file = path.join(root, url);
  if (!file.startsWith(root)) {
    res.writeHead(403);
    return res.end();
  }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, "index.html");
  fs.readFile(file, (err, data) => {
    if (err) {
      res.writeHead(404);
      return res.end("404");
    }
    const ext = path.extname(file).toLowerCase();
    if (ext === ".html") {
      const rel = path.relative(root, file).split(path.sep);
      let resource = "";
      for (let i = rel.length - 1; i >= 0; i--) {
        const dir = path.join(root, ...rel.slice(0, i));
        if (fs.existsSync(path.join(dir, "fxmanifest.lua"))) {
          resource = path.basename(dir);
          break;
        }
      }
      const map = Object.fromEntries(pages(root).map((p) => [p.resource, p.base]));
      const html = data
        .toString("utf8")
        .replace(/nui:\/\/game\/ui\/jquery\.js/g, "/__jquery.js")
        .replace(/https:\/\/cfx-nui-([A-Za-z0-9_.-]+)\//g, (m, r) => (map[r] ? map[r] + "/" : m));
      const at = html.search(/<head[^>]*>/i);
      const tag = probe(resource);
      const out = at >= 0 ? html.replace(/<head[^>]*>/i, (m) => m + tag) : tag + html;
      res.writeHead(200, { "Content-Type": types[ext] });
      return res.end(out);
    }
    res.writeHead(200, { "Content-Type": types[ext] || "application/octet-stream" });
    res.end(data);
  });
}).listen(port, () => console.log("nui-idle harness " + root + " on " + port));
