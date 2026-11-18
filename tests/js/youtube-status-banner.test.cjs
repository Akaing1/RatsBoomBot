const {test} = require('node:test');
const fs = require('node:fs');
async function exercise(source) {
    const handlers = {}, timers = [], nodes = {};
    const node = key => nodes[key] ||= {hidden: true, classList: {toggle() {}}, addEventListener() {}};
    const banner = {dataset: {authPlatform: 'YouTube', authEndpoint: '/channel/api/youtube/authorization'},
        hidden: true, querySelector: node};
    const document = {hidden: false, querySelectorAll: selector => selector === '[data-channel-auth-banner]' ? [banner] : [],
        addEventListener: (name, fn) => {handlers[name] = fn;},
        dispatchEvent: event => handlers[event.type]?.(event)};
    const window = {setInterval: fn => timers.push(fn), addEventListener() {}};
    let required = false;
    const requests = [];
    const fetch = async url => { requests.push(url); return {ok: true, status: 200,
        json: async () => ({required, ...(url.includes('cached') ? {state: {reauth_required: required, receiving: false}} : {})})}; };
    new Function('document', 'window', 'fetch', 'AbortController', 'setTimeout', 'clearTimeout', 'CustomEvent', source)(
        document, window, fetch, class {signal = {}; abort() {}}, () => 1, () => {}, class {constructor(type, data) {this.type = type; this.detail = data.detail;}});
    const flush = async () => {for (let i = 0; i < 12; i++) await Promise.resolve();};
    await flush();
    if (!banner.hidden) throw Error('healthy banner visible');
    handlers['youtube-chat-status']({detail: {reauth_required: true, receiving: false}});
    if (banner.hidden || node('[data-channel-auth-connect]').hidden) throw Error('reauth not visible');
    required = true;
    timers[0](); await flush();
    if (!requests.at(-1).endsWith('?cached=true') || banner.hidden) throw Error('cached refresh failed');
    handlers['youtube-chat-status']({detail: {reauth_required: false, receiving: true}});
    if (!banner.hidden) throw Error('recovery did not clear banner');
}
test('YouTube banner updates while open and clears after reconnect', async () => {
    await exercise(fs.readFileSync('web/static/js/channel-authorization.js', 'utf8'));
});
