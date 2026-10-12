"use strict";
const PanelCharts={
 colors:{green:"#43b897",blue:"#719ced",amber:"#d5a34b",violet:"#ac8cdb",cyan:"#55b5c2"},
 format(value,unit){return value==null?"Unavailable":unit==="bytes"?bytes(value):unit==="rate"?rate(value):unit==="percent"?pct(value):unit==="seconds"?number(value,1)+" s":unit==="count_rate"?number(value,2)+" /s":unit==="native"?number(value,2):number(value,0);},
 html(panel){
  const s=panel.series||[],v=s[0]?.value;
  if(panel.visual==="stat")return `<div class="stat-panel">${s.map(x=>`<div><strong style="color:${PanelCharts.colors[panel.color]}">${esc(PanelCharts.format(x.value,panel.unit))}</strong><span>${esc(x.name)}</span>${panel.threshold!=null&&x.value!=null&&x.value>=panel.threshold?'<span class="threshold-flag">Above threshold</span>':""}</div>`).join("")}</div>`;
  if(panel.visual==="table")return `<div class="widget-table"><table class="data-table"><thead><tr><th>RESOURCE</th><th>${esc(panel.metric_label)}</th></tr></thead><tbody>${s.map(x=>`<tr><td>${esc(x.name)}</td><td class="mono">${esc(PanelCharts.format(x.value,panel.unit))}</td></tr>`).join("")}</tbody></table></div>`;
  return `${panel.visual==="bar"?'<div class="bar-scroll">':""}<div class="panel-canvas-wrap" ${panel.visual==="bar"?`style="min-height:${Math.max(80,s.length*40+20)}px"`:""}><canvas data-panel-canvas="${esc(panel.id)}" role="img" aria-label="${esc(panel.title)}"></canvas>${s.every(x=>x.value==null)&&s.every(x=>!x.points?.some(p=>p.v!=null))?'<span class="canvas-empty">No measurements available</span>':""}</div>${panel.visual==="bar"?"</div>":""}<div class="panel-legend">${s.map((x,i)=>`<span><i style="background:${PanelCharts.palette(panel.color,i)}"></i>${esc(x.name)} <b>${esc(PanelCharts.format(x.value,panel.unit))}</b></span>`).join("")}</div>`;
 },
 palette(base,index){const palette=[PanelCharts.colors[base],...Object.entries(PanelCharts.colors).filter(([k])=>k!==base).map(([,v])=>v)];return palette[index%palette.length];},
 drawAll(panels,range=15){for(const p of panels||[])PanelCharts.draw(p,range);},
 draw(panel,range){
  const c=document.querySelector(`[data-panel-canvas="${CSS.escape(panel.id)}"]`);if(!c)return;
  const r=c.getBoundingClientRect(),w=r.width,h=r.height;if(w<1||h<1)return;
  const ratio=window.devicePixelRatio||1;c.width=w*ratio;c.height=h*ratio;const ctx=c.getContext("2d");ctx.scale(ratio,ratio);
  const theme=getComputedStyle(document.documentElement),grid=theme.getPropertyValue("--chart-grid").trim()||"#e6eaee",text=theme.getPropertyValue("--chart-text").trim()||"#82909b",series=panel.series||[];
  ctx.font='10px "Segoe UI", sans-serif';ctx.fillStyle=text;
  if(panel.visual==="gauge"){
   const value=series.reduce((sum,s)=>s.value==null?NaN:sum+s.value,0),fraction=Number.isFinite(value)?Math.max(0,Math.min(1,(value-panel.min)/(panel.max-panel.min))):0;
   const radius=Math.max(25,Math.min(w*.32,h*.55)),x=w/2,y=h*.70,start=Math.PI*.85,end=Math.PI*2.15;
   ctx.lineWidth=12;ctx.lineCap="round";ctx.strokeStyle=grid;ctx.beginPath();ctx.arc(x,y,radius,start,end);ctx.stroke();ctx.strokeStyle=panel.threshold!=null&&value>=panel.threshold?PanelCharts.colors.amber:PanelCharts.colors[panel.color];ctx.beginPath();ctx.arc(x,y,radius,start,start+(end-start)*fraction);ctx.stroke();
   ctx.fillStyle=text;ctx.textAlign="center";ctx.font='26px Consolas, monospace';ctx.fillText(PanelCharts.format(Number.isFinite(value)?value:null,panel.unit),x,y+5);ctx.font='10px "Segoe UI",sans-serif';ctx.fillText(`${PanelCharts.format(panel.min,panel.unit)} — ${PanelCharts.format(panel.max,panel.unit)}`,x,y+27);return;
  }
  if(panel.visual==="bar"){
   const max=Math.max(1,...series.map(s=>s.value||0)),row=Math.min(45,(h-15)/Math.max(1,series.length));
   series.forEach((s,i)=>{const y=8+i*row;ctx.textAlign="left";ctx.fillStyle=text;ctx.fillText(s.name.slice(0,38),8,y+10);ctx.textAlign="right";ctx.fillText(PanelCharts.format(s.value,panel.unit),w-8,y+10);ctx.fillStyle=grid;ctx.fillRect(8,y+18,w-16,5);ctx.fillStyle=PanelCharts.palette(panel.color,i);ctx.fillRect(8,y+18,(w-16)*(s.value||0)/max,5);});return;
  }
  const pad={l:59,r:12,t:12,b:25},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b,end=Date.now(),start=end-range*60000;
  const values=series.flatMap(s=>(s.points||[]).filter(p=>p.t>=start&&p.v!=null).map(p=>p.v));
  const max=Math.max(1,...values)*1.12;
  for(let i=0;i<=3;i++){const y=pad.t+ch*i/3;ctx.strokeStyle=grid;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillStyle=text;ctx.textAlign="right";ctx.fillText(PanelCharts.format(max*(1-i/3),panel.unit),pad.l-7,y+3);}
  for(let i=0;i<=2;i++){ctx.textAlign=i===0?"left":i===2?"right":"center";ctx.fillStyle=text;ctx.fillText(new Date(start+(end-start)*i/2).toLocaleTimeString("en-GB",{hour:"2-digit",minute:"2-digit"}),pad.l+cw*i/2,h-5);}
  series.forEach((s,i)=>{ctx.strokeStyle=PanelCharts.palette(panel.color,i);ctx.lineWidth=2;ctx.beginPath();let active=false,last=null;
   for(const p of s.points||[]){if(p.t<start)continue;if(p.v==null){active=false;continue;}const x=pad.l+(p.t-start)/(end-start)*cw,y=pad.t+ch-p.v/max*ch;if(!active){ctx.moveTo(x,y);active=true;}else ctx.lineTo(x,y);last={x,y};}ctx.stroke();if(last){ctx.fillStyle=PanelCharts.palette(panel.color,i);ctx.beginPath();ctx.arc(last.x,last.y,2.5,0,Math.PI*2);ctx.fill();}
  });
  if(panel.threshold!=null&&panel.threshold<max){const y=pad.t+ch-panel.threshold/max*ch;ctx.setLineDash([4,4]);ctx.strokeStyle=PanelCharts.colors.amber;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.setLineDash([]);}
 }
};
