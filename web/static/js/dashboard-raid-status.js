(() => {
    const banner = document.querySelector("[data-pending-raid]");
    if (!banner) return;
    const channel = banner.querySelector("[data-pending-raid-channel]");
    const text = banner.querySelector("[data-pending-raid-text]");
    const description = banner.querySelector("[data-pending-raid-description]");
    const cancel = banner.querySelector("[data-pending-raid-cancel]");
    const avatar = banner.querySelector("[data-pending-raid-avatar]");
    const follow = banner.querySelector("[data-pending-raid-follow]");
    const countdown = banner.querySelector("[data-pending-raid-countdown]");
    const secondsLabel = banner.querySelector("[data-pending-raid-seconds]");
    const progress = banner.querySelector("[data-pending-raid-progress]");
    const ring = banner.querySelector("[data-pending-raid-ring]");
    const followDefault = follow?.checked !== false;
    let poll = null, polling = false, followed = false, navigationArmed = false;
    avatar?.addEventListener("error", () => { avatar.hidden = true; });
    let pending = null, clock = null, revision = 0;
    let progressAnimations = [];
    let dismissal = null;

    function cancelDismissal() {
        const animation = dismissal;
        dismissal = null;
        animation?.cancel?.();
    }

    function stopClock() {
        clearInterval(clock); clock = null;
        progressAnimations.forEach(animation => animation.cancel?.()); progressAnimations = [];
    }
    function raidTime() {
        const expires = Number(pending.expires_at), created = Date.parse(pending.created_at) / 1000;
        const duration = Number.isFinite(created) && expires > created ? expires - created : 90;
        const remaining = !pending.completed && Number.isFinite(expires) ? Math.max(0, expires - Date.now() / 1000) : 0;
        return {remaining, fraction: Math.max(0, Math.min(1, remaining / duration))};
    }
    function animateProgress() {
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        const {remaining, fraction} = raidTime();
        const options = {duration: remaining * 1000, easing: "linear", fill: "forwards"};
        for (const [element, frames] of [
            [progress, [{transform: `scaleX(${fraction})`}, {transform: "scaleX(0)"}]],
            [ring, [{strokeDashoffset: String(1 - fraction)}, {strokeDashoffset: "1"}]],
        ]) {
            if (!element?.animate) continue;
            const animation = element.animate(frames, options);
            animation.finished.catch(() => {}); progressAnimations.push(animation);
        }
    }
    function followRaid() {
        if (!navigationArmed || followed || !follow?.checked || cancel.disabled || !/^[A-Za-z0-9_]{1,25}$/.test(pending?.login || "")) return;
        followed = true;
        window.location.assign(`https://www.twitch.tv/${encodeURIComponent(pending.login)}`);
    }
    function updateDescription() {
        if (!pending) return;
        if (description) {
            const viewers = pending.viewer_count;
            // Confirmed raid counts already include everyone who joined.
            const count = viewers + (!pending.completed && follow?.checked ? 1 : 0);
            description.textContent = Number.isSafeInteger(viewers) && viewers >= 0 && Number.isSafeInteger(count)
                ? `Raiding with ${count.toLocaleString()} ${count === 1 ? "viewer" : "viewers"}` : "Raiding";
        }
    }
    follow?.addEventListener("change", updateDescription);
    function updateTime() {
        if (!pending) return;
        updateDescription();
        const {remaining, fraction} = raidTime();
        const seconds = Math.ceil(remaining);
        if (secondsLabel) secondsLabel.textContent = String(seconds);
        countdown?.setAttribute("aria-label", `${seconds} seconds remaining`);
        if (countdown) countdown.hidden = Boolean(pending.completed);
        if (progress) { progress.hidden = Boolean(pending.completed); progress.style.transform = `scaleX(${fraction})`; }
        if (ring) ring.style.strokeDashoffset = String(1 - fraction);
        text.textContent = seconds || pending.completed ? "" : "Countdown elapsed. Check Twitch chat for the raid’s status.";
        cancel.hidden = !seconds;
        if (!seconds) followRaid();
        if (!seconds) stopClock(); // A countdown is not proof that a raid completed.
    }
    function showRaid(raid) {
        cancelDismissal();
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
        if (!cancel.hidden) { clock = setInterval(updateTime, 1000); animateProgress(); }
        if (!raid.completed && !poll) poll = setInterval(checkRaid, 3000);
    }
    function dismissRaid() {
        pending = null; navigationArmed = false;
        stopClock(); clearInterval(poll); poll = null;
        cancel.disabled = true;
        if (banner.hidden || !banner.animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            showRaid(null); return;
        }
        const height = banner.getBoundingClientRect().height;
        const style = getComputedStyle(banner);
        const animation = banner.animate([
            {transform: "translateY(0)", opacity: 1, height: `${height}px`, marginBottom: style.marginBottom,
                paddingTop: style.paddingTop, paddingBottom: style.paddingBottom, borderWidth: style.borderWidth},
            {transform: `translateY(-${height}px)`, opacity: 0, height: "0px", marginBottom: "0px",
                paddingTop: "0px", paddingBottom: "0px", borderWidth: "0px"},
        ], {duration: 240, easing: "cubic-bezier(.4,0,1,1)", fill: "forwards"});
        dismissal = animation;
        const finish = () => {
            if (dismissal !== animation) return;
            showRaid(null);
        };
        animation.finished.then(finish, finish);
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
            if (!payload.raid) { dismissRaid(); return; }
            if (payload.raid.created_at !== snapshot.created_at || payload.raid.target_id !== snapshot.target_id) return;
            if (Object.hasOwn(payload.raid, "viewer_count")) {
                pending.viewer_count = payload.raid.viewer_count;
                updateTime();
            }
            if (payload.raid.completed) {
                pending = payload.raid; updateTime(); clearInterval(poll); poll = null;
            }
        } catch (_) { /* A transient status failure never means the raid completed. */ }
        finally { polling = false; }
    }
    function showError(message) {
        cancelDismissal();
        banner.hidden = false;
        banner.classList.add("is-error");
        text.textContent = message;
        if (!pending && description) description.textContent = "";
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
            if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !width || !height || !to.width || !to.height || !flyer.animate) {
                flyer.remove(); banner.focus({preventScroll: true}); return;
            }
            const frame = document.createElement("div");
            frame.setAttribute("aria-hidden", "true"); frame.inert = true;
            frame.classList.add("raid-browser-flyer");
            Object.assign(frame.style, {left: `${from.left}px`, top: `${from.top}px`, width: `${width}px`, height: `${height}px`, boxSizing: "border-box"});
            Object.assign(flyer.style, {position: "absolute", left: "0", top: "0", width: `${width}px`, height: `${height}px`, overflow: "hidden", transformOrigin: "top left"});
            frame.append(flyer); document.body.append(frame);
            const sourceStyle = getComputedStyle(flyer), targetStyle = getComputedStyle(banner);
            const sourceBorder = {borderRadius: sourceStyle.borderRadius, borderWidth: sourceStyle.borderWidth, borderColor: sourceStyle.borderColor};
            const targetBorder = {borderRadius: targetStyle.borderRadius, borderWidth: targetStyle.borderWidth, borderColor: targetStyle.borderColor};
            Object.assign(frame.style, sourceBorder, {borderStyle: sourceStyle.borderStyle, background: sourceStyle.background});
            // The frame morphs independently so its border is never squashed.
            Object.assign(flyer.style, {border: "0", borderRadius: "0"});
            banner.classList.add("is-arriving");
            const scale = Math.min(1, to.width / width, to.height / height);
            const x = (to.width - width * scale) / 2;
            const y = (to.height - height * scale) / 2;
            const fitted = `translate(${x}px,${y}px) scale(${scale})`;
            const options = {duration: 650, easing: "cubic-bezier(.22,1,.36,1)", fill: "forwards"};
            const contentAnimation = flyer.animate([
                {transform: "translate(0,0) scale(1)", opacity: 1, offset: 0},
                {transform: fitted, opacity: 1, offset: .85},
                {transform: fitted, opacity: 0, offset: 1}
            ], options);
            const destination = {transform: `translate(${to.left - from.left}px,${to.top - from.top}px)`,
                width: `${to.width}px`, height: `${to.height}px`, ...targetBorder};
            const animation = frame.animate([
                {transform: "translate(0,0)", width: `${width}px`, height: `${height}px`, ...sourceBorder, opacity: 1, offset: 0},
                {...destination, opacity: 1, offset: .85},
                {...destination, opacity: 0, offset: 1}
            ], options);
            contentAnimation.finished.catch(() => {});
            const finish = () => {
                contentAnimation.cancel?.(); flyer.remove(); frame.remove();
                banner.classList.remove("is-arriving"); banner.focus({preventScroll: true});
            };
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
            if (currentRevision === revision) dismissRaid();
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
