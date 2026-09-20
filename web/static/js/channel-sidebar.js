(() => {
    const shell = document.querySelector("[data-channel-shell]");
    const toggle = document.querySelector("[data-sidebar-toggle]");
    if (!shell || !toggle) return;

    const storageKey = "ratsboombot-channel-sidebar-collapsed";

    function applyState(collapsed) {
        shell.classList.toggle("sidebar-collapsed", collapsed);
        toggle.setAttribute("aria-expanded", String(!collapsed));
        toggle.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
        toggle.title = collapsed ? "Expand navigation" : "Collapse navigation";
        const icon = toggle.querySelector("span");
        if (icon) icon.textContent = collapsed ? "›" : "‹";
    }

    let collapsed = false;
    try {
        collapsed = window.localStorage.getItem(storageKey) === "true";
    } catch (error) {
        // Storage may be unavailable in privacy-restricted browser contexts.
    }
    applyState(collapsed);

    toggle.addEventListener("click", () => {
        collapsed = !shell.classList.contains("sidebar-collapsed");
        applyState(collapsed);
        try {
            window.localStorage.setItem(storageKey, String(collapsed));
        } catch (error) {
            // The current page still keeps the selected state without persistence.
        }
    });
})();
