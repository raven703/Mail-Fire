(() => {
  const themes = ['system', 'light', 'dark'];
  let preference = 'system';
  try {
    const value = localStorage.getItem('mice.theme');
    if (themes.includes(value)) preference = value;
  } catch (_) {}
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  function apply() {
    document.documentElement.dataset.theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
  }
  apply();
  media.addEventListener('change', apply);
  document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('theme-preference');
    if (!select) return;
    let changed = false;
    let pending = Promise.resolve();
    const set = value => {
      if (!themes.includes(value)) return;
      select.value = preference = value;
      try { localStorage.setItem('mice.theme', value); } catch (_) {}
      apply();
    };
    const save = value => {
      changed = true;
      set(value);
      const csrf = document.querySelector('.user-menu [name=csrfmiddlewaretoken]').value;
      pending = pending.then(() => fetch(select.dataset.url, {
        method: 'POST', headers: {'X-CSRFToken': csrf}, body: new URLSearchParams({theme: value}),
      })).then(response => {
        if (!response.ok) throw new Error();
      }).catch(() => {
        document.getElementById('workspace-status').textContent = 'Не удалось сохранить тему в профиле.';
      });
    };
    select.value = preference;
    select.addEventListener('change', () => save(select.value));
    document.querySelector('[data-theme-toggle]').addEventListener('click', () => save(
      document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'
    ));
    fetch(select.dataset.url, {cache: 'no-store'}).then(response => response.json()).then(data => {
      if (!changed) set(data.theme);
    }).catch(() => {});
    const health = document.querySelector('[data-system-health]');
    const check = async () => {
      if (document.hidden) return;
      let ok = false;
      try { ok = (await fetch(health.dataset.systemHealth, {cache: 'no-store'})).ok; } catch (_) {}
      health.firstElementChild.className = 'health-dot ' + (ok ? 'ok' : 'error');
      health.title = ok ? 'API и PostgreSQL доступны' : 'Проверить состояние системы';
    };
    check();
    setInterval(check, 15000);
  });
})();
