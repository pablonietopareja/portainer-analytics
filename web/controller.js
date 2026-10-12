"use strict";

function route(){const params=new URLSearchParams(location.hash.slice(1));const view=params.get("view");if(Object.hasOwn(labels,view))state.view=view;const id=Number(params.get("env"));if(id>0)state.envId=id;}
function saveRoute(){history.replaceState(null,"",`#env=${state.envId??""}&view=${state.view}`);}
function navigate(view){if(!Object.hasOwn(labels,view))return;state.view=view;state.query="";state.filter="all";state.sort="name";$(".sidebar").classList.remove("open");saveRoute();render();if(view==="events")loadEvents();}
function changeEnvironment(id){state.envId=Number(id);state.query="";state.filter="all";state.events=null;state.eventsEnv=null;state.eventsAt=0;state.eventsError=null;state.detail=null;state.detailRequest++;$("#detail").close();saveRoute();render();if(state.view==="events")loadEvents();}
async function getJSON(path){const r=await fetch(path,{signal:AbortSignal.timeout(15000)});const data=await r.json();if(r.status===401){sessionState.admin=false;showLogin();}if(!r.ok)throw Error(data.error||"The request is unavailable.");return data;}
async function loadEvents(){
    if(state.eventsLoading||!state.envId||state.paused)return;
    state.eventsLoading=true;const eid=state.envId;if(state.view==="events")render();
    try{const data=await getJSON(`/api/environments/${eid}/events`);if(eid!==state.envId||state.paused)return;state.events=data.events;state.eventsEnv=eid;state.eventsAt=Date.now();state.eventsError=null;}
    catch(error){if(eid===state.envId){state.eventsError=error.message;state.eventsAt=Date.now();}}
    finally{state.eventsLoading=false;if(state.view==="events")render();}
}
function openDetail(kind,id){
    state.detail={kind,id,tab:"summary",data:null,error:null,loading:false,loadedAt:0};state.detailRequest++;
    renderDetail();if(!$("#detail").open)$("#detail").showModal();
}
function detailContainerSummary(c){
    const m=c.stats||{};
    return `<div class="detail-badge">${stateChip(c)} <span class="caption-inline">${esc(c.status)}</span></div>`+
    `<div class="detail-metrics">${metric("CPU",pct(m.cpu_percent),"100% = 1 CPU","CPU")}${metric("RAM",bytes(m.memory_bytes),"working set","MEM")}${metric("WRITABLE",bytes(c.writable_bytes),"writable layer","RW")}</div>`+
    (c.stats_error?`<div class="notice">${esc(c.stats_error)}</div>`:"")+panel("Identity","",definition([["ID",c.id],["Image",c.image],["Stack / project",c.stack||"Standalone"],["Service",c.service||"—"],["Created",dateText(c.created)],["Sample",timeText(m.sample_at)]]))+
    panel("Ports","Published and exposed ports",table(["HOST","PUBLISHED","CONTAINER","PROTOCOL"],c.ports.map(p=>`<tr><td class="mono">${esc(p.IP||"—")}</td><td class="mono">${p.PublicPort??"—"}</td><td class="mono">${p.PrivatePort??"—"}</td><td>${esc(p.Type)}</td></tr>`),"This container has no exposed ports in the inventory."));
}
function detailContainerResources(c){const m=c.stats||{};return `<div class="detail-metrics">${metric("CPU",pct(m.cpu_percent),"100% = 1 logical CPU","CPU")}${metric("RAM",bytes(m.memory_bytes),"working set","MEM")}${metric("MEMORY CACHE",bytes(m.cache_bytes),"inactive files","CCH")}${metric("RX",rate(m.rx_rate),"received","RX")}${metric("TX",rate(m.tx_rate),"transmitted","TX")}${metric("PROCESSES",number(m.pids,0),"current PIDs","PID")}</div>`+panel("Memory and disk","",definition([["Raw memory",bytes(m.memory_raw_bytes)],["Effective memory limit",bytes(m.memory_limit)],["Limit usage",m.memory_bytes!=null&&m.memory_limit?pct(m.memory_bytes/m.memory_limit*100):"—"],["Inactive memory cache",bytes(m.cache_bytes)],["Writable layer",bytes(c.writable_bytes)],["Virtual root filesystem",bytes(c.rootfs_bytes)],["Cumulative disk reads",bytes(m.block_read_bytes)],["Cumulative disk writes",bytes(m.block_write_bytes)],["Cumulative network received",bytes(m.rx_bytes)],["Cumulative network transmitted",bytes(m.tx_bytes)]]))+`<div class="info-box">I/O counters show cumulative bytes transferred, not disk space used. The effective memory limit may equal host capacity when no explicit limit is set. — means the engine does not report the counter or the first sample is still pending.</div>`+telemetryDetails(c);}
function detailContainerNetwork(c){return panel("Mounts","Volumes and bind mounts",`<ul class="drawer-list" style="padding:0 20px 20px">${c.mounts.map(m=>`<li><strong>${esc(m.Destination)}</strong>${esc(m.Type)} · ${m.RW?"Read / write":"Read only"}<br><span class="mono">${esc(m.Name||m.Source)}</span>${m.Name?`<br><button class="text-button" data-volume="${esc(m.Name)}">Open volume →</button>`:""}</li>`).join("")||'<li>No mounts</li>'}</ul>`)+panel("Connected networks","",table(["NETWORK","IP ADDRESS","GATEWAY"],c.networks.map(n=>`<tr><td>${esc(n.name)}</td><td class="mono">${esc(n.ip||"—")}</td><td class="mono">${esc(n.gateway||"—")}</td></tr>`)));}
function renderDetail(){
    const d=state.detail,e=environment();if(!d||!e)return;
    const collections={container:"containers",stack:"stacks",image:"images",volume:"volumes",network:"networks"};
    const key=["stack","volume"].includes(d.kind)?"name":"id";
    if(!(e[collections[d.kind]]||[]).some(x=>x[key]===d.id)){
        $("#detail-tabs").innerHTML="";$("#detail-body").innerHTML='<div class="notice" style="margin-top:24px">This resource is no longer in the current inventory.</div>';return;
    }
    const scroll=$("#detail").scrollTop,preScroll=$("#detail-body .pre")?.scrollTop||0;
    let title="",eyebrow="DETAIL",body="",tabs="";
    if(d.kind==="container"){
        const c=e.containers.find(c=>c.id===d.id);if(!c){$("#detail-body").innerHTML='<div class="notice">This container is no longer in the current inventory.</div>';return;}
        title=c.name;eyebrow="CONTAINER / "+e.name;
        tabs=`<div class="drawer-tabs">${[["summary","Summary"],["resources","Resources"],["network","Mounts / network"],["logs","Logs"],["inspect","Inspect"]].map(([v,l])=>`<button data-detail-tab="${v}" class="${d.tab===v?"active":""}">${l}</button>`).join("")}</div>`;
        if(d.tab==="summary")body=detailContainerSummary(c);
        if(d.tab==="resources")body=detailContainerResources(c);
        if(d.tab==="network")body=detailContainerNetwork(c);
        if(d.tab==="logs"||d.tab==="inspect")body=`<div class="panel-heading" style="padding:0 0 14px"><span class="subtle">${d.tab==="logs"?"Last 200 lines · refreshed every 5s":"Operational configuration · environment values hidden"}</span><button id="refresh-detail" class="button" ${d.loading?"disabled":""}>↻ Refresh</button></div>${d.error?`<div class="notice error">${esc(d.error)}</div>`:""}${d.loading&&!d.data?'<div class="empty-state"><span class="loader"></span><p>Querying Portainer…</p></div>':`<pre class="pre">${esc(d.data?(d.tab==="logs"?(d.data.logs||"No log lines."):JSON.stringify(d.data,null,2)):"Waiting for data…")}</pre>`}<p class="note">Updated ${timeText(d.loadedAt||null)}${d.tab==="logs"?" · Application output may contain sensitive information; review it before sharing.":""}</p>`;
    }else if(d.kind==="stack"){
        const s=e.stacks.find(s=>s.name===d.id);if(!s)return;title=s.name;eyebrow="STACK / "+s.source;
        const members=e.containers.filter(c=>s.containers.includes(c.id));
        body=`<div class="detail-metrics">${metric("RUNNING",`${s.running}<small>/ ${s.total}</small>`,"containers","CTR")}${metric("CPU",pct(s.cpu_percent),"Combined CPU","CPU")}${metric("RAM",bytes(s.memory_bytes),"working set","MEM")}</div>`+panel("Stack containers","",table(["CONTAINER","STATUS","RAM"],members.map(c=>`<tr><td><button class="name-link" data-container="${c.id}">${esc(c.name)}</button><small class="cell-sub">${esc(c.service||c.image)}</small></td><td>${stateChip(c)}</td><td class="resource-value">${bytes(c.stats?.memory_bytes)}</td></tr>`)))+panel("Deployment","",definition([["Source",s.source],["Type",s.type===1?"Docker Swarm":"Docker Compose"],["Portainer ID",s.id??"Project detected from labels"],["Portainer status",s.status===1?"Active":s.status===2?"Inactive":"Unavailable"],["Writable layers",bytes(s.writable_bytes)],["Created",dateText(s.created)]]));
    }else if(d.kind==="image"){
        const i=e.images.find(i=>i.id===d.id);if(!i)return;title=i.tags[0]||"Untagged image";eyebrow="IMAGE / DOCKER";
        body='<div style="height:24px"></div>'+panel("Image","",definition([["ID",i.id],["Tags",i.tags.join("\n")||"No tags"],["Virtual size",bytes(i.size)],["Shared layers",bytes(i.shared_size)],["References",i.containers],["Created",dateText(i.created)]]))+panel("Containers using this image","",table(["CONTAINER","STATUS"],e.containers.filter(c=>c.image_id===i.id).map(c=>`<tr><td><button class="name-link" data-container="${c.id}">${esc(c.name)}</button></td><td>${stateChip(c)}</td></tr>`)))+panel("Labels","",`<pre class="pre" style="margin:0 20px 20px">${esc(JSON.stringify(i.labels,null,2))}</pre>`);
    }else if(d.kind==="volume"){
        const v=e.volumes.find(v=>v.name===d.id);if(!v)return;title=v.name;eyebrow="VOLUME / "+v.driver;
        body='<div style="height:24px"></div>'+panel("Volume","",definition([["Name",v.name],["Driver",v.driver],["Scope",v.scope],["Size",bytes(v.size)],["Docker references",v.references??"—"],["Mountpoint",v.mountpoint],["Created",dateText(v.created)]]))+panel("Associated containers","",table(["CONTAINER","STATUS"],e.containers.filter(c=>v.containers.includes(c.name)).map(c=>`<tr><td><button class="name-link" data-container="${c.id}">${esc(c.name)}</button></td><td>${stateChip(c)}</td></tr>`)))+`<p class="note">An unavailable size does not mean zero bytes. Some drivers do not report storage usage.</p>`;
    }else if(d.kind==="network"){
        const n=e.networks.find(n=>n.id===d.id);if(!n)return;title=n.name;eyebrow="NETWORK / "+n.driver;
        body='<div style="height:24px"></div>'+panel("Network","",definition([["ID",n.id],["Driver",n.driver],["Scope",n.scope],["Internal",n.internal?"Yes":"No"],["Attachable",n.attachable?"Yes":"No"],["Subnet",n.ipam.map(x=>x.Subnet).join(", ")||"—"]]))+panel("Connected containers","",table(["CONTAINER","IP"],e.containers.filter(c=>n.containers.includes(c.name)).map(c=>`<tr><td><button class="name-link" data-container="${c.id}">${esc(c.name)}</button></td><td class="mono">${esc(c.networks.find(x=>x.name===n.name)?.ip||"—")}</td></tr>`)));
    }
    $("#detail-title").textContent=title;$("#detail-eyebrow").textContent=eyebrow;$("#detail-tabs").innerHTML=tabs;$("#detail-body").innerHTML=body;
    $("#detail").scrollTop=scroll;if($("#detail-body .pre"))$("#detail-body .pre").scrollTop=preScroll;
}
async function loadDetail(){
    const d=state.detail;if(!d||d.kind!=="container"||!["logs","inspect"].includes(d.tab)||d.loading||state.paused)return;
    d.loading=true;const request=++state.detailRequest,eid=state.envId,tab=d.tab;renderDetail();
    try{const data=await getJSON(`/api/environments/${eid}/containers/${d.id}/${tab}`);if(state.detailRequest!==request||eid!==state.envId||state.paused)return;d.data=data;d.error=null;d.loadedAt=Date.now();}
    catch(error){if(state.detailRequest===request){d.error=error.message;d.loadedAt=Date.now();}}
    finally{if(state.detailRequest===request){d.loading=false;renderDetail();}}
}
async function poll(){
    if(!state.paused&&sessionState.admin){
        try{
            const data=await getJSON("/api/snapshot"),changed=state.networkError||!state.snapshot||data.generation!==state.snapshot.generation||data.sequence!==state.snapshot.sequence||data.status!==state.snapshot.status;
            if(state.paused){setTimeout(poll,2000);return;}
            if(state.expectedGeneration&&state.expectedGeneration!==data.generation){setTimeout(poll,2000);return;}
            state.expectedGeneration=null;
            if(state.snapshot&&data.generation!==state.snapshot.generation){state.envId=null;state.events=null;state.eventsAt=0;state.detail=null;state.detailRequest++;$("#detail").close();}
            state.networkError=false;state.snapshot=data;
            if(!data.environments.some(e=>e.id===state.envId)){
                // Prefer the Edge gateway on the first visit; URL parameters still win when valid.
                state.envId=data.environments.find(e=>/edge/i.test(e.name))?.id??data.environments[0]?.id??null;
                saveRoute();
            }
            if(changed){render();if(state.detail&&!["logs","inspect"].includes(state.detail.tab))renderDetail();}else status();
            if(state.view==="events"&&Date.now()-state.eventsAt>15000)loadEvents();
            if(state.detail?.tab==="logs"&&Date.now()-state.detail.loadedAt>5000)loadDetail();
            if(state.view==="dashboards")Dashboards.refresh();
        }catch{
            state.networkError=true;$("#connection").className="live-badge offline";$("#connection").innerHTML='<span class="dot"></span>Server disconnected';
            $("#alerts").innerHTML='<div class="notice error">Cannot connect to the local console. Check that the Python process is still running. The last sample is retained.</div>';
        }
    }
    setTimeout(poll,2000);
}
document.addEventListener("click",event=>{
    const target=event.target.closest("button, a");if(!target)return;
    if(target.dataset.view){event.preventDefault();navigate(target.dataset.view);return;}
    if(target.dataset.env){changeEnvironment(target.dataset.env);return;}
    for(const kind of ["container","stack","image","volume","network"]){if(target.dataset[kind]){openDetail(kind,target.dataset[kind]);return;}}
    if(target.dataset.storageTab){state.storageTab=target.dataset.storageTab;state.query="";render();return;}
    if(target.dataset.detailTab){state.detailRequest++;state.detail.tab=target.dataset.detailTab;state.detail.data=null;state.detail.error=null;state.detail.loading=false;state.detail.loadedAt=0;renderDetail();loadDetail();return;}
    if(target.id==="refresh-detail")loadDetail();
    if(target.id==="refresh-events")loadEvents();
});
document.addEventListener("input",event=>{if(event.target.id==="search"){state.query=event.target.value;render();}});
document.addEventListener("change",event=>{
    const id=event.target.id,value=event.target.value;
    if(id==="environment")changeEnvironment(value);
    if(id==="state-filter"){state.filter=value;render();}
    if(id==="sort"){state.sort=value;render();}
    if(id==="chart-range"){state.range=Number(value);drawCharts();}
});
$("#pause").addEventListener("click",()=>{state.paused=!state.paused;$("#pause").innerHTML=state.paused?"▶ Resume view":"Ⅱ Pause view";status();if(!state.paused){if(state.detail&&!state.detail.data)loadDetail();if(state.view==="events")loadEvents();}});
$("#mobile-menu").addEventListener("click",()=>$(".sidebar").classList.toggle("open"));
$("#close-detail").addEventListener("click",()=>$("#detail").close());
$("#detail").addEventListener("close",()=>{state.detail=null;state.detailRequest++;});
$("#detail").addEventListener("click",event=>{if(event.target===$("#detail")){const r=$("#detail").getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right)$("#detail").close();}});
$("#export").addEventListener("click",()=>{
    const e=environment();if(!e)return;const payload={exported_at:new Date().toISOString(),mode:"read-only",environment:e};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"application/json"})),a=document.createElement("a");
    a.href=url;a.download=`edge-console-${e.name.replace(/[^a-z0-9_-]/gi,"_")}-${new Date().toISOString().slice(0,10)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast("Environment snapshot exported");
});
document.addEventListener("keydown",event=>{if(event.key==="/"&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)&&!$("#detail").open){if($("#search")){event.preventDefault();$("#search").focus();}}if(event.key==="Escape")$(".sidebar").classList.remove("open");});
window.addEventListener("resize",drawCharts);
window.addEventListener("hashchange",()=>{const previous=state.envId;route();if(previous!==state.envId)changeEnvironment(state.envId);else{render();if(state.view==="events")loadEvents();}});
setInterval(()=>{$("#clock").textContent=new Date().toLocaleTimeString("en-US");status();},1000);
initializeApplication().finally(()=>{route();poll();});
