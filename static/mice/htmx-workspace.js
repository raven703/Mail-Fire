/* Progressive enhancement: native links/forms remain the no-JS fallback. */
(() => {
  htmx.config.historyCacheSize = 0;
  htmx.config.allowEval = false;
  htmx.config.allowScriptTags = false;
  function initialize(root = document) {
    root.querySelectorAll('form[enctype="multipart/form-data"]').forEach(form => {
      form.setAttribute('hx-encoding', 'multipart/form-data');
      htmx.process(form);
    });
    root.querySelectorAll('a[href]').forEach(link => {
      const url = new URL(link.href, location.href);
      if (/\/(original|download)\/$/.test(url.pathname) || url.searchParams.has('export')) {
        link.setAttribute('hx-boost', 'false');
        htmx.process(link);
      }
      if (link.closest('.mice-navigation')) {
        if (url.pathname === location.pathname) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      }
    });
  }
  document.addEventListener('DOMContentLoaded', () => initialize());
  document.addEventListener('htmx:afterSettle', () => initialize());
  document.addEventListener('htmx:configRequest', event => {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (token) event.detail.headers['X-CSRFToken'] = token.value;
  });
  document.addEventListener('htmx:beforeSwap', event => {
    if ([400, 422].includes(event.detail.xhr.status)) {
      event.detail.shouldSwap = true;
      event.detail.isError = false;
    }
  });
  document.addEventListener('htmx:beforeRequest', () => {
    document.getElementById('workspace-status').textContent = 'Загрузка…';
  });
  document.addEventListener('htmx:afterRequest', event => {
    document.getElementById('workspace-status').textContent = event.detail.successful ? '' : 'Не удалось выполнить запрос. Повторите действие.';
  });
  document.addEventListener('htmx:beforeCleanupElement', event => {
    if (event.detail.elt.querySelector && event.detail.elt.querySelector('dialog[open]')) document.body.style.overflow = '';
  });
})();