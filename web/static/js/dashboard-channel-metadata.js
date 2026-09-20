(() => {
    const card = document.querySelector("[data-channel-metadata]");
    if (!card) return;
    const endpoint = card.dataset.updateUrl;
    const gamesEndpoint = card.dataset.gamesUrl;
    const csrfToken = card.dataset.csrfToken;
    const status = card.querySelector("[data-channel-metadata-status]");
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
        statusFadeTimer = window.setTimeout(() => status.classList.add("is-fading"), 3000);
    }

    statusFadeTimer = window.setTimeout(() => status.classList.add("is-fading"), 3000);

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
            button.addEventListener("mousedown", event => {
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
        gameSuggestions.hidden = true;
        gameField.blur();
    }

    async function searchGames(query = "") {
        if (!gamesEndpoint) return;
        gameSearchController?.abort();
        gameSearchController = new AbortController();
        try {
            const url = new URL(gamesEndpoint, window.location.origin);
            if (query.trim()) url.searchParams.set("query", query.trim());
            const response = await fetch(url, {
                headers: {Accept: "application/json"},
                cache: "no-store",
                signal: gameSearchController.signal
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || "Games could not be loaded.");
            renderGameOptions(result.games);
        } catch (error) {
            if (error.name !== "AbortError") showStatus(error.message, "error");
        }
    }

    if (gameField && gameSuggestions) {
        gameField.addEventListener("focus", () => searchGames(""));
        gameField.addEventListener("input", () => {
            window.clearTimeout(gameSearchTimer);
            gameSearchTimer = window.setTimeout(() => searchGames(gameField.textContent), 200);
        });
        gameField.addEventListener("keydown", event => {
            if (gameSuggestions.hidden || !gameOptions.length) return;
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                event.stopImmediatePropagation();
                highlightGame(selectedGame + (event.key === "ArrowDown" ? 1 : -1));
            } else if (event.key === "Tab" || event.key === "Enter") {
                event.preventDefault();
                event.stopImmediatePropagation();
                chooseGame(selectedGame);
            } else if (event.key === "Escape") {
                gameSuggestions.hidden = true;
            }
        });
    }

    card.querySelectorAll("[data-channel-field]").forEach(field => {
        let originalValue = field.textContent.trim();

        field.addEventListener("focus", () => {
            originalValue = field.textContent.trim();
            field.classList.add("editing");
        });
        field.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                field.blur();
            } else if (event.key === "Escape") {
                event.preventDefault();
                field.textContent = originalValue;
                field.dataset.cancelEdit = "true";
                field.blur();
            }
        });
        field.addEventListener("blur", async () => {
            field.classList.remove("editing");
            if (field === gameField) gameSuggestions.hidden = true;
            if (field.dataset.cancelEdit) {
                delete field.dataset.cancelEdit;
                return;
            }
            const value = field.textContent.trim();
            if (value === originalValue) return;
            showStatus("Saving…");
            const data = new FormData();
            data.set("csrf_token", csrfToken);
            data.set("field", field.dataset.channelField);
            data.set("value", value);
            try {
                const response = await fetch(endpoint, {method: "POST", body: data});
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || "The Twitch channel could not be updated.");
                field.textContent = result.value;
                originalValue = result.value;
                showStatus("Saved to Twitch.", "success");
            } catch (error) {
                field.textContent = originalValue;
                showStatus(error.message, "error");
            }
        });
    });
})();
