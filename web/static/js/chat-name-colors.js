(() => {
    const luminance = rgb => rgb.map(value => {
        const channel = value / 255;
        return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
    }).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
    const luminanceContrast = (a, b) => (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    const contrast = (a, b) => luminanceContrast(luminance(a), luminance(b));
    function readable(color, backgrounds) {
        const rgb = [1, 3, 5].map(offset => parseInt(color.slice(offset, offset + 2), 16));
        const backgroundLuminances = backgrounds.map(luminance);
        const passes = candidate => {
            const value = luminance(candidate);
            return backgroundLuminances.every(background => luminanceContrast(value, background) >= 4.5);
        };
        if (passes(rgb)) return color;
        // Mix toward white first to preserve the user's hue on our dark theme.
        for (const end of [255, 0]) {
            for (let step = 1; step <= 100; step++) {
                const mixed = rgb.map(value => Math.round(value + (end - value) * step / 100));
                if (passes(mixed)) return `rgb(${mixed.join(', ')})`;
            }
        }
        return backgroundLuminances[0] < .18 ? '#ffffff' : '#000000';
    }
    function parse(value) {
        const match = value.match(/^rgba?\(([^)]+)\)/);
        if (!match) return null;
        const parts = match[1].split(/[\s,/]+/).filter(Boolean).map(Number);
        return parts.length >= 3 ? [...parts.slice(0, 3), parts[3] ?? 1] : null;
    }
    const composite = (top, bottom) => top.slice(0, 3).map((value, index) => value * top[3] + bottom[index] * (1 - top[3]));
    function backgrounds(element) {
        const ancestors = [];
        for (let node = element.parentElement; node; node = node.parentElement) ancestors.push(node);
        let background = [15, 17, 21];
        let samples = [];
        for (const node of ancestors.reverse()) {
            const style = getComputedStyle(node);
            const color = parse(style.backgroundColor || '');
            if (color) background = composite(color, background);
            if (node.classList.contains('live-chat-message')) {
                // Role highlights are translucent gradients over the row color.
                samples = [...(style.backgroundImage || '').matchAll(/rgba?\([^)]+\)/g)]
                    .map(match => parse(match[0])).filter(Boolean).map(color => composite(color, background));
            }
        }
        return [background, ...samples];
    }
    function apply(name) {
        const original = name.dataset.chatNameColor;
        if (!/^#[0-9a-f]{6}$/i.test(original || '')) return;
        name.style.color = readable(original, backgrounds(name));
    }
    function refresh() { document.querySelectorAll('[data-chat-name-color]').forEach(apply); }
    window.dashboardNameColors = {apply, readable, contrast};
    refresh();
    new MutationObserver(refresh).observe(document.documentElement, {attributes: true, attributeFilter: ['class', 'style']});
})();
