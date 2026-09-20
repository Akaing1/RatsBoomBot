(() => {
    const panel = document.querySelector("[data-viewer-queue-panel]");
    if (!panel) return;
    const stateUrl = panel.dataset.stateUrl;
    const actionUrl = panel.dataset.actionUrl;
    const csrfToken = panel.dataset.csrfToken;
    const queueContent = document.getElementById("viewer-queue-content");
    const stateButton = panel.querySelector("[data-queue-toggle]");
    const count = panel.querySelector("[data-queue-count]");
    const status = panel.querySelector("[data-queue-action-status]");
    let requestInProgress = false;
    let draggingPosition = 0;
    let lastSignature = null;
    let statusFadeTimer = null;

    function showStatus(message, tone = "") {
        window.clearTimeout(statusFadeTimer);
        status.className = `queue-action-status${tone ? ` ${tone}` : ""}`;
        status.textContent = message;
        statusFadeTimer = window.setTimeout(() => status.classList.add("is-fading"), 3000);
    }

    function actionButton(symbol, label, action, position, dangerous = false, iconClass = "") {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `queue-item-action${dangerous ? " danger" : ""}`;
        if (iconClass) button.classList.add(iconClass);
        if (typeof symbol === "string") button.textContent = symbol;
        else button.appendChild(symbol);
        button.title = label;
        button.setAttribute("aria-label", label);
        button.addEventListener("click", () => runAction(action, position));
        return button;
    }

    function moveIcon(direction) {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("aria-hidden", "true");
        const bar = document.createElementNS(svg.namespaceURI, "path");
        const chevron = document.createElementNS(svg.namespaceURI, "path");
        if (direction === "top") {
            bar.setAttribute("d", "M5 5h14");
            chevron.setAttribute("d", "m6 13 6-6 6 6");
        } else {
            bar.setAttribute("d", "M5 19h14");
            chevron.setAttribute("d", "m6 11 6 6 6-6");
        }
        svg.append(bar, chevron);
        return svg;
    }

    function updateState(data) {
        const isOpen = Boolean(data.open);
        const users = Array.isArray(data.users) ? data.users : [];
        stateButton.dataset.open = String(isOpen);
        stateButton.classList.toggle("live", isOpen);
        stateButton.querySelector(".queue-state-current").textContent = isOpen ? "Open" : "Closed";
        stateButton.querySelector(".queue-state-alternate").textContent = isOpen ? "Close" : "Open";
        count.textContent = `${users.length} queued`;
        return users;
    }

    function renderQueue(data) {
        const users = updateState(data);
        const signature = JSON.stringify([Boolean(data.open), users]);
        if (signature === lastSignature || draggingPosition) return;
        lastSignature = signature;
        queueContent.replaceChildren();

        if (!users.length) {
            const empty = document.createElement("div");
            empty.className = "compact-empty-state";
            const heading = document.createElement("h4");
            heading.textContent = "The queue is empty";
            const message = document.createElement("p");
            message.textContent = data.open ? "Viewers can join with !join." : "The viewer queue is currently closed.";
            empty.append(heading, message);
            queueContent.appendChild(empty);
            return;
        }

        const list = document.createElement("ul");
        list.className = "queue-list";
        users.forEach((member, index) => {
            const username = typeof member === "string" ? member : member.username;
            const label = typeof member === "string" ? member : (member.label || member.username);
            const position = index + 1;
            const item = document.createElement("li");
            item.className = "queue-list-item";
            item.draggable = true;
            item.dataset.position = String(position);

            const positionLabel = document.createElement("span");
            positionLabel.className = "queue-position";
            positionLabel.textContent = String(position);
            positionLabel.title = "Drag to reorder";
            const usernameLabel = document.createElement("strong");
            usernameLabel.className = "queue-username";
            usernameLabel.textContent = label;
            const actions = document.createElement("div");
            actions.className = "queue-item-actions";
            actions.append(
                actionButton(moveIcon("top"), `Move ${username} to top`, "top", position),
                actionButton(moveIcon("bottom"), `Move ${username} to bottom`, "bottom", position),
                actionButton("🗑", `Remove ${username}`, "remove", position, true)
            );
            item.append(positionLabel, usernameLabel, actions);

            item.addEventListener("dragstart", event => {
                draggingPosition = position;
                item.classList.add("dragging");
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData("text/plain", String(position));
            });
            item.addEventListener("dragover", event => {
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                item.classList.add("drag-target");
            });
            item.addEventListener("dragleave", () => item.classList.remove("drag-target"));
            item.addEventListener("drop", event => {
                event.preventDefault();
                item.classList.remove("drag-target");
                if (draggingPosition && draggingPosition !== position) runAction("reorder", draggingPosition, position);
            });
            item.addEventListener("dragend", () => {
                draggingPosition = 0;
                item.classList.remove("dragging");
                list.querySelectorAll(".drag-target").forEach(target => target.classList.remove("drag-target"));
            });
            list.appendChild(item);
        });
        queueContent.appendChild(list);
    }

    async function runAction(action, position = 0, newPosition = 0) {
        if (requestInProgress) return;
        if (action === "clear" && !window.confirm("Clear the entire viewer queue?")) return;
        requestInProgress = true;
        const data = new FormData();
        data.set("csrf_token", csrfToken);
        data.set("action", action);
        data.set("position", String(position));
        data.set("new_position", String(newPosition));
        try {
            const response = await fetch(actionUrl, {method: "POST", body: data});
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || "The queue could not be updated.");
            draggingPosition = 0;
            lastSignature = null;
            renderQueue(result);
            showStatus(result.message || "Queue updated.", "success");
        } catch (error) {
            showStatus(error.message, "error");
        } finally {
            requestInProgress = false;
        }
    }

    async function refreshQueue() {
        if (requestInProgress || draggingPosition || document.hidden) return;
        requestInProgress = true;
        try {
            const response = await fetch(stateUrl, {headers: {Accept: "application/json"}, cache: "no-store"});
            if (response.status === 401) return window.location.assign("/connect");
            if (response.ok) renderQueue(await response.json());
        } finally {
            requestInProgress = false;
        }
    }

    stateButton.addEventListener("click", () => runAction("toggle"));
    panel.querySelectorAll("[data-queue-action]").forEach(button => {
        button.addEventListener("click", () => runAction(button.dataset.queueAction));
    });
    refreshQueue();
    window.setInterval(refreshQueue, 2000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshQueue(); });
})();
