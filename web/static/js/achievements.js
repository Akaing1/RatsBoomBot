document.querySelectorAll('[data-achievement-filter]').forEach(button => button.addEventListener('click', () => {
    const scope = button.dataset.achievementFilter;
    document.querySelectorAll('[data-achievement-filter]').forEach(filter => {
        const active = filter === button;
        filter.classList.toggle('active', active);
        filter.setAttribute('aria-pressed', String(active));
    });
    let visible = 0;
    document.querySelectorAll('[data-achievement-scope]').forEach(card => {
        card.hidden = scope !== 'all' && scope !== card.dataset.achievementScope;
        if (!card.hidden) visible += 1;
    });
    document.getElementById('achievement-empty').hidden = visible > 0;
}));
