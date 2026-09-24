// Preview serves the exact complete static build deployed by GitHub Pages.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const output = path.join(root, '_site');
const python = process.env.SITE_PYTHON || 'python';
const types = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.ico':'image/x-icon','.svg':'image/svg+xml','.pdf':'application/pdf','.xml':'application/xml','.txt':'text/plain'};
function build() {
  const result = spawnSync(python,[path.join(__dirname,'build_site.py')],{cwd:root,encoding:'utf8',windowsHide:true});
  if (result.error || result.status !== 0) throw new Error(result.stderr || result.error?.message || 'Site build failed');
  return result.stdout.trim();
}
console.log(build());
const server = http.createServer((req,res)=>{
  let url;
  try {url = decodeURIComponent(new URL(req.url,'http://localhost').pathname);} catch {res.writeHead(400);res.end();return;}
  let file = path.resolve(output,'.'+url);
  if (file !== output && !file.startsWith(output+path.sep)) {res.writeHead(403);res.end();return;}
  const isPage = !path.extname(url) || url.endsWith('.html');
  try {
    if (isPage) build();
    if (!path.extname(url)) file = path.join(file,'index.html');
    const exists = fs.existsSync(file) && fs.statSync(file).isFile();
    if (!exists) file = path.join(output,'404.html');
    res.writeHead(exists?200:404,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});
    if (req.method === 'HEAD') {res.end();return;}
    fs.createReadStream(file).pipe(res);
  } catch(error) {
    res.writeHead(500,{'Content-Type':'text/plain'});res.end('Build failed. Check the preview terminal.');console.error(error.message);
  }
});
server.listen(4173,'127.0.0.1',()=>console.log('Complete site preview: http://127.0.0.1:4173'));
