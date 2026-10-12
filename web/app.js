"use strict";
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const number = (value, digits=1) => value == null || !Number.isFinite(value) ? "—" : Number(value).toLocaleString("en-US",{maximumFractionDigits:digits});
const bytes = value => {if(value == null || !Number.isFinite(value))return "—";const units=["B","KiB","MiB","GiB","TiB"];let n=Math.max(0,value),i=0;while(n>=1024&&i<4){n/=1024;i++;}return `${number(n,i?1:0)} ${units[i]}`;};
const pct = value => value == null ? "—" : `${number(value)}%`;
const rate = value => value == null ? "—" : bytes(value)+"/s";
const timeText = value => value ? new Date(value).toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit",second:"2-digit"}) : "—";
const dateText = value => {if(!value)return "—";const d=new Date(typeof value==="number"?value*1000:value);return Number.isNaN(d.getTime())?"—":d.toLocaleString("en-US",{dateStyle:"short",timeStyle:"short"});};
const chip = (label,kind="") => `<span class="chip ${kind}">${esc(label)}</span>`;
const labelState = value => ({running:"Running",exited:"Stopped",created:"Created",restarting:"Restarting",paused:"Paused",dead:"Failed",removing:"Removing"}[value]||value||"—");
const stateChip = c => chip(c.status?.includes("unhealthy")?"Unhealthy":labelState(c.state),c.status?.includes("unhealthy")||c.state==="dead"?"danger":c.state==="running"?"":c.state==="restarting"?"warning":"stopped");
const state = {snapshot:null,envId:null,view:"overview",paused:false,query:"",filter:"all",sort:"name",storageTab:"volumes",range:5,detail:null,events:null,eventsEnv:null,eventsLoading:false,eventsAt:0,eventsError:null,networkError:false,detailRequest:0};
const environment = () => state.snapshot?.environments.find(e=>e.id===state.envId);
const labels = {overview:["Overview","Live operational visibility into your infrastructure."],containers:["Containers","Resources, status, and diagnostics for every workload."],stacks:["Stacks","Services grouped by project and deployment."],images:["Images","Docker image and shared-layer inventory."],storage:["Storage","Volumes, writable layers, and build cache."],networks:["Networks","Logical topology and container connectivity."],events:["Activity","Recent Docker Engine events · past hour."],system:["System","Host and Docker Engine configuration and capabilities."]};

function metric(label,value,note,code,bar=null){return `<article class="metric"><div class="metric-label">${label}<span class="metric-code">${code}</span></div><div class="metric-value">${value}</div>${bar!==null?`<div class="mini-bar"><i style="width:${Math.min(100,Math.max(0,bar))}%"></i></div>`:""}<div class="metric-note">${note}</div></article>`;}
function panel(title,subtitle,body,action="",foot=""){return `<section class="panel"><div class="panel-heading"><div><h2>${title}</h2>${subtitle?`<p>${subtitle}</p>`:""}</div>${action}</div>${body}${foot?`<div class="panel-foot">${foot}</div>`:""}</section>`;}
function table(headers,rows,empty="No records match this selection."){return `<div class="table-scroll"><table class="data-table"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.length?rows.join(""):`<tr><td class="table-empty" colspan="${headers.length}">${esc(empty)}</td></tr>`}</tbody></table></div>`;}
function definition(items){return `<dl class="definition-list">${items.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>`;}
function searchToolbar(count,extra=""){return `<div class="toolbar"><div class="search"><input id="search" type="search" placeholder="Search this view…" aria-label="Search" value="${esc(state.query)}" autocomplete="off"><kbd>/</kbd></div>${extra}<span class="record-count">${count} RECORDS</span></div>`;}
function matches(...values){return !state.query||values.join(" ").toLowerCase().includes(state.query.toLowerCase());}
function opt(value,label,current){return `<option value="${value}" ${current===value?"selected":""}>${label}</option>`;}
function shell(){
    const s=state.snapshot,e=environment();if(!s)return;
    const select=$("#environment");const options=s.environments.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join("");
    if(select.innerHTML!==options)select.innerHTML=options||'<option>No environments</option>';select.value=state.envId;
    $("#breadcrumb-env").textContent=e?.name||"Portainer";
    $("#env-connection").innerHTML=e?`<span class="dot ${e.status==="offline"?"off":e.status==="degraded"?"warn":""}"></span>Endpoint ${e.id} · ${e.type===1?"Direct Docker":e.type===2?"Portainer Agent":"Edge Agent"}`:"Disconnected";
    $("#fleet").innerHTML=s.environments.map(x=>`<button class="fleet-item" data-env="${x.id}" ${x.id===state.envId?'aria-current="true"':""}><span class="dot ${x.status==="offline"?"off":x.status==="degraded"?"warn":""}"></span>${esc(x.name)}<span class="fleet-type">${String(x.id).padStart(2,"0")}</span></button>`).join("");
    for(const k of ["containers","stacks","images","networks"])$("#count-"+k).textContent=e?.[k]?.length??"—";
    $("#export").disabled=!e;status();
}
function status(){
    const s=state.snapshot,e=environment();if(!s||state.networkError)return;
    const stale=s.updated_at&&Date.now()-new Date(s.updated_at)>Math.max(20000,s.interval*4000);
    const off=s.status==="offline"||e?.status==="offline"||stale;
    const partial=e?.status==="degraded"||e?.status==="unsupported";
    $("#connection").className=`live-badge ${off?"offline":state.paused||s.status==="connecting"||partial?"pending":""}`;
    $("#connection").innerHTML=`<span class="dot"></span>${state.paused?"View paused":off?"No recent update":partial?"Partial data":s.status==="connecting"?"Connecting":"Live"}`;
    $("#freshness").textContent=`Metrics ${timeText(e?.updated_at)} · Inventory ${timeText(e?.inventory_updated_at)} · Storage ${timeText(e?.storage_updated_at)}`;
    const messages=[];
    if(s.error)messages.push(`<div class="notice error">${esc(s.error)}. The last available sample is retained.</div>`);
    if(e?.error)messages.push(`<div class="notice error">${esc(e.error)}</div>`);
    if(e?.errors?.length)messages.push(`<div class="notice">Partial data · ${e.errors.map(x=>esc(x.resource)+": "+esc(x.message)).join(" · ")}</div>`);
    if(e?.host?.memory_accounting===false)messages.push('<div class="notice">This host does not expose container memory counters. Memory is shown as unavailable; check the warnings under System.</div>');
    if(stale&&!state.paused&&!s.error)messages.push('<div class="notice">The latest sample is delayed. The displayed values correspond to the timestamp in the footer.</div>');
    if(state.paused)messages.push('<div class="notice">View paused. The server continues collecting metrics; resume to receive new samples.</div>');
    $("#alerts").innerHTML=messages.join("");
}
function render(){
    if(["settings","dashboards"].includes(state.view)&&state.paused){state.paused=false;$("#pause").textContent="\u2161 Pause view";}
    const focused=document.activeElement?.id;const selection=focused==="search"?[$("#search").selectionStart,$("#search").selectionEnd]:null;
    const scrolls=Array.from(document.querySelectorAll(".table-scroll")).map(x=>x.scrollLeft);
    $("#page-title").textContent=labels[state.view][0];$("#page-description").textContent=labels[state.view][1];shell();
    document.querySelectorAll(".nav-item").forEach(x=>{x.classList.toggle("active",x.dataset.view===state.view);x.setAttribute("aria-current",x.dataset.view===state.view?"page":"false");});
    const e=environment();
    $(".heading-actions").hidden=["settings","dashboards"].includes(state.view);
    if(state.view==="settings"){Settings.mount();return;}
    if(state.view==="dashboards"){Dashboards.mount();return;}
    if(!e){$("#content").innerHTML=`<div class="empty-state">${state.snapshot?.status==="live"?"":'<span class="loader"></span>'}<h2>${state.snapshot?.status==="offline"?"Portainer is unavailable":state.snapshot?.status==="live"?"No accessible environments":"Connecting to your infrastructure"}</h2><p>${state.snapshot?.status==="live"?"No environments were found with this API key's permissions.":"The console collects inventory and reconnects automatically."}</p></div>`;return;}
    if(e.status==="unsupported"){ $("#content").innerHTML='<div class="empty-state"><h2>Unsupported environment type</h2><p>This console supports Docker Standalone, Docker Agent, and Edge Agent environments.</p></div>';return; }
    if(!e.metrics){$("#content").innerHTML='<div class="empty-state"><h2>Environment unreachable</h2><p>The connection will be retried automatically.</p></div>';return;}
    $("#content").innerHTML=renderView(e);
    document.querySelectorAll(".table-scroll").forEach((x,i)=>x.scrollLeft=scrolls[i]||0);
    if(focused&&$("#"+focused)){const element=$("#"+focused);element.focus({preventScroll:true});if(selection)element.setSelectionRange(...selection);}
    drawCharts();
}
function toast(message){$("#toast").textContent=message;$("#toast").classList.add("visible");setTimeout(()=>$("#toast").classList.remove("visible"),3000);}
