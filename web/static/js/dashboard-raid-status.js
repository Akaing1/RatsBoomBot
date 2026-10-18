(() => {
    const banner = document.querySelector("[data-pending-raid]");
    if (!banner) return;
    const channel = banner.querySelector("[data-pending-raid-channel]");
    const text = banner.querySelector("[data-pending-raid-text]");
    const cancel = banner.querySelector("[data-pending-raid-cancel]");
    const avatar = banner.querySelector("[data-pending-raid-avatar]");
    const follow = banner.querySelector("[data-pending-raid-follow]");
    const followDefault = follow?.checked !== false;
    let poll = null, polling = false, followed = false, navigationArmed = false;
    avatar?.addEventListener("error", () => { avatar.hidden = true; });
    let pending = null, clock = null, revision = 0;

    function stopClock() { clearInterval(clock); clock = null; }
    function followRaid() {
        if (!navigationArmed || followed || !follow?.checked || cancel.disabled || !/^[A-Za-z0-9_]{1,25}$/.test(pending?.login || "")) return;
        followed = true;
        window.location.assign(`https://www.twitch.tv/${encodeURIComponent(pending.login)}`);
    }
    function updateTime() {
        if (!pending) return;
        const seconds = pending.completed ? 0 : Math.max(0, Math.ceil(Number(pending.expires_at) - Date.now() / 1000));
        text.textContent = seconds ? `Raid queued on Twitch · ${seconds}s. Use Twitch chat for Raid Now.`
            : "Countdown elapsed. Check Twitch chat for the raid’s status.";
        cancel.hidden = !seconds;
        if (pending.completed) text.textContent = "Raid started";
        if (!seconds) followRaid();
        if (!seconds) stopClock(); // A countdown is not proof that a raid completed.
    }
    function showRaid(raid) {
        pending = raid;
        stopClock();
        banner.classList.remove("is-error");
        banner.hidden = !raid;
        if (!raid) { clearInterval(poll); poll = null; return; }
        const display = raid.display_name || raid.login;
        channel.textContent = display.toLowerCase() === raid.login.toLowerCase() ? display : `${display} (${raid.login})`;
        channel.href = `https://www.twitch.tv/${encodeURIComponent(raid.login)}`;
        if (avatar) {
            const valid = /^https:\/\/static-cdn\.jtvnw\.net\//.test(raid.profile_image_url || "");
            avatar.hidden = !valid;
            if (valid) avatar.src = raid.profile_image_url;
            else avatar.removeAttribute("src");
        }
        cancel.disabled = false;
        updateTime();
        if (!cancel.hidden) clock = setInterval(updateTime, 1000);
        if (!raid.completed && !poll) poll = setInterval(checkRaid, 3000);
    }
    async function checkRaid() {
        if (polling || !pending) return;
        const snapshot = pending, currentRevision = revision;
        if (Date.now() / 1000 > Number(snapshot.expires_at) + 120) { clearInterval(poll); poll = null; return; }
        polling = true;
        try {
            const response = await fetch(banner.dataset.pendingUrl, {headers: {Accept: "application/json"}, cache: "no-store"});
            if (!response.ok) return;
            const payload = await response.json();
            if (currentRevision !== revision || pending !== snapshot) return;
            if (!payload.raid) { showRaid(null); return; }
            if (payload.raid.created_at !== snapshot.created_at || payload.raid.target_id !== snapshot.target_id) return;
            if (payload.raid.completed) {
                pending = payload.raid; updateTime(); clearInterval(poll); poll = null;
            }
        } catch (_) { /* A transient status failure never means the raid completed. */ }
        finally { polling = false; }
    }
    function showError(message) {
        banner.hidden = false;
        banner.classList.add("is-error");
        text.textContent = message;
        if (!pending) { channel.textContent = "Raid"; channel.removeAttribute("href"); cancel.hidden = true; if (avatar) avatar.hidden = true; }
    }
    function animateIntoChat(detail) {
        const flyer = detail.flyer;
        if (!flyer) return;
        requestAnimationFrame(() => requestAnimationFrame(() => {
            banner.scrollIntoView?.({block: "nearest", behavior: "instant"});
            const from = detail.sourceRect, to = banner.getBoundingClientRect();
            const width = from.width || from.right - from.left;
            const height = from.height || from.bottom - from.top;
            if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !width || !height || !to.width || !flyer.animate) {
                flyer.remove(); banner.focus({preventScroll: true}); return;
            }
            flyer.setAttribute("aria-hidden", "true"); flyer.inert = true;
            flyer.classList.add("raid-browser-flyer");
            Object.assign(flyer.style, {left: `${from.left}px`, top: `${from.top}px`, width: `${width}px`, height: `${height}px`});
            document.body.append(flyer);
            banner.classList.add("is-arriving");
            const animation = flyer.animate([
                {transform: "translate(0,0) scale(1)", opacity: 1},
                {transform: `translate(${to.left - from.left}px,${to.top - from.top}px) scale(${to.width / width},${to.height / height})`, opacity: 0}
            ], {duration: 500, easing: "cubic-bezier(.22,1,.36,1)", fill: "forwards"});
            const finish = () => { flyer.remove(); banner.classList.remove("is-arriving"); banner.focus({preventScroll: true}); };
            animation.finished.then(finish, finish);
        }));
    }
    function animateAvatar(detail) {
        const flyer = detail.avatarFlyer, from = detail.avatarRect;
        if (!flyer || !from || !avatar || avatar.hidden) return;
        requestAnimationFrame(() => requestAnimationFrame(() => {
            const to = avatar.getBoundingClientRect();
            const width = from.width || from.right - from.left, height = from.height || from.bottom - from.top;
            if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !width || !height || !to.width || !flyer.animate) {
                flyer.remove(); return;
            }
            flyer.classList.add("raid-browser-avatar-flyer"); flyer.setAttribute("aria-hidden", "true");
            Object.assign(flyer.style, {left: `${from.left}px`, top: `${from.top}px`, width: `${width}px`, height: `${height}px`});
            document.body.append(flyer); avatar.style.opacity = "0";
            const animation = flyer.animate([{transform: "translate(0,0) scale(1)", opacity: 1},
                {transform: `translate(${to.left - from.left}px,${to.top - from.top}px) scale(${to.width / width},${to.height / height})`, opacity: 1}],
                {duration: 550, easing: "cubic-bezier(.22,1,.36,1)", fill: "forwards"});
            const finish = () => { flyer.remove(); avatar.style.opacity = ""; };
            animation.finished.then(finish, finish);
        }));
    }
    document.addEventListener("dashboard-raid-started", event => {
        revision++; followed = false; navigationArmed = true; if (follow) follow.checked = followDefault;
        clearInterval(poll); poll = null;
        showRaid(event.detail.raid); animateIntoChat(event.detail); animateAvatar(event.detail);
    });
    document.addEventListener("dashboard-raid-error", event => { revision++; showError(event.detail.message); });
    cancel.addEventListener("click", async () => {
        if (cancel.disabled || !pending) return;
        cancel.disabled = true;
        const currentRevision = ++revision;
        try {
            const body = new URLSearchParams({action: "cancel", csrf_token: banner.dataset.csrfToken || ""});
            const response = await fetch(banner.dataset.actionUrl, {method: "POST", body, headers: {Accept: "application/json"}});
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || "Twitch could not cancel the raid.");
            if (currentRevision === revision) showRaid(null);
        } catch (error) {
            if (currentRevision === revision) { showError(error.message); cancel.disabled = false; stopClock(); }
        }
    });
    const initialRevision = revision;
    fetch(banner.dataset.pendingUrl, {headers: {Accept: "application/json"}}).then(async response => {
        if (!response.ok) return;
        const payload = await response.json();
        if (revision === initialRevision && payload.raid) {
            // Restore an active countdown, but don't redirect on a stale pin
            // when the user deliberately returns to their dashboard later.
            navigationArmed = !payload.raid.completed && Number(payload.raid.expires_at) > Date.now() / 1000;
            showRaid(payload.raid);
        }
    }).catch(() => {});
})();
