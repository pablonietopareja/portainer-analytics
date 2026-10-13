"use strict";
const sessionState = {csrf:null,admin:false};
function showSetup(){
    const target=$("#auth-screen");target.hidden=false;
    target.innerHTML=`<form id="setup-form" class="auth-card setup-card"><div class="eyebrow">EDGE CONSOLE / FIRST RUN</div><h1>Set up your workspace</h1><p>Create your administrator access and connect your Portainer server. This installation starts with no connection or dashboards.</p><div class="form-columns"><div><label for="setup-password">Administrator password</label><input id="setup-password" type="password" minlength="12" maxlength="1024" autocomplete="new-password" required placeholder="At least 12 characters"></div><div><label for="setup-confirm">Confirm password</label><input id="setup-confirm" type="password" autocomplete="new-password" required></div></div><label for="setup-url">Portainer server URL</label><input id="setup-url" type="url" autocomplete="url" required placeholder="https://portainer.example:9443"><label for="setup-token">Portainer API token</label><input id="setup-token" type="password" autocomplete="new-password" required placeholder="Your Portainer access token"><label class="check-label"><input id="setup-verify" type="checkbox" checked>Verify the Portainer TLS certificate</label><button type="submit" class="button dark">Test connection & create workspace</button><div id="setup-result" class="form-message" role="status"></div><small>For a trusted server with a self-signed certificate, turn off TLS verification. Connection details stay on this gateway. Shared dashboards never expose the token.</small></form>`;
    $("#setup-form").addEventListener("submit",async e=>{
        e.preventDefault();const result=$("#setup-result"),button=e.target.querySelector("button");
        if($("#setup-password").value!==$("#setup-confirm").value){result.textContent="The passwords do not match.";return;}
        button.disabled=true;result.textContent="Testing Portainer before saving your workspace…";
        try{const response=await fetch("/api/setup",{method:"POST",headers:{"Content-Type":"application/json","X-Console-CSRF":sessionState.csrf},body:JSON.stringify({password:$("#setup-password").value,url:$("#setup-url").value,token:$("#setup-token").value,verify:$("#setup-verify").checked,timeout:8}),signal:AbortSignal.timeout(45000)});const data=await response.json();if(!response.ok)throw Error(data.error||"Setup could not be completed.");sessionState.admin=true;sessionState.csrf=data.csrf;state.expectedGeneration=data.generation;state.snapshot=null;target.innerHTML="";target.hidden=true;navigate("overview");toast("Workspace ready");}
        catch(error){result.textContent=error.message;}finally{button.disabled=false;}
    });
}
async function apiWrite(path,method,data){
    const response=await fetch(path,{method,headers:{"Content-Type":"application/json","X-Console-CSRF":sessionState.csrf||""},body:JSON.stringify(data),signal:AbortSignal.timeout(45000)});
    const payload=await response.json();
    if(response.status===401){sessionState.admin=false;showLogin();}
    if(!response.ok)throw Error(payload.error||"The request could not be completed.");
    return payload;
}
function showLogin(available=true){
    const target=$("#auth-screen");target.hidden=false;
    target.innerHTML=`<form id="login-form" class="auth-card"><div class="eyebrow">EDGE CONSOLE / ADMINISTRATION</div><h1>Administrator access</h1><p>${available?"Sign in to configure connections and manage dashboards.":"Administrator access is unavailable. Check the workspace configuration and server logs."}</p>${available?'<label for="login-password">Administrator password</label><input id="login-password" type="password" autocomplete="current-password" required><button class="button dark" type="submit">Sign in</button>':""}<div id="login-error" class="form-message" role="status"></div><small>Shared dashboard links do not require administrator access.</small></form>`;
    $("#login-form").addEventListener("submit",async event=>{event.preventDefault();const b=event.target.querySelector("button");b.disabled=true;try{const r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("#login-password").value})});const d=await r.json();if(!r.ok)throw Error(d.error);sessionState.admin=true;sessionState.csrf=d.csrf;target.hidden=true;$("#login-password").value="";route();render();}catch(e){$("#login-error").textContent=e.message;}finally{b.disabled=false;}});
}
async function initializeApplication(){
    const port=$("#workspace-port");if(port)port.textContent=":"+(location.port||(location.protocol==="https:"?"443":"80"));
    try{const r=await fetch("/api/session");const s=await r.json();sessionState.admin=s.admin;sessionState.csrf=s.csrf;if(s.setup_required)showSetup();else if(!s.admin)showLogin(s.login_available);}
    catch{$("#alerts").innerHTML='<div class="notice error">The console server is unavailable. Check the service and try again.</div>';}
}
const Settings={
    mounted:false,
    async mount(){
        if($(".settings-page"))return;
        $("#content").innerHTML='<div class="settings-page"><div class="empty-state"><span class="loader"></span><p>Loading settings…</p></div></div>';
        try{const config=await getJSON("/api/settings");if(state.view!=="settings")return;Settings.config=config;Settings.paint(config);}
        catch(e){if(state.view==="settings")$("#content").innerHTML=`<div class="notice error">${esc(e.message)}</div>`;}
    },
    paint(c){
        $("#content").innerHTML=`<div class="settings-page"><div class="settings-layout"><section class="panel settings-panel"><div class="panel-heading"><div><h2>Portainer connection</h2><p>Change the server used by this workspace.</p></div><span class="chip">${c.saved?"SAVED CONNECTION":"LOCAL BOOTSTRAP"}</span></div><form id="connection-form" class="settings-form"><label for="portainer-url">Server URL</label><input id="portainer-url" type="url" required value="${esc(c.url)}" placeholder="https://portainer.example.com:9443" autocomplete="url"><small>Include http:// or https:// and the Portainer port.</small><label for="portainer-token">Portainer API token ${c.has_token?'<span class="field-note">TOKEN STORED</span>':""}</label><input id="portainer-token" type="password" autocomplete="new-password" placeholder="${c.has_token?"Leave blank to keep the current token for this URL":"Enter a Portainer API token"}"><small>The token stays on the server and is never returned to the browser. A different server URL requires a new token.</small><div class="settings-row"><label class="check-label"><input id="portainer-tls" type="checkbox" ${c.verify?"checked":""}> Verify TLS certificate</label><label class="compact-field">Timeout <select id="portainer-timeout">${[3,5,8,15,30].map(v=>opt(String(v),v+" seconds",String(c.timeout))).join("")}</select></label></div><small>Disable verification only for a trusted local server using a self-signed certificate.</small><div class="form-actions"><button type="button" id="test-connection" class="button">Test connection</button><button type="submit" class="button dark">Save & reconnect</button></div><div id="connection-result" class="form-message" role="status"></div></form></section><div><section class="panel settings-panel"><div class="panel-heading"><div><h2>Appearance</h2><p>Applies to every view on this device.</p></div></div><div class="settings-form"><label for="appearance-mode">Theme</label><select id="appearance-mode" data-theme-control><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select><small>System follows your operating system and updates automatically.</small></div></section><section class="panel settings-panel"><div class="panel-heading"><div><h2>LAN administrator access</h2><p>Keep editing separate from shared monitoring screens.</p></div></div><form id="admin-password-form" class="settings-form"><label for="admin-password">${c.admin_password_set?"New administrator password":"Create an administrator password"}</label><input id="admin-password" type="password" autocomplete="new-password" minlength="12" required placeholder="At least 12 characters"><small>Network visitors can view shared dashboards. This password is required to access the editor and settings from another computer.</small><button class="button" type="submit">${c.admin_password_set?"Update password":"Set password"}</button><div id="password-result" class="form-message" role="status"></div></form></section></div></div><div class="info-box">Dashboard definitions and connection settings are saved on the server. Dashboards stay bound to their original Portainer URL, so switching servers will not silently redirect existing dashboards to unrelated environments.</div></div>`;
        $("#appearance-mode").value=Theme.mode;
        $("#test-connection").addEventListener("click",()=>Settings.connection(false));
        $("#connection-form").addEventListener("submit",e=>{e.preventDefault();Settings.connection(true);});
        $("#admin-password-form").addEventListener("submit",async e=>{e.preventDefault();const b=e.target.querySelector("button");b.disabled=true;try{await apiWrite("/api/admin/password","POST",{password:$("#admin-password").value});$("#admin-password").value="";$("#password-result").textContent="Administrator password saved. Other administrator sessions have been signed out.";}catch(error){$("#password-result").textContent=error.message;}finally{b.disabled=false;}});
    },
    async connection(save){
        const form=$("#connection-form");if(!form.reportValidity())return;
        const body={url:$("#portainer-url").value,token:$("#portainer-token").value,verify:$("#portainer-tls").checked,timeout:Number($("#portainer-timeout").value)};
        const result=$("#connection-result");form.querySelectorAll("button").forEach(b=>b.disabled=true);result.textContent=save?"Testing the connection before saving…":"Testing Portainer access…";
        try{
            const data=await apiWrite(save?"/api/settings":"/api/settings/test",save?"PUT":"POST",body);
            result.textContent=save?`Connection saved. Reconnecting to ${data.environments} environments…`:`Connection successful. ${data.environments} environments accessible.`;
            result.className="form-message success";
            if(save){$("#portainer-token").value="";state.expectedGeneration=data.generation;state.snapshot=null;state.envId=null;state.events=null;state.eventsAt=0;state.detailRequest++;state.detail=null;$("#detail").close();Settings.config=data.connection;toast("Connection saved");}
        }catch(e){result.className="form-message error";result.textContent=e.message;}
        finally{form.querySelectorAll("button").forEach(b=>b.disabled=false);}
    },
};
