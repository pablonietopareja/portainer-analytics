/* Isolated Chromium integration with synthetic Portainer data only. */
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {createFixture,browserOptions}=require('./fixture.cjs');
const output=fs.mkdtempSync(path.join(os.tmpdir(),'portainer-console-browser-'));
async function main(){
 const fixture=await createFixture(),base=fixture.base;
 let browser;
 try{browser=await chromium.launch(browserOptions());}catch(error){await fixture.dispose();throw error;}
 const context=await browser.newContext({viewport:{width:1600,height:1000},colorScheme:'light'}),page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));let savedId;
 const shot=async(name)=>{await page.screenshot({path:path.join(output,name+'.png'),fullPage:true,animations:"disabled"});};
 async function noOverflow(){assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'page must fit viewport');}
 async function save(){const response=page.waitForResponse(r=>new URL(r.url()).pathname===(savedId?'/api/dashboards/'+savedId:'/api/dashboards')&&['POST','PUT'].includes(r.request().method()));await page.locator('[data-board-action="save"]').click();const r=await response;assert.ok(r.ok());savedId=(await r.json()).id;await page.locator('[data-board-action="edit"]').waitFor();}
 try{
  const login=await context.request.post(base+'/api/login',{data:{password:fixture.password}});assert.equal(login.status(),200);
  await page.goto(base);await page.locator('.metric').first().waitFor();
  await page.locator('.theme-switch').selectOption('light');await shot('overview-light');await noOverflow();
  await page.locator('.theme-switch').selectOption('dark');await shot('overview-dark');
  for(const view of ['containers','stacks','images','storage','networks','events','system']){await page.locator(`.nav-item[data-view="${view}"]`).click();assert.ok((await page.locator('#content').innerText()).length>100);await noOverflow();}
  await page.locator('.theme-switch').selectOption('system');await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
  await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
  await page.locator('[data-view="settings"]').click();await page.locator('#portainer-url').waitFor();
  assert.equal(await page.locator('#portainer-token').inputValue(),'');
  const serverURL=await page.locator('#portainer-url').inputValue();await page.locator('#portainer-url').fill('https://unsaved.invalid');
  await page.waitForResponse(r=>r.url().endsWith('/api/snapshot'));assert.equal(await page.locator('#portainer-url').inputValue(),'https://unsaved.invalid');
  await page.locator('#portainer-url').fill(serverURL);await page.locator('#test-connection').click();
  await page.locator('#connection-result.success').waitFor({timeout:45000});await shot('settings-light');
  await page.locator('.theme-switch').selectOption('dark');await shot('settings-dark');
  await page.locator('[data-view="overview"]').first().click();await page.locator('#pause').click();
  await page.evaluate(()=>{location.hash='view=dashboards';});await page.locator('[data-board-action="new"]').first().click();
  await page.locator('#new-board-name').fill('Temporary browser validation');await page.locator('#new-board-form button[type="button"]').first().isVisible();
  await page.getByRole('button',{name:'Start building',exact:true}).click();
  await page.locator('.source-card').first().dragTo(page.locator('.drop-zone'));await page.locator('#widget-form').waitFor();
  await page.locator('#widget-metric').selectOption('memory_bytes');await page.locator('#widget-title').fill('Memory working set');
  await page.getByRole('button',{name:'Add panel',exact:true}).click();
  for(const [kind,visual,metric,title] of [['stack','stat','cpu_percent','Stack CPU'],['network','bar','rx_rate','Network receive'],['environment','gauge','memory_host_percent','Host memory share'],['environment','table','running','Running containers']]){
   await page.locator('#palette-kind').selectOption(kind);await page.locator('.source-card').first().click();
   await page.locator('#widget-metric').selectOption(metric);await page.locator('#widget-visual').selectOption(visual);await page.locator('#widget-title').fill(title);
   await page.getByRole('button',{name:'Add panel',exact:true}).click();
  }
  for(const kind of ['image','volume','disk']){await page.locator('#palette-kind').selectOption(kind);assert.ok(await page.locator('.source-card').count(),kind+' must be supplied by synthetic API');await page.locator('.source-card').first().click();await page.getByRole('button',{name:'Add panel',exact:true}).click();assert.equal(await page.locator('.dashboard-widget').count(),6);await page.locator('[data-remove-widget]').last().click();}
  await page.locator('#palette-kind').selectOption('container');await page.locator('.source-card').first().click();await page.locator('#widget-metric-search').fill('raw');assert.ok(await page.locator('#widget-metric option').count()>1);await page.locator('#widget-metric').selectOption({label:'Docker raw / cpu_stats.cpu_usage.total_usage'});await page.getByRole('button',{name:'Add panel',exact:true}).click();await page.locator('[data-remove-widget]').last().click();
  await page.locator('[data-drag-widget]').first().dragTo(page.locator('[data-widget-id]').nth(1));await page.locator('[data-board-action="undo"]').click();
  await page.locator('#board-range').selectOption('1440');await page.locator('#board-theme').selectOption('dark');
  await shot('editor-dark');await noOverflow();await save();
  await page.locator('#board-status').filter({hasText:'Live'}).waitFor();await shot('dashboard-dark');
  await page.locator('.theme-switch').selectOption('light');await shot('dashboard-light');
  await page.locator('[data-board-action="edit"]').click();await page.locator('[data-board-action="undo"]').click();
  assert.equal(await page.locator('.dashboard-widget').count(),5,'saved state is outside next edit undo history');
  await page.locator('[data-edit-widget]').first().click();await page.locator('#widget-title').fill('RAM monitor');
  await page.getByRole('button',{name:'Apply changes',exact:true}).click();await save();
  await page.reload();await page.locator(`[data-open-board="${savedId}"]`).click();await page.getByRole('heading',{name:'RAM monitor',exact:true}).waitFor();
  await page.locator('[data-board-action="share"]').click();await page.locator('#share-link').waitFor();
  const shareURL=await page.locator('#share-link').inputValue();
  const viewerContext=await browser.newContext({viewport:{width:1920,height:1600},colorScheme:'dark'}),viewer=await viewerContext.newPage();viewer.on('pageerror',e=>errors.push(e.message));
  await viewer.goto(shareURL);await viewer.locator('.dashboard-widget').first().waitFor();
  assert.equal(await viewer.locator('.dashboard-widget').count(),5);assert.equal(await viewer.locator('html').getAttribute('data-theme'),'dark');
  assert.equal(await viewer.locator('[data-view="settings"]').count(),0);
  for(const mode of ['dark','light','system']){await viewer.locator('[data-theme-control]').selectOption(mode);const colors=await viewer.evaluate(()=>({root:getComputedStyle(document.documentElement).backgroundColor,body:getComputedStyle(document.body).backgroundColor,height:document.body.getBoundingClientRect().height,viewport:innerHeight}));assert.equal(colors.root,colors.body,'root background must match dashboard');assert.ok(colors.height>=colors.viewport,'short dashboards fill the viewport');}
  await viewer.screenshot({path:path.join(output,'shared-dark.png'),fullPage:true,animations:"disabled"});
  await viewer.setViewportSize({width:390,height:844});await viewer.locator('[data-theme-control]').selectOption('light');
  assert.ok(await viewer.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await viewer.screenshot({path:path.join(output,'shared-mobile-light.png'),fullPage:true,animations:"disabled"});
  await page.locator('#disable-share').click();await viewer.reload();await viewer.locator('#display-status.offline').waitFor({state:'attached'});assert.equal(await viewer.locator('.dashboard-widget').count(),0);await viewerContext.close();
  await page.setViewportSize({width:390,height:844});await noOverflow();await shot('dashboard-mobile-light');
  await page.locator('#mobile-menu').click();await page.locator('[data-view="settings"]').click();await page.locator('#portainer-url').waitFor();await noOverflow();await shot('settings-mobile-light');
  assert.deepEqual(errors,[]);console.log('PASS: real Chromium rendering with synthetic API, all views, light/dark/system, live settings, native drag/drop, five chart types, save/edit/reload, scoped sharing/revocation, desktop/mobile fit.');
  console.log('Screenshots: '+output);
 }catch(error){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true,animations:"disabled"}).catch(()=>{});console.error('Screenshots: '+output);throw error;}
 finally{
  try{if(savedId){const s=await(await context.request.get(base+'/api/session')).json();const d=await(await context.request.get(base+'/api/dashboards/'+savedId)).json();const r=await context.request.delete(base+'/api/dashboards/'+savedId,{headers:{'X-Console-CSRF':s.csrf},data:{revision:d.revision}});assert.ok(r.ok(),'temporary dashboard removed');}}
  finally{await browser.close();await fixture.dispose();}
 }
}
main().catch(e=>{console.error(e);process.exitCode=1});
