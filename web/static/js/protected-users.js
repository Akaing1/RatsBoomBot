(() => {
    const tabs = Array.from(document.querySelectorAll("[data-command-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-command-panel]"));

    function selectTab(name) {
        tabs.forEach(tab => {
            const active = tab.dataset.commandTab === name;
            tab.classList.toggle("active", active);
            tab.setAttribute("aria-selected", String(active));
        });
        panels.forEach(panel => {
            panel.hidden = panel.dataset.commandPanel !== name;
        });
    }

    tabs.forEach(tab => tab.addEventListener("click", () => selectTab(tab.dataset.commandTab)));

    const searchForm = document.querySelector("[data-protected-user-search]");
    const resultForm = document.querySelector("[data-protected-user-result]");
    if (!searchForm || !resultForm) return;

    const queryInput = searchForm.querySelector('input[name="query"]');
    const message = searchForm.querySelector("[data-protected-search-message]");
    const resultId = resultForm.querySelector("[data-protected-result-id]");
    const resultLabel = resultForm.querySelector("[data-protected-result-label]");
    const addButton = resultForm.querySelector("[data-protected-add]");

    searchForm.addEventListener("submit", async event => {
        event.preventDefault();
        resultForm.hidden = true;
        message.textContent = "Searching Twitch...";

        try {
            const response = await fetch(`${searchForm.dataset.searchUrl}?query=${encodeURIComponent(queryInput.value)}`, {
                headers: {"Accept": "application/json"}
            });
            const payload = await response.json();

            if (!response.ok) throw new Error(payload.detail || "Twitch user lookup failed.");

            const user = payload.user;
            resultId.value = user.id;
            resultLabel.textContent = `${user.display_name} (${user.id})`;
            addButton.disabled = user.already_protected;
            addButton.textContent = user.already_protected ? "Already Protected" : "Add User";
            resultForm.hidden = false;
            message.textContent = user.automatic
                ? "This account is protected automatically."
                : (user.already_protected ? "This user is already protected." : "User found. Confirm to add them.");
        } catch (error) {
            message.textContent = error.message || "Twitch user lookup failed.";
        }
    });
})();
