document.querySelectorAll('[data-achievement-filter]').forEach(button => button.addEventListener('click', () => {
    const category = button.dataset.achievementFilter;
    document.querySelectorAll('[data-achievement-filter]').forEach(filter => {
        const active = filter === button;
        filter.classList.toggle('active', active);
        filter.setAttribute('aria-pressed', String(active));
    });
    let visible = 0;
    document.querySelectorAll('[data-achievement-category]').forEach(card => {
        card.hidden = category !== 'all' && category !== card.dataset.achievementCategory;
        if (!card.hidden) visible += 1;
    });
    document.getElementById('achievement-empty').hidden = visible > 0;
}));
