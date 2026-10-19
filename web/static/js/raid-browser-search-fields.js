(() => {
    const form = document.querySelector("[data-raid-browser-search]");
    if (!form) return;
    for (const input of form.querySelectorAll('input[type="search"]')) {
        const wrapper = document.createElement("span");
        wrapper.className = "raid-browser-search-field";
        const clear = document.createElement("button");
        clear.type = "button";
        clear.className = "raid-browser-search-clear";
        clear.title = "Clear";
        const label = input.getAttribute("aria-label") || input.closest("label")?.firstChild?.textContent.trim() || "search";
        clear.setAttribute("aria-label", `Clear ${label}`);
        clear.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
        clear.addEventListener("pointerdown", event => event.preventDefault());
        clear.addEventListener("click", () => {
            input.value = "";
            input.focus({preventScroll: true});
            input.dispatchEvent(new Event("input", {bubbles: true}));
        });
        input.before(wrapper);
        wrapper.append(input, clear);
    }
})();
