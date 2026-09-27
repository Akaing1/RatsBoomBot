(() => {
    const layout = document.querySelector("[data-dashboard-carousel]");
    const deck = layout?.querySelector("[data-dashboard-carousel-deck]");
    const previous = layout?.querySelector("[data-dashboard-carousel-prev]");
    const next = layout?.querySelector("[data-dashboard-carousel-next]");
    const position = document.querySelector("[data-dashboard-carousel-position]");
    const positionCount = position?.querySelector("[data-dashboard-carousel-count]");
    const positionName = position?.querySelector("[data-dashboard-carousel-name]");
    if (!layout || !deck || !previous || !next || !positionCount || !positionName) return;

    const media = window.matchMedia("(max-width: 768px)");
    const groups = [
        {name: "Stream and Ads", selectors: [".dashboard-video-card", ".dashboard-ads-panel"]},
        {name: "Viewer Queue", selectors: ["[data-viewer-queue-panel]"]},
        {name: "Moderation and Activity", selectors: [".dashboard-moderation-panel", ".dashboard-community-panel"]},
        {name: "Combined Chat", selectors: [".live-chat-panel"]}
    ];
    const cards = groups.map(group => ({
        name: group.name,
        elements: group.selectors.map(selector => layout.querySelector(selector))
    }));
    if (cards.some(card => card.elements.some(element => !element))) return;

    // Place the iframe in its permanent slide before dashboard-stream-player.js sets src.
    // Reparenting a loaded iframe at a breakpoint would restart the Twitch player.
    const player = cards[0].elements[0];
    const playerSlide = document.createElement("section");
    playerSlide.className = "dashboard-carousel-slide";
    playerSlide.dataset.dashboardCarouselSlide = "0";
    playerSlide.append(player);
    deck.append(playerSlide);

    let slides = [];
    let originals = [];
    let activeIndex = 0;
    let touchStart = null;
    let suppressClickUntil = 0;

    function showCard(index, focusCard = false) {
        activeIndex = Math.min(Math.max(index, 0), slides.length - 1);
        slides.forEach((slide, slideIndex) => {
            slide.classList.toggle("is-active", slideIndex === activeIndex);
            slide.classList.toggle("is-before", slideIndex < activeIndex);
            slide.classList.toggle("is-after", slideIndex > activeIndex);
            slide.classList.toggle("is-neighbor", Math.abs(slideIndex - activeIndex) === 1);
            slide.inert = slideIndex !== activeIndex;
            slide.setAttribute("aria-hidden", String(slideIndex !== activeIndex));
        });
        previous.disabled = activeIndex === 0;
        next.disabled = activeIndex === slides.length - 1;
        previous.setAttribute("aria-label", `Previous card: ${cards[Math.max(0, activeIndex - 1)].name}`);
        next.setAttribute("aria-label", `Next card: ${cards[Math.min(slides.length - 1, activeIndex + 1)].name}`);
        positionCount.textContent = `${activeIndex + 1} / ${slides.length} ·`;
        positionName.textContent = cards[activeIndex].name;
        if (focusCard) slides[activeIndex].focus({preventScroll: true});
    }

    function enableCarousel() {
        if (slides.length) return;
        deck.tabIndex = 0;
        deck.setAttribute("role", "region");
        deck.setAttribute("aria-roledescription", "carousel");
        deck.setAttribute("aria-keyshortcuts", "ArrowLeft ArrowRight Home End");
        originals = cards.flatMap((card, index) => index === 0 ? card.elements.slice(1) : card.elements).map(element => {
            const marker = document.createComment("dashboard carousel position");
            element.before(marker);
            return {element, marker};
        });
        slides = [playerSlide];
        cards.forEach((card, index) => {
            if (index === 0) {
                card.elements.slice(1).forEach(element => playerSlide.append(element));
                return;
            }
            const slide = document.createElement("section");
            slide.className = "dashboard-carousel-slide";
            slide.dataset.dashboardCarouselSlide = String(index);
            card.elements.forEach(element => slide.append(element));
            deck.append(slide);
            slides.push(slide);
        });
        slides.forEach((slide, index) => {
            slide.tabIndex = -1;
            slide.setAttribute("role", "group");
            slide.setAttribute("aria-roledescription", "slide");
            slide.setAttribute("aria-label", `${cards[index].name}, ${index + 1} of ${cards.length}`);
        });
        showCard(activeIndex);
        layout.classList.add("has-carousel");
    }

    function disableCarousel() {
        if (!slides.length) return;
        layout.classList.remove("has-carousel");
        deck.removeAttribute("tabindex");
        deck.removeAttribute("role");
        deck.removeAttribute("aria-roledescription");
        deck.removeAttribute("aria-keyshortcuts");
        originals.forEach(({element, marker}) => {
            element.inert = false;
            marker.replaceWith(element);
        });
        slides.slice(1).forEach(slide => slide.remove());
        playerSlide.classList.remove("is-active", "is-before", "is-after", "is-neighbor");
        playerSlide.inert = false;
        playerSlide.removeAttribute("aria-hidden");
        playerSlide.removeAttribute("tabindex");
        playerSlide.removeAttribute("role");
        playerSlide.removeAttribute("aria-roledescription");
        playerSlide.removeAttribute("aria-label");
        slides = [];
        originals = [];
    }

    function updateLayout() {
        if (media.matches) enableCarousel();
        else disableCarousel();
    }

    previous.addEventListener("click", () => showCard(activeIndex - 1, true));
    next.addEventListener("click", () => showCard(activeIndex + 1, true));
    deck.addEventListener("keydown", event => {
        if (!media.matches || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        if (event.target !== deck && !slides.includes(event.target)) return;
        const destination = event.key === "ArrowLeft" ? activeIndex - 1
            : event.key === "ArrowRight" ? activeIndex + 1
            : event.key === "Home" ? 0
            : event.key === "End" ? slides.length - 1 : null;
        if (destination === null || destination < 0 || destination >= slides.length) return;
        event.preventDefault();
        showCard(destination, true);
    });
    deck.addEventListener("touchstart", event => {
        touchStart = null;
        if (event.touches.length !== 1 || event.target.closest(".dashboard-tabs, .chat-emote-picker, .twitch-game-suggestions, .queue-list")) return;
        const touch = event.changedTouches[0];
        touchStart = {x: touch.clientX, y: touch.clientY, startedAt: performance.now(), horizontal: false};
    }, {passive: true});
    deck.addEventListener("touchmove", event => {
        if (!touchStart || event.touches.length !== 1) return;
        if (performance.now() - touchStart.startedAt > 500 && !touchStart.horizontal) {
            touchStart = null;
            return;
        }
        const touch = event.changedTouches[0];
        const deltaX = touch.clientX - touchStart.x;
        const deltaY = touch.clientY - touchStart.y;
        if (!touchStart.horizontal && Math.abs(deltaY) > 18 && Math.abs(deltaY) > Math.abs(deltaX)) {
            touchStart = null;
            return;
        }
        if (Math.abs(deltaX) > 18 && Math.abs(deltaX) > Math.abs(deltaY) * 1.25) touchStart.horizontal = true;
        if (touchStart.horizontal) event.preventDefault();
    }, {passive: false});
    deck.addEventListener("touchend", event => {
        if (!touchStart) return;
        const touch = event.changedTouches[0];
        const deltaX = touch.clientX - touchStart.x;
        const deltaY = touch.clientY - touchStart.y;
        touchStart = null;
        if (Math.abs(deltaX) < 60 || Math.abs(deltaX) < Math.abs(deltaY) * 1.25) return;
        const destination = activeIndex + (deltaX < 0 ? 1 : -1);
        if (destination < 0 || destination >= slides.length) return;
        suppressClickUntil = performance.now() + 350;
        showCard(destination);
    }, {passive: true});
    deck.addEventListener("touchcancel", () => { touchStart = null; }, {passive: true});
    deck.addEventListener("click", event => {
        if (performance.now() >= suppressClickUntil) return;
        suppressClickUntil = 0;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
    media.addEventListener("change", updateLayout);
    updateLayout();
})();
