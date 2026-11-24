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
        if (event.submitter && (event.submitter.value.startsWith('edit_category:') || ['create_category', 'edit_category', 'save_category', 'cancel_category'].includes(event.submitter.value))) return;
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
  document.addEventListener('htmx:afterSettle', initialize);
})();
(() => {
  function dispose(root) {
    root.querySelectorAll('[data-document-viewer]').forEach(form => form.dispatchEvent(new Event('mice:dispose')));
  }

  document.addEventListener('htmx:afterSwap', event => {
    const dialog = event.detail.target;
    if (dialog.id !== 'attachment-viewer-host' || !dialog.querySelector('#attachment-viewer')) return;
    const trigger = event.detail.requestConfig.elt;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.addEventListener('close', () => {
      dispose(dialog);
      dialog.replaceChildren();
      document.body.style.overflow = overflow;
      if (trigger && trigger.isConnected) trigger.focus();
    }, {once: true});
    dialog.querySelectorAll('[data-viewer-close]').forEach(button => {
      button.addEventListener('click', () => dialog.close());
    });
    dialog.showModal();
  });

  document.addEventListener('htmx:beforeCleanupElement', event => {
    const root = event.detail.elt;
    if (root.matches && root.matches('[data-document-viewer]')) root.dispatchEvent(new Event('mice:dispose'));
    if (root.querySelectorAll) dispose(root);
    if (root.matches && root.matches('#attachment-viewer-host[open]')) root.close();
  });
})();
