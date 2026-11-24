/* Accessible progressive tabs: every section remains visible without JavaScript. */
(() => {
  function initialize() {
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