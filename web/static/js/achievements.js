const achievementScope = document.getElementById('achievement-scope');
achievementScope?.addEventListener('change', () => {
    let visible = 0;
    document.querySelectorAll('[data-achievement-scope]').forEach(card => {
        card.hidden = achievementScope.value !== 'all' && achievementScope.value !== card.dataset.achievementScope;
        if (!card.hidden) visible += 1;
    });
    document.getElementById('achievement-empty').hidden = visible > 0;
});
