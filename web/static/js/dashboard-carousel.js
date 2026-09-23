(() => {
    const layout = document.querySelector("[data-dashboard-carousel]");
    const deck = layout?.querySelector("[data-dashboard-carousel-deck]");
    const previous = layout?.querySelector("[data-dashboard-carousel-prev]");
    const next = layout?.querySelector("[data-dashboard-carousel-next]");
    const position = document.querySelector("[data-dashboard-carousel-position]");
    const positionCount = position?.querySelector("[data-dashboard-carousel-count]");
    const positionName = position?.querySelector("[data-dashboard-carousel-name]");
    if (!layout || !deck || !previous || !next || !positionCount || !positionName) return;

    const media = window.matchMedia("(max-width: 1100px)");
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
    playerSlide.setAttribute("aria-label", cards[0].name);
    playerSlide.dataset.dashboardCarouselSlide = "0";
    playerSlide.append(player);
    deck.append(playerSlide);

    let slides = [];
    let originals = [];
    let activeIndex = 0;
    let touchStart = null;

    function showCard(index) {
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
        positionCount.textContent = `${activeIndex + 1} / ${slides.length} ·`;
        positionName.textContent = cards[activeIndex].name;
    }

    function enableCarousel() {
        if (slides.length) return;
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
            slide.setAttribute("aria-label", card.name);
            slide.dataset.dashboardCarouselSlide = String(index);
            card.elements.forEach(element => slide.append(element));
            deck.append(slide);
            slides.push(slide);
        });
        showCard(activeIndex);
        layout.classList.add("has-carousel");
    }

    function disableCarousel() {
        if (!slides.length) return;
        layout.classList.remove("has-carousel");
        originals.forEach(({element, marker}) => {
            element.inert = false;
            marker.replaceWith(element);
        });
        slides.slice(1).forEach(slide => slide.remove());
        playerSlide.classList.remove("is-active", "is-before", "is-after", "is-neighbor");
        playerSlide.inert = false;
        playerSlide.removeAttribute("aria-hidden");
        slides = [];
        originals = [];
    }

    function updateLayout() {
        if (media.matches) enableCarousel();
        else disableCarousel();
    }

    previous.addEventListener("click", () => showCard(activeIndex - 1));
    next.addEventListener("click", () => showCard(activeIndex + 1));
    deck.addEventListener("touchstart", event => {
        if (event.target.closest(".dashboard-tabs, .chat-emote-picker, input, textarea, select, [contenteditable]")) return;
        const touch = event.changedTouches[0];
        touchStart = {x: touch.clientX, y: touch.clientY};
    }, {passive: true});
    deck.addEventListener("touchend", event => {
        if (!touchStart) return;
        const touch = event.changedTouches[0];
        const deltaX = touch.clientX - touchStart.x;
        const deltaY = touch.clientY - touchStart.y;
        touchStart = null;
        if (Math.abs(deltaX) < 60 || Math.abs(deltaX) < Math.abs(deltaY) * 1.25) return;
        showCard(activeIndex + (deltaX < 0 ? 1 : -1));
    }, {passive: true});
    deck.addEventListener("touchcancel", () => { touchStart = null; }, {passive: true});
    media.addEventListener("change", updateLayout);
    updateLayout();
})();
