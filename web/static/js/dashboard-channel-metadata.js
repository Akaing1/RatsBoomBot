(() => {
    const card = document.querySelector("[data-channel-metadata]");
    if (!card) return;
    const endpoint = card.dataset.updateUrl;
    const gamesEndpoint = card.dataset.gamesUrl;
    const csrfToken = card.dataset.csrfToken;
    const status = card.querySelector("[data-channel-metadata-status]");
    const titleField = card.querySelector('[data-channel-field="title"]');
    const gameField = card.querySelector('[data-channel-field="game"]');
    const gameSuggestions = card.querySelector("[data-game-suggestions]");
    const gameOptionsList = card.querySelector("[data-game-options]");
    const currentCategoryArt = card.querySelector("[data-current-category-art]");
    const categoryArtHome = currentCategoryArt?.parentElement;
    const selectionPreview = card.querySelector("[data-game-selection-preview]");
    categoryArtHome?.addEventListener("click", () => {
        if (document.activeElement === gameField) {
            searchGames(gameField.dataset.hasDraft ? gameField.textContent.trim() : "");
        } else {
            gameField.focus();
        }
    });
    let savedCategoryArt = currentCategoryArt?.getAttribute("src") || "";
    let savedCategoryName = gameField.textContent.trim();
    let categoryArtAnimation = null;
    currentCategoryArt?.addEventListener("error", () => { currentCategoryArt.hidden = true; });
    let statusFadeTimer = null;
    let gameSearchTimer = null;
    let gameSearchController = null;
    let gameOptions = [];
    let renderedGameQuery = null;
    let selectedGame = 0;
    let statusSpaceTimer = null;
    let refreshGamePencil = () => {};

    function showStatus(message, tone = "") {
        window.clearTimeout(statusFadeTimer);
        status.className = `channel-metadata-status${tone ? ` ${tone}` : ""}`;
        status.textContent = message;
        if (message !== "Unsaved. Press Enter to save.") {
            statusFadeTimer = window.setTimeout(() => {
                if (card.querySelector('[data-has-draft="true"]')) {
                    showStatus("Unsaved. Press Enter to save.", "warning");
                } else {
                    status.classList.add("is-fading");
                }
            }, 3000);
        }
    }

    function refreshDraftWarning() {
        if (card.querySelector('[data-has-draft="true"]')) {
            showStatus("Unsaved. Press Enter to save.", "warning");
        } else if (status.textContent === "Unsaved. Press Enter to save.") {
            status.classList.add("is-fading");
        }
    }

    statusFadeTimer = window.setTimeout(() => status.classList.add("is-fading"), 3000);

    [titleField, gameField].filter(Boolean).forEach(field => {
        function updateFieldPencil() {
            field.classList.remove("metadata-truncated");
            const range = document.createRange();
            range.selectNodeContents(field);
            const textWidth = range.getBoundingClientRect().width;
            const style = window.getComputedStyle(field);
            const pencilStyle = window.getComputedStyle(field, "::after");
            const availableWidth = field.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
            const pencilWidth = parseFloat(pencilStyle.fontSize) + parseFloat(pencilStyle.marginLeft);
            field.classList.toggle("metadata-truncated", textWidth + pencilWidth > availableWidth + 1);
        }
        if (field === gameField) refreshGamePencil = updateFieldPencil;
        new MutationObserver(updateFieldPencil).observe(field, {childList: true, characterData: true, subtree: true});
        new ResizeObserver(updateFieldPencil).observe(field, {box: "border-box"});
        field.addEventListener("blur", () => {
            field.scrollLeft = 0;
            window.requestAnimationFrame(() => {
                if (document.activeElement === field) return;
                field.scrollLeft = 0;
                updateFieldPencil();
            });
        });
        window.requestAnimationFrame(updateFieldPencil);
    });

    if (gameField) {
        function setStatusSpace(width) {
            gameField.style.setProperty("--metadata-status-padding", `${width ? width + 31 : 8}px`);
            gameField.style.setProperty("--metadata-status-pencil-right", `${width ? width + 6 : 8}px`);
            window.requestAnimationFrame(refreshGamePencil);
        }
        function updateStatusSpace() {
            window.clearTimeout(statusSpaceTimer);
            if (document.activeElement === gameField) {
                setStatusSpace(0);
            } else if (status.classList.contains("is-fading")) {
                statusSpaceTimer = window.setTimeout(() => setStatusSpace(0), 450);
            } else {
                setStatusSpace(Math.ceil(status.getBoundingClientRect().width));
            }
        }
        new MutationObserver(updateStatusSpace).observe(status, {attributes: true, attributeFilter: ["class"], childList: true, characterData: true, subtree: true});
        new ResizeObserver(updateStatusSpace).observe(status);
        gameField.addEventListener("focus", updateStatusSpace);
        gameField.addEventListener("blur", () => window.requestAnimationFrame(updateStatusSpace));
        updateStatusSpace();
    }

    if (titleField) {
        const titleLength = text => Array.from(text).length;
        titleField.addEventListener("beforeinput", event => {
            if (!event.inputType?.startsWith("insert") || !event.data || event.isComposing) return;
            const selection = window.getSelection();
            const selectedLength = selection && titleField.contains(selection.anchorNode) && titleField.contains(selection.focusNode)
                ? titleLength(selection.toString()) : 0;
            if (titleLength(titleField.textContent) - selectedLength + titleLength(event.data) > 140) {
                event.preventDefault();
                showStatus("Titles are limited to 140 characters.", "warning");
            }
        });
        titleField.addEventListener("paste", event => {
            const selection = window.getSelection();
            if (!selection?.rangeCount || !titleField.contains(selection.getRangeAt(0).commonAncestorContainer)) return;
            event.preventDefault();
            const range = selection.getRangeAt(0);
            const pasted = (event.clipboardData?.getData("text/plain") || "").replace(/\r?\n/g, " ");
            const available = Math.max(0, 140 - titleLength(titleField.textContent) + titleLength(range.toString()));
            const inserted = Array.from(pasted).slice(0, available).join("");
            if (inserted) {
                range.deleteContents();
                const node = document.createTextNode(inserted);
                range.insertNode(node);
                range.setStartAfter(node);
                range.collapse(true);
                selection.removeAllRanges();
                selection.addRange(range);
                titleField.dispatchEvent(new Event("input", {bubbles: true}));
            }
            if (titleLength(pasted) > available) showStatus("Titles are limited to 140 characters.", "warning");
        });
        titleField.addEventListener("input", () => {
            if (titleLength(titleField.textContent) <= 140) return;
            titleField.textContent = Array.from(titleField.textContent).slice(0, 140).join("");
            const selection = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(titleField);
            range.collapse(false);
            selection?.removeAllRanges();
            selection?.addRange(range);
            showStatus("Titles are limited to 140 characters.", "warning");
        });
    }

    function updateCategoryPreview(game) {
        setCurrentCategoryArt(game?.box_art_url || "", game?.name || savedCategoryName);
    }
    function setCurrentCategoryArt(url, name = savedCategoryName) {
        if (!currentCategoryArt) return;
        categoryArtHome?.setAttribute("title", name);
        currentCategoryArt.setAttribute("title", name);
        currentCategoryArt.hidden = !url;
        if (url) currentCategoryArt.src = url;
        else currentCategoryArt.removeAttribute("src");
    }

    function setGameSuggestionsVisible(visible, restoreArtwork = true) {
        const destination = visible ? selectionPreview : categoryArtHome;
        if (gameSuggestions.hidden === !visible
            && (!currentCategoryArt || currentCategoryArt.parentElement === destination)) return;
        const oldRect = currentCategoryArt && !currentCategoryArt.hidden
            ? currentCategoryArt.getBoundingClientRect() : null;
        categoryArtAnimation?.cancel();
        gameSuggestions.classList.remove("is-art-animating");
        gameSuggestions.hidden = !visible;
        categoryArtHome?.setAttribute("aria-expanded", String(visible));
        card.classList.toggle("is-category-selecting", visible);
        let moved = false;
        if (currentCategoryArt) {
            if (destination && currentCategoryArt.parentElement !== destination) {
                destination.appendChild(currentCategoryArt);
                moved = true;
            }
        }
        if (!visible && restoreArtwork) setCurrentCategoryArt(savedCategoryArt);
        if (moved && oldRect?.width && oldRect.height && !currentCategoryArt.hidden
            && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            const newRect = currentCategoryArt.getBoundingClientRect();
            if (!newRect.width || !newRect.height) return;
            gameSuggestions.classList.add("is-art-animating");
            categoryArtAnimation = currentCategoryArt.animate([
                {transform: `translate(${oldRect.left - newRect.left}px, ${oldRect.top - newRect.top}px) scale(${oldRect.width / newRect.width}, ${oldRect.height / newRect.height})`},
                {transform: "translate(0px, 0px) scale(1, 1)"}
            ], {duration: 260, easing: "cubic-bezier(.22, 1, .36, 1)"});
            categoryArtAnimation.onfinish = () => gameSuggestions.classList.remove("is-art-animating");
        }
    }
    document.addEventListener("dashboard-carousel-card-changed", () => setGameSuggestionsVisible(false));

    function renderGameOptions(games, query, moreGames = [], expanded = false) {
        const normalizedQuery = query.trim().toLowerCase();
        const previousScroll = normalizedQuery === renderedGameQuery ? gameOptionsList.scrollTop : 0;
        renderedGameQuery = normalizedQuery;
        const mainGames = Array.isArray(games) ? games : [];
        const extraGames = Array.isArray(moreGames) ? moreGames : [];
        gameOptions = expanded ? [...mainGames, ...extraGames] : mainGames;
        selectedGame = 0;
        gameOptionsList.replaceChildren();
        gameOptions.forEach((game, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = `twitch-game-option${index === selectedGame ? " active" : ""}`;
            if (game.box_art_url) {
                const image = document.createElement("img");
                image.className = "twitch-category-art";
                image.src = game.box_art_url;
                image.alt = "";
                image.loading = "lazy";
                image.addEventListener("error", () => { image.hidden = true; });
                button.appendChild(image);
            }
            const name = document.createElement("span");
            name.textContent = game.name;
            button.appendChild(name);
            button.setAttribute("role", "option");
            button.setAttribute("aria-selected", String(index === selectedGame));
            button.addEventListener("pointerenter", () => highlightGame(index, false));
            button.addEventListener("pointerdown", event => {
                event.preventDefault();
                chooseGame(index);
            });
            gameOptionsList.appendChild(button);
        });
        if (extraGames.length) {
            const moreButton = document.createElement("button");
            moreButton.type = "button";
            moreButton.className = "twitch-game-more";
            moreButton.textContent = `${expanded ? "Fewer" : "More"} results (${extraGames.length})`;
            moreButton.setAttribute("aria-expanded", String(expanded));
            moreButton.addEventListener("pointerdown", event => event.preventDefault());
            moreButton.addEventListener("click", () => renderGameOptions(mainGames, query, extraGames, !expanded));
            gameOptionsList.appendChild(moreButton);
        }
        if (gameOptions.length) updateCategoryPreview(gameOptions[selectedGame]);
        else setCurrentCategoryArt(savedCategoryArt);
        setGameSuggestionsVisible(gameOptions.length > 0 || extraGames.length > 0);
        gameOptionsList.scrollTop = previousScroll;
    }

    function highlightGame(index, scroll = true) {
        if (!gameOptions.length) return;
        selectedGame = (index + gameOptions.length) % gameOptions.length;
        gameSuggestions.querySelectorAll(".twitch-game-option").forEach((option, optionIndex) => {
            option.classList.toggle("active", optionIndex === selectedGame);
            option.setAttribute("aria-selected", String(optionIndex === selectedGame));
        });
        updateCategoryPreview(gameOptions[selectedGame]);
        if (scroll) gameOptionsList.children[selectedGame]?.scrollIntoView({block: "nearest"});
    }

    function chooseGame(index) {
        const game = gameOptions[index];
        if (!game) return;
        gameField.textContent = game.name;
        gameField.dataset.commitEdit = "true";
        updateCategoryPreview(game);
        setGameSuggestionsVisible(false, false);
        gameField.blur();
    }

    async function searchGames(query = "") {
        if (!gamesEndpoint) return;
        gameSearchController?.abort();
        const controller = new AbortController();
        gameSearchController = controller;
        try {
            const url = new URL(gamesEndpoint, window.location.origin);
            if (query.trim()) url.searchParams.set("query", query.trim());
            const response = await fetch(url, {
                headers: {Accept: "application/json"},
                cache: "no-store",
                signal: controller.signal
            });
            const result = await response.json();
            if (controller.signal.aborted || document.activeElement !== gameField) return;
            if (!response.ok) throw new Error(result.detail || "Games could not be loaded.");
            renderGameOptions(result.games, query, result.more_games);
        } catch (error) {
            if (error.name !== "AbortError" && document.activeElement === gameField) showStatus(error.message, "error");
        }
    }

    if (gameField && gameSuggestions) {
        gameField.addEventListener("focus", () => searchGames(gameField.dataset.hasDraft ? gameField.textContent.trim() : ""));
        gameField.addEventListener("input", () => {
            window.clearTimeout(gameSearchTimer);
            gameSearchController?.abort();
            gameOptions = [];
            setGameSuggestionsVisible(false);
            gameSearchTimer = window.setTimeout(() => searchGames(gameField.textContent), 200);
        });
        gameField.addEventListener("keydown", event => {
            if (gameSuggestions.hidden || !gameOptions.length) return;
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                event.stopImmediatePropagation();
                highlightGame(selectedGame + (event.key === "ArrowDown" ? 1 : -1));
            } else if (event.key === "Enter") {
                event.preventDefault();
                event.stopImmediatePropagation();
                chooseGame(selectedGame);
            } else if (event.key === "Escape") {
                setGameSuggestionsVisible(false);
            }
        });
    }

    card.querySelectorAll("[data-channel-field]").forEach(field => {
        let savedValue = field.textContent.trim();

        field.addEventListener("focus", () => {
            field.classList.add("editing");
            window.requestAnimationFrame(() => {
                if (document.activeElement !== field) return;
                const selection = window.getSelection();
                if (!selection) return;
                selection.setBaseAndExtent(field, 0, field, field.childNodes.length);
                field.scrollLeft = field.scrollWidth;
            });
        });
        field.addEventListener("input", () => {
            if (field.textContent.trim() !== savedValue) {
                field.dataset.hasDraft = "true";
            } else {
                delete field.dataset.hasDraft;
            }
            refreshDraftWarning();
        });
        field.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                field.dataset.commitEdit = "true";
                field.blur();
            } else if (event.key === "Escape") {
                event.preventDefault();
                field.textContent = savedValue;
                delete field.dataset.hasDraft;
                field.dataset.cancelEdit = "true";
                field.blur();
            }
        });
        field.addEventListener("blur", async () => {
            field.classList.remove("editing");
            if (field === gameField) {
                window.clearTimeout(gameSearchTimer);
                gameSearchController?.abort();
                setGameSuggestionsVisible(false);
            }
            if (field.dataset.cancelEdit) {
                delete field.dataset.cancelEdit;
                delete field.dataset.commitEdit;
                refreshDraftWarning();
                return;
            }
            const shouldCommit = field.dataset.commitEdit === "true";
            delete field.dataset.commitEdit;
            if (!shouldCommit) {
                if (field.textContent.trim() !== savedValue) {
                    field.dataset.hasDraft = "true";
                } else {
                    delete field.dataset.hasDraft;
                }
                refreshDraftWarning();
                return;
            }
            const value = field.textContent.trim();
            if (value === savedValue) {
                delete field.dataset.hasDraft;
                refreshDraftWarning();
                return;
            }
            showStatus("Saving…");
            const data = new FormData();
            data.set("csrf_token", csrfToken);
            data.set("field", field.dataset.channelField);
            data.set("value", value);
            try {
                const response = await fetch(endpoint, {method: "POST", body: data});
                const result = await response.json();
                if (!response.ok) {
                    const error = new Error(result.detail || "The Twitch channel could not be updated.");
                    error.code = result.code;
                    throw error;
                }
                field.textContent = result.value;
                savedValue = result.value;
                if (field === gameField && currentCategoryArt) {
                    savedCategoryArt = result.box_art_url || "";
                    savedCategoryName = result.value;
                    setCurrentCategoryArt(savedCategoryArt);
                }
                delete field.dataset.hasDraft;
                showStatus(
                    result.announcement_sent ? "Saved to Twitch and announced in chat." : "Saved to Twitch, but chat announcement failed.",
                    result.announcement_sent ? "success" : "warning"
                );
            } catch (error) {
                if (field === gameField) setCurrentCategoryArt(savedCategoryArt);
                if (field === gameField && error.code === "category_not_found") {
                    field.textContent = savedValue;
                    delete field.dataset.hasDraft;
                } else {
                    field.dataset.hasDraft = "true";
                }
                showStatus(error.message, "error");
            }
        });
    });
})();
