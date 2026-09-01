document.querySelectorAll("[data-chatter-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
        const selected = tab.dataset.chatterTab;
        document.querySelectorAll("[data-chatter-tab]").forEach((button) => {
            const active = button.dataset.chatterTab === selected;
            button.classList.toggle("active", active);
            button.setAttribute("aria-selected", String(active));
        });
        document.querySelectorAll("[data-chatter-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.chatterPanel !== selected;
        });
    });
});
