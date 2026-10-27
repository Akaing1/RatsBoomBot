(() => {
    const banner = document.querySelector("[data-mod-auth-banner]");
    const root = document.body.dataset.channelRoot;
    if (!banner || !root?.startsWith("/me/mod/")) return;
    let pending = false;
    async function refresh() {
        if (pending) return;
        pending = true;
        try {
            const response = await fetch(`${root}/api/authorization`, {headers: {Accept: "application/json"}, cache: "no-store"});
            if (response.ok) banner.hidden = !(await response.json()).required;
        } catch (_) { /* Keep the server-rendered authorization state. */ }
        finally { pending = false; }
    }
    window.addEventListener("focus", refresh);
    document.addEventListener("moderator-authorization-check", refresh);
})();
