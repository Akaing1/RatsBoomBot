(() => {
    const shell = document.querySelector("[data-dashboard-shell]");
    const toggle = document.querySelector("[data-sidebar-toggle]");
    if (!shell || !toggle) return;
    const sidebar = shell.querySelector(".sidebar");

    const storageKey = shell.dataset.sidebarStorageKey || "ratsboombot-dashboard-sidebar-collapsed";
    const mobileMedia = window.matchMedia("(max-width: 768px)");
    const compactMedia = window.matchMedia("(min-width: 769px) and (max-width: 1100px)");
    let desktopCollapsed = false;
    let compactExpanded = false;
    let mobileExpanded = false;
    let readyFrame = 0;

    function enableTransitionsAfterLayout() {
        window.cancelAnimationFrame(readyFrame);
        readyFrame = window.requestAnimationFrame(() => {
            readyFrame = window.requestAnimationFrame(() => shell.classList.add("sidebar-ready"));
        });
    }

    function applyState(collapsed) {
        const mobile = mobileMedia.matches;
        shell.classList.remove("sidebar-hover-expanded");
        sidebar?.classList.remove("sidebar-hover-expanded");
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
        applyState(mobileMedia.matches ? !mobileExpanded : compactMedia.matches ? !compactExpanded : desktopCollapsed);
    }

    try {
        desktopCollapsed = window.localStorage.getItem(storageKey) === "true";
    } catch (error) {
        // Storage may be unavailable in privacy-restricted browser contexts.
    }
    applyResponsiveState();
    enableTransitionsAfterLayout();

    toggle.addEventListener("click", () => {
        if (mobileMedia.matches) {
            mobileExpanded = shell.classList.contains("sidebar-collapsed");
            applyResponsiveState();
            return;
        }
        if (compactMedia.matches) {
            compactExpanded = shell.classList.contains("sidebar-collapsed");
            shell.classList.toggle("sidebar-hover-locked", !compactExpanded);
            sidebar?.classList.toggle("sidebar-hover-locked", !compactExpanded);
            applyResponsiveState();
            return;
        }
        desktopCollapsed = !shell.classList.contains("sidebar-collapsed");
        shell.classList.toggle("sidebar-hover-locked", desktopCollapsed);
        sidebar?.classList.toggle("sidebar-hover-locked", desktopCollapsed);
        applyResponsiveState();
        try {
            window.localStorage.setItem(storageKey, String(desktopCollapsed));
        } catch (error) {
            // The current page still keeps the selected state without persistence.
        }
    });

    function expandOnPointer(event) {
        if (event.pointerType === "touch" || mobileMedia.matches
            || !shell.classList.contains("sidebar-collapsed")
            || shell.classList.contains("sidebar-hover-locked")
            || toggle.matches(":hover")) return;
        shell.classList.add("sidebar-hover-expanded");
        sidebar.classList.add("sidebar-hover-expanded");
    }

    // Entering the floating toggle must not move it away from the pointer.
    // Moving from the toggle into the menu still opens the hover preview.
    sidebar?.addEventListener("pointerenter", expandOnPointer);
    sidebar?.addEventListener("pointermove", expandOnPointer);
    sidebar?.addEventListener("pointerleave", () => {
        shell.classList.remove("sidebar-hover-expanded");
        sidebar.classList.remove("sidebar-hover-expanded");
        shell.classList.remove("sidebar-hover-locked");
        sidebar.classList.remove("sidebar-hover-locked");
    });

    function handleBreakpointChange() {
        shell.classList.remove("sidebar-ready", "sidebar-hover-locked");
        sidebar?.classList.remove("sidebar-hover-locked");
        mobileExpanded = false;
        applyResponsiveState();
        enableTransitionsAfterLayout();
    }
    mobileMedia.addEventListener("change", handleBreakpointChange);
    compactMedia.addEventListener("change", handleBreakpointChange);
})();
