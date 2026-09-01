const CACHE='bsd7-community-v1.2.1';
const SHELL=['./','./index.html','./app.js','./config.js','./update.js','./install.js','./install-ui.css','./manifest.json','./icons/app-192.svg','./icons/app-512.svg','./icons/apple-touch-icon.svg'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('message',e=>{if(e.data==='SKIP_WAITING')self.skipWaiting()});
self.addEventListener('fetch',e=>{const r=e.request;if(r.method!=='GET')return;const u=new URL(r.url);if(u.hostname.endsWith('supabase.co')||u.pathname.endsWith('/version.txt')||u.hostname==='cdn.jsdelivr.net')return;e.respondWith(fetch(new Request(r,{cache:'no-cache'})).then(res=>{if(res.ok&&u.origin===location.origin)caches.open(CACHE).then(c=>c.put(r,res.clone()));return res}).catch(()=>caches.match(r,{ignoreSearch:true}).then(x=>x||caches.match('./index.html'))))});
