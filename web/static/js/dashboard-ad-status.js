(() => {
    const container = document.querySelector("[data-ad-status]");
    if (!container) return;

    const label = container.querySelector("[data-ad-status-text]");
    const progressRing = container.querySelector("[data-ad-progress-ring]");
    const completionCheck = container.querySelector(".dashboard-ad-progress-check");
    const panel = document.querySelector("[data-ad-panel]");
    const actionStatus = panel?.querySelector("[data-ad-action-status]");
    const actionButtons = Array.from(panel?.querySelectorAll("[data-ad-action]") || []);
    let refreshInProgress = false;
    let actionInProgress = false;
    let simulationActive = false;
    let simulationStartTimer = null;
    let completionTimer = null;
    let ringIntroTimer = null;
    let ringIntroActive = false;
    let ringCountdownActive = false;
    let scheduledRefreshAt = "";
    let actualStatus = {
        state: container.dataset.state,
        label: label.textContent,
        next_ad_at: container.dataset.nextAdAt,
        started_at: container.dataset.startedAt,
        ends_at: container.dataset.endsAt,
        snoozes_available: container.dataset.snoozesAvailable
    };
    const ringCircumference = 2 * Math.PI * 9;
    const appearanceClasses = ["ad-neutral", "ad-idle", "ad-scheduled", "ad-warning", "ad-running", "ad-complete"];

    function formatDuration(totalSeconds) {
        const seconds = Math.max(0, Math.ceil(totalSeconds));
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainder = seconds % 60;
        if (hours) return `${hours}h ${minutes}m`;
        if (minutes) return `${minutes}m ${remainder}s`;
        return `${remainder}s`;
    }

    function setAppearance(appearance) {
        if (container.classList.contains(appearance)) return;
        container.classList.remove(...appearanceClasses);
        container.classList.add(appearance);
    }

    function clearRingIntro() {
        if (ringIntroTimer !== null) window.clearTimeout(ringIntroTimer);
        ringIntroTimer = null;
        ringIntroActive = false;
        container.classList.remove("ad-ring-intro");
    }

    function clearRingCountdown() {
        ringCountdownActive = false;
        container.classList.remove("ad-ring-countdown");
    }

    function beginRingCountdown(fromFull = true) {
        if (!progressRing || container.dataset.state !== "running") return;
        const remainingMs = new Date(container.dataset.endsAt).getTime() - Date.now();
        if (!Number.isFinite(remainingMs) || remainingMs <= 0) {
            render();
            return;
        }
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            clearRingCountdown();
            render();
            return;
        }
        const fromOffset = fromFull ? 0 : parseFloat(window.getComputedStyle(progressRing).strokeDashoffset) || 0;
        clearRingCountdown();
        progressRing.style.strokeDashoffset = String(fromOffset);
        progressRing.style.setProperty("--ad-ring-from", String(fromOffset));
        progressRing.style.setProperty("--ad-ring-duration", `${remainingMs}ms`);
        void progressRing.getBoundingClientRect();
        ringCountdownActive = true;
        container.classList.add("ad-ring-countdown");
    }

    function beginRingIntro() {
        if (!progressRing) return;
        clearRingIntro();
        clearRingCountdown();
        ringIntroActive = true;
        progressRing.style.strokeDashoffset = String(ringCircumference);
        container.classList.add("ad-ring-intro");
        const animationSeconds = parseFloat(window.getComputedStyle(progressRing).animationDuration) || 0;
        if (animationSeconds <= 0) {
            clearRingIntro();
            beginRingCountdown();
            return;
        }
        ringIntroTimer = window.setTimeout(() => {
            clearRingIntro();
            beginRingCountdown();
        }, animationSeconds * 1000);
    }

    function showCompletion() {
        if (completionTimer !== null) return;
        displayStatus({state: "complete", label: "Ads finished"});
        const animationSeconds = completionCheck
            ? parseFloat(window.getComputedStyle(completionCheck).animationDuration) || 0
            : 0;
        completionTimer = window.setTimeout(() => {
            completionTimer = null;
            simulationActive = false;
            const expiredStatus = actualStatus.state === "running" &&
                new Date(actualStatus.ends_at).getTime() <= Date.now();
            displayStatus(expiredStatus ? {state: "none", label: "Checking next ad…"} : actualStatus);
            void refresh();
        }, 5000 + animationSeconds * 1000);
        render();
        void refresh();
    }

    function render() {
        const now = Date.now();
        if (container.dataset.state === "running" && container.dataset.endsAt) {
            const endsAt = new Date(container.dataset.endsAt).getTime();
            const remaining = (endsAt - now) / 1000;
            if (remaining <= 0) {
                showCompletion();
                return;
            }
            label.textContent = `Ends in ${formatDuration(remaining)}`;
            const startedAt = new Date(container.dataset.startedAt).getTime();
            const duration = endsAt - startedAt;
            const fraction = duration > 0 ? Math.min(1, Math.max(0, (endsAt - now) / duration)) : 0;
            if (progressRing && !ringIntroActive && !ringCountdownActive) {
                progressRing.style.strokeDashoffset = String(ringCircumference * (1 - fraction));
            }
            setAppearance("ad-running");
        } else if (container.dataset.state === "scheduled" && container.dataset.nextAdAt) {
            const remaining = (new Date(container.dataset.nextAdAt).getTime() - now) / 1000;
            label.textContent = remaining > 0 ? `Starts in ${formatDuration(remaining)}` : "Starting…";
            if (remaining <= 0) {
                setAppearance("ad-warning");
                if (!simulationActive && scheduledRefreshAt !== container.dataset.nextAdAt) {
                    scheduledRefreshAt = container.dataset.nextAdAt;
                    void refresh();
                }
            } else if (remaining < 60) {
                setAppearance("ad-warning");
            } else {
                setAppearance("ad-scheduled");
            }
        } else if (container.dataset.state === "offline") {
            setAppearance("ad-neutral");
        } else if (container.dataset.state === "complete") {
            setAppearance("ad-complete");
        } else {
            setAppearance("ad-idle");
        }
        const state = container.dataset.state;
        const snoozes = container.dataset.snoozesAvailable;
        actionButtons.forEach(button => {
            button.disabled = simulationActive || completionTimer !== null || actionInProgress || state === "offline" ||
                (button.dataset.adAction === "snooze" &&
                    (state !== "scheduled" || (snoozes !== "" && Number(snoozes) <= 0))) ||
                (button.dataset.adAction !== "snooze" && state === "running");
        });
    }

    function displayStatus(data) {
        const enteringRunning = data.state === "running" && container.dataset.state !== "running";
        const previousEndsAt = container.dataset.endsAt;
        if (data.state !== "running") {
            clearRingIntro();
            clearRingCountdown();
        }
        Array.from(container.classList).filter(name => name.startsWith("state-")).forEach(name => container.classList.remove(name));
        container.classList.add(`state-${data.state}`);
        container.dataset.state = data.state;
        container.dataset.nextAdAt = data.next_ad_at || "";
        container.dataset.startedAt = data.started_at || "";
        container.dataset.endsAt = data.ends_at || "";
        container.dataset.snoozesAvailable = data.snoozes_available ?? "";
        label.textContent = data.label;
        render();
        if (enteringRunning && container.dataset.state === "running") beginRingIntro();
        else if (data.state === "running" && previousEndsAt !== container.dataset.endsAt && ringCountdownActive) {
            beginRingCountdown(false);
        }
    }

    function applyStatus(data) {
        actualStatus = data;
        if (!simulationActive && completionTimer === null) displayStatus(data);
    }

    function startSimulatedAd(durationSeconds) {
        const startedAt = Date.now();
        displayStatus({
            state: "running", label: "Ad running", next_ad_at: null,
            started_at: new Date(startedAt).toISOString(),
            ends_at: new Date(startedAt + durationSeconds * 1000).toISOString(),
            snoozes_available: null
        });
    }

    function prepareSimulation() {
        if (completionTimer !== null) window.clearTimeout(completionTimer);
        if (simulationStartTimer !== null) window.clearTimeout(simulationStartTimer);
        completionTimer = null;
        simulationStartTimer = null;
        simulationActive = true;
    }

    function checkedSeconds(value, minimum, name) {
        const seconds = Number(value);
        if (!Number.isFinite(seconds) || seconds < minimum || seconds > 3600) {
            throw new RangeError(`${name} must be between ${minimum} and 3600 seconds.`);
        }
        return seconds;
    }

    // Browser-console preview only: ad controls are disabled and no Twitch action is sent.
    window.dashboardAdTest = {
        start(seconds = 15) {
            const duration = checkedSeconds(seconds, 1, "Duration");
            prepareSimulation();
            startSimulatedAd(duration);
        },
        schedule(secondsUntilStart = 5, durationSeconds = 15) {
            const wait = checkedSeconds(secondsUntilStart, 0, "Delay");
            const duration = checkedSeconds(durationSeconds, 1, "Duration");
            prepareSimulation();
            displayStatus({
                state: "scheduled", label: "Next ad",
                next_ad_at: new Date(Date.now() + wait * 1000).toISOString(),
                started_at: null, ends_at: null, snoozes_available: null
            });
            simulationStartTimer = window.setTimeout(() => {
                simulationStartTimer = null;
                if (simulationActive) startSimulatedAd(duration);
            }, wait * 1000);
        },
        stop() {
            if (!simulationActive) return;
            if (simulationStartTimer !== null) window.clearTimeout(simulationStartTimer);
            if (completionTimer !== null) window.clearTimeout(completionTimer);
            simulationStartTimer = null;
            completionTimer = null;
            simulationActive = false;
            displayStatus(actualStatus);
            void refresh();
        }
    };

    async function runAction(action) {
        if (actionInProgress || simulationActive) return;
        if (action !== "snooze" && !window.confirm(`Start a ${action === "run-90" ? "90-second" : "3-minute"} ad now?`)) return;
        actionInProgress = true;
        actionStatus.textContent = "Working…";
        actionStatus.className = "dashboard-ad-action-status";
        render();
        const body = new FormData();
        body.set("action", action);
        body.set("csrf_token", panel.dataset.csrfToken);
        try {
            const response = await fetch(panel.dataset.actionUrl, {method: "POST", body, headers: {Accept: "application/json"}});
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "Twitch could not complete that ad action.");
            if (data.status) applyStatus(data.status);
            actionStatus.textContent = data.message || "Ad action completed.";
            actionStatus.classList.add("success");
        } catch (error) {
            actionStatus.textContent = error.message || "Ad action failed.";
            actionStatus.classList.add("error");
        } finally {
            actionInProgress = false;
            render();
        }
    }

    async function refresh() {
        if (refreshInProgress) return;
        refreshInProgress = true;
        try {
            const response = await fetch("/channel/api/ad-status", {headers: {Accept: "application/json"}});
            if (response.ok) applyStatus(await response.json());
        } catch (error) {
            // Keep the last known schedule during transient network failures.
        } finally {
            refreshInProgress = false;
        }
    }

    render();
    if (container.dataset.state === "running") beginRingIntro();
    actionButtons.forEach(button => button.addEventListener("click", () => runAction(button.dataset.adAction)));
    window.setInterval(render, 1000);
    window.setInterval(refresh, 30000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
})();
