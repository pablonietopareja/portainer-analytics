/* DOM-level integration tests against an owned synthetic fixture. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const {createFixture}=require('./fixture.cjs');
let base,fixture,csrf='',saved=null;
async function serverFetch(url,options={}){return fixture.request(url,options);}
async function waitFor(fn,label){for(let i=0;i<100;i++){if(await fn())return;await new Promise(r=>setTimeout(r,40));}throw Error('Timed out: '+label);}
const errors=[];
function setup(html){const dom=new JSDOM(html,{url:base,runScripts:'outside-only',pretendToBeVisual:true});const w=dom.window;
 w.fetch=serverFetch;w.structuredClone=structuredClone;w.AbortSignal=AbortSignal;w.CSS={escape:s=>String(s).replaceAll('"','\\"')};w.matchMedia=()=>({matches:false,addEventListener(){}});
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({}, {get:(t,k)=>t[k]||(()=>{}),set:(t,k,v)=>(t[k]=v,true)});
 w.HTMLElement.prototype.getBoundingClientRect=()=>({width:540,height:210,left:0,right:540,top:0,bottom:210});
 w.addEventListener('error',e=>errors.push(e.error||e.message));return dom;}
function run(dom,name){vm.runInContext(fs.readFileSync(path.join(__dirname,'../web',name),'utf8'),dom.getInternalVMContext(),{filename:name});}
function click(w,selector){const e=w.document.querySelector(selector);assert.ok(e,'Missing '+selector);e.click();}
function drag(w,from,to){const values={};const transfer={types:[],setData(k,v){values[k]=v;this.types.push(k);},getData(k){return values[k]||'';}};for(const [type,node] of [['dragstart',from],['dragover',to],['drop',to],['dragend',from]]){const event=new w.Event(type,{bubbles:true,cancelable:true});Object.defineProperty(event,'dataTransfer',{value:transfer});node.dispatchEvent(event);}}
async function main(){
 fixture=await createFixture();base=fixture.base;
 const dom=setup(fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8')),w=dom.window;
 try{
  for(const f of ['theme.js','app.js','views.js','charts.js','settings.js','dashboards.js','controller.js'])run(dom,f);
  await waitFor(()=>w.eval('state.snapshot?.environments.length>0'),'initial snapshot');
  for(const view of ['overview','containers','stacks','images','storage','networks','events','system']){click(w,`[data-view="${view}"]`);assert.ok(w.document.querySelector('#content').textContent.length>100,view);}
  for(const mode of ['dark','light','system']){w.Theme.set(mode);assert.equal(w.document.documentElement.dataset.theme,mode==='system'?'light':mode);}
  click(w,'[data-view="settings"]');await waitFor(()=>w.document.querySelector('#portainer-url'),'settings form');
  assert.equal(w.document.querySelector('#portainer-token').value,'');
  const originalURL=w.document.querySelector('#portainer-url').value;
  w.document.querySelector('#portainer-url').value='https://unsaved.invalid';w.eval('render()');
  assert.equal(w.document.querySelector('#portainer-url').value,'https://unsaved.invalid','poll must preserve settings edits');
  w.document.querySelector('#portainer-url').value=originalURL;
  click(w,'[data-view="overview"]');click(w,'#pause');assert.equal(w.eval('state.paused'),true);
  click(w,'[data-view="dashboards"]');assert.equal(w.eval('state.paused'),false,'dashboard navigation resumes telemetry');await waitFor(()=>w.document.querySelector('[data-board-action="new"]'),'dashboard library');
  click(w,'[data-board-action="new"]');w.document.querySelector('#new-board-name').value='Temporary UI regression dashboard';
  w.document.querySelector('#new-board-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await waitFor(()=>w.document.querySelector('.source-card'),'resource palette');
  drag(w,w.document.querySelector('.source-card'),w.document.querySelector('.drop-zone'));assert.ok(w.document.querySelector('#widget-form'));
  w.document.querySelector('#widget-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  assert.equal(w.eval('Dashboards.draft.widgets.length'),1);
  click(w,'.source-card');w.document.querySelector('#widget-visual').value='stat';
  w.document.querySelector('#widget-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  assert.equal(w.eval('Dashboards.draft.widgets.length'),2);
  const first=w.eval('Dashboards.draft.widgets[0].id');drag(w,w.document.querySelector(`[data-drag-widget="${first}"]`),Array.from(w.document.querySelectorAll('[data-widget-id]')).at(-1));
  assert.equal(w.eval('Dashboards.draft.widgets[1].id'),first);
  click(w,'[data-board-action="undo"]');assert.equal(w.eval('Dashboards.draft.widgets[0].id'),first);
  click(w,'[data-board-action="save"]');await waitFor(()=>w.eval('Dashboards.draft.id && !Dashboards.editing')&&w.document.querySelector('[data-board-action="share"]'),'saved dashboard');saved=w.eval('structuredClone(Dashboards.draft)');csrf=w.eval('sessionState.csrf');
  click(w,'[data-board-action="share"]');await waitFor(()=>w.document.querySelector('#share-link'),'shared URL');
  const shareURL=w.document.querySelector('#share-link').value;const capability=new URL(shareURL).pathname.split('/').pop();
  const publicData=await(await serverFetch('/api/public/dashboards/'+capability)).json();assert.equal(publicData.widgets.length,2);assert.ok(!('environments' in publicData));
  click(w,'[data-close-modal]');click(w,'[data-board-action="edit"]');click(w,'[data-board-action="undo"]');
  assert.equal(w.eval('Dashboards.draft.id'),saved.id,'undo must not restore an unsaved dashboard identity');
  assert.equal(w.eval('Dashboards.draft.widgets.length'),2,'new editing sessions have separate history');
  w.eval('Dashboards.draft.widgets[0].sources.push("Temporary unavailable source")');
  click(w,`[data-edit-widget="${first}"]`);
  assert.ok(w.document.querySelector('[name="resource"][value="Temporary unavailable source"]').checked);
  w.document.querySelector('#widget-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  assert.ok(w.eval('Dashboards.draft.widgets[0].sources.includes("Temporary unavailable source")'),'panel edits preserve missing bindings');
  click(w,`[data-edit-widget="${first}"]`);w.document.querySelector('[name="resource"][value="Temporary unavailable source"]').checked=false;
  w.document.querySelector('#widget-title').value='Renamed panel';w.document.querySelector('#widget-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  click(w,'[data-board-action="save"]');await waitFor(()=>w.eval('Dashboards.draft.revision===2')&&w.document.querySelector('[data-board-action="share"]'),'updated dashboard');saved=w.eval('structuredClone(Dashboards.draft)');
  assert.equal((await(await serverFetch('/api/dashboards/'+saved.id)).json()).widgets[0].title,'Renamed panel');
  assert.equal(errors.length,0,errors.map(String).join('\n'));
  console.log('PASS: all original views, 3 themes, settings draft preservation, no token readback, no-code panels, reorder/undo, save/edit and scoped share (DOM emulation).');
 }finally{
  if(!saved){try{saved=w.eval('Dashboards.draft?.id ? structuredClone(Dashboards.draft) : null');csrf=w.eval('sessionState.csrf');}catch{}}
  if(saved)await serverFetch('/api/dashboards/'+saved.id,{method:'DELETE',headers:{'Content-Type':'application/json','X-Console-CSRF':csrf},body:JSON.stringify({revision:saved.revision})});
  dom.window.close();await fixture.dispose();
 }
}
main().catch(e=>{console.error(e);process.exitCode=1});
