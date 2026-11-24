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
        const jobs = new URLSearchParams(location.search).get('tab') === 'jobs';
        const operations = url.pathname === '/operations/';
        if ((location.pathname === url.pathname || location.pathname.startsWith(url.pathname)) &&
            (!operations || (url.searchParams.get('tab') === 'jobs') === jobs)) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      }
    });
    const title = document.querySelector('[data-workspace-title]');
    const heading = document.querySelector('.mice-navigation a[aria-current="page"] .nav-label, #mice-content h1');
    if (title && heading) title.textContent = heading.textContent.trim();
  }
  document.addEventListener('DOMContentLoaded', () => initialize());
  document.addEventListener('htmx:afterSettle', () => initialize());
  document.addEventListener('htmx:configRequest', event => {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (token) event.detail.headers['X-CSRFToken'] = token.value;
  });
  document.addEventListener('htmx:beforeSwap', event => {
    if ([400, 409, 422].includes(event.detail.xhr.status) &&
        (event.detail.xhr.getResponseHeader('Content-Type') || '').includes('text/html')) {
      event.detail.shouldSwap = true;
      event.detail.isError = false;
    }
  });
  function requestStatus(event, message) {
    const status = document.getElementById('workspace-status');
    if (status && !['monitor-live', 'overview-live'].includes(event.detail.elt.id)) status.textContent = message;
  }
  document.addEventListener('htmx:beforeRequest', event => requestStatus(event, 'Загрузка…'));
  document.addEventListener('htmx:afterRequest', event => {
    requestStatus(event, event.detail.successful ? '' : 'Не удалось выполнить запрос. Повторите действие.');
    const dialog = event.detail.elt.closest('dialog[data-editor]');
    if (dialog && !event.detail.successful) {
      dialog.dataset.busy = 'false';
      dialog.querySelectorAll('[data-dialog-close]').forEach(button => button.disabled = false);
    }
  });
  document.addEventListener('htmx:beforeCleanupElement', event => {
    if (event.detail.elt.querySelector && event.detail.elt.querySelector('dialog[open]')) document.body.style.overflow = '';
  });
})();