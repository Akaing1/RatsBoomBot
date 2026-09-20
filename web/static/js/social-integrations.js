(() => {
    const tabs = Array.from(document.querySelectorAll("[data-social-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-social-panel]"));

    function selectTab(name) {
        tabs.forEach(tab => {
            const active = tab.dataset.socialTab === name;
            tab.classList.toggle("active", active);
            tab.setAttribute("aria-selected", String(active));
        });
        panels.forEach(panel => {
            panel.hidden = panel.dataset.socialPanel !== name;
        });
    }

    tabs.forEach(tab => tab.addEventListener("click", () => selectTab(tab.dataset.socialTab)));

    document.querySelectorAll("[data-copy-widget-url]").forEach(button => {
        button.addEventListener("click", async () => {
            const input = document.querySelector(`[data-widget-url="${button.dataset.copyWidgetUrl}"]`);
            if (!input) return;

            try {
                await navigator.clipboard.writeText(input.value);
                button.textContent = "Copied";
            } catch (error) {
                input.select();
                document.execCommand("copy");
                button.textContent = "Copied";
            }

            window.setTimeout(() => { button.textContent = "Copy URL"; }, 1600);
        });
    });
})();
