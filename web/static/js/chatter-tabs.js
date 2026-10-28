const chatterTabs = document.querySelectorAll("[data-chatter-tab]");
function selectChatterTab(selected) {
    chatterTabs.forEach((button) => {
        const active = button.dataset.chatterTab === selected;
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", String(active));
    });
    document.querySelectorAll("[data-chatter-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.chatterPanel !== selected;
    });
}
chatterTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        selectChatterTab(tab.dataset.chatterTab);
    });
});
function resolveChatterTab(value) {
    return ["shop", "gamble"].includes(value) && Array.from(chatterTabs).some(tab => tab.dataset.chatterTab === "activity") ? "activity" : value;
}
const selectedTab = resolveChatterTab(new URLSearchParams(window.location.search).get("tab") || window.location.hash.slice(1));
if (selectedTab && Array.from(chatterTabs).some((tab) => tab.dataset.chatterTab === selectedTab)) {
    selectChatterTab(selectedTab);
}

window.addEventListener("hashchange", () => {
    const selected = resolveChatterTab(window.location.hash.slice(1));
    if (Array.from(chatterTabs).some((tab) => tab.dataset.chatterTab === selected)) {
        selectChatterTab(selected);
    }
});
