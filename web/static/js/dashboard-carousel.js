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
        {name: "Stream and Chat", selectors: [".dashboard-video-card", ".live-chat-panel"]},
        {name: "Ads and Viewer Queue", selectors: [".dashboard-ads-panel", "[data-viewer-queue-panel]"]},
        {name: "Moderation and Activity", selectors: [".dashboard-moderation-panel", ".dashboard-community-panel"]}
    ];
    const cards = groups.map(group => ({
        name: group.name,
        elements: group.selectors.map(selector => layout.querySelector(selector))
    }));
    if (cards.some(card => card.elements.some(element => !element))) return;

    // Mount the player in its permanent slide before Twitch creates its iframe.
    // Reparenting a loaded embed at a breakpoint would restart playback.
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
    const chat = cards[0].elements[1];
    const chatExpand = chat.querySelector("[data-chat-expand]");
    const chatLock = chat.querySelector("[data-chat-lock]");
    const chatInput = chat.querySelector('[data-chat-composer] [name="message"]');
    const main = layout.closest(".streamer-main-content");
    let chatLocked = false;
    let followFrame = 0;

    function preserveChatScroll(update) {
        const feed = chat.querySelector("[data-live-chat-feed]");
        const following = feed && feed.scrollHeight - feed.scrollTop - feed.clientHeight <= 24;
        window.cancelAnimationFrame(followFrame);
        update();
        if (following) {
            const finishAt = performance.now() + 320;
            const follow = now => {
                feed.scrollTop = feed.scrollHeight;
                if (media.matches && now < finishAt) followFrame = window.requestAnimationFrame(follow);
            };
            followFrame = window.requestAnimationFrame(follow);
        }
    }

    function updateChatControls() {
        const expanded = playerSlide.classList.contains("is-chat-expanded");
        if (chatExpand) {
            chatExpand.setAttribute("aria-pressed", String(expanded));
            chatExpand.setAttribute("aria-label", expanded ? "Collapse chat" : "Expand chat to full height");
            chatExpand.title = chatExpand.getAttribute("aria-label");
        }
        if (chatLock) {
            chatLock.setAttribute("aria-pressed", String(chatLocked));
            chatLock.setAttribute("aria-label", chatLocked ? "Enable automatic chat resizing" : "Lock automatic chat resizing");
            chatLock.title = chatLock.getAttribute("aria-label");
        }
    }

    function setChatExpanded(expanded, force = false) {
        if (chatLocked && !force) return;
        expanded = expanded && media.matches;
        if (playerSlide.classList.contains("is-chat-expanded") === expanded) return;
        preserveChatScroll(() => {
            playerSlide.classList.toggle("is-chat-expanded", expanded);
            player.inert = expanded;
            if (expanded) player.setAttribute("aria-hidden", "true");
            else player.removeAttribute("aria-hidden");
        });
        updateChatControls();
    }

    function updateChatOffset() {
        if (!media.matches || !slides.length) return;
        const gap = parseFloat(window.getComputedStyle(playerSlide).rowGap) || 0;
        const offset = `${player.offsetHeight + gap}px`;
        if (playerSlide.style.getPropertyValue("--dashboard-chat-top") !== offset) {
            preserveChatScroll(() => playerSlide.style.setProperty("--dashboard-chat-top", offset));
        }
    }

    function updateVisibleHeight() {
        if (!main || !window.visualViewport) return;
        preserveChatScroll(() => {
            if (media.matches && Math.abs(window.visualViewport.scale - 1) < .01) {
                main.style.setProperty("--dashboard-mobile-viewport-height", `${window.visualViewport.height}px`);
            } else main.style.removeProperty("--dashboard-mobile-viewport-height");
        });
    }

    chatInput?.addEventListener("focus", () => {
        if (!media.matches) return;
        showCard(0);
        setChatExpanded(true);
    });
    chat.addEventListener("focusout", event => {
        if (!media.matches || (event.relatedTarget && chat.contains(event.relatedTarget))) return;
        setChatExpanded(false);
    });
    chatLock?.addEventListener("click", () => {
        if (!media.matches) return;
        chatLocked = !chatLocked;
        updateChatControls();
    });
    chatExpand?.addEventListener("click", () => {
        if (!media.matches) return;
        const expanded = !playerSlide.classList.contains("is-chat-expanded");
        chatLocked = expanded;
        if (!expanded) chatInput?.blur();
        setChatExpanded(expanded, true);
        updateChatControls();
    });
    document.addEventListener("dashboard-chat-sent", () => {
        if (!media.matches || chatLocked) return;
        chatInput?.blur();
        setChatExpanded(false);
    });
    chat.addEventListener("wheel", () => window.cancelAnimationFrame(followFrame), {passive: true});
    chat.addEventListener("touchstart", () => window.cancelAnimationFrame(followFrame), {passive: true});
    window.visualViewport?.addEventListener("resize", updateVisibleHeight);
    if ("ResizeObserver" in window) {
        const observer = new ResizeObserver(updateChatOffset);
        observer.observe(player);
    } else window.addEventListener("resize", updateChatOffset);

    function showCard(index, focusCard = false) {
        activeIndex = Math.min(Math.max(index, 0), slides.length - 1);
        if (activeIndex !== 0) {
            setChatExpanded(false);
            if (chat.contains(document.activeElement)) document.activeElement.blur();
        }
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
        updateChatOffset();
    }

    function disableCarousel() {
        if (!slides.length) return;
        chatLocked = false;
        setChatExpanded(false, true);
        updateChatControls();
        playerSlide.style.removeProperty("--dashboard-chat-top");
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
        updateVisibleHeight();
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
        if (!media.matches || event.touches.length !== 1) return;
        if (event.target.closest(".chat-emote-picker, .twitch-game-suggestions")) return;
        if (event.target.closest(".queue-list") && !event.target.closest("button")) return;
        const touch = event.changedTouches[0];
        touchStart = {id: touch.identifier, x: touch.clientX, y: touch.clientY, horizontal: false};
    }, {capture: true, passive: true});
    deck.addEventListener("touchmove", event => {
        if (!touchStart) return;
        if (event.touches.length !== 1) {
            touchStart = null;
            return;
        }
        const touch = [...event.changedTouches].find(candidate => candidate.identifier === touchStart.id);
        if (!touch) return;
        const deltaX = touch.clientX - touchStart.x;
        const deltaY = touch.clientY - touchStart.y;
        if (!touchStart.horizontal && Math.abs(deltaY) > 18 && Math.abs(deltaY) > Math.abs(deltaX)) {
            touchStart = null;
            return;
        }
        if (Math.abs(deltaX) > 18 && Math.abs(deltaX) > Math.abs(deltaY) * 1.25) touchStart.horizontal = true;
        if (touchStart.horizontal) event.preventDefault();
    }, {capture: true, passive: false});
    deck.addEventListener("touchend", event => {
        if (!touchStart) return;
        const touch = [...event.changedTouches].find(candidate => candidate.identifier === touchStart.id);
        if (!touch) return;
        const deltaX = touch.clientX - touchStart.x;
        const deltaY = touch.clientY - touchStart.y;
        touchStart = null;
        if (Math.abs(deltaX) < 60 || Math.abs(deltaX) < Math.abs(deltaY) * 1.25) return;
        event.preventDefault();
        suppressClickUntil = performance.now() + 350;
        const destination = activeIndex + (deltaX < 0 ? 1 : -1);
        if (destination < 0 || destination >= slides.length) return;
        showCard(destination);
    }, {capture: true, passive: false});
    deck.addEventListener("touchcancel", () => { touchStart = null; }, {capture: true, passive: true});
    deck.addEventListener("click", event => {
        if (performance.now() >= suppressClickUntil) return;
        suppressClickUntil = 0;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
    media.addEventListener("change", updateLayout);
    updateLayout();
})();
