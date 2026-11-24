/* Local theme preference only; no original content is stored in the browser. */
(() => {
  let preference = "system";
  try { preference = localStorage.getItem("mice.theme") || "system"; } catch (_) {}
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  function apply() {
    document.documentElement.dataset.theme = preference === "system" ? (media.matches ? "dark" : "light") : preference;
  }
  apply();
  media.addEventListener("change", apply);
  document.addEventListener("DOMContentLoaded", () => {
    const select = document.getElementById("theme-preference");
    if (!select) return;
    select.value = preference;
    select.addEventListener("change", () => {
      preference = select.value;
      try { localStorage.setItem("mice.theme", preference); } catch (_) {}
      apply();
    });
  });
})();