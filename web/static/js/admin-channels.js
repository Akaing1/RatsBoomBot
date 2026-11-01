(() => {
    const filters = document.querySelector('[data-channel-filters]');
    if (!filters) return;
    const search = filters.querySelector('[data-channel-search]');
    const status = filters.querySelector('[data-channel-status]');
    const cards = [...document.querySelectorAll('[data-channel-card]')];
    const count = document.querySelector('[data-channel-count]');
    const empty = document.querySelector('[data-channel-no-results]');
    function update() {
        const query = search.value.trim().toLocaleLowerCase();
        let visible = 0;
        cards.forEach(card => {
            card.hidden = !(card.dataset.search.toLocaleLowerCase().includes(query)
                && (status.value === 'all' || card.dataset.live === status.value));
            if (!card.hidden) visible++;
        });
        count.textContent = `${visible} of ${cards.length} channels`;
        empty.hidden = visible !== 0;
    }
    search.addEventListener('input', update);
    status.addEventListener('change', update);
    filters.querySelector('[data-channel-reset]').addEventListener('click', () => {
        search.value = ''; status.value = 'all'; update(); search.focus();
    });
    filters.hidden = false;
    update();
})();
