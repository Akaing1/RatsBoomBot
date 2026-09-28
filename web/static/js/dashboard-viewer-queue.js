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
    const nextCountSelect = panel.querySelector("[data-queue-next-select]");
    const nextCountPicker = nextCountSelect.closest(".queue-next-picker");
    const nextCountLabel = panel.querySelector("[data-queue-next-count]");
    const nextCountStorageKey = `ratsboombot-queue-next-count:${panel.dataset.channelId}`;
    let nextCount = 4;
    let requestInProgress = false;
    let draggingPosition = 0;
    let lastSignature = null;
    let statusFadeTimer = null;
    let touchDrag = null;
    let touchDragTimer = null;
    let mouseDrag = null;
    let dragPreview = null;
    let dragScrollFrame = null;
    let queueAnimating = false;
    let previewLineGeneration = 0;
    const shiftAnimations = new WeakMap();
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let simulationActive = false;
    let actualState = {
        open: stateButton.dataset.open === "true",
        users: [...queueContent.querySelectorAll(".queue-list-item")].map(item => ({
            username: item.dataset.username,
            label: item.querySelector(".queue-username")?.textContent || item.dataset.username
        }))
    };
    let simulatedState = null;

    function updatePreviewLine(list, order) {
        if (!list || !order.length) return;
        const last = order[Math.min(nextCount, order.length) - 1];
        const center = item => {
            const position = item.querySelector(".queue-position");
            return item.offsetTop + position.offsetTop + position.offsetHeight / 2;
        };
        const top = center(order[0]);
        list.style.setProperty("--queue-line-top", `${top}px`);
        list.style.setProperty("--queue-line-height", `${Math.max(0, center(last) - top)}px`);
    }

    function highlightNext() {
        const items = [...queueContent.querySelectorAll(".queue-list-item")];
        const newVisible = Math.min(nextCount, items.length);
        items.forEach((item, index) => {
            item.style.setProperty("--queue-preview-delay", "0ms");
            item.classList.toggle("is-next-preview", index < nextCount);
            item.classList.toggle("is-next-preview-first", index === 0 && newVisible > 0);
            item.classList.toggle("is-next-preview-last", index === newVisible - 1);
        });
        updatePreviewLine(queueContent.querySelector(".queue-list"), items);
    }

    function chooseNextCount(value) {
        const parsed = Number(value);
        nextCount = Number.isInteger(parsed) && parsed >= 1 && parsed <= 10 ? parsed : 4;
        nextCountSelect.value = String(nextCount);
        nextCountLabel.textContent = String(nextCount);
        highlightNext();
    }

    try {
        chooseNextCount(window.localStorage.getItem(nextCountStorageKey));
    } catch (error) {
        chooseNextCount(4);
    }
    nextCountSelect.addEventListener("change", () => {
        chooseNextCount(nextCountSelect.value);
        nextCountPicker.classList.add("is-selection-committed");
        if (!nextCountPicker.matches(":hover")) nextCountPicker.classList.remove("is-selection-committed");
        try { window.localStorage.setItem(nextCountStorageKey, String(nextCount)); } catch (error) { /* Storage is optional. */ }
    });
    nextCountPicker.addEventListener("pointerleave", () => nextCountPicker.classList.remove("is-selection-committed"));

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
        button.dataset.queueItemAction = action;
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

    function grabIndicator() {
        const indicator = document.createElement("span");
        indicator.className = "queue-grab-indicator";
        indicator.setAttribute("aria-hidden", "true");
        return indicator;
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

    function trackPreviewLine(list, rows, duration) {
        const generation = ++previewLineGeneration;
        const until = window.performance.now() + duration;
        const followLine = () => {
            if (!list.isConnected || generation !== previewLineGeneration || rows.some(row => row.parentElement !== list)) return;
            updatePreviewLine(list, rows);
            if (window.performance.now() < until) window.requestAnimationFrame(followLine);
        };
        window.requestAnimationFrame(followLine);
    }

    function renderQueue(data, afterExit = false, movePosition = 0) {
        if (queueAnimating) return;
        const users = updateState(data);
        const signature = JSON.stringify([Boolean(data.open), users]);
        if ((!afterExit && signature === lastSignature) || draggingPosition || touchDrag || mouseDrag) return;
        const previousRows = [...queueContent.querySelectorAll(".queue-list-item")];
        const movedUsername = previousRows[movePosition - 1]?.dataset.username;
        const previousTops = movedUsername && !reduceMotion.matches
            ? new Map(previousRows.map(item => [item.dataset.username, item.getBoundingClientRect().top]))
            : null;
        const previousNames = new Set(previousRows.map(item => item.dataset.username));
        const currentNames = new Set(users.map(member => typeof member === "string" ? member : member.username));
        const removedRows = previousRows.filter(item => !currentNames.has(item.dataset.username));
        if (removedRows.length && !afterExit && !reduceMotion.matches) {
            queueAnimating = true;
            const list = queueContent.querySelector(".queue-list");
            list.classList.add("is-exiting");
            removedRows.forEach((item, index) => {
                item.style.setProperty("--queue-row-height", `${item.getBoundingClientRect().height}px`);
                item.style.setProperty("--queue-exit-delay", `${Math.min(index * 45, 900)}ms`);
                item.classList.add("is-removing");
            });
            const exitDuration = Math.min((removedRows.length - 1) * 45, 900) + 360;
            trackPreviewLine(list, previousRows, exitDuration);
            window.setTimeout(() => {
                queueAnimating = false;
                renderQueue(data, true);
            }, exitDuration);
            return;
        }
        lastSignature = signature;
        previewLineGeneration++;
        const list = queueContent.querySelector(".queue-list");

        if (!users.length) {
            queueContent.replaceChildren();
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

        const nextList = list || document.createElement("ul");
        nextList.className = "queue-list";
        nextList.replaceChildren();
        const addedRows = [];
        users.forEach((member, index) => {
            const username = typeof member === "string" ? member : member.username;
            const label = typeof member === "string" ? member : (member.label || member.username);
            const position = index + 1;
            const item = document.createElement("li");
            item.className = "queue-list-item";
            item.dataset.position = String(position);
            item.dataset.username = username;

            const positionLabel = document.createElement("span");
            positionLabel.className = "queue-position";
            positionLabel.textContent = String(position);
            positionLabel.title = "Drag to reorder";
            const usernameLabel = document.createElement("strong");
            usernameLabel.className = "queue-username";
            usernameLabel.textContent = label;
            const actions = document.createElement("div");
            actions.className = "queue-item-actions";
            if (index > 0) actions.appendChild(actionButton(moveIcon("top"), `Move ${username} to top`, "top", position));
            if (index < users.length - 1) actions.appendChild(actionButton(moveIcon("bottom"), `Move ${username} to bottom`, "bottom", position));
            actions.appendChild(actionButton("🗑", `Remove ${username}`, "remove", position, true));
            item.append(positionLabel, usernameLabel, grabIndicator(), actions);
            nextList.appendChild(item);
            if (!previousNames.has(username)) addedRows.push(item);
        });
        if (!list) queueContent.replaceChildren(nextList);
        highlightNext();
        if (previousTops) {
            nextList.querySelectorAll(".queue-list-item").forEach(item => {
                const previousTop = previousTops.get(item.dataset.username);
                if (previousTop === undefined || typeof item.animate !== "function") return;
                const shift = previousTop - item.getBoundingClientRect().top;
                if (Math.abs(shift) < 1) return;
                if (item.dataset.username === movedUsername) item.classList.add("is-moving");
                const animation = item.animate(
                    [{transform: `translateY(${shift}px)`}, {transform: "translateY(0)"}],
                    {duration: 320, easing: "cubic-bezier(.2,.8,.2,1)"}
                );
                const finish = () => item.classList.remove("is-moving");
                animation.addEventListener("finish", finish, {once: true});
                animation.addEventListener("cancel", finish, {once: true});
            });
        }
        if (!reduceMotion.matches) {
            if (addedRows.length) nextList.classList.add("is-entering");
            addedRows.forEach((item, index) => {
                item.style.setProperty("--queue-row-height", `${item.getBoundingClientRect().height}px`);
                item.style.setProperty("--queue-enter-delay", `${Math.min(index * 45, 600)}ms`);
                item.classList.add("is-appearing");
                item.addEventListener("animationend", () => item.classList.remove("is-appearing"), {once: true});
            });
            if (addedRows.length) {
                const enterDuration = Math.min((addedRows.length - 1) * 45, 600) + 360;
                trackPreviewLine(nextList, [...nextList.querySelectorAll(".queue-list-item")], enterDuration);
                window.setTimeout(() => nextList.classList.remove("is-entering"), enterDuration);
            }
        }
    }

    async function runAction(action, position = 0, newPosition = 0) {
        if (requestInProgress || queueAnimating) return;
        if (action === "clear" && !window.confirm(simulationActive ? "Clear the test viewer queue?" : "Clear the entire viewer queue?")) return;
        const expectedUsers = action === "next"
            ? [...queueContent.querySelectorAll(".is-next-preview")].map(item => item.dataset.username)
            : [];
        if (action === "next" && !expectedUsers.length) {
            showStatus("The viewer queue is empty.");
            return;
        }
        if (simulationActive) {
            const users = simulatedState.users;
            if (action === "toggle") simulatedState.open = !simulatedState.open;
            else if (action === "next") users.splice(0, nextCount);
            else if (action === "clear") users.length = 0;
            else if (action === "remove") users.splice(position - 1, 1);
            else if (["top", "bottom", "reorder"].includes(action)) {
                const [member] = users.splice(position - 1, 1);
                if (member) users.splice(action === "top" ? 0 : action === "bottom" ? users.length : newPosition - 1, 0, member);
            }
            draggingPosition = 0;
            renderQueue(simulatedState, false, action === "top" || action === "bottom" ? position : 0);
            showStatus("Test queue updated; no Twitch action was sent.", "success");
            return;
        }
        requestInProgress = true;
        const data = new FormData();
        data.set("csrf_token", csrfToken);
        data.set("action", action);
        data.set("position", String(position));
        data.set("new_position", String(newPosition));
        if (action === "next") {
            data.set("count", String(nextCount));
            data.set("expected_users", expectedUsers.join(","));
        }
        let stalePreview = false;
        let failedReorder = false;
        try {
            const response = await fetch(actionUrl, {method: "POST", body: data});
            const result = await response.json();
            stalePreview = response.status === 409;
            if (!response.ok) throw new Error(result.detail || "The queue could not be updated.");
            actualState = result;
            draggingPosition = 0;
            lastSignature = null;
            if (!simulationActive) renderQueue(result, false, action === "top" || action === "bottom" ? position : 0);
            showStatus(result.message || "Queue updated.", "success");
        } catch (error) {
            showStatus(error.message, "error");
            if (action === "reorder") {
                lastSignature = null;
                failedReorder = true;
            }
        } finally {
            requestInProgress = false;
            if (stalePreview || failedReorder) refreshQueue();
        }
    }

    async function refreshQueue() {
        if (requestInProgress || queueAnimating || draggingPosition || touchDrag || mouseDrag || document.hidden) return;
        requestInProgress = true;
        try {
            const response = await fetch(stateUrl, {headers: {Accept: "application/json"}, cache: "no-store"});
            if (response.status === 401) return window.location.assign("/connect");
            if (response.ok) {
                actualState = await response.json();
                if (!simulationActive) renderQueue(actualState);
            }
        } finally {
            requestInProgress = false;
        }
    }

    function previewOrder(list, source, placeholder) {
        return [...list.children].filter(item => item === placeholder || (item.classList.contains("queue-list-item") && item !== source));
    }

    function renumberRows(list) {
        [...list.querySelectorAll(".queue-list-item")].forEach((item, index) => {
            item.querySelector(".queue-position").textContent = String(index + 1);
        });
    }

    function updateDragPreviewOrder() {
        if (!dragPreview) return;
        const {list, source, placeholder, ghost} = dragPreview;
        const order = previewOrder(list, source, placeholder);
        const lastHighlighted = Math.min(nextCount, order.length) - 1;
        order.forEach((item, index) => {
            item.querySelector(".queue-position").textContent = String(index + 1);
            item.classList.toggle("is-next-preview", index <= lastHighlighted);
            item.classList.toggle("is-next-preview-first", index === 0);
            item.classList.toggle("is-next-preview-last", index === lastHighlighted);
        });
        const newPosition = order.indexOf(placeholder);
        ghost.querySelector(".queue-position").textContent = String(newPosition + 1);
        ghost.classList.toggle("is-next-preview", newPosition <= lastHighlighted);
        updatePreviewLine(list, order);
    }

    function placeDragPlaceholder(clientY) {
        if (!dragPreview) return;
        const {list, source, placeholder} = dragPreview;
        const rows = [...list.querySelectorAll(".queue-list-item")].filter(item => item !== source);
        const relativeY = clientY - list.getBoundingClientRect().top;
        const index = rows.findIndex(item => relativeY < item.offsetTop + item.offsetHeight / 2);
        const destination = index < 0 ? rows.length : index;
        const current = previewOrder(list, source, placeholder).indexOf(placeholder);
        if (destination === current) {
            updateDragPreviewOrder();
            return;
        }
        const oldTops = new Map(rows.map(item => [item, item.getBoundingClientRect().top]));
        list.insertBefore(placeholder, rows[destination] || null);
        if (!reduceMotion.matches) {
            rows.forEach(item => {
                if (typeof item.animate !== "function") return;
                const shift = oldTops.get(item) - item.getBoundingClientRect().top;
                if (Math.abs(shift) < 1) return;
                shiftAnimations.get(item)?.cancel();
                shiftAnimations.set(item, item.animate(
                    [{transform: `translateY(${shift}px)`}, {transform: "translateY(0)"}],
                    {duration: 180, easing: "cubic-bezier(.2,.8,.2,1)"}
                ));
            });
        }
        updateDragPreviewOrder();
    }

    function moveDragPreview(clientX, clientY) {
        if (!dragPreview) return;
        dragPreview.x = clientX;
        dragPreview.y = clientY;
        dragPreview.ghost.style.left = `${clientX - dragPreview.offsetX}px`;
        dragPreview.ghost.style.top = `${clientY - dragPreview.offsetY}px`;
        placeDragPlaceholder(clientY);
    }

    function scrollWhileDragging() {
        dragScrollFrame = null;
        if (!dragPreview) return;
        const bounds = queueContent.getBoundingClientRect();
        const edge = 42;
        const direction = dragPreview.y < bounds.top + edge ? -1 : dragPreview.y > bounds.bottom - edge ? 1 : 0;
        if (direction) queueContent.scrollTop += direction * 12;
        placeDragPlaceholder(dragPreview.y);
        dragScrollFrame = window.requestAnimationFrame(scrollWhileDragging);
    }

    function beginDrag(source, clientX, clientY) {
        const rect = source.getBoundingClientRect();
        const list = source.parentElement;
        const ghost = source.cloneNode(true);
        ghost.classList.add("queue-drag-ghost");
        ghost.setAttribute("aria-hidden", "true");
        ghost.style.width = `${rect.width}px`;
        ghost.style.height = `${rect.height}px`;
        ghost.style.left = `${rect.left}px`;
        ghost.style.top = `${rect.top}px`;
        document.body.appendChild(ghost);

        const placeholder = document.createElement("li");
        placeholder.className = "queue-drop-placeholder";
        placeholder.setAttribute("aria-hidden", "true");
        placeholder.style.height = `${rect.height}px`;
        const position = document.createElement("span");
        position.className = "queue-position";
        position.textContent = source.dataset.position;
        const label = document.createElement("strong");
        label.textContent = "Drop here";
        placeholder.append(position, label);
        list.insertBefore(placeholder, source);
        source.classList.add("dragging");
        source.style.display = "none";
        list.classList.add("is-reordering");
        draggingPosition = Number(source.dataset.position);
        dragPreview = {source, list, placeholder, ghost, offsetX: clientX - rect.left, offsetY: clientY - rect.top, x: clientX, y: clientY};
        placeDragPlaceholder(clientY);
        window.requestAnimationFrame(() => {
            if (ghost.isConnected && !ghost.classList.contains("is-dropping")) ghost.classList.add("is-lifted");
        });
        dragScrollFrame = window.requestAnimationFrame(scrollWhileDragging);
    }

    function finishDrag(commit) {
        if (dragScrollFrame !== null) window.cancelAnimationFrame(dragScrollFrame);
        dragScrollFrame = null;
        if (!dragPreview) return;
        const {source, list, placeholder, ghost} = dragPreview;
        const originalPosition = draggingPosition;
        const newPosition = previewOrder(list, source, placeholder).indexOf(placeholder) + 1;
        const destination = placeholder.getBoundingClientRect();
        dragPreview = null;
        ghost.querySelector(".queue-position").textContent = String(commit ? newPosition : originalPosition);
        list.querySelectorAll(".queue-list-item").forEach(item => {
            shiftAnimations.get(item)?.cancel();
            shiftAnimations.delete(item);
        });
        if (commit && newPosition !== originalPosition) list.insertBefore(source, placeholder);
        placeholder.remove();
        source.style.display = "";
        source.classList.remove("dragging");
        list.classList.remove("is-reordering");
        renumberRows(list);
        highlightNext();
        ghost.style.left = `${commit ? destination.left : source.getBoundingClientRect().left}px`;
        ghost.style.top = `${commit ? destination.top : source.getBoundingClientRect().top}px`;
        ghost.classList.add("is-dropping");
        window.setTimeout(() => ghost.remove(), 180);
        draggingPosition = 0;
        if (commit && newPosition !== originalPosition) runAction("reorder", originalPosition, newPosition);
    }

    function endTouchDrag(commit) {
        window.clearTimeout(touchDragTimer);
        touchDragTimer = null;
        if (!touchDrag) return;
        const active = touchDrag.active;
        touchDrag = null;
        if (active) finishDrag(commit);
    }

    queueContent.addEventListener("pointerdown", event => {
        if (event.pointerType === "touch" || event.button !== 0 || requestInProgress || queueAnimating || event.target.closest("button, a, select, input, form")) return;
        const source = event.target.closest(".queue-list-item");
        if (!source) return;
        mouseDrag = {source, id: event.pointerId, x: event.clientX, y: event.clientY, active: false};
    });
    window.addEventListener("pointermove", event => {
        if (!mouseDrag || event.pointerId !== mouseDrag.id) return;
        if (event.buttons === 0) {
            mouseDrag = null;
            finishDrag(false);
            return;
        }
        if (!mouseDrag.active && Math.hypot(event.clientX - mouseDrag.x, event.clientY - mouseDrag.y) < 5) return;
        if (!mouseDrag.active) {
            beginDrag(mouseDrag.source, mouseDrag.x, mouseDrag.y);
            mouseDrag.active = true;
        }
        event.preventDefault();
        moveDragPreview(event.clientX, event.clientY);
    });
    window.addEventListener("pointerup", event => {
        if (!mouseDrag || event.pointerId !== mouseDrag.id) return;
        const active = mouseDrag.active;
        mouseDrag = null;
        if (active) finishDrag(true);
    });
    window.addEventListener("pointercancel", event => {
        if (!mouseDrag || event.pointerId !== mouseDrag.id) return;
        mouseDrag = null;
        finishDrag(false);
    });
    window.addEventListener("blur", () => {
        mouseDrag = null;
        endTouchDrag(false);
        finishDrag(false);
    });
    document.addEventListener("keydown", event => {
        if (event.key !== "Escape" || !dragPreview) return;
        mouseDrag = null;
        endTouchDrag(false);
        finishDrag(false);
    });

    queueContent.addEventListener("touchstart", event => {
        if (event.touches.length !== 1) {
            endTouchDrag(false);
            return;
        }
        if (requestInProgress || queueAnimating || event.target.closest("button, a, select, input, form")) return;
        const source = event.target.closest(".queue-list-item");
        if (!source) return;
        const touch = event.changedTouches[0];
        touchDrag = {source, id: touch.identifier, x: touch.clientX, y: touch.clientY, active: false};
        touchDragTimer = window.setTimeout(() => {
            if (!touchDrag) return;
            touchDrag.active = true;
            beginDrag(touchDrag.source, touchDrag.x, touchDrag.y);
        }, 300);
    }, {passive: true});
    document.addEventListener("touchmove", event => {
        if (!touchDrag) return;
        const touch = [...event.changedTouches].find(candidate => candidate.identifier === touchDrag.id);
        if (!touch) return;
        if (!touchDrag.active && Math.hypot(touch.clientX - touchDrag.x, touch.clientY - touchDrag.y) > 10) {
            endTouchDrag(false);
            return;
        }
        if (!touchDrag.active) return;
        event.preventDefault();
        moveDragPreview(touch.clientX, touch.clientY);
    }, {passive: false});
    document.addEventListener("touchend", event => {
        if (touchDrag && [...event.changedTouches].some(touch => touch.identifier === touchDrag.id)) endTouchDrag(true);
    });
    document.addEventListener("touchcancel", () => endTouchDrag(false));
    queueContent.addEventListener("contextmenu", event => {
        if (touchDrag?.active) event.preventDefault();
    });

    // Browser-console preview only: dummy viewers and queue actions stay in this tab.
    window.dashboardQueueTest = {
        add(count = 1) {
            const amount = Number(count);
            if (!Number.isInteger(amount) || amount < 1 || amount > 100) {
                throw new RangeError("Count must be between 1 and 100 dummy viewers.");
            }
            if (queueAnimating || draggingPosition || touchDrag || mouseDrag) throw new Error("Wait for the queue animation to finish before changing the test queue.");
            if (!simulationActive) {
                simulatedState = {
                    open: actualState.open,
                    users: actualState.users.map(member => typeof member === "string" ? member : {...member})
                };
                simulationActive = true;
            }
            const names = ["squid", "car", "mina", "rat", "pee", "nyxi", "birb"];
            const taken = new Set(simulatedState.users.map(member => typeof member === "string" ? member : member.username));
            const added = [];
            for (let index = 0; index < amount; index += 1) {
                const base = `test_${names[Math.floor(Math.random() * names.length)]}`;
                let username = base;
                let suffix = 2;
                while (taken.has(username)) username = `${base}${suffix++}`;
                taken.add(username);
                simulatedState.users.push({username, label: username});
                added.push(username);
            }
            draggingPosition = 0;
            renderQueue(simulatedState);
            console.info("Added preview viewers:", added.join(", "));
            return added;
        },
        stop() {
            if (!simulationActive) return;
            if (queueAnimating || draggingPosition || touchDrag || mouseDrag) throw new Error("Wait for the queue animation to finish before stopping the test queue.");
            simulationActive = false;
            simulatedState = null;
            draggingPosition = 0;
            lastSignature = null;
            renderQueue(actualState);
            showStatus("Test queue preview ended.");
            void refreshQueue();
        }
    };

    stateButton.addEventListener("click", () => runAction("toggle"));
    panel.querySelectorAll("[data-queue-action]").forEach(button => {
        button.addEventListener("click", () => runAction(button.dataset.queueAction));
    });
    refreshQueue();
    window.setInterval(refreshQueue, 2000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshQueue(); });
})();
