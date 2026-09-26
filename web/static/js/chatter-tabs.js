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
const selectedTab = new URLSearchParams(window.location.search).get("tab");
if (selectedTab && Array.from(chatterTabs).some((tab) => tab.dataset.chatterTab === selectedTab)) {
    selectChatterTab(selectedTab);
}
