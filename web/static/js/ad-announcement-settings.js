(() => {
    const book = document.querySelector('[data-settings-book]');
    if (!book) return;
    function update() {
        const type = book.querySelector('[data-setting-key="ad_message_type"] select');
        const color = book.querySelector('[data-setting-key="ad_announcement_color"]');
        if (type && color) color.hidden = type.value !== 'announcement';
    }
    book.addEventListener('change', update);
    book.addEventListener('settings-saved', update);
    book.addEventListener('input', update);
    update();
})();
