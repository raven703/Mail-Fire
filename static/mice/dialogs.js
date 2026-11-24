(() => {
  function initialize() {
    document.querySelectorAll('dialog[data-editor]').forEach(dialog => {
      if (dialog.open) return;
      const previous = document.activeElement;
      const overflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      const close = () => {
        if (dialog.dataset.busy === 'true') return;
        dialog.close();
        document.body.style.overflow = overflow;
        if (previous && previous.focus) previous.focus();
        window.location.assign(dialog.dataset.closeUrl);
      };
      dialog.addEventListener('cancel', event => {
        event.preventDefault();
        event.stopPropagation();
        close();
      });
      dialog.querySelectorAll('[data-dialog-close]').forEach(button => {
        button.addEventListener('click', close);
      });
      dialog.querySelector('form').addEventListener('submit', event => {
        const confirmation = event.submitter && event.submitter.dataset.confirm;
        if (confirmation && !window.confirm(confirmation)) {
          event.preventDefault();
          return;
        }
        dialog.dataset.busy = 'true';
        // Preserve submitter name/value: disabling it here would omit the action.
        dialog.querySelectorAll('[data-dialog-close]').forEach(button => button.disabled = true);
      });
      dialog.showModal();
      const input = dialog.querySelector('input:not([type="hidden"]):not(:disabled)');
      if (input) input.focus();
    });
  }
  document.addEventListener('DOMContentLoaded', initialize);
})();