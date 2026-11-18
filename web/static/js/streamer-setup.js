(() => {
    const tour = document.querySelector('[data-setup-spotlight]');
    if (!tour) return;

    const card = tour.querySelector('[data-setup-card]');
    const outline = tour.querySelector('[data-setup-outline]');
    const pointer = tour.querySelector('[data-setup-pointer]');
    const shades = Object.fromEntries([...tour.querySelectorAll('[data-setup-shade]')]
        .map(shade => [shade.dataset.setupShade, shade]));
    const step = Number(tour.dataset.step);
    const active = tour.dataset.active === 'true';
    const settingsPage = document.querySelector('.settings-page:not([hidden])');
    const selectors = {
        0: '[data-setup-welcome] h2',
        1: '[data-chat-composer] .dashboard-chat-compose-row',
        3: '#setting-points-display_name',
        4: '[data-chat-composer] .dashboard-chat-compose-row',
        5: '.navigation a[href="/channel/for-you"]',
    };
    const target = !active ? null : step === 2
        ? settingsPage?.querySelector('.settings-master-control, .settings-switch-row, .settings-header-switches:has(button)')
            || settingsPage?.querySelector('.settings-page-heading')
        : document.querySelector(selectors[step]) || (step === 0 ? document.querySelector('.navigation a[href="/channel"]') : null);

    const padding = 12;
    const gap = 14;
    const clamp = (value, min, max) => Math.min(Math.max(value, min), Math.max(min, max));
    let frame = 0;

    function box(element, x, y, width, height) {
        Object.assign(element.style, {
            left: x + 'px', top: y + 'px',
            width: Math.max(0, width) + 'px', height: Math.max(0, height) + 'px',
        });
    }

    function paint() {
        frame = 0;
        const width = tour.clientWidth;
        const height = tour.clientHeight;
        const cardWidth = card.offsetWidth;
        const cardHeight = card.offsetHeight;
        const targetBox = target?.getBoundingClientRect();
        const visible = targetBox && targetBox.width && targetBox.height &&
            targetBox.bottom > 0 && targetBox.top < height && targetBox.right > 0 && targetBox.left < width;
        tour.toggleAttribute('data-anchored', Boolean(visible));
        outline.hidden = !visible;
        pointer.hidden = true;

        if (!visible) {
            box(shades.top, 0, 0, width, height);
            for (const edge of ['left', 'right', 'bottom']) box(shades[edge], 0, 0, 0, 0);
            card.style.left = Math.max(padding, (width - cardWidth) / 2) + 'px';
            card.style.top = Math.max(padding, (height - cardHeight) / 2) + 'px';
            if (target) {
                // A control can move out of view while its settings panel scrolls.
                for (const shade of Object.values(shades)) shade.style.pointerEvents = 'none';
            }
            return;
        }
        for (const shade of Object.values(shades)) shade.style.pointerEvents = '';

        const left = Math.max(0, targetBox.left - 5);
        const right = Math.min(width, targetBox.right + 5);
        const feed = step === 4 ? document.querySelector('.dashboard-chat-feed') : null;
        const feedBox = feed?.getBoundingClientRect();
        const replySpace = feedBox && feedBox.bottom <= targetBox.top + 12
            ? Math.max(0, targetBox.top - Math.max(feedBox.top, feedBox.bottom - 96)) : 0;
        const top = Math.max(0, targetBox.top - 5 - replySpace);
        const bottom = Math.min(height, targetBox.bottom + 5);
        const middleX = (left + right) / 2;
        const middleY = (top + bottom) / 2;
        box(outline, left, top, right - left, bottom - top);
        box(shades.top, 0, 0, width, top);
        box(shades.left, 0, top, left, bottom - top);
        box(shades.right, right, top, width - right, bottom - top);
        box(shades.bottom, 0, bottom, width, height - bottom);

        let x = clamp(middleX - cardWidth / 2, padding, width - cardWidth - padding);
        let y = clamp(middleY - cardHeight / 2, padding, height - cardHeight - padding);
        let arrowX, arrowY, angle;
        if (width - right >= cardWidth + gap + padding) {
            x = right + gap;
            arrowX = x;
            arrowY = clamp(middleY, y + 16, y + cardHeight - 16);
            angle = 135;
        } else if (left >= cardWidth + gap + padding) {
            x = left - cardWidth - gap;
            arrowX = x + cardWidth;
            arrowY = clamp(middleY, y + 16, y + cardHeight - 16);
            angle = -45;
        } else if (height - bottom >= cardHeight + gap + padding) {
            y = bottom + gap;
            arrowX = clamp(middleX, x + 16, x + cardWidth - 16);
            arrowY = y;
            angle = 225;
        } else if (top >= cardHeight + gap + padding) {
            y = top - cardHeight - gap;
            arrowX = clamp(middleX, x + 16, x + cardWidth - 16);
            arrowY = y + cardHeight;
            angle = 45;
        } else {
            y = top > height - bottom ? padding : height - cardHeight - padding;
        }
        card.style.left = x + 'px';
        card.style.top = y + 'px';
        if (angle !== undefined) {
            pointer.style.left = arrowX + 'px';
            pointer.style.top = arrowY + 'px';
            pointer.style.setProperty('--setup-arrow-angle', angle + 'deg');
            pointer.hidden = false;
        }
    }

    function schedulePaint() {
        if (!frame) frame = requestAnimationFrame(paint);
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (target?.getClientRects().length) target.scrollIntoView({block: 'center', inline: 'nearest'});
        card.focus({preventScroll: true});
        paint();
        tour.setAttribute('data-ready', '');
    }, {once: true});
    window.addEventListener('resize', schedulePaint);
    window.addEventListener('scroll', schedulePaint, {capture: true, passive: true});
    const resize = new ResizeObserver(schedulePaint);
    resize.observe(card);
    if (target) resize.observe(target);

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && (card.contains(event.target) || target?.contains(event.target) || event.target === document.body)) {
            const close = card.querySelector('[value="dismiss"], a[href="/channel"].button');
            if (close) {
                event.preventDefault();
                close.click();
            }
        }
        if (event.key !== 'Tab') return;
        const focusable = 'button:not([disabled]), a[href], input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex="0"]';
        const controls = [...new Set([
            ...(target?.matches(focusable) ? [target] : []),
            ...(target?.querySelectorAll(focusable) || []),
            ...card.querySelectorAll(focusable),
        ])].filter(control => control.getClientRects().length);
        if (!controls.length) return;
        const index = controls.indexOf(document.activeElement);
        event.preventDefault();
        controls[index < 0 ? (event.shiftKey ? controls.length - 1 : 0)
            : (index + (event.shiftKey ? -1 : 1) + controls.length) % controls.length].focus();
    });
})();
