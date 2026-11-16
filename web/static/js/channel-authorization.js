(() => {
    'use strict';
    document.querySelectorAll('[data-channel-auth-banner]').forEach(banner => {
        const platform = banner.dataset.authPlatform || 'Twitch';
        const endpoint = banner.dataset.authEndpoint || '/channel/api/authorization';
        const message = banner.querySelector('[data-channel-auth-message]');
        const connect = banner.querySelector('[data-channel-auth-connect]');
        const retry = banner.querySelector('[data-channel-auth-retry]');
        let checking = false;
        function showRequired(required) {
            banner.hidden = !required;
            message.textContent = platform === 'YouTube'
                ? 'YouTube chat is disconnected. Reauthorize YouTube to restore the connection.'
                : 'New or updated features need additional Twitch permissions. Reauthorize your channel to enable them.';
            connect.hidden = !required;
            retry.hidden = true;
        }
        let revision = 0;
        if (platform === 'YouTube') {
            document.addEventListener('youtube-chat-status', event => {
                if (typeof event.detail?.reauth_required === 'boolean') {
                    ++revision;
                    showRequired(event.detail.reauth_required);
                    const state = event.detail;
                    document.querySelectorAll('[data-youtube-settings-status]').forEach(node => {
                        node.textContent = state.reauth_required ? 'Disconnected — reauthorize YouTube'
                            : state.receiving ? 'Connected' : 'Disconnected';
                        node.classList.toggle('enabled', state.receiving === true);
                    });
                    document.querySelectorAll('[data-youtube-settings-detail]').forEach(node => {
                        node.textContent = state.detail || '';
                    });
                }
            });
            window.setInterval(() => { if (!document.hidden) check(true); }, 30000);
            document.addEventListener('visibilitychange', () => { if (!document.hidden) check(true); });
        }
        async function check(cached = false) {
            cached = cached === true;
            if (checking) return;
            checking = true;
            const currentRevision = revision;
            retry.disabled = true;
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 10000);
            try {
                const response = await fetch(endpoint + (cached ? '?cached=true' : ''), {cache: 'no-store', signal: controller.signal, headers: {Accept: 'application/json'}});
                if (currentRevision !== revision) return;
                if (response.status === 401) {
                    banner.hidden = false;
                    message.textContent = `Sign in to reconnect your ${platform} channel.`;
                    connect.hidden = false;
                    retry.hidden = true;
                    return;
                }
                if (!response.ok || response.redirected) throw new Error('Unavailable');
                const state = await response.json();
                if (typeof state.required !== 'boolean') throw new Error('Invalid response');
                if (currentRevision !== revision) return;
                showRequired(state.required);
                if (state.state) document.dispatchEvent(new CustomEvent('youtube-chat-status', {detail: state.state}));
            } catch {
                if (currentRevision !== revision || cached) return;
                banner.hidden = false;
                message.textContent = `Could not check ${platform} permissions. Please try again.`;
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
    });
})();
