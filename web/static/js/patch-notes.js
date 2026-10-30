(() => {
    const body = document.querySelector('[data-release-body]');
    const outline = document.querySelector('[data-release-outline]');
    if (!body || !outline) return;
    const headings = body.querySelectorAll('h2');
    if (!headings.length) return;
    headings.forEach((heading, index) => {
        heading.id = `release-section-${index + 1}`;
        const link = document.createElement('a');
        link.href = `#${heading.id}`;
        link.textContent = heading.textContent;
        outline.querySelector('[data-release-links]').append(link);
    });
    outline.hidden = false;
})();
