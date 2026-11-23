(() => {
    const selector = '.state-toggle, .queue-state-toggle';
    document.addEventListener('click', event => {
        const toggle = event.target.closest(selector);
        if (!toggle || toggle.disabled || toggle.hasAttribute('data-toggle-hover-label')) return;
        if (event.pointerType === 'touch') return;
        if (!event.detail && document.activeElement !== toggle) return;
        const label = toggle.querySelector('.state-toggle-alternate, .queue-state-alternate');
        if (label) toggle.dataset.toggleHoverLabel = label.textContent;
    }, true);
    document.addEventListener('pointerout', event => {
        const toggle = event.target.closest(selector);
        if (!toggle || toggle.contains(event.relatedTarget)) return;
        // Replacing saved label nodes can emit pointerout without the pointer
        // leaving the button. Keep the held appearance in that case.
        const rect = toggle.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX >= rect.right || event.clientY < rect.top || event.clientY >= rect.bottom) {
            delete toggle.dataset.toggleHoverLabel;
        }
    });
    document.addEventListener('focusout', event => {
        const toggle = event.target.closest(selector);
        if (toggle && !toggle.matches(':hover')) delete toggle.dataset.toggleHoverLabel;
    });
})();
