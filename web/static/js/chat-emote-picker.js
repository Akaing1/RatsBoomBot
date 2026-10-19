(() => {
    // The dashboard and raid preview share the same picker layout and section renderer.
    window.createChatEmotePicker = ({picker, getEmotes, getPersonalGroup = () => "", insert}) => {
    let closed = false, emotes = [], personalGroup = "", selectedGroup = null;
    let sortedSource = null, sortedEmotes = [];
    const insertValue = value => { if (!closed) insert(value); };
    const element = (tag, className, text) => {
        const node = document.createElement(tag); node.className = className;
        if (text) node.textContent = text;
        return node;
    };
    let emoteSearch = picker.querySelector?.("[data-emote-search]");
    let emoteGroup, emoteChannels, seventvButton, emoteGrid, emoteCount, emoteNote;
    if (emoteSearch) {
        emoteGroup = picker.querySelector("[data-emote-group]");
        emoteChannels = picker.querySelector("[data-emote-channels]");
        seventvButton = picker.querySelector("[data-emote-seventv]");
        emoteGrid = picker.querySelector("[data-emote-grid]");
        emoteCount = picker.querySelector("[data-emote-count]");
        emoteNote = picker.querySelector("[data-emote-note]");
    } else {
        const header = element("div", "chat-emote-picker-header");
        emoteSearch = element("input", ""); emoteSearch.type = "search";
        emoteSearch.placeholder = "Search emotes…"; emoteSearch.autocomplete = "off";
        emoteSearch.setAttribute("aria-label", "Search emotes");
        const count = element("span", "chat-emote-count");
        emoteCount = element("strong", ""); count.append(emoteCount, element("span", "", "emotes"));
        header.append(emoteSearch, count);
        const body = element("div", "chat-emote-picker-body");
        emoteGrid = element("div", "chat-emote-grid");
        emoteGroup = element("div", "chat-emote-rail"); emoteGroup.setAttribute("role", "group");
        emoteGroup.setAttribute("aria-label", "Filter emotes by section; select again to show all");
        emoteChannels = element("div", "chat-emote-channel-list");
        seventvButton = element("button", "chat-emote-section-button chat-emote-seventv", "7TV");
        seventvButton.type = "button"; seventvButton.setAttribute("aria-pressed", "false");
        emoteGroup.append(emoteChannels, seventvButton); body.append(emoteGrid, emoteGroup);
        emoteNote = element("p", "chat-emote-picker-note"); emoteNote.setAttribute("role", "status");
        picker.replaceChildren(header, body, emoteNote);
    }

    function groupKey(emote) {
        return emote.group_key || (emote.provider === "7tv" ? "7tv" : `${emote.provider || "twitch"}:other`);
    }

    function orderedGroups() {
        const groups = new Map();
        emotes.forEach(emote => groups.set(groupKey(emote), {
            key: groupKey(emote), label: emote.group || (emote.provider || "twitch").toUpperCase(), image: emote.group_image || ""
        }));
        const rank = key => key === personalGroup ? 0 : key === "7tv" ? 3 : key === "twitch:global" ? 2 : 1;
        return Array.from(groups.values()).sort((a, b) => rank(a.key) - rank(b.key)
            || a.label.localeCompare(b.label, undefined, {sensitivity: "base"}));
    }

    function setGroupIcon(button, group) {
        button.replaceChildren();
        button.title = group.key === personalGroup ? `Your channel · ${group.label}` : group.label;
        button.setAttribute("aria-label", button.title);
        const fallback = document.createElement("span");
        fallback.textContent = group.key === "7tv" ? "7TV" : group.label.slice(0, 2);
        const image = document.createElement("img");
        image.alt = "";
        image.src = group.key === "7tv" ? "/static/img/7tv.svg"
            : /^https:\/\/[^/]*jtvnw\.net\//.test(group.image) ? group.image
            : "/static/img/twitch.svg";
        image.addEventListener("error", () => image.replaceWith(fallback), {once: true});
        button.appendChild(image);
    }

    function emoteSrcset(url) {
        const larger = url.includes("static-cdn.jtvnw.net/")
            ? url.replace(/\/2\.0$/, "/3.0")
            : url.replace(/\/2x\.webp$/, "/3x.webp");
        return larger === url ? "" : `${url} 2x, ${larger} 3x`;
    }

    function renderPicker() {
        if (closed) return;
        emotes = getEmotes(); personalGroup = getPersonalGroup();
        // Catalogs are replaced on refresh; searches only change the filter.
        if (sortedSource !== emotes) {
            sortedEmotes = [...emotes].sort((left, right) => left.name.localeCompare(right.name, undefined, {sensitivity: "variant"}));
            sortedSource = emotes;
        }
        const query = emoteSearch.value.trim().toLocaleLowerCase();
        const matches = sortedEmotes.filter(emote =>
            (selectedGroup === null || groupKey(emote) === selectedGroup)
            && (!query || emote.name.toLocaleLowerCase().includes(query))
        );
        emoteGrid.replaceChildren();
        emoteGrid.scrollTop = 0;
        emoteCount.textContent = String(matches.length);
        const grouped = new Map();
        for (const emote of matches) {
            const key = groupKey(emote);
            if (!grouped.has(key)) grouped.set(key, []);
            grouped.get(key).push(emote);
        }

        orderedGroups().forEach(group => {
            const items = grouped.get(group.key) || [];
            if (!items.length) return;
            const section = document.createElement("section");
            section.className = "chat-emote-section";
            const heading = document.createElement("h4");
            heading.textContent = group.key === personalGroup ? `Your channel · ${group.label}` : group.label;
            const grid = document.createElement("div");
            grid.className = "chat-emote-section-grid";
            items.forEach(emote => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "chat-emote-option";
            button.title = `${emote.name} · ${emote.group || (emote.provider || "twitch").toUpperCase()}`;
            button.setAttribute("aria-label", button.title);

            const image = document.createElement("img");
            image.src = emote.url;
            image.srcset = emoteSrcset(emote.url);
            image.alt = "";
            image.loading = "lazy";
            image.decoding = "async";

            const label = document.createElement("span");
            label.textContent = emote.name;
            button.append(image, label);
            button.addEventListener("mousedown", event => event.preventDefault());
            button.addEventListener("click", () => insertValue(emote.name));
            grid.appendChild(button);
            });
            section.append(heading, grid);
            emoteGrid.appendChild(section);
        });
    }

    function renderGroupOptions() {
        if (closed) return;
        emotes = getEmotes(); personalGroup = getPersonalGroup();
        const groups = orderedGroups();
        if (!groups.some(group => group.key === selectedGroup)) selectedGroup = null;
        emoteChannels.replaceChildren();
        groups.filter(group => group.key !== "7tv").forEach(group => {
                const key = group.key;
                const button = document.createElement("button");
                button.type = "button";
                button.className = "chat-emote-section-button";
                button.dataset.emoteSection = key;
                setGroupIcon(button, group);
                button.addEventListener("click", () => selectEmoteGroup(key));
                emoteChannels.appendChild(button);
            });
        seventvButton.dataset.emoteSection = "7tv";
        setGroupIcon(seventvButton, {key: "7tv", label: "7TV", image: ""});
        updateGroupButtons();
    }

    function updateGroupButtons() {
        [...emoteChannels.children, seventvButton].forEach(button => {
            button.setAttribute("aria-pressed", String(button.dataset.emoteSection === selectedGroup));
        });
    }

    function selectEmoteGroup(key) {
        selectedGroup = selectedGroup === key ? null : key;
        updateGroupButtons();
        renderPicker();
    }

    emoteSearch.addEventListener("input", renderPicker);
    const selectSevenTv = () => { if (!closed) selectEmoteGroup("7tv"); };
    seventvButton.addEventListener("click", selectSevenTv);
    return {search: emoteSearch, note: emoteNote, render: renderPicker, renderGroups: renderGroupOptions,
        destroy() {
            if (closed) return;
            closed = true;
            emoteSearch.removeEventListener("input", renderPicker);
            seventvButton.removeEventListener("click", selectSevenTv);
        }};
    };
})();
