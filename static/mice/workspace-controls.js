/* Accessible progressive tabs: every section remains visible without JavaScript. */
(() => {
  function initialize() {
    document.querySelectorAll('[data-document-viewer]').forEach(form => {
      if (form.dataset.ready) return;
      form.dataset.ready = 'true';
      const image = form.querySelector('[data-viewer-image]');
      const status = form.querySelector('[data-viewer-status]');
      const previous = form.querySelector('[data-viewer-prev]');
      const next = form.querySelector('[data-viewer-next]');
      const page = form.elements.page;
      const panel = form.closest('[role="tabpanel"]');
      let pages = Number(page.max), controller, objectUrl;
      const cancel = () => {
        if (controller) controller.abort();
        controller = null;
      };
      const dispose = () => {
        cancel();
        if (objectUrl) URL.revokeObjectURL(objectUrl);
      };
      const load = async () => {
        if (panel.hidden || !form.reportValidity()) return;
        cancel();
        const request = new AbortController();
        controller = request;
        previous.disabled = next.disabled = true;
        image.hidden = true;
        status.textContent = 'Подготовка страницы…';
        try {
          const url = form.dataset.pageUrl + '?' + new URLSearchParams(new FormData(form));
          const response = await fetch(url, {signal: request.signal, cache: 'no-store'});
          if (!response.ok || response.headers.get('Content-Type') !== 'image/png') {
            throw new Error('Безопасный просмотр недоступен. Откройте распознанный текст.');
          }
          const blob = await response.blob();
          if (request.signal.aborted || !form.isConnected) return;
          if (objectUrl) URL.revokeObjectURL(objectUrl);
          objectUrl = URL.createObjectURL(blob);
          image.src = objectUrl;
          image.hidden = false;
          pages = Number(response.headers.get('X-Document-Pages')) || 1;
          page.max = Math.min(1000, pages);
          form.querySelector('[data-viewer-pages]').textContent = '/ ' + pages;
          status.textContent = '';
        } catch (error) {
          if (!request.signal.aborted && form.isConnected) status.textContent = error.message;
        } finally {
          if (controller === request) {
            previous.disabled = Number(page.value) <= 1;
            next.disabled = Number(page.value) >= Number(page.max) || image.hidden;
          }
        }
      };
      form.addEventListener('submit', event => { event.preventDefault(); load(); });
      previous.addEventListener('click', () => { page.stepDown(); load(); });
      next.addEventListener('click', () => { page.stepUp(); load(); });
      form.elements.scale.addEventListener('change', load);
      form.elements.highlight.addEventListener('change', load);
      panel.addEventListener('mice:tab', () => panel.hidden ? cancel() : load());
      form.addEventListener('mice:dispose', dispose);
    });
    document.querySelectorAll('[data-date-range]').forEach(group => {
      if (group.dataset.ready) return;
      group.dataset.ready = 'true';
      const start = group.querySelector('[name="start"]');
      const end = group.querySelector('[name="end"]');
      const period = group.querySelector('[data-period]');
      const form = period.form;
      group.querySelector('[data-timezone]').textContent = 'Часовой пояс: ' + Intl.DateTimeFormat().resolvedOptions().timeZone;
      const update = () => {
        const custom = period.value === 'custom';
        group.querySelectorAll('[data-custom-date]').forEach(label => label.hidden = !custom);
        start.disabled = end.disabled = !custom;
        form.elements.start_offset.disabled = form.elements.end_offset.disabled = !custom;
        form.elements.start_offset.value = start.value ? -new Date(start.value).getTimezoneOffset() : '';
        form.elements.end_offset.value = end.value ? -new Date(end.value).getTimezoneOffset() : '';
        end.setCustomValidity(start.value && end.value && start.value >= end.value ? 'Начало должно предшествовать окончанию' : '');
      };
      period.addEventListener('change', () => {
        update();
        if (period.value !== 'custom' && group.dataset.autoPeriod === 'true') form.requestSubmit();
      });
      start.addEventListener('input', update);
      end.addEventListener('input', update);
      update();
    });
    document.querySelectorAll('[data-structured-rule]').forEach(editor => {
      if (editor.dataset.ready) return;
      editor.dataset.ready = 'true';
      const kind = editor.querySelector('[name$="kind"]');
      const mode = editor.querySelector('[name$="match_type"]');
      const rows = [...editor.querySelectorAll('[data-term-row]')];
      const textInput = row => row.querySelector('input[name$="_text"]');
      rows.forEach(row => {
        row.hidden = !textInput(row).value;
        row.querySelector('[data-remove-term]').addEventListener('click', () => {
          textInput(row).value = '';
          row.querySelector('input[name$="_weight"]').value = 1;
          row.querySelector('input[type="checkbox"]').checked = false;
          row.hidden = true;
        });
      });
      editor.querySelector('[data-add-term]').addEventListener('click', () => {
        const row = rows.find(item => item.hidden);
        if (row) { row.hidden = false; textInput(row).focus(); }
      });
      const update = () => {
        editor.querySelectorAll('[data-rule-kind]').forEach(panel => panel.hidden = panel.dataset.ruleKind !== kind.value);
        editor.querySelector('[data-flexible-terms]').hidden = mode.value !== 'flexible';
      };
      kind.addEventListener('change', update); mode.addEventListener('change', update); update();
    });
    document.querySelectorAll('[data-rule-formset]').forEach(group => {
      if (group.dataset.ready) return;
      group.dataset.ready = 'true';
      const total = group.querySelector('[name$="-TOTAL_FORMS"]');
      const button = group.querySelector('[data-add-rule]');
      button.addEventListener('click', () => {
        const index = Number(total.value);
        if (index >= 100) return;
        const template = group.querySelector('[data-empty-rule]');
        const fragment = template.content.cloneNode(true);
        fragment.querySelectorAll('*').forEach(element => {
          [...element.attributes].forEach(attribute => {
            if (attribute.value.includes('__prefix__')) element.setAttribute(attribute.name, attribute.value.replaceAll('__prefix__', index));
          });
        });
        group.insertBefore(fragment, template);
        total.value = index + 1;
        initialize();
      });
    });
    document.querySelectorAll('[data-navigation-toggle]').forEach(button => {
      if (button.dataset.ready) return;
      button.dataset.ready = 'true';
      button.addEventListener('click', () => {
        const collapsed = document.body.classList.toggle('navigation-collapsed');
        button.setAttribute('aria-expanded', String(!collapsed));
      });
    });
    document.querySelectorAll('[data-select-page]').forEach(toggle => {
      if (toggle.dataset.ready) return;
      toggle.dataset.ready = 'true';
      const form = toggle.form;
      const boxes = () => [...document.querySelectorAll('input[name="message_ids"]')].filter(box => box.form === form);
      const update = () => {
        const items = boxes(), count = items.filter(box => box.checked).length;
        toggle.checked = items.length > 0 && count === items.length;
        toggle.indeterminate = count > 0 && count < items.length;
        form.querySelector('[data-selection-count]').textContent = 'Выбрано: ' + count;
      };
      toggle.addEventListener('change', () => { boxes().forEach(box => box.checked = toggle.checked); update(); });
      boxes().forEach(box => box.addEventListener('change', update));
      form.addEventListener('reset', () => setTimeout(() => { boxes().forEach(box => box.checked = false); update(); }, 0));
      update();
    });
    document.querySelectorAll('[data-policy-summary]').forEach(summary => {
      if (summary.dataset.ready) return;
      summary.dataset.ready = 'true';
      const form = summary.closest('form');
      const update = () => {
        const categories = [...form.querySelectorAll('[name="categories"]:checked')].map(box => box.parentElement.textContent.trim());
        const mode = form.querySelector('[name="category_match"]:checked');
        summary.textContent = (categories.length ? categories.join(mode && mode.value === 'all' ? ' И ' : ' ИЛИ ') : 'Все категории') +
          ' · Риск каждого срабатывания ≥ ' + form.elements.min_risk.value + ' · Число срабатываний ≥ ' + form.elements.min_count.value;
      };
      form.addEventListener('input', update); update();
    });
    document.querySelectorAll('[data-tabs]').forEach(group => {
      if (group.dataset.ready) return;
      group.dataset.ready = 'true';
      const buttons = [...group.querySelectorAll('[data-tab]')].filter(button => button.closest('[data-tabs]') === group);
      const activate = button => {
        buttons.forEach(item => {
          const selected = item === button;
          item.setAttribute('aria-selected', String(selected));
          item.tabIndex = selected ? 0 : -1;
          item.classList.toggle('selected', selected);
          const panel = document.getElementById(item.dataset.tab);
          if (panel) {
            panel.hidden = !selected;
            panel.dispatchEvent(new Event('mice:tab'));
          }
        });
      };
      buttons.forEach((button, index) => {
        button.addEventListener('click', () => activate(button));
        button.addEventListener('keydown', event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 :
            (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
          activate(buttons[next]); buttons[next].focus();
        });
      });
      if (buttons.length) activate(buttons[0]);
    });
  }
  document.addEventListener('DOMContentLoaded', initialize);
  document.addEventListener('htmx:afterSettle', initialize);
})();
document.addEventListener('click', event => {
  const link = event.target.closest('[data-resource-link]');
  if (!link) return;
  const details = document.getElementById(link.hash.slice(1));
  if (details) details.open = true;
});
