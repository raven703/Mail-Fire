/* Accessible progressive tabs: every section remains visible without JavaScript. */
(() => {
  function initialize() {
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
      const buttons = [...group.querySelectorAll('[data-tab]')];
      const activate = button => {
        buttons.forEach(item => {
          const selected = item === button;
          item.setAttribute('aria-selected', String(selected));
          item.tabIndex = selected ? 0 : -1;
          const panel = document.getElementById(item.dataset.tab);
          if (panel) panel.hidden = !selected;
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