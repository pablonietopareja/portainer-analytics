"use strict";
(() => {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  let mode = "system", saved = false;
  try { const value = localStorage.getItem("edge-console-theme"); if (["light", "dark", "system"].includes(value)) { mode = value; saved = true; } } catch {}
  const apply = () => {
    document.documentElement.dataset.theme = mode === "system" ? (media.matches ? "dark" : "light") : mode;
    document.documentElement.style.colorScheme = document.documentElement.dataset.theme;
    document.querySelectorAll("[data-theme-control]").forEach(el => el.value = mode);
    window.dispatchEvent(new CustomEvent("edge-theme-change"));
  };
  window.Theme = {
    get mode() { return mode; },
    set(value) { if (!["light", "dark", "system"].includes(value)) return; mode = value; saved = true; try { localStorage.setItem("edge-console-theme", value); } catch {} apply(); },
    preset(value) { if (!saved && ["light", "dark", "system"].includes(value)) { mode = value; apply(); } },
  };
  media.addEventListener("change", () => { if (mode === "system") apply(); });
  document.addEventListener("change", event => { if (event.target.matches("[data-theme-control]")) Theme.set(event.target.value); });
  document.addEventListener("DOMContentLoaded", apply);
  apply();
})();
