(() => {
    const shell = document.querySelector("[data-dashboard-shell]");
    const toggle = document.querySelector("[data-sidebar-toggle]");
    if (!shell || !toggle) return;

    const storageKey = shell.dataset.sidebarStorageKey || "ratsboombot-dashboard-sidebar-collapsed";
    const mobileMedia = window.matchMedia("(max-width: 1100px)");
    let desktopCollapsed = false;
    let mobileExpanded = false;

    function applyState(collapsed) {
        const mobile = mobileMedia.matches;
        shell.classList.toggle("sidebar-collapsed", collapsed);
        toggle.setAttribute("aria-expanded", String(!collapsed));
        toggle.setAttribute("aria-label", mobile
            ? (collapsed ? "Open navigation" : "Close navigation")
            : (collapsed ? "Expand navigation" : "Collapse navigation"));
        toggle.title = toggle.getAttribute("aria-label");
        const icon = toggle.querySelector("span");
        if (icon) icon.textContent = mobile ? (collapsed ? "☰" : "×") : (collapsed ? "›" : "‹");
    }

    function applyResponsiveState() {
        applyState(mobileMedia.matches ? !mobileExpanded : desktopCollapsed);
    }

    try {
        desktopCollapsed = window.localStorage.getItem(storageKey) === "true";
    } catch (error) {
        // Storage may be unavailable in privacy-restricted browser contexts.
    }
    applyResponsiveState();

    toggle.addEventListener("click", () => {
        if (mobileMedia.matches) {
            mobileExpanded = shell.classList.contains("sidebar-collapsed");
            applyResponsiveState();
            return;
        }
        desktopCollapsed = !shell.classList.contains("sidebar-collapsed");
        applyResponsiveState();
        try {
            window.localStorage.setItem(storageKey, String(desktopCollapsed));
        } catch (error) {
            // The current page still keeps the selected state without persistence.
        }
    });

    mobileMedia.addEventListener("change", () => {
        mobileExpanded = false;
        applyResponsiveState();
    });
})();
