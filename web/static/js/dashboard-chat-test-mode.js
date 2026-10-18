(() => {
    const key = 'ratsboombot:youtube-chat-test';
    let active = false, sequence = 0, nextFailure = null;
    try { active = window.sessionStorage.getItem(key) === 'true'; } catch (_) {}
    function emitMessage(text, platform = 'youtube', badges = []) {
        if (!['youtube', 'twitch'].includes(platform)) return;
        const id = `${platform}:test-${Date.now()}-${++sequence}`;
        document.dispatchEvent(new CustomEvent('dashboard-chat-test-message', {detail: {
            id, platform, kind: 'message', test_mode: true,
            username: 'test_viewer', display_name: `Test ${platform === 'youtube' ? 'YouTube' : 'Twitch'}`,
            timestamp: new Date().toISOString(), message: String(text), badges, is_bot: badges.includes('bot')
        }}));
        return id;
    }
    function message(...args) { if (active) return emitMessage(...args); }
    window.dashboardChatDebug = {
        active,
        youtube(enabled = true) {
            window.sessionStorage.setItem(key, String(Boolean(enabled)));
            window.location.reload();
        },
        message,
        notice(type = 'all') {
            const samples = {
                sub: ['sub', 'Subscription', 'Test viewer subscribed at Tier 1.'],
                prime: ['sub', 'Prime subscription', 'Test viewer subscribed with Prime.'],
                resub: ['resub', 'Resubscription', 'Test viewer subscribed for 12 months!', 'Happy to be here!'],
                primeresub: ['resub', 'Prime resubscription', 'Test viewer subscribed with Prime for 12 months!'],
                giftsub: ['sub_gift', 'Gift sub', 'Test viewer gifted a Tier 1 sub to Test recipient!'],
                giftsubs: ['community_sub_gift', 'Gift subs', 'Test viewer gifted 5 Tier 1 subs to the community!'],
                watchstreak: ['watch_streak', 'Watch streak', 'Test viewer watched 10 consecutive streams!'],
                substreak: ['resub', 'Resubscription', 'Test viewer subscribed for 12 months! · 6 consecutive months'],
                redeem: ['redemption', 'Redeem', 'Redeemed Hydrate · 1,000 points', 'Time for water!'],
                raid: ['raid', 'Incoming raid', 'Test raider is raiding with 25 viewers!']
            };
            if (type !== 'all' && !Object.hasOwn(samples, type)) throw new Error(`Use all or: ${Object.keys(samples).join(', ')}.`);
            return (type === 'all' ? Object.keys(samples) : [type]).map(key => {
                const [notice_type, notice_label, notice, text = ''] = samples[key];
                const id = `twitch:test-notice-${Date.now()}-${++sequence}`;
                document.dispatchEvent(new CustomEvent('dashboard-chat-test-notice', {detail: {
                    id, platform: 'twitch', kind: 'chat', test_mode: true, username: 'test_viewer',
                    display_name: key === 'raid' ? 'Test raider' : 'Test viewer',
                    timestamp: new Date().toISOString(), message: text, notice_type, notice_label, notice,
                    badges: ['sub', 'resub'].includes(notice_type) ? ['subscriber'] : [],
                    is_redeem: key === 'redeem'
                }}));
                return id;
            });
        },
        failNext(platform = 'all') {
            if (!['twitch', 'youtube', 'all', 'both'].includes(platform)) throw new Error('Use twitch, youtube, or all.');
            nextFailure = platform === 'all' ? 'both' : platform;
            return `Next send is local-only: simulate ${platform === 'both' ? 'all' : platform} failing. Other selected platforms simulate success. Nothing will be posted.`;
        },
        send(text, target) {
            if (!active && !nextFailure) return null;
            const failure = nextFailure;
            nextFailure = null;
            const targets = target === 'both' ? ['twitch', 'youtube'] : [target];
            const errors = Object.fromEntries(targets.filter(platform => failure === 'both' || failure === platform)
                .map(platform => [platform, `Simulated ${platform === 'youtube' ? 'YouTube' : 'Twitch'} send failure. Nothing was posted.`]));
            const sent = targets.filter(platform => !errors[platform]);
            const message_ids = Object.fromEntries(sent.map(platform => [platform, emitMessage(text, platform)]));
            return {message: 'Test mode: nothing sent to Twitch or YouTube.', tone: 'warning', sent, errors, message_ids};
        }
    };
    if (!active) return;
    const form = document.querySelector('[data-chat-composer]');
    if (!form) return;
    form.dataset.youtubeConnected = 'true';
    form.querySelector('[name="message"]').placeholder = 'Test message (not sent)…';
    const youtube = document.querySelector('[data-chat-filter-platform="youtube"]');
    if (youtube) {
        youtube.disabled = false; youtube.hidden = false;
        const section = youtube.closest('.chat-filter-platform-section');
        section.children[1].hidden = false;
        const badge = section.querySelector('[data-chat-filter-connection]');
        badge.dataset.connected = 'true'; badge.textContent = 'Test connection';
        badge.title = 'YouTube test connection'; badge.classList.add('is-connected');
    }
    document.querySelectorAll('[data-chat-filter-platform]').forEach(input => { input.hidden = false; });
    const dot = document.querySelector('.chat-platform-dot.youtube');
    if (dot) { dot.classList.add('active'); dot.title = 'YouTube test mode'; dot.setAttribute('aria-label', dot.title); }
    document.addEventListener('DOMContentLoaded', () => {
        message('Test Twitch message', 'twitch');
        message('Test YouTube message');
        message('Test YouTube moderator', 'youtube', ['moderator']);
        message('Test YouTube member', 'youtube', ['member']);
        message('Test YouTube bot', 'youtube', ['bot']);
    }, {once: true});
})();
