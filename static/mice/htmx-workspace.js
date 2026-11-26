/* Progressive enhancement: native links/forms remain the no-JS fallback. */
(() => {
  htmx.config.historyCacheSize = 0;
  htmx.config.allowEval = false;
  htmx.config.allowScriptTags = false;
  // The workspace starts below a sticky toolbar. Scrolling the swap target
  // itself to the viewport top hides its heading/period behind that toolbar.
  htmx.config.scrollIntoViewOnBoost = false;

  // Opt-in read-only filters; retain native submit as a no-JS fallback.
  const filterSelector = 'form[data-live-filter]';
  const timers = new WeakMap();
  let filterRevision = 0;
  function scheduleFilter(event, delay) {
    const field = event.target;
    const form = field.closest(filterSelector);
    if (!form || !field.name || field.type === 'hidden' || event.isComposing) return;
    filterRevision++;
    clearTimeout(timers.get(form));
    timers.set(form, setTimeout(() => {
      if (form.isConnected && form.checkValidity()) form.requestSubmit();
    }, delay));
  }
  document.addEventListener('input', event => {
    if (event.target.matches('input:not([type]), input[type=text], input[type=search]')) scheduleFilter(event, 350);
  });
  document.addEventListener('compositionend', event => scheduleFilter(event, 350));
  document.addEventListener('change', event => {
    if (event.target.matches('select, input[type=checkbox], input[type=radio], input[type=date], input[type=datetime-local]')) scheduleFilter(event, 0);
  });
  document.addEventListener('submit', event => {
    if (event.target.matches(filterSelector)) {
      clearTimeout(timers.get(event.target));
      event.target.querySelectorAll('[name="page"]').forEach(field => field.remove());
    }
  }, true);
  function prepareFilters(root) {
    root.querySelectorAll(filterSelector).forEach(form => {
      form.setAttribute('hx-sync', '#mice-content:replace');
      form.querySelectorAll('input:not([type=hidden]), select').forEach((field, i) => {
        if (!field.id) field.id = 'live-' + form.dataset.liveFilter + '-' + i;
      });
      form.querySelectorAll('[data-live-submit]').forEach(button => button.hidden = true);
      htmx.process(form);
    });
  }
  document.addEventListener('htmx:beforeRequest', event => {
    if (event.detail.elt.matches(filterSelector)) event.detail.xhr.miceFilterRevision = filterRevision;
  });
  document.addEventListener('htmx:beforeSwap', event => {
    const revision = event.detail.xhr.miceFilterRevision;
    if (revision !== undefined && (revision !== filterRevision || event.detail.xhr.miceGeneration !== generation)) {
      event.detail.shouldSwap = false;
      return;
    }
    const active = document.activeElement;
    if (revision !== undefined && active && active.closest(filterSelector)) {
      event.detail.xhr.miceFilterFocus = {
        id: active.id, start: active.selectionStart, end: active.selectionEnd,
        direction: active.selectionDirection,
      };
    }
  });
  document.addEventListener('htmx:afterSwap', event => {
    const saved = event.detail.xhr && event.detail.xhr.miceFilterFocus;
    if (!saved) return;
    prepareFilters(document);
    const field = document.getElementById(saved.id);
    if (!field) return;
    field.focus({preventScroll: true});
    if (saved.start !== null && typeof field.setSelectionRange === 'function') {
      field.setSelectionRange(saved.start, saved.end, saved.direction);
    }
  });

  function initialize(root = document) {
    prepareFilters(root);
    const globalPeriod = document.querySelector('[data-global-period]');
    if (globalPeriod) {
      const dates = new URLSearchParams();
      ['range', 'start', 'end', 'start_offset', 'end_offset'].forEach(key => {
        const input = globalPeriod.elements[key];
        const value = input && (input.dataset.dateValue || input.value);
        if (input && !input.disabled && value && (globalPeriod.elements.range.value === 'custom' || key === 'range')) dates.set(key, value);
      });
      root.querySelectorAll('a[href]').forEach(link => {
        const url = new URL(link.href, location.href);
        if (!['/overview/', '/incidents/', '/messages/', '/analytics/'].includes(url.pathname)) return;
        if (link.closest('.mice-navigation') || (!url.searchParams.has('range') && !url.searchParams.has('start'))) {
          if (link.closest('.mice-navigation')) ['range', 'start', 'end', 'start_offset', 'end_offset'].forEach(key => url.searchParams.delete(key));
          dates.forEach((value, key) => url.searchParams.set(key, value));
          link.href = url.pathname + url.search;
        }
      });
      document.querySelectorAll('#mice-content form[method="get"]:not([data-global-period])').forEach(form => {
        dates.forEach((value, key) => {
          if (form.elements[key]) return;
          const input = document.createElement('input');
          input.type = 'hidden'; input.name = key; input.value = value; form.append(input);
        });
      });
    }
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
        const path = location.pathname;
        const section = /^\/(datasets|models)\//.test(path) ? '/models/' :
          /^\/(settings|retention|llm)\//.test(path) ? '/settings/' : path;
        if (section === url.pathname || section.startsWith(url.pathname)) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      }
    });
    const title = document.querySelector('[data-workspace-title]');
    const heading = document.querySelector('.mice-navigation a[aria-current="page"] .nav-label, #mice-content h1');
    if (title && heading) title.textContent = heading.textContent.trim();
  }
  document.addEventListener('DOMContentLoaded', () => initialize());
  document.addEventListener('htmx:afterSettle', event => {
    initialize();
    if (event.detail.target && event.detail.target.id === 'mice-content' && (!event.detail.xhr || event.detail.xhr.miceFilterRevision === undefined)) window.scrollTo(0, 0);
  });
  document.addEventListener('htmx:configRequest', event => {
    if (event.detail.elt.id === 'overview-live') event.detail.headers['X-MICE-Period-Poll'] = 'true';
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (token) event.detail.headers['X-CSRFToken'] = token.value;
  });
  let generation = 0;
  document.addEventListener('htmx:beforeRequest', event => {
    if (event.detail.elt.id !== 'overview-live') generation++;
    event.detail.xhr.miceGeneration = generation;
  });
  document.addEventListener('htmx:beforeSwap', event => {
    if (event.detail.xhr.getResponseHeader('X-MICE-Period-Poll') === 'true' && event.detail.xhr.miceGeneration !== generation) {
      event.detail.shouldSwap = false;
      return;
    }
    if ([400, 409, 422].includes(event.detail.xhr.status) &&
        (event.detail.xhr.miceFilterRevision === undefined ||
         (event.detail.xhr.miceFilterRevision === filterRevision && event.detail.xhr.miceGeneration === generation)) &&
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