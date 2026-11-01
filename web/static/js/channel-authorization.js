(() => {
    'use strict';
    const banner = document.querySelector('[data-channel-auth-banner]');
    if (!banner) return;
    const message = banner.querySelector('[data-channel-auth-message]');
    const connect = banner.querySelector('[data-channel-auth-connect]');
    const retry = banner.querySelector('[data-channel-auth-retry]');
    let checking = false;
    async function check() {
        if (checking) return;
        checking = true;
        retry.disabled = true;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch('/channel/api/authorization', {cache: 'no-store', signal: controller.signal, headers: {Accept: 'application/json'}});
            if (response.status === 401) {
                banner.hidden = false;
                message.textContent = 'Sign in to reconnect your Twitch channel.';
                connect.hidden = false;
                retry.hidden = true;
                return;
            }
            if (!response.ok || response.redirected) throw new Error('Unavailable');
            const state = await response.json();
            if (typeof state.required !== 'boolean') throw new Error('Invalid response');
            banner.hidden = !state.required;
            message.textContent = 'New or updated features need additional Twitch permissions. Reauthorize your channel to enable them.';
            connect.hidden = !state.required;
            retry.hidden = true;
        } catch {
            banner.hidden = false;
            message.textContent = 'Could not check Twitch permissions. Please try again.';
            connect.hidden = true;
            retry.hidden = false;
        } finally {
            clearTimeout(timeout);
            checking = false;
            retry.disabled = false;
        }
    }
    retry.addEventListener('click', check);
    window.addEventListener('pageshow', event => { if (event.persisted) check(); });
    check();
})();
