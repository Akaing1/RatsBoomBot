(() => {
    const dialog = document.querySelector("[data-raid-browser]");
    const opener = document.querySelector("[data-raid-browser-open]");
    if (!dialog || !opener) return;
    const search = dialog.querySelector("[data-raid-browser-search]");
    const filtersToggle = dialog.querySelector("[data-raid-filters-toggle]");
    const mobileLayout = () => window.innerWidth <= 750;
    let filtersOpen = false;
    let pendingFilters = false;
    function positionFilters() {
        if (filtersOpen && filtersToggle) dialog.style.setProperty("--raid-filter-top",
            `${filtersToggle.getBoundingClientRect().bottom - dialog.getBoundingClientRect().top + 8}px`);
    }
    function setFiltersOpen(open) {
        filtersOpen = open;
        dialog.classList.toggle("is-filters-open", open);
        filtersToggle?.setAttribute("aria-expanded", String(open));
        if (open) positionFilters();
        else { closeCategoryPicker(); closeTagDropdown(); }
    }
    function updateFilters() {
        if (mobileLayout()) { pendingFilters = true; return; }
        pendingFilters = false;
        load();
    }
    filtersToggle?.addEventListener("click", () => setFiltersOpen(!filtersOpen));
    window.addEventListener("resize", () => {
        schedulePreviewLayout();
        applyView();
        applySize();
        scheduleRender();
        if (mobileLayout()) { positionFilters(); return; }
        setFiltersOpen(false);
        if (pendingFilters && dialog.open) { pendingFilters = false; load(); }
    });
    const input = search.querySelector("input");
    const results = dialog.querySelector("[data-raid-browser-results]");
    const status = dialog.querySelector("[data-raid-browser-status]");
    const channelPreview = document.querySelector("[data-raid-preview]");
    const previewVideo = channelPreview?.querySelector("[data-raid-preview-video]");
    const previewChat = channelPreview?.querySelector("[data-raid-preview-chat]");
    const previewRaid = channelPreview?.querySelector("[data-raid-preview-raid]");
    const previewStatus = channelPreview?.querySelector("[data-raid-preview-status]");
    const previewFavorite = channelPreview?.querySelector("[data-raid-preview-favorite]");
    const favoriteIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m16 3 5 5-3 1-3 5v3l-3-3-7 7-1-1 7-7-3-3h3l5-3z"/></svg>';
    const previewMenu = channelPreview?.querySelector("[data-raid-preview-menu]");
    let previewDetailsController = null;
    let previewSource = null;
    let previewLinkController = null, previewLinkLogin = "";
    let previewChatController = null;
    let previewPlayerController = null;
    const previewMain = channelPreview?.querySelector("[data-raid-preview-main]");
    const previewDetails = channelPreview?.querySelector("[data-raid-preview-details]");
    const previewFooter = channelPreview?.querySelector("[data-raid-preview-footer]");
    let previewLayoutFrame = 0;
    function fitPreviewWidth() {
        previewLayoutFrame = 0;
        if (!channelPreview?.open || mobileLayout() || !previewMain || !previewDetails) return;
        const details = previewDetails.getBoundingClientRect();
        const height = previewMain.clientHeight - (details.bottom - details.top);
        const rect = channelPreview.getBoundingClientRect();
        const chromeWidth = rect.right - rect.left - previewMain.clientWidth;
        if (height <= 0 || previewMain.clientWidth <= 0 || chromeWidth < 0) return;
        const width = Math.min(window.innerWidth - 48, Math.max(Math.ceil(300 * 16 / 9) + chromeWidth, Math.floor(height * 16 / 9 + chromeWidth)));
        channelPreview.style.setProperty("--raid-preview-width", `${width}px`);
    }
    function schedulePreviewLayout() {
        if (!previewLayoutFrame && channelPreview?.open) previewLayoutFrame = requestAnimationFrame(fitPreviewWidth);
    }
    if (channelPreview) {
        const observer = new ResizeObserver(schedulePreviewLayout);
        for (const element of [channelPreview, previewMain, previewDetails, previewFooter]) if (element) observer.observe(element);
    }
    function copyPreviewBadge(source) {
        if (!source) return null;
        const copy = source.cloneNode?.(true) || document.createElement("span");
        if (!source.cloneNode) { copy.className = source.className || ""; copy.textContent = source.textContent; }
        copy.classList.remove("raid-browser-tag-overflowed");
        return copy;
    }
    function refreshPreviewFavorite() {
        if (!previewSource || !previewFavorite) return;
        const pinned = favorites.has(previewSource.channel.id);
        previewFavorite.innerHTML = favoriteIcon;
        previewFavorite.title = pinned ? "Unfavorite" : "Favorite";
        previewFavorite.setAttribute("aria-label", previewFavorite.title);
        previewFavorite.setAttribute("aria-pressed", String(pinned));
    }
    async function loadPreviewFollowers(channel, badge) {
        previewDetailsController?.abort();
        const url = channelPreview.dataset.detailsUrl;
        if (!url) { badge.textContent = "Followers unavailable"; return; }
        const request = new AbortController(); previewDetailsController = request;
        const query = new URL(url, window.location.origin); query.searchParams.set("target_id", channel.id);
        badge.textContent = "Followers…";
        try {
            const response = await fetch(query, {signal: request.signal, cache: "no-store", headers: {Accept: "application/json"}});
            const payload = await response.json();
            if (request.signal.aborted || previewDetailsController !== request || previewSource?.channel.id !== channel.id) return;
            const count = payload.follower_count;
            badge.textContent = response.ok && Number.isInteger(count) && count >= 0
                ? `${count.toLocaleString()} followers` : "Followers unavailable";
        } catch (_) {
            if (!request.signal.aborted && previewDetailsController === request) badge.textContent = "Followers unavailable";
        }
    }
    function openChannelPreview(channel, source, raidButton, sourceCard) {
        if (!channelPreview || !dialog.open || !/^[A-Za-z0-9_]{1,25}$/.test(channel.login)) return;
        previewLinkController?.abort(); previewLinkController = null; previewLinkLogin = "";
        const hash = `${raidBrowserHash}?channel=${channel.login.toLowerCase()}`;
        if (window.location.hash !== hash) window.history.pushState(null, "", hash);
        previewSource = {source, raidButton, channel, sourceCard, isSelf: Boolean(channel.is_self)};
        const display = channel.display_name || channel.login;
        const identity = channelPreview.querySelector("[data-raid-preview-identity]");
        identity.replaceChildren();
        for (const selector of [".raid-browser-language", ".raid-browser-follow-badge"]) {
            const badge = copyPreviewBadge(sourceCard.querySelector(selector));
            if (badge) identity.append(badge);
        }
        if (/^https:\/\/static-cdn\.jtvnw\.net\//.test(channel.profile_image_url || "")) {
            const avatar = document.createElement("img"); avatar.src = channel.profile_image_url; avatar.alt = "";
            avatar.width = 40; avatar.height = 40; identity.append(avatar);
        }
        const link = document.createElement("a"); link.textContent = display;
        link.href = `https://www.twitch.tv/${encodeURIComponent(channel.login)}`;
        link.target = "_blank"; link.rel = "noopener noreferrer"; link.title = "Open channel"; identity.append(link);
        const verified = copyPreviewBadge(sourceCard.querySelector(".raid-browser-verified"));
        if (verified) identity.append(verified);
        const followers = document.createElement("span"); followers.className = "raid-preview-followers";
        identity.append(followers);
        channelPreview.querySelector("[data-raid-preview-stream-title]").textContent = channel.title || "";
        channelPreview.querySelector("[data-raid-preview-stream-title]").title = channel.title || "";
        channelPreview.querySelector("[data-raid-preview-meta]").textContent = channel.category || "No category";
        channelPreview.querySelector("[data-raid-preview-meta]").title = channelPreview.querySelector("[data-raid-preview-meta]").textContent;
        channelPreview.querySelector("[data-raid-preview-description]").textContent = channel.description || "";
        channelPreview.querySelector("[data-raid-preview-description]").title = channel.description || "";
        const badges = channelPreview.querySelector("[data-raid-preview-badges]"); badges.replaceChildren();
        const events = channelPreview.querySelector("[data-raid-preview-events]"); events.replaceChildren();
        for (const label of channel.events || []) {
            const badge = document.createElement("span"); badge.textContent = label; badge.title = label; events.append(badge);
        }
        const viewers = document.createElement("span"); viewers.className = "raid-preview-viewers";
        viewers.textContent = `${Math.max(0, Number(channel.viewers) || 0).toLocaleString()} viewers`; badges.append(viewers);
        const startedAt = Date.parse(channel.started_at);
        if (Number.isFinite(startedAt)) {
            const timer = document.createElement("span"); timer.className = "raid-preview-live-time";
            timer.dataset.startedAt = String(startedAt); badges.append(timer);
        }
        const teams = channelPreview.querySelector("[data-raid-preview-teams]"); teams.replaceChildren();
        for (const label of channel.teams || []) {
            const badge = document.createElement("span"); badge.textContent = label; badge.title = label; teams.append(badge);
        }
        const tags = channelPreview.querySelector("[data-raid-preview-tags]"); tags.replaceChildren();
        for (const tag of sourceCard.querySelector(".raid-browser-tags")?.children || []) tags.append(copyPreviewBadge(tag));
        tags.title = [...tags.children].map(tag => tag.textContent).join(" · ");
        previewPlayerController?.destroy(); previewPlayerController = null;
        previewVideo.replaceChildren();
        if (!window.createRaidPreviewPlayer) {
            const playerUrl = new URL("https://player.twitch.tv/");
            playerUrl.search = new URLSearchParams({channel: channel.login,
                parent: new URL(window.location.origin).hostname, autoplay: "true", muted: "true"}).toString();
            const player = document.createElement("iframe"); player.src = playerUrl.href;
            player.title = `${display} stream`; player.allow = "autoplay; fullscreen";
            previewVideo.append(player);
        }
        previewChatController?.destroy();
        previewChatController = window.createRaidPreviewChat?.(previewChat, channel, dialog.dataset.csrfToken || "");
        previewRaid.disabled = startingRaid || Boolean(channel.is_self);
        previewStatus.textContent = "";
        previewStatus.classList.remove("error");
        if (previewMenu) previewMenu.open = false;
        refreshPreviewFavorite();
        if (!channelPreview.open) channelPreview.showModal();
        fitPreviewWidth();
        if (window.createRaidPreviewPlayer) {
            const blockedMessage = "Autoplay was blocked. Press Play in the video.";
            previewPlayerController = window.createRaidPreviewPlayer(previewVideo, channel.login, message => {
                if (!channelPreview.open) return;
                if (!previewStatus.textContent || previewStatus.textContent === blockedMessage) previewStatus.textContent = message;
            });
        }
        updateLiveTimes();
        loadPreviewFollowers(channel, followers);
    }
    channelPreview?.querySelector("[data-raid-preview-back]").addEventListener("click", () => channelPreview.close());
    channelPreview?.querySelector("[data-raid-preview-close]").addEventListener("click", () => channelPreview.close());
    previewRaid?.addEventListener("click", () => previewSource?.raidButton.click());
    previewFavorite?.addEventListener("click", () => {
        previewSource?.sourceCard.querySelector(".raid-browser-pin")?.click(); refreshPreviewFavorite();
    });
    channelPreview?.querySelector("[data-raid-preview-block]").addEventListener("click", () => {
        const id = previewSource?.channel.id;
        if (previewMenu) previewMenu.open = false;
        if (id) blacklistChannel(id);
    });
    channelPreview?.addEventListener("pointerdown", event => {
        recordBackdropPress(channelPreview, event);
        if (previewMenu && !previewMenu.contains(event.target)) previewMenu.open = false;
    });
    channelPreview?.addEventListener("click", event => dismissOnBackdropClick(channelPreview, event));
    channelPreview?.addEventListener("pointercancel", () => backdropPresses.delete(channelPreview));
    channelPreview?.addEventListener("close", () => {
        if (dialog.open && raidBrowserRoute()?.channel === previewSource?.channel.login.toLowerCase()) {
            window.history.replaceState(null, "", raidBrowserHash);
        }
        backdropPresses.delete(channelPreview);
        previewDetailsController?.abort(); previewDetailsController = null;
        cancelAnimationFrame(previewLayoutFrame); previewLayoutFrame = 0;
        if (previewMenu) previewMenu.open = false;
        previewChatController?.destroy(); previewChatController = null;
        previewPlayerController?.destroy(); previewPlayerController = null;
        // Removing the player stops playback; the chat controller closes its stream.
        previewVideo.replaceChildren(); previewChat.replaceChildren();
        if (dialog.open) (previewSource?.source.isConnected ? previewSource.source : results).focus({preventScroll: true});
        previewSource = null;
    });
    let showMatchValues = false;
    window.dashboardRaidDebug = {
        matches(enabled = !showMatchValues) {
            showMatchValues = Boolean(enabled);
            dialog.classList.toggle("show-match-values", showMatchValues);
            return showMatchValues;
        },
    };
    const tagOptions = dialog.querySelector("#raid-browser-tag-options");
    const tagSearch = search.querySelector("[data-raid-tag-search]");
    const tagLimit = search.querySelector("[data-raid-tag-limit]");
    const tagMatchToggle = search.querySelector("[data-raid-tag-match]");
    function syncTagMatch() {
        const all = search.querySelector('[name="tag_match"]')?.value !== "any";
        if (!tagMatchToggle) return;
        tagMatchToggle.querySelector(".queue-state-current").textContent = all ? "All" : "Any";
        tagMatchToggle.querySelector(".queue-state-alternate").textContent = all ? "Any" : "All";
        tagMatchToggle.classList.toggle("live", all);
        tagMatchToggle.setAttribute("aria-pressed", String(all));
    }
    syncTagMatch();
    tagMatchToggle?.addEventListener("click", () => {
        const field = search.querySelector('[name="tag_match"]');
        field.value = field.value === "all" ? "any" : "all";
        syncTagMatch();
        if (search.querySelector('[name="tags"]')?.value.trim()) updateFilters();
    });
    const selectedTags = dialog.querySelector("[data-raid-selected-tags]");
    const categorySearch = search.querySelector("[data-raid-category-search]");
    const categoryOptions = dialog.querySelector("#raid-browser-category-options");
    const backdropPresses = new WeakMap();
    function isOutsidePopup(popup, event) {
        if (event.target !== popup) return false;
        const rect = popup.getBoundingClientRect();
        return event.clientX < rect.left || event.clientX > rect.right
            || event.clientY < rect.top || event.clientY > rect.bottom;
    }
    function recordBackdropPress(popup, event) {
        backdropPresses.set(popup, event.isPrimary !== false
            && (event.button === undefined || event.button === 0) && isOutsidePopup(popup, event));
    }
    function dismissOnBackdropClick(popup, event) {
        const pressedOutside = backdropPresses.get(popup);
        backdropPresses.delete(popup);
        if (pressedOutside && isOutsidePopup(popup, event)) popup.close();
    }
    let categoryTimer = null, categoryController = null;
    let categoryKeyboardFocus = false;
    function focusCategoryInput() {
        categoryKeyboardFocus = true;
        categorySearch?.focus({preventScroll: true});
        categoryKeyboardFocus = false;
    }
    function closeCategoryPicker() {
        clearTimeout(categoryTimer);
        categoryController?.abort();
        categoryOptions?.hidePopover?.();
        if (categoryOptions) categoryOptions.hidden = true;
        categorySearch?.setAttribute("aria-expanded", "false");
    }
    async function searchCategories() {
        if (!categorySearch || !categoryOptions || !dialog.open) return;
        categoryController?.abort();
        const request = new AbortController(); categoryController = request;
        const query = categorySearch.value.trim();
        const url = new URL("/channel/api/games", window.location.origin);
        url.searchParams.set("query", query);
        url.searchParams.set("current_first", "true");
        categoryOptions.replaceChildren();
        categoryOptions.hidden = false;
        categorySearch.setAttribute("aria-expanded", "true");
        const rect = categorySearch.getBoundingClientRect();
        categoryOptions.style.left = `${rect.left}px`;
        categoryOptions.style.width = `${rect.right - rect.left}px`;
        categoryOptions.style.top = `${rect.bottom + 4}px`;
        categoryOptions.style.maxHeight = `${Math.max(60, Math.min(280, (window.innerHeight || 768) - rect.bottom - 12))}px`;
        categoryOptions.showPopover?.();
        const note = document.createElement("span"); note.textContent = "Loading categories..."; categoryOptions.append(note);
        function render(games, more = []) {
            categoryOptions.replaceChildren(); categoryOptions.scrollTop = 0;
            for (const game of games) {
                const button = document.createElement("button"); button.type = "button";
                button.setAttribute("data-hover-pointer-only", "");
                if (/^https:\/\/static-cdn\.jtvnw\.net\//.test(game.box_art_url || "")) {
                    const image = document.createElement("img"); image.alt = ""; image.src = game.box_art_url; button.append(image);
                }
                const name = document.createElement("span"); name.textContent = game.name; button.append(name);
                button.addEventListener("mousedown", event => event.preventDefault());
                button.addEventListener("click", () => {
                    search.querySelector('[name="category_id"]').value = String(game.id); categorySearch.value = game.name;
                    closeCategoryPicker(); updateFilters();
                });
                categoryOptions.append(button);
            }
            if (more.length) {
                const button = document.createElement("button"); button.type = "button"; button.textContent = "More results";
                button.setAttribute("data-hover-pointer-only", "");
                button.addEventListener("mousedown", event => event.preventDefault());
                button.addEventListener("click", () => render([...games, ...more])); categoryOptions.append(button);
            }
        }
        try {
            const response = await fetch(url, {signal: request.signal, cache: "no-store", headers: {Accept: "application/json"}});
            const payload = await response.json();
            if (request.signal.aborted || !dialog.open || categorySearch.value.trim() !== query) return;
            if (!response.ok) throw new Error(payload.detail || "Categories could not be loaded.");
            render(payload.games || [], payload.more_games || []);
        } catch (error) {
            if (!request.signal.aborted) { categoryOptions.replaceChildren(); note.textContent = error.message; categoryOptions.append(note); }
        }
    }
    categorySearch?.addEventListener("focus", () => { if (!categoryKeyboardFocus) searchCategories(); });
    categorySearch?.addEventListener("blur", event => { if (!categoryOptions?.contains(event.relatedTarget)) closeCategoryPicker(); });
    categorySearch?.addEventListener("keydown", event => {
        if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); closeCategoryPicker(); }
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const options = [...categoryOptions?.children || []].filter(option => option.tagName.toLowerCase() === "button");
            const option = event.key === "ArrowUp" ? options.at(-1) : options[0];
            option?.focus(); option?.scrollIntoView?.({block: "nearest"});
        }
        if (event.key === "Enter") {
            event.preventDefault();
            if (categoryOptions && !categoryOptions.hidden) categoryOptions.querySelector("button")?.click();
        }
    });
    categoryOptions?.addEventListener("keydown", event => {
        const options = [...categoryOptions.children].filter(option => option.tagName.toLowerCase() === "button");
        const index = options.indexOf(event.target);
        if (index < 0) return;
        if (event.key === "Escape") {
            event.preventDefault(); event.stopPropagation();
            focusCategoryInput(); closeCategoryPicker(); return;
        }
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault(); event.target.click();
            if (categoryOptions.hidden) focusCategoryInput();
            else categoryOptions.children[index]?.focus();
            return;
        }
        if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        if (event.key === "ArrowUp" && index === 0) { focusCategoryInput(); return; }
        const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
            : Math.max(0, Math.min(options.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)));
        options[next].focus(); options[next].scrollIntoView?.({block: "nearest"});
    });
    categoryOptions?.addEventListener("focusout", event => {
        if (event.relatedTarget !== categorySearch && !categoryOptions.contains(event.relatedTarget)) closeCategoryPicker();
    });
    const availableTags = new Map([["vtuber", "VTuber"]]);
    let channelTags = new Set();
    let tagDropdownOpen = false;
    function closeTagDropdown() {
        tagDropdownOpen = false;
        tagOptions?.hidePopover?.();
        if (tagOptions) tagOptions.hidden = true;
        tagSearch?.setAttribute("aria-expanded", "false");
    }
    function addTypedTag() {
        const tag = (tagSearch?.value || "").trim();
        if (!tag || Array.from(tag).length > 25) return;
        const field = search.querySelector('[name="tags"]');
        const selected = field.value.split(",").map(value => value.trim()).filter(Boolean);
        if (!selected.some(value => value.toLowerCase() === tag.toLowerCase())) {
            if (selected.length >= 10 || [...selected, tag].join(", ").length > 250) return;
            field.value = [...selected, tag].join(", ");
            availableTags.set(tag.toLowerCase(), tag);
        }
        tagSearch.value = "";
        renderTags();
        updateFilters();
    }
    function renderTags() {
        if (tagLimit) tagLimit.hidden = (tagSearch?.value || "").length < 25;
        if (!tagOptions) return;
        const field = search.querySelector('[name="tags"]');
        const selected = new Set(field.value.split(",").map(tag => tag.trim().toLowerCase()).filter(Boolean));
        tagOptions.replaceChildren();
        selectedTags?.replaceChildren();
        const query = (tagSearch?.value || "").trim().toLowerCase();
        const tags = [...availableTags.values()];
        for (const tag of field.value.split(",").map(value => value.trim()).filter(Boolean)) {
            if (!availableTags.has(tag.toLowerCase())) tags.push(tag);
        }
        tags.sort((a, b) => (a.toLowerCase() !== "vtuber") - (b.toLowerCase() !== "vtuber")
            || Number(channelTags.has(b.toLowerCase())) - Number(channelTags.has(a.toLowerCase()))
            || a.localeCompare(b)).forEach(tag => {
            const added = selected.has(tag.toLowerCase());
            if (!added && tag.toLowerCase() !== "vtuber" && (query ? !tag.toLowerCase().includes(query) : !channelTags.has(tag.toLowerCase()))) return;
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = added ? `${tag} ×` : tag;
            button.setAttribute("aria-label", `${added ? "Remove" : "Add"} ${tag}`);
            if (!added) button.setAttribute("data-hover-pointer-only", "");
            if (!added) button.addEventListener("mousedown", event => event.preventDefault());
            button.addEventListener("click", () => {
                const values = field.value.split(",").map(value => value.trim()).filter(Boolean);
                const next = selected.has(tag.toLowerCase()) ? values.filter(value => value.toLowerCase() !== tag.toLowerCase()) : [...values, tag];
                if (next.join(", ").length > 250 || next.length > 10) return;
                field.value = next.join(", ");
                if (tagSearch && !added) tagSearch.value = "";
                renderTags();
                updateFilters();
            });
            (added ? selectedTags : tagOptions)?.append(button);
        });
        const visible = tagDropdownOpen && tagOptions.children.length > 0;
        tagOptions.hidden = !visible;
        tagSearch?.setAttribute("aria-expanded", String(visible));
        if (visible && tagSearch) {
            const rect = tagSearch.getBoundingClientRect();
            const viewportHeight = window.innerHeight || 768;
            const below = viewportHeight - rect.bottom - 12;
            const above = rect.top - 12;
            const upward = below < 120 && above > below;
            const height = Math.min(240, Math.max(40, upward ? above : below));
            tagOptions.style.width = `${Math.min(rect.right - rect.left, (window.innerWidth || 1024) - 16)}px`;
            tagOptions.style.left = `${Math.max(8, Math.min(rect.left, (window.innerWidth || 1024) - (rect.right - rect.left) - 8))}px`;
            tagOptions.style.maxHeight = `${height}px`;
            tagOptions.style.top = upward ? "auto" : `${rect.bottom + 4}px`;
            tagOptions.style.bottom = upward ? `${viewportHeight - rect.top + 4}px` : "auto";
            tagOptions.showPopover?.();
        } else tagOptions.hidePopover?.();
    }
    tagSearch?.addEventListener("focus", () => { tagDropdownOpen = true; renderTags(); });
    tagSearch?.addEventListener("blur", event => {
        if (!tagOptions?.contains(event.relatedTarget)) closeTagDropdown();
    });
    tagOptions?.addEventListener("focusout", event => {
        if (event.relatedTarget !== tagSearch && !tagOptions.contains(event.relatedTarget)) closeTagDropdown();
    });
    tagSearch?.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.isComposing) { event.preventDefault(); addTypedTag(); }
        if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); closeTagDropdown(); }
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault(); tagDropdownOpen = true; renderTags();
            const options = [...tagOptions?.children || []];
            const option = event.key === "ArrowUp" ? options.at(-1) : options[0];
            option?.focus(); option?.scrollIntoView?.({block: "nearest"});
        }
    });
    tagOptions?.addEventListener("keydown", event => {
        const options = [...tagOptions.children];
        const index = options.indexOf(event.target);
        if (index < 0) return;
        if (event.key === "Escape") {
            event.preventDefault(); event.stopPropagation();
            tagSearch?.focus(); closeTagDropdown(); return;
        }
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault(); event.target.click(); tagSearch?.focus(); return;
        }
        if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        if (event.key === "ArrowUp" && index === 0) { tagSearch?.focus(); return; }
        const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
            : Math.max(0, Math.min(options.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)));
        options[next].focus(); options[next].scrollIntoView?.({block: "nearest"});
    });
    tagOptions?.addEventListener("toggle", event => {
        if (event.newState === "closed") { tagDropdownOpen = false; tagOptions.hidden = true; tagSearch?.setAttribute("aria-expanded", "false"); }
    });
    // A focus-opened auto popover can be light-dismissed by the same click's
    // pointerup. Handle outside presses ourselves, before focus opens a picker.
    dialog.addEventListener("pointerdown", event => {
        recordBackdropPress(dialog, event);
        if (filtersOpen && !search.contains(event.target) && !filtersToggle?.contains(event.target)) setFiltersOpen(false);
        if (event.target !== categorySearch && !categoryOptions?.contains(event.target)) closeCategoryPicker();
        if (event.target !== tagSearch && !tagOptions?.contains(event.target)) closeTagDropdown();
    });
    dialog.addEventListener("keydown", event => {
        if (event.key !== "Escape") return;
        if (categoryOptions?.hidden !== false && tagOptions?.hidden !== false) {
            if (!filtersOpen) return;
            event.preventDefault(); event.stopPropagation();
            setFiltersOpen(false); filtersToggle?.focus({preventScroll: true}); return;
        }
        event.preventDefault();
        event.stopPropagation();
        closeCategoryPicker();
        closeTagDropdown();
    });
    const collectionButtons = dialog.querySelectorAll("[data-raid-browser-tab]");
    const manager = document.querySelector("[data-raid-lists]");
    const listTabs = manager ? [...manager.querySelectorAll("[data-raid-list-tab]")] : [];
    function selectListTab(button) {
        for (const tab of listTabs) {
            const active = tab === button;
            tab.setAttribute("aria-selected", String(active));
            tab.setAttribute("tabindex", active ? "0" : "-1");
            const panel = manager.querySelector(`[data-raid-list-panel="${tab.dataset.raidListTab}"]`);
            if (panel) panel.hidden = !active;
        }
    }
    listTabs.forEach((button, index) => {
        button.addEventListener("click", () => selectListTab(button));
        button.addEventListener("keydown", event => {
            let next;
            if (event.key === "ArrowRight") next = (index + 1) % listTabs.length;
            if (event.key === "ArrowLeft") next = (index + listTabs.length - 1) % listTabs.length;
            if (event.key === "Home") next = 0;
            if (event.key === "End") next = listTabs.length - 1;
            if (next === undefined) return;
            event.preventDefault(); selectListTab(listTabs[next]); listTabs[next].focus();
        });
    });
    const manageButton = dialog.querySelector("[data-raid-lists-open]");
    const identities = new Map();
    let activeTab = "browse";
    const collectionTabs = dialog.querySelector("[data-raid-collection-tabs]");
    const collectionSelect = dialog.querySelector("[data-raid-collection-select]");
    let collectionOptions = "";
    function syncCollectionSelect() {
        if (!collectionSelect) return;
        const visible = [...collectionButtons].filter(button => !button.hidden);
        const signature = visible.map(button => button.dataset.raidBrowserTab).join(",");
        if (signature !== collectionOptions) {
            collectionOptions = signature;
            collectionSelect.replaceChildren(...visible.map(button => {
                const option = document.createElement("option");
                option.value = button.dataset.raidBrowserTab;
                option.textContent = button.textContent;
                return option;
            }));
        }
        collectionSelect.value = activeTab;
    }
    collectionSelect?.addEventListener("change", () => {
        const selected = [...collectionButtons].find(button => button.dataset.raidBrowserTab === collectionSelect.value && !button.hidden);
        if (selected) selected.click();
        else syncCollectionSelect();
    });
    function syncTabIndicator() {
        syncCollectionSelect();
        if (!collectionTabs || !dialog.open) return;
        const selected = [...collectionButtons].find(button => button.dataset.raidBrowserTab === activeTab && !button.hidden);
        if (!selected) return;
        const rect = selected.getBoundingClientRect();
        const parent = collectionTabs.getBoundingClientRect();
        collectionTabs.style.setProperty("--raid-tab-x", `${rect.left - parent.left}px`);
        collectionTabs.style.setProperty("--raid-tab-y", `${rect.top - parent.top}px`);
        collectionTabs.style.setProperty("--raid-tab-width", `${rect.right - rect.left}px`);
        collectionTabs.style.setProperty("--raid-tab-height", `${rect.bottom - rect.top + 1}px`);
        collectionTabs.classList.add("has-tab-indicator");
    }
    if (collectionTabs) {
        const tabObserver = new ResizeObserver(syncTabIndicator);
        tabObserver.observe(collectionTabs);
        collectionButtons.forEach(button => tabObserver.observe(button));
    }
    let startingRaid = false;
    function disableRaidButtons(disabled) {
        startingRaid = disabled;
        if (previewRaid) previewRaid.disabled = disabled || Boolean(previewSource?.isSelf);
        for (const card of rendered.values()) {
            const button = card.querySelector(".raid-browser-start-raid");
            if (button) button.disabled = disabled || button.dataset.isSelf === "true";
        }
    }
    let managerController = null;
    const spacer = document.createElement("div");
    spacer.className = "raid-browser-spacer";
    const windowGrid = document.createElement("div");
    windowGrid.className = "raid-browser-window";
    spacer.append(windowGrid);
    results.append(spacer);
    let controller = null;
    let searchTimer = null;
    let liveTimer = null;
    function updateLiveTimes() {
        const timers = [...rendered.values()].map(card => card.querySelector(".raid-browser-live-time"));
        if (channelPreview?.open) timers.push(channelPreview.querySelector(".raid-preview-live-time"));
        for (const timer of timers) {
            if (!timer) continue;
            const seconds = Math.max(0, Math.floor((Date.now() - Number(timer.dataset.startedAt)) / 1000));
            const text = `${Math.floor(seconds / 3600)}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
            if (timer.textContent === text) continue;
            timer.textContent = text;
            timer.title = text;
            timer.setAttribute("aria-label", `Live for ${text}`);
        }
    }
    let cursor = "";
    let currentQuery = "";
    let currentFilters = {};
    let rankedFavorites = new Set();
    const filterNames = ["sort", "category_id", "tags", "tag_match", "following", "mutual", "language", "event"];
    function readFilters() {
        const values = {};
        for (const name of filterNames) {
            if (name === "tag_match" && !search.querySelector('[name="tags"]')?.value.trim()) continue;
            if (activeTab === "favorites" && ["following", "mutual"].includes(name)) continue;
            const field = search.querySelector(`[name="${name}"]`);
            if (!field) continue;
            const value = field.type === "checkbox" ? (field.checked ? "true" : "") : field.value.trim();
            if (value) values[name] = value;
        }
        if (activeTab !== "favorites") values.recommended = "true";
        if (activeTab === "team") values.same_team = "true";
        if (activeTab === "developer") values.developer_only = "true";
        return values;
    }
    const seen = new Set();
    const knownLiveChannels = new Set();
    const favoriteKey = `ratsboombot:raid-favorites:${dialog.dataset.channelId}`;
    const blacklistKey = `ratsboombot:raid-blacklist:${dialog.dataset.channelId}`;
    let blacklist = new Set();
    try {
        const saved = JSON.parse(window.localStorage.getItem(blacklistKey) || "[]");
        if (Array.isArray(saved)) blacklist = new Set(saved.filter(id => typeof id === "string" && /^\d{1,25}$/.test(id)).slice(0, 100));
    } catch (_) {}
    const viewKey = `ratsboombot:raid-browser-view:${dialog.dataset.channelId}`;
    const sizeKey = `ratsboombot:raid-browser-size:${dialog.dataset.channelId}`;
    const sizeSlider = dialog.querySelector("[data-raid-browser-size]");
    const sizeNames = ["Small", "Medium", "Large"];
    let preferredSize = 1, size = 1;
    try {
        const saved = window.localStorage.getItem(sizeKey);
        if (["0", "1", "2"].includes(saved)) preferredSize = Number(saved);
    } catch (_) {}
    const viewButtons = dialog.querySelectorAll("[data-raid-browser-view]");
    let preferredView = "cards", view = "cards";
    try { if (window.localStorage.getItem(viewKey) === "list") preferredView = "list"; } catch (_) {}
    let favorites = new Set();
    try {
        const saved = JSON.parse(window.localStorage.getItem(favoriteKey) || "[]");
        if (Array.isArray(saved)) favorites = new Set(saved.filter(id => typeof id === "string" && /^\d{1,25}$/.test(id)).slice(0, 100));
    } catch (_) { /* Keep browsing usable if storage is blocked or malformed. */ }
    const channels = [];
    const rendered = new Map();
    let tabSwapWaiting = false;
    let tabCardOrigins = null;
    const cardMoves = new Set();
    function cancelCardMoves() {
        for (const animation of cardMoves) animation.cancel();
        cardMoves.clear();
        tabCardOrigins = null;
    }
    function captureTabCards() {
        const positions = new Map();
        if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return positions;
        const viewport = results.getBoundingClientRect();
        for (const card of rendered.values()) {
            const rect = card.getBoundingClientRect();
            if (rect.bottom > viewport.top && rect.top < viewport.bottom
                && rect.right > viewport.left && rect.left < viewport.right)
                positions.set(card.dataset.channelId, rect);
        }
        return positions;
    }
    function animateSharedCards() {
        const origins = tabCardOrigins;
        tabCardOrigins = null;
        if (!origins || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
        for (const card of rendered.values()) {
            const previous = origins.get(card.dataset.channelId);
            if (!previous || !card.animate) continue;
            const rect = card.getBoundingClientRect();
            const x = previous.left - rect.left, y = previous.top - rect.top;
            if (Math.abs(x) < 1 && Math.abs(y) < 1) continue;
            const animation = card.animate([
                {transform: `translate(${x}px, ${y}px)`, zIndex: 2},
                {transform: "translate(0px, 0px)", zIndex: 2},
            ], {duration: 260, easing: "cubic-bezier(.22,1,.36,1)"});
            cardMoves.add(animation);
            animation.finished.then(() => cardMoves.delete(animation), () => cardMoves.delete(animation));
        }
    }
    function clearLoadedCards() {
        seen.clear();
        channels.length = 0;
        rendered.clear();
        windowGrid.replaceChildren();
        spacer.style.height = "0px";
        results.scrollTop = 0;
    }
    let loading = false;
    let loadError = false;
    let renderFrame = 0;
    let columns = 1;
    let rowStride = 1;
    let totalHeight = 0;
    function applySize() {
        size = mobileLayout() ? 2 : preferredSize;
        dialog.dataset.resultSize = String(size);
        if (sizeSlider) {
            sizeSlider.value = String(size);
            sizeSlider.setAttribute("aria-valuetext", sizeNames[size]);
        }
    }
    sizeSlider?.addEventListener("input", () => {
        if (mobileLayout()) return;
        preferredSize = Math.max(0, Math.min(2, Math.round(Number(sizeSlider.value) || 0)));
        applySize();
        try { window.localStorage.setItem(sizeKey, String(size)); } catch (_) {}
        scheduleRender();
    });
    applySize();
    function saveLists() {
        try {
            window.localStorage.setItem(favoriteKey, JSON.stringify([...favorites]));
            window.localStorage.setItem(blacklistKey, JSON.stringify([...blacklist]));
        } catch (_) { showStatus("Lists updated for this visit, but browser storage could not save them.", true); }
        const hasLiveFavorite = [...favorites].some(id => knownLiveChannels.has(id) && !blacklist.has(id));
        collectionButtons.forEach(button => {
            if (button.dataset.raidBrowserTab === "favorites") button.hidden = !hasLiveFavorite;
        });
        if (!hasLiveFavorite && activeTab === "favorites" && dialog.open) {
            collectionButtons.forEach(button => { if (button.dataset.raidBrowserTab === "browse") button.click(); });
        }
        syncCollectionSelect();
    }
    function blacklistChannel(id) {
        if (favorites.has(id) && !window.confirm(`Stop recommending ${channelLabel(id)} and remove them from favorites?`)) return false;
        if (!blacklist.has(id) && blacklist.size >= 100) {
            showStatus("You can block up to 100 recommended channels.", true); return false;
        }
        favorites.delete(id); blacklist.add(id);
        const index = channels.findIndex(channel => channel.id === id);
        if (index !== -1) channels.splice(index, 1);
        saveLists();
        if (channelPreview?.open && previewSource?.channel.id === id) channelPreview.close();
        results.scrollTop = Math.min(results.scrollTop, Math.max(0, totalHeight - rowStride - results.clientHeight));
        renderWindow();
        showStatus(`${channelLabel(id)} won’t be recommended. You can restore them in Manage lists.`);
        return true;
    }
    function channelLabel(id) {
        const channel = identities.get(id);
        if (!channel) return "Unavailable Twitch channel";
        const display = channel.display_name || channel.login;
        return channel.login && display.toLowerCase() !== channel.login.toLowerCase()
            ? `${display} (${channel.login})` : display;
    }
    function confirmUnfavorite(id) {
        return window.confirm(`Remove ${channelLabel(id)} from your favorites?`);
    }
    function renderManager() {
        if (!manager) return;
        for (const [selector, list, label] of [["[data-raid-favorite-list]", favorites, "Remove favorite"],
            ["[data-raid-blocked-list]", blacklist, "Allow recommendations"]]) {
            const container = manager.querySelector(selector);
            container.replaceChildren();
            if (!list.size) { container.textContent = "No channels saved."; continue; }
            container.textContent = "";
            for (const id of list) {
                const row = document.createElement("div");
                row.className = "raid-lists-row";
                const name = document.createElement("span");
                name.textContent = channelLabel(id);
                const button = document.createElement("button");
                button.type = "button"; button.className = "button secondary"; button.textContent = label;
                button.setAttribute("aria-label", `${label}: ${channelLabel(id)}`);
                button.addEventListener("click", () => {
                    if (list === favorites && !confirmUnfavorite(id)) return;
                    list.delete(id); saveLists(); renderManager();
                    if (dialog.open && list !== favorites) load();
                });
                row.append(name, button); container.append(row);
            }
        }
    }
    manageButton?.addEventListener("click", async () => {
        managerController?.abort();
        const request = new AbortController(); managerController = request;
        manager.showModal(); renderManager();
        const managerStatus = manager.querySelector("[data-raid-lists-status]");
        managerStatus.textContent = "Loading saved channel names...";
        const url = new URL(`${dialog.dataset.browserUrl}/lists`, window.location.origin);
        url.searchParams.set("ids", [...new Set([...favorites, ...blacklist])].join(","));
        try {
            const response = await fetch(url, {signal: request.signal, cache: "no-store"});
            const payload = await response.json();
            if (!manager.open || request.signal.aborted) return;
            if (!response.ok) throw new Error(payload.detail || "Saved channels could not be loaded.");
            for (const channel of payload.channels || []) identities.set(channel.id, channel);
            renderManager(); managerStatus.textContent = "";
        } catch (error) {
            if (!request.signal.aborted && manager.open) managerStatus.textContent = error.message;
        }
    });
    manager?.querySelector("[data-raid-lists-close]").addEventListener("click", () => manager.close());
    manager?.addEventListener("pointerdown", event => recordBackdropPress(manager, event));
    manager?.addEventListener("pointercancel", () => backdropPresses.delete(manager));
    manager?.addEventListener("click", event => dismissOnBackdropClick(manager, event));
    manager?.addEventListener("close", () => { backdropPresses.delete(manager); managerController?.abort(); manageButton?.focus({preventScroll: true}); });
    collectionButtons.forEach(button => button.addEventListener("click", () => {
        const origins = activeTab === button.dataset.raidBrowserTab ? null : captureTabCards();
        activeTab = button.dataset.raidBrowserTab;
        collectionButtons.forEach(item => item.setAttribute("aria-pressed", String(item === button)));
        syncTabIndicator();
        for (const name of ["following", "mutual"]) {
            const field = search.querySelector(`[name="${name}"]`);
            if (field) field.disabled = activeTab === "favorites";
        }
        load(false, origins);
    }));
    function applyView() {
        view = mobileLayout() ? "cards" : preferredView;
        dialog.classList.toggle("is-list-view", view === "list");
        viewButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.raidBrowserView === view)));
    }
    viewButtons.forEach(button => button.addEventListener("click", () => {
        if (mobileLayout()) return;
        preferredView = button.dataset.raidBrowserView;
        applyView();
        try { window.localStorage.setItem(viewKey, view); } catch (_) {}
        scheduleRender();
    }));
    applyView();
    function sortChannels() {
        channels.sort((a, b) => {
            const favoriteOrder = Number(rankedFavorites.has(b.id)) - Number(rankedFavorites.has(a.id));
            if (favoriteOrder) return favoriteOrder;
            const devOrder = Number(Boolean(b.dev_priority)) - Number(Boolean(a.dev_priority));
            if (devOrder) return devOrder;
            let order;
            if (currentFilters.sort === "viewers_asc") order = a.viewers - b.viewers;
            else if (currentFilters.sort === "viewers_desc") order = b.viewers - a.viewers;
            else if (currentFilters.sort === "name_asc") order = (a.display_name || a.login).localeCompare(b.display_name || b.login, undefined, {sensitivity: "base"});
            else if (currentFilters.sort === "name_desc") order = (b.display_name || b.login).localeCompare(a.display_name || a.login, undefined, {sensitivity: "base"});
            else if (["uptime_asc", "uptime_desc"].includes(currentFilters.sort)) {
                const first = Date.parse(a.started_at), second = Date.parse(b.started_at);
                if (!Number.isFinite(first) || !Number.isFinite(second)) order = Number(!Number.isFinite(first)) - Number(!Number.isFinite(second));
                else order = currentFilters.sort === "uptime_desc" ? first - second : second - first;
            }
            else order = (currentQuery ? (b.search_score || 0) - (a.search_score || 0) : 0)
                || (b.relevance || 0) - (a.relevance || 0) || b.viewers - a.viewers;
            return order || a.login.localeCompare(b.login);
        });
    }

    function scheduleRender() {
        if (!renderFrame) renderFrame = requestAnimationFrame(renderWindow);
    }
    function renderWindow() {
        renderFrame = 0;
        if (!dialog.open || tabSwapWaiting) return;
        const width = results.clientWidth;
        if (!width) return;
        const previousColumns = columns;
        const previousStride = rowStride;
        const anchor = Math.floor(results.scrollTop / rowStride) * previousColumns;
        const minimumCardWidth = [180, 300, 320][size];
        columns = mobileLayout() || view === "list" ? 1 : Math.max(1, Math.floor((width + 12) / (minimumCardWidth + 12)));
        if (view !== "list" && size === 1) columns = Math.min(4, columns);
        const cardWidth = (width - (columns - 1) * 12) / columns;
        const rowHeight = view === "list" ? [116, 156, 220][size] : Math.ceil((cardWidth - 22) * 9 / 16 + [144, 154, 164][size]);
        rowStride = rowHeight + 12;
        const rows = Math.ceil(channels.length / columns);
        totalHeight = Math.max(0, rows * rowStride - 12);
        spacer.style.height = `${totalHeight}px`;
        if ((previousColumns !== columns || previousStride !== rowStride) && rendered.size) results.scrollTop = Math.floor(anchor / columns) * rowStride;
        const firstRow = Math.max(0, Math.floor(results.scrollTop / rowStride) - 2);
        const lastRow = Math.min(rows, Math.ceil((results.scrollTop + results.clientHeight) / rowStride) + 2);
        const start = Math.min(channels.length, firstRow * columns);
        const end = Math.min(channels.length, lastRow * columns);
        windowGrid.style.top = `${firstRow * rowStride}px`;
        windowGrid.style.gridTemplateColumns = `repeat(${columns},minmax(0,1fr))`;
        windowGrid.style.gridAutoRows = `${rowHeight}px`;
        windowGrid.style.setProperty("--raid-browser-row-height", `${rowHeight}px`);
        for (const [index, card] of rendered) {
            if (index >= start && index < end && card.dataset.channelId === channels[index].id) continue;
            if (card.contains(document.activeElement)) results.focus({preventScroll: true});
            card.remove();
            rendered.delete(index);
        }
        for (let index = start; index < end; index++) {
            let card = rendered.get(index);
            if (!card) {
                card = channelCard(channels[index]);
                card.dataset.channelIndex = String(index);
                card.dataset.channelId = channels[index].id;
                card.setAttribute("role", "listitem");
                rendered.set(index, card);
            }
            card.setAttribute("aria-posinset", String(index + 1));
            card.setAttribute("aria-setsize", cursor ? "-1" : String(channels.length));
            // Leave existing cards in place so scrolling doesn't steal link focus.
            const slot = windowGrid.children[index - start];
            if (slot !== card) windowGrid.insertBefore(card, slot || null);
        }
        for (const card of rendered.values()) {
            const title = card.querySelector(".raid-browser-stream-title");
            const tags = card.querySelector(".raid-browser-tags");
            const titleHeight = view === "list" ? title.clientHeight : [28, 36, 44][size];
            const tagsHeight = view === "list" ? tags.clientHeight : [18, 22, 24][size];
            card.classList.toggle("has-title-overflow", title.scrollHeight > titleHeight + 1);
            const tagsOverflow = tags.scrollHeight > tagsHeight + 1 || tags.scrollWidth > tags.clientWidth + 1;
            card.classList.toggle("has-tags-overflow", tagsOverflow);
            const bounds = tags.getBoundingClientRect();
            const markerWidth = view === "list" && size === 1 ? 22 : [19, 20, 22][size];
            const firstTop = tags.children[0]?.getBoundingClientRect().top;
            const firstBottom = tags.children[0]?.getBoundingClientRect().bottom;
            tags.style.setProperty("--raid-tags-more-height", `${Math.min(tagsHeight, firstBottom - firstTop || tagsHeight)}px`);
            let end = 0;
            let full = false;
            for (const tag of tags.children) {
                const rect = tag.getBoundingClientRect();
                const fits = !full && rect.top <= firstTop + 1
                    && rect.bottom <= firstTop + tagsHeight + 1
                    && rect.right - bounds.left + 5 + markerWidth <= tags.clientWidth;
                const hidden = tagsOverflow && !fits;
                tag.classList.toggle("raid-browser-tag-overflowed", hidden);
                if (hidden) full = true;
                else if (tagsOverflow) end = rect.right - bounds.left + 5;
            }
            tags.style.setProperty("--raid-tags-more-left", `${end}px`);
        }
        updateLiveTimes();
        animateSharedCards();
        if (!loading && !loadError && cursor && input.value.trim() === currentQuery
            && JSON.stringify(readFilters()) === JSON.stringify(currentFilters)
            && totalHeight - results.scrollTop - results.clientHeight < rowStride * 2) load(true);
    }

    function showStatus(message, error = false) {
        status.textContent = message;
        status.classList.toggle("error", error);
        if (channelPreview?.open) {
            previewStatus.textContent = message;
            previewStatus.classList.toggle("error", error);
        }
    }
    function channelCard(channel) {
        const card = document.createElement("article");
        card.className = "raid-browser-channel";
        const pin = document.createElement("button");
        pin.type = "button";
        pin.className = "raid-browser-pin";
        pin.innerHTML = favoriteIcon;
        function refreshPin() {
            const pinned = favorites.has(channel.id);
            card.classList.toggle("is-favorite", pinned);
            pin.setAttribute("aria-pressed", String(pinned));
            const label = `${pinned ? "Unpin" : "Pin"} ${channel.display_name || channel.login} ${pinned ? "from" : "as"} a favorite`;
            pin.setAttribute("aria-label", label);
            pin.title = pinned ? "Unfavorite" : "Favorite";
        }
        refreshPin();
        pin.addEventListener("click", () => {
            if (favorites.has(channel.id)) {
                if (!confirmUnfavorite(channel.id)) return;
                favorites.delete(channel.id);
            }
            else {
                if (favorites.size >= 100) { showStatus("You can pin up to 100 favorite channels.", true); return; }
                favorites.add(channel.id);
                blacklist.delete(channel.id);
            }
            refreshPin();
            saveLists();
        });
        const more = document.createElement("button");
        more.type = "button"; more.className = "raid-browser-more"; more.textContent = "⋮";
        more.setAttribute("aria-label", `More options for ${channel.display_name || channel.login}`);
        more.title = "Options";
        more.setAttribute("aria-haspopup", "menu"); more.setAttribute("aria-expanded", "false");
        const menu = document.createElement("div"); menu.className = "raid-browser-channel-menu";
        menu.setAttribute("popover", "auto"); menu.hidden = true;
        menu.setAttribute("role", "menu");
        const block = document.createElement("button"); block.type = "button"; block.textContent = "Don’t recommend";
        block.setAttribute("role", "menuitem");
        function closeMenu() { menu.hidePopover?.(); menu.hidden = true; more.setAttribute("aria-expanded", "false"); }
        menu.addEventListener("toggle", event => { if (event.newState === "closed") { menu.hidden = true; more.setAttribute("aria-expanded", "false"); } });
        more.addEventListener("click", () => {
            if (!menu.hidden) { closeMenu(); return; }
            menu.hidden = false; menu.showPopover?.();
            const rect = more.getBoundingClientRect();
            menu.style.left = `${Math.max(8, Math.min(rect.right - 200, (window.innerWidth || 1024) - 208))}px`;
            menu.style.top = `${Math.max(8, Math.min(rect.bottom + 4, (window.innerHeight || 768) - 60))}px`;
            more.setAttribute("aria-expanded", "true"); block.focus({preventScroll: true});
        });
        block.addEventListener("click", () => {
            if (blacklistChannel(channel.id)) closeMenu();
        });
        menu.append(block);
        const preview = document.createElement("button");
        preview.type = "button";
        preview.setAttribute("aria-label", `Preview ${channel.display_name || channel.login}`);
        preview.setAttribute("aria-haspopup", "dialog");
        preview.setAttribute("aria-controls", "dashboard-raid-preview");
        preview.className = "raid-browser-thumbnail";
        const viewers = document.createElement("span");
        viewers.className = "raid-browser-viewers";
        viewers.textContent = `${Math.max(0, Number(channel.viewers) || 0).toLocaleString()} viewers`;
        if (/^https:\/\/static-cdn\.jtvnw\.net\//.test(channel.thumbnail_url || "")) {
            const image = document.createElement("img");
            image.alt = "";
            image.loading = "lazy";
            image.width = 320;
            image.height = 180;
            // Lazy auto-sizing lets the browser use the actual card/row width
            // and screen density, including after layout or size changes.
            image.sizes = "auto, 100vw";
            const sources = new Map();
            for (const [url, width] of [[channel.thumbnail_url, 320], [channel.thumbnail_url_medium, 640], [channel.thumbnail_url_large, 1280]]) {
                if (/^https:\/\/static-cdn\.jtvnw\.net\//.test(url || "") && !sources.has(url)) sources.set(url, width);
            }
            image.srcset = [...sources].map(([url, width]) => `${url} ${width}w`).join(", ");
            image.src = channel.thumbnail_url;
            image.addEventListener("error", () => image.remove(), {once: true});
            preview.append(image);
        }
        preview.append(viewers);
        if ((channel.tags || []).some(tag => typeof tag === "string" && tag.trim().toLowerCase() === "vtuber")) {
            const vtuber = document.createElement("span");
            vtuber.className = "raid-browser-vtuber";
            vtuber.textContent = "VT";
            vtuber.title = "VTuber";
            vtuber.setAttribute("aria-label", "VTuber");
            preview.append(vtuber);
        }
        const heading = document.createElement("div");
        heading.className = "raid-browser-channel-heading";
        if (channel.language) {
            const language = document.createElement("span");
            language.className = "raid-browser-language";
            let label = channel.language.toUpperCase();
            try { label = channel.language === "other" ? "Other" : new Intl.DisplayNames(["en"], {type: "language"}).of(channel.language); } catch (_) {}
            language.textContent = channel.language === "other" ? "??" : channel.language.slice(0, 2).toUpperCase();
            language.title = label;
            heading.append(language);
        }
        if (channel.followed || channel.mutual) {
            const following = document.createElement("span");
            following.className = `raid-browser-follow-badge${channel.mutual ? " is-mutual" : ""}`;
            const heart = 'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z';
            following.innerHTML = channel.mutual
                ? `<svg viewBox="0 0 32 24" aria-hidden="true"><path d="${heart}" transform="translate(0 0) scale(.8)"/><path d="${heart}" transform="translate(12 5) scale(.8)"/></svg>`
                : `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${heart}"/></svg>`;
            following.title = channel.mutual ? "Mutual following" : "Following";
            following.setAttribute("role", "img");
            following.setAttribute("aria-label", following.title);
            heading.append(following);
        }
        const name = document.createElement("a");
        name.className = "raid-browser-name";
        name.href = `https://www.twitch.tv/${encodeURIComponent(channel.login)}`;
        name.target = "_blank";
        name.rel = "noopener noreferrer";
        const display = channel.display_name || channel.login;
        name.textContent = display.toLowerCase() === channel.login.toLowerCase()
            ? display : `${display} (${channel.login})`;
        if (/^https:\/\/static-cdn\.jtvnw\.net\//.test(channel.profile_image_url || "")) {
            const avatar = document.createElement("img");
            avatar.className = "raid-browser-avatar";
            avatar.src = channel.profile_image_url;
            avatar.alt = "";
            avatar.width = 20; avatar.height = 20;
            avatar.loading = "lazy";
            avatar.addEventListener("error", () => avatar.remove(), {once: true});
            const label = document.createElement("span"); label.textContent = name.textContent;
            name.textContent = "";
            name.append(avatar, label);
        }
        name.title = display.toLowerCase() === channel.login.toLowerCase() ? display : `${display} (${channel.login})`;
        heading.append(name);
        if (channel.verified === true) {
            const badge = document.createElement("span");
            badge.className = "raid-browser-verified";
            badge.setAttribute("role", "img");
            badge.setAttribute("aria-label", "Verified Twitch Partner");
            badge.title = "Verified";
            badge.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 1 3 3 4-.2.2 4 3 3-3 3-.2 4-4-.2-3 3-3-3-4 .2-.2-4-3-3 3-3 .2-4 4 .2z"/><path d="m7.5 12 3 3 6-6" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
            heading.append(badge);
        }
        const startedAt = Date.parse(channel.started_at);
        const streamActions = document.createElement("div");
        streamActions.className = "raid-browser-stream-actions";
        if (channel.teams?.length) {
            const team = document.createElement("span");
            team.className = "raid-browser-team";
            team.textContent = channel.teams.join(" · ");
            team.title = team.textContent;
            streamActions.append(team);
        }
        if (Number.isFinite(startedAt)) {
            const timer = document.createElement("span");
            timer.className = "raid-browser-live-time";
            timer.dataset.startedAt = String(startedAt);
            preview.append(timer);
        }
        const raid = document.createElement("button");
        raid.type = "button"; raid.className = "raid-browser-start-raid"; raid.textContent = "Raid";
        raid.dataset.isSelf = String(Boolean(channel.is_self));
        raid.disabled = startingRaid || Boolean(channel.is_self);
        raid.title = channel.is_self ? "You cannot raid your own channel" : `Start a Twitch raid to ${channel.display_name || channel.login}`;
        raid.setAttribute("aria-label", raid.title);
        raid.title = channel.is_self ? "Your channel" : "Raid";
        raid.addEventListener("click", async () => {
            if (startingRaid || channel.is_self || !window.confirm(`Start a Twitch raid to ${channel.display_name || channel.login}?`)) return;
            const sourceRect = card.getBoundingClientRect();
            const sourceAvatar = channelPreview?.open
                ? channelPreview.querySelector("[data-raid-preview-identity]")?.querySelector("img")
                : card.querySelector(".raid-browser-avatar");
            const avatarRect = sourceAvatar?.getBoundingClientRect();
            const avatarFlyer = sourceAvatar?.cloneNode?.(true);
            disableRaidButtons(true);
            showStatus("Starting raid on Twitch...");
            try {
                const body = new URLSearchParams({action: "start", target_id: channel.id, csrf_token: dialog.dataset.csrfToken || ""});
                const response = await fetch(dialog.dataset.raidActionUrl || "/channel/api/raid-browser/action", {
                    method: "POST", body, headers: {Accept: "application/json"}});
                const payload = await response.json();
                if (!response.ok || !payload.raid) throw new Error(payload.detail || "Twitch could not start the raid.");
                const flyer = card.cloneNode?.(true);
                if (flyer) {
                    // Keep row/grid and size-specific styling after the clone
                    // leaves the dialog and its ancestor-dependent selectors.
                    const originals = [card, ...card.querySelectorAll("*")];
                    const copies = [flyer, ...flyer.querySelectorAll("*")];
                    const properties = ["display", "position", "grid-template-columns", "grid-template-rows", "grid-column", "grid-row",
                        "flex", "gap", "align-items", "align-self", "padding", "font-size", "font-weight", "line-height",
                        "width", "height", "box-sizing", "aspect-ratio", "margin-left", "background", "color", "top", "right", "bottom", "left"];
                    originals.forEach((element, index) => {
                        const computed = getComputedStyle(element);
                        properties.forEach(property => copies[index].style.setProperty(property, computed.getPropertyValue(property)));
                    });
                }
                if (dialog.open) dialog.close();
                document.dispatchEvent(new CustomEvent("dashboard-raid-started", {detail: {raid: payload.raid, sourceRect, flyer, avatarRect, avatarFlyer}}));
            } catch (error) {
                showStatus(error.message, true);
                if (!dialog.open) document.dispatchEvent(new CustomEvent("dashboard-raid-error", {detail: {message: error.message}}));
            } finally {
                disableRaidButtons(false);
            }
        });
        preview.addEventListener("click", () => openChannelPreview(channel, preview, raid, card));
        heading.append(streamActions, pin, more);
        const title = document.createElement("p");
        title.className = "raid-browser-stream-title";
        title.textContent = channel.title;
        const info = document.createElement("p");
        info.className = "raid-browser-stream-info";
        const category = document.createElement("span");
        category.className = "raid-browser-category-name";
        category.textContent = channel.category || "No category";
        info.append(category);
        const events = [...new Set((channel.events || []).filter(event => typeof event === "string" && event.trim()).map(event => event.trim()))];
        if (events.length) {
            const labels = document.createElement("span");
            labels.className = "raid-browser-stream-events";
            labels.textContent = events.join(" · ");
            labels.title = labels.textContent;
            info.append(labels);
        }
        const tags = document.createElement("div");
        tags.className = "raid-browser-tags";
        tags.setAttribute("aria-label", "Stream tags");
        const filterTags = new Set((currentFilters.tags || "").split(",").map(tag => tag.trim().toLowerCase()).filter(Boolean));
        const isMatchedTag = tag => filterTags.has(String(tag).trim().toLowerCase());
        function appendStreamTag(tag, matched = false) {
            const label = document.createElement("span");
            label.textContent = tag;
            label.title = tag;
            if (matched) label.className = "raid-browser-tag-matched";
            tags.append(label);
        }
        for (const tag of channel.tags || []) {
            if (isMatchedTag(tag)) appendStreamTag(tag, true);
        }
        if (channel.dev_priority) {
            const developer = document.createElement("span");
            developer.className = "raid-browser-developer-tag";
            developer.textContent = "Developer";
            developer.title = "Developer";
            tags.append(developer);
        }
        if (channel.suggested) {
            const label = document.createElement("span"); label.textContent = "Suggested"; tags.append(label);
        }
        if (channel.recent_raider) {
            const label = document.createElement("span"); label.textContent = "Raided you recently"; tags.append(label);
        }
        for (const tag of channel.tags || []) {
            if (!isMatchedTag(tag)) appendStreamTag(tag);
        }
        const footer = document.createElement("div");
        footer.className = "raid-browser-channel-footer";
        footer.append(tags, raid);
        card.append(preview, heading, title, info, footer, menu);
        const matchInfo = document.createElement("pre");
        matchInfo.className = "raid-browser-match-debug";
        const lines = [`Match score: ${channel.relevance || 0}`];
        for (const [label, points] of Object.entries(channel.match_breakdown || {})) lines.push(`${label}: +${points}`);
        if (!channel.match_breakdown) lines.push("Refresh for breakdown");
        if (channel.search_score) lines.push(`Search score: ${channel.search_score} (separate)`);
        if (rankedFavorites.has(channel.id)) lines.push("Favorite: priority placement");
        if (channel.dev_priority) lines.push("Developer: priority placement");
        if (channel.mutual === null) lines.push("Mutual following: unverified");
        matchInfo.textContent = lines.join("\n");
        card.append(matchInfo);
        return card;
    }
    async function load(append = false, origins = null) {
        if (append && (loading || !cursor)) return;
        clearTimeout(searchTimer);
        controller?.abort();
        const tagField = search.querySelector('[name="tags"]');
        const tagTooLong = (tagField?.value || "").split(",").some(tag => Array.from(tag.trim()).length > 25);
        tagField?.setCustomValidity?.(tagTooLong ? "Each tag must be 25 characters or fewer." : "");
        if (tagTooLong) {
            loading = false;
            showStatus("Each tag must be 25 characters or fewer.", true);
            tagField?.reportValidity?.();
            return;
        }
        const request = new AbortController();
        controller = request;
        if (!append) cancelCardMoves();
        tabSwapWaiting = !append && Boolean(origins?.size);
        loading = true;
        loadError = false;
        if (!append) {
            pendingFilters = false;
            rankedFavorites = new Set(favorites);
            currentQuery = input.value.trim();
            currentFilters = readFilters();
            cursor = "";
            if (!tabSwapWaiting) clearLoadedCards();
        }
        showStatus("Loading live channels...");
        results.setAttribute("aria-busy", "true");
        const url = new URL(dialog.dataset.browserUrl, window.location.origin);
        const requestedFavorites = [...favorites].join(",");
        if (currentQuery) url.searchParams.set("query", currentQuery);
        for (const [name, value] of Object.entries(currentFilters)) url.searchParams.set(name, value);
        if (activeTab === "favorites") url.searchParams.set("favorites_only", "true");
        if (favorites.size) url.searchParams.set("favorites", [...favorites].join(","));
        if (blacklist.size) url.searchParams.set("blocked", [...blacklist].join(","));
        const previousCursor = cursor;
        if (append && previousCursor) url.searchParams.set("after", previousCursor);
        try {
            const response = await fetch(url, {signal: request.signal, cache: "no-store", headers: {Accept: "application/json"}});
            const payload = await response.json();
            if (request.signal.aborted || !dialog.open) return;
            if (!response.ok) {
                throw new Error(payload.detail || "Live channels could not be loaded.");
            }
            if (Array.isArray(payload.live_favorite_ids) && requestedFavorites === [...favorites].join(",")) {
                for (const id of favorites) knownLiveChannels.delete(id);
                for (const id of payload.live_favorite_ids) knownLiveChannels.add(id);
            }
            for (const channel of payload.channels || []) knownLiveChannels.add(channel.id);
            let activeCollectionEmpty = false;
            for (const [tab, property] of [["developer", "developers_live"], ["favorites", "favorites_live"], ["team", "team_live"]]) {
                if (typeof payload[property] !== "boolean") continue;
                if (tab === "favorites" && requestedFavorites !== [...favorites].join(",")) continue;
                collectionButtons.forEach(button => {
                    if (button.dataset.raidBrowserTab === tab) button.hidden = !payload[property];
                });
                if (!payload[property] && activeTab === tab) activeCollectionEmpty = true;
            }
            if (activeCollectionEmpty) {
                activeTab = "browse";
                collectionButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.raidBrowserTab === "browse")));
                for (const name of ["following", "mutual"]) {
                    const field = search.querySelector(`[name="${name}"]`);
                    if (field) field.disabled = false;
                }
                load();
                return;
            }
            if (!append && tabSwapWaiting) {
                clearLoadedCards();
                tabSwapWaiting = false;
                tabCardOrigins = origins;
            }
            const anchorId = append ? channels[Math.floor(results.scrollTop / rowStride) * columns]?.id : null;
            if (Array.isArray(payload.channel_tags)) {
                channelTags = new Set();
                for (const tag of payload.channel_tags) {
                    if (typeof tag !== "string" || !tag.trim() || Array.from(tag.trim()).length > 25) continue;
                    channelTags.add(tag.trim().toLowerCase());
                    availableTags.set(tag.trim().toLowerCase(), tag.trim());
                }
            }
            for (const channel of payload.channels || []) {
                identities.set(channel.id, channel);
                if (!/^[A-Za-z0-9_]{1,25}$/.test(channel.login) || seen.has(channel.id) || blacklist.has(channel.id)
                    || (activeTab === "favorites" && !favorites.has(channel.id))
                    || (activeTab === "developer" && !channel.dev_priority)) continue;
                seen.add(channel.id);
                channels.push(channel);
            }
            syncTabIndicator();
            sortChannels();
            if (anchorId) {
                const anchorIndex = channels.findIndex(channel => channel.id === anchorId);
                if (anchorIndex >= 0) results.scrollTop = Math.floor(anchorIndex / columns) * rowStride + results.scrollTop % rowStride;
            }
            cursor = payload.cursor && payload.cursor !== previousCursor ? payload.cursor : "";
            for (const channel of payload.channels || []) {
                for (const tag of channel.tags || []) {
                    if (typeof tag === "string" && tag.trim() && Array.from(tag.trim()).length <= 25)
                        availableTags.set(tag.trim().toLowerCase(), tag.trim());
                }
            }
            renderTags();
            showStatus(seen.size ? ""
                : activeTab === "favorites" ? "No live favorites match your filters. Manage lists includes offline favorites too."
                : activeTab === "team" ? "No live stream team channels match your filters."
                : activeTab === "developer" ? "No live developer channels match your filters."
                : "No live channels found. Try another channel or category.");
            if (payload.suggested_status === "stale") status.textContent += " Using last saved suggested streamers.";
            if (payload.suggested_status === "unavailable") status.textContent += " Suggested streamers are temporarily unavailable.";
            if (payload.sort_scope === "fetched") status.textContent += " Using Twitch's official fallback. Sorting applies to fetched channels, not the entire directory.";
            if (payload.search_limited) status.textContent += " Checked up to 500 streams. Narrow your filters to find more relevant matches.";
        } catch (error) {
            if (error.name !== "AbortError" && !request.signal.aborted && dialog.open) {
                loadError = true;
                showStatus(append && seen.size
                    ? "Couldn't load more channels. Existing results are still available. Change a filter to retry."
                    : error.message, true);
            }
        } finally {
            if (controller === request) {
                tabSwapWaiting = false;
                loading = false;
                results.setAttribute("aria-busy", "false");
                scheduleRender();
            }
        }
    }
    const raidBrowserHash = "#raidbrowser";
    function raidBrowserRoute() {
        const hash = window.location.hash;
        if (hash === raidBrowserHash) return {channel: ""};
        if (!hash.startsWith(`${raidBrowserHash}?`)) return null;
        const login = new URLSearchParams(hash.slice(raidBrowserHash.length + 1)).get("channel") || "";
        return {channel: /^[A-Za-z0-9_]{1,25}$/.test(login) ? login.toLowerCase() : ""};
    }
    async function restoreChannelPreview(login) {
        if (channelPreview?.open && previewSource?.channel.login.toLowerCase() === login) return;
        if (previewLinkController && previewLinkLogin === login) return;
        previewLinkController?.abort();
        const request = new AbortController(); previewLinkController = request; previewLinkLogin = login;
        try {
            let channel = channels.find(item => item.login.toLowerCase() === login);
            if (!channel) {
                const url = new URL(dialog.dataset.browserUrl, window.location.origin);
                url.searchParams.set("query", login); url.searchParams.set("sort", "for_you");
                if (blacklist.size) url.searchParams.set("blocked", [...blacklist].join(","));
                const response = await fetch(url, {signal: request.signal, cache: "no-store"});
                const payload = await response.json();
                if (!response.ok) throw new Error(payload.detail || "Channel preview could not be loaded.");
                channel = (payload.channels || []).find(item => item.login?.toLowerCase() === login);
            }
            if (request.signal.aborted || !dialog.open || raidBrowserRoute()?.channel !== login) return;
            if (!channel || blacklist.has(channel.id)) {
                showStatus("This channel is offline or unavailable in the raid browser.", true); return;
            }
            identities.set(channel.id, channel);
            const index = channels.findIndex(item => item.id === channel.id);
            const card = rendered.get(index) || channelCard(channel);
            openChannelPreview(channel, card.querySelector(".raid-browser-thumbnail"), card.querySelector(".raid-browser-start-raid"), card);
        } catch (error) {
            if (!request.signal.aborted && dialog.open && raidBrowserRoute()?.channel === login) showStatus(error.message, true);
        } finally {
            if (previewLinkController === request) { previewLinkController = null; previewLinkLogin = ""; }
        }
    }
    function openRaidBrowser() {
        if (dialog.open) return;
        dialog.showModal();
        syncTabIndicator();
        liveTimer = setInterval(updateLiveTimes, 1000);
        document.documentElement.classList.add("raid-browser-open");
        if (!mobileLayout()) input.focus();
        renderTags();
        load();
    }
    opener.addEventListener("click", () => {
        if (window.location.hash !== raidBrowserHash) window.history.pushState(null, "", raidBrowserHash);
        openRaidBrowser();
    });
    dialog.querySelector("[data-raid-browser-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", event => dismissOnBackdropClick(dialog, event));
    dialog.addEventListener("pointercancel", () => backdropPresses.delete(dialog));
    dialog.addEventListener("close", () => {
        previewLinkController?.abort(); previewLinkController = null; previewLinkLogin = "";
        if (channelPreview?.open) channelPreview.close();
        cancelCardMoves();
        tabSwapWaiting = false;
        setFiltersOpen(false);
        backdropPresses.delete(dialog);
        closeCategoryPicker();
        clearInterval(liveTimer);
        liveTimer = null;
        closeTagDropdown();
        if (manager?.open) manager.close();
        controller?.abort();
        clearTimeout(searchTimer);
        cancelAnimationFrame(renderFrame);
        renderFrame = 0;
        rendered.clear();
        windowGrid.replaceChildren();
        document.documentElement.classList.remove("raid-browser-open");
        if (raidBrowserRoute()) {
            window.history.replaceState(null, "", window.location.pathname + window.location.search);
        }
        opener.focus({preventScroll: true});
    });
    search.addEventListener("submit", event => {
        event.preventDefault();
        pendingFilters = false;
        setFiltersOpen(false);
        if (mobileLayout()) filtersToggle?.focus({preventScroll: true});
        load();
    });
    search.addEventListener("input", event => {
        if (categorySearch && event?.target === categorySearch) {
            closeCategoryPicker();
            const categoryField = search.querySelector('[name="category_id"]');
            if (!categorySearch.value.trim() && categoryField.value) {
                categoryField.value = "";
                updateFilters();
            }
            categoryTimer = setTimeout(searchCategories, 500); return;
        }
        if (tagSearch && event?.target === tagSearch) { tagDropdownOpen = true; renderTags(); return; }
        if (event?.target?.type === "checkbox" || event?.target?.tagName === "SELECT") return;
        const tagField = search.querySelector('[name="tags"]');
        tagField?.setCustomValidity?.("");
        if (mobileLayout()) { pendingFilters = true; renderTags(); return; }
        controller?.abort();
        clearTimeout(searchTimer);
        cursor = "";
        renderTags();
        searchTimer = setTimeout(() => load(), 500);
    });
    search.addEventListener("change", event => {
        if (event.target === input || event.target === tagSearch || event.target === categorySearch || event.target === search.querySelector('[name="tags"]')) return;
        const following = search.querySelector('[name="following"]');
        const mutual = search.querySelector('[name="mutual"]');
        if (event.target === mutual && mutual.checked) following.checked = true;
        if (event.target === following && !following.checked) mutual.checked = false;
        updateFilters();
    });
    search.addEventListener("reset", event => {
        event.preventDefault();
        clearTimeout(searchTimer);
        controller?.abort();
        closeCategoryPicker();
        closeTagDropdown();
        input.value = "";
        if (categorySearch) categorySearch.value = "";
        if (tagSearch) tagSearch.value = "";
        // Hidden inputs' value assignments also change their native reset
        // defaults, so explicitly clear the selected category and tags.
        for (const name of filterNames) {
            const field = search.querySelector(`[name="${name}"]`);
            if (!field) continue;
            if (field.type === "checkbox") { field.checked = false; field.disabled = false; }
            else field.value = name === "sort" ? "for_you" : name === "tag_match" ? "all" : "";
            field.setCustomValidity?.("");
        }
        activeTab = "browse";
        syncTagMatch();
        collectionButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.raidBrowserTab === "browse")));
        syncTabIndicator();
        renderTags();
        updateFilters();
    });
    results.addEventListener("scroll", scheduleRender, {passive: true});
    new ResizeObserver(scheduleRender).observe(results);
    windowGrid.addEventListener("keydown", event => {
        if (event.key !== "Tab" || event.altKey || event.ctrlKey || event.metaKey) return;
        const card = event.target.closest("[data-channel-index]");
        if (!card) return;
        const lastControl = item => {
            const raid = item?.querySelector(".raid-browser-start-raid");
            return raid && !raid.disabled ? raid : item?.querySelector(".raid-browser-more");
        };
        if (event.shiftKey ? event.target !== card.querySelector(".raid-browser-thumbnail") : event.target !== lastControl(card)) return;
        const next = Number(card.dataset.channelIndex) + (event.shiftKey ? -1 : 1);
        if (next < 0 || next >= channels.length || rendered.has(next)) return;
        event.preventDefault();
        results.scrollTop = Math.floor(next / columns) * rowStride;
        renderWindow();
        const nextControl = event.shiftKey ? lastControl(rendered.get(next)) : rendered.get(next)?.querySelector(".raid-browser-thumbnail");
        nextControl?.focus({preventScroll: true});
    });
    function syncRaidBrowserHash() {
        const route = raidBrowserRoute();
        if (!route) { if (dialog.open) dialog.close(); return; }
        openRaidBrowser();
        if (route.channel) restoreChannelPreview(route.channel);
        else {
            previewLinkController?.abort(); previewLinkController = null; previewLinkLogin = "";
            if (channelPreview?.open) channelPreview.close();
        }
    }
    window.addEventListener("hashchange", syncRaidBrowserHash);
    window.addEventListener("popstate", syncRaidBrowserHash);
    syncRaidBrowserHash();
})();
