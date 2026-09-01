import { APP_VERSION } from './config.js';

const CHECK_MS=10*60*1000;
let checking=false;
let availableVersion='';
let scrollGuardReady=false;

function newer(a,b){
  const x=String(a).trim().split('.').map(Number),y=String(b).trim().split('.').map(Number);
  for(let i=0;i<Math.max(x.length,y.length);i++){
    if((x[i]||0)>(y[i]||0))return true;
    if((x[i]||0)<(y[i]||0))return false;
  }
  return false;
}

async function latest(){
  const r=await fetch(`./version.txt?cb=${Date.now()}`,{cache:'no-store'});
  if(!r.ok)throw new Error('version check failed');
  return (await r.text()).trim();
}

function syncScrollState(){
  const root=document.documentElement;
  const viewport=Math.ceil(window.visualViewport?.height||window.innerHeight||0);
  const content=Math.ceil(root.scrollHeight);
  root.classList.toggle('page-fit',content<=viewport+2);
}

function setupScrollGuard(){
  if(scrollGuardReady)return;
  scrollGuardReady=true;
  const sync=()=>requestAnimationFrame(syncScrollState);
  sync();
  window.addEventListener('resize',sync,{passive:true});
  window.addEventListener('orientationchange',sync,{passive:true});
  window.visualViewport?.addEventListener('resize',sync,{passive:true});
  if('ResizeObserver'in window)new ResizeObserver(sync).observe(document.body);
  else new MutationObserver(sync).observe(document.body,{subtree:true,childList:true,attributes:true});
}

function showUpdate(v){
  availableVersion=v;
  const title=document.querySelector('#update-title');
  const detail=document.querySelector('#update-detail');
  if(title)title.textContent='Update available';
  if(detail)detail.textContent=`v${APP_VERSION} → v${v}`;
  document.querySelector('#update')?.classList.remove('hidden');
  document.documentElement.classList.add('update-visible');
  document.querySelector('#install-card')?.classList.add('hidden');
  syncScrollState();
}

async function check(){
  if(checking)return;
  checking=true;
  try{
    const v=await latest();
    if(newer(v,APP_VERSION))showUpdate(v);
  }finally{checking=false}
}

async function update(){
  const button=document.querySelector('#update-go');
  if(button){button.disabled=true;button.textContent='Updating…'}
  try{
    if('serviceWorker'in navigator){
      const regs=await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map(r=>r.update().catch(()=>{})));
      for(const r of regs)if(r.waiting)r.waiting.postMessage('SKIP_WAITING');
      await new Promise(resolve=>setTimeout(resolve,250));
    }
  }finally{
    const base=location.pathname;
    location.replace(`${base}?update=${encodeURIComponent(availableVersion||Date.now())}&cb=${Date.now()}${location.hash}`);
  }
}

export function setupUpdates(){
  setupScrollGuard();
  document.querySelector('#update-go')?.addEventListener('click',update);
  check().catch(()=>{});
  window.addEventListener('focus',()=>check().catch(()=>{}));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)check().catch(()=>{})});
  window.addEventListener('online',()=>check().catch(()=>{}));
  setInterval(()=>{if(!document.hidden)check().catch(()=>{})},CHECK_MS);
}
