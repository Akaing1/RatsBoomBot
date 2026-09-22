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
    let statusFadeTimer = null;
    let gameSearchTimer = null;
    let gameSearchController = null;
    let gameOptions = [];
    let selectedGame = 0;

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
            field.classList.toggle("metadata-truncated", field.scrollWidth > field.clientWidth + 1);
        }
        new MutationObserver(updateFieldPencil).observe(field, {childList: true, characterData: true, subtree: true});
        new ResizeObserver(updateFieldPencil).observe(field, {box: "border-box"});
        field.addEventListener("blur", () => window.requestAnimationFrame(updateFieldPencil));
        window.requestAnimationFrame(updateFieldPencil);
    });

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
        function updateTitleEditingWidth() {
            if (document.activeElement !== titleField) return;
            titleField.style.removeProperty("width");
            const fieldBounds = titleField.getBoundingClientRect();
            const cardBounds = card.getBoundingClientRect();
            const rightPadding = parseFloat(window.getComputedStyle(card).paddingRight) || 0;
            const maxWidth = Math.max(0, cardBounds.right - rightPadding - fieldBounds.left);
            const width = Math.min(maxWidth, Math.max(fieldBounds.width, titleField.scrollWidth + 2));
            titleField.style.width = `${width}px`;
        }
        titleField.addEventListener("focus", updateTitleEditingWidth);
        titleField.addEventListener("input", updateTitleEditingWidth);
        titleField.addEventListener("blur", () => titleField.style.removeProperty("width"));
        new ResizeObserver(updateTitleEditingWidth).observe(card, {box: "border-box"});
    }

    function renderGameOptions(games) {
        gameOptions = Array.isArray(games) ? games : [];
        selectedGame = 0;
        gameSuggestions.replaceChildren();
        gameOptions.forEach((game, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = `twitch-game-option${index === selectedGame ? " active" : ""}`;
            button.textContent = game.name;
            button.setAttribute("role", "option");
            button.addEventListener("pointerdown", event => {
                event.preventDefault();
                chooseGame(index);
            });
            gameSuggestions.appendChild(button);
        });
        gameSuggestions.hidden = gameOptions.length === 0;
    }

    function highlightGame(index) {
        if (!gameOptions.length) return;
        selectedGame = (index + gameOptions.length) % gameOptions.length;
        gameSuggestions.querySelectorAll(".twitch-game-option").forEach((option, optionIndex) => {
            option.classList.toggle("active", optionIndex === selectedGame);
        });
        gameSuggestions.children[selectedGame]?.scrollIntoView({block: "nearest"});
    }

    function chooseGame(index) {
        const game = gameOptions[index];
        if (!game) return;
        gameField.textContent = game.name;
        gameField.dataset.commitEdit = "true";
        gameSuggestions.hidden = true;
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
            renderGameOptions(result.games);
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
            gameSuggestions.hidden = true;
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
                gameSuggestions.hidden = true;
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
                gameSuggestions.hidden = true;
                window.requestAnimationFrame(() => {
                    if (document.activeElement !== gameField) gameField.scrollLeft = 0;
                });
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
                delete field.dataset.hasDraft;
                showStatus(
                    result.announcement_sent ? "Saved to Twitch and announced in chat." : "Saved to Twitch, but chat announcement failed.",
                    result.announcement_sent ? "success" : "warning"
                );
            } catch (error) {
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
