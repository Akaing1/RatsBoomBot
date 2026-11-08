(() => {
    const artwork = new WeakMap();
    function update(image) {
        const state = artwork.get(image);
        if (!state) return;
        const width = state.width || image.clientWidth || 96;
        if (width * (window.devicePixelRatio || 1) > 768) {
            image.removeAttribute('srcset');
            image.removeAttribute('sizes');
            image.src = state.original;
        } else {
            image.sizes = `${width}px`;
            image.srcset = state.srcset;
            image.src = state.small;
        }
    }
    const observer = new ResizeObserver(entries => entries.forEach(({target}) => update(target)));
    window.categoryArtwork = {
        set(image, source, width = 0) {
            observer.unobserve(image);
            artwork.delete(image);
            image.removeAttribute('srcset');
            image.removeAttribute('sizes');
            if (!source) { image.removeAttribute('src'); return; }
            let url;
            try { url = new URL(source, location.href); } catch (_) { image.src = source; return; }
            const match = url.pathname.match(/^(\/ttv-boxart\/.+?)(?:-\d+x\d+)?(\.(?:jpe?g|png|webp))$/i);
            if (url.origin !== 'https://static-cdn.jtvnw.net' || !match) { image.src = source; return; }
            const sized = size => `${url.origin}${match[1]}-${size}x${Math.round(size * 4 / 3)}${match[2]}${url.search}`;
            artwork.set(image, {width, original: `${url.origin}${match[1]}${match[2]}${url.search}`, small: sized(96),
                srcset: [48, 96, 192, 384, 768].map(size => `${sized(size)} ${size}w`).join(', ')});
            update(image);
            if (!width) observer.observe(image);
        },
    };
})();
