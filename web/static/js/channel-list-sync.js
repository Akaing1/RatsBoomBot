(() => {
    'use strict';
    const localLists = {raidFavorites: 'raid-favorites', raidBlacklist: 'raid-blacklist'};
    const serverLists = ['automaticShoutouts', 'incomingRaidBlacklist', 'queueBlacklist'];
    let importing = false;
    async function request(method = 'GET', payload) {
        const headers = {Accept: 'application/json'};
        if (payload) {
            headers['Content-Type'] = 'application/json';
            headers['X-CSRF-Token'] = document.querySelector('.sidebar-logout [name=csrf_token]')?.value || '';
        }
        const response = await fetch('/channel/api/user-lists', {method, headers, cache: 'no-store', ...(payload ? {body: JSON.stringify(payload)} : {})});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'User lists could not be synchronized.');
        return result;
    }
    function normalize(name, users) {
        const ids = name in localLists, maximum = name === 'queueBlacklist' ? 1000 : 100;
        if (!Array.isArray(users) || users.length > maximum || users.some(user => typeof user !== 'string' || !(ids ? /^\d{1,25}$/ : /^[a-zA-Z0-9_]{1,25}$/).test(user))) {
            throw new Error(`${name} must contain up to ${maximum} valid Twitch ${ids ? 'IDs' : 'usernames'}.`);
        }
        return [...new Set(users.map(user => ids ? user : user.toLowerCase()))].sort();
    }
    function storageKey(name, channelId) { return `ratsboombot:${localLists[name]}:${channelId}`; }
    function readLocal(name, channelId) { return normalize(name, JSON.parse(localStorage.getItem(storageKey(name, channelId)) || '[]')); }
    window.ratsLists = Object.freeze({
        async export() {
            const result = await request();
            for (const name of Object.keys(localLists)) result.lists[name] = readLocal(name, result.channelId);
            return JSON.stringify(result, null, 2);
        },
        async import(source, {replace = false} = {}) {
            if (importing) throw new Error('Wait for the current list import to finish.');
            importing = true;
            try {
                const data = typeof source === 'string' ? JSON.parse(source) : source;
                if (!data || data.version !== 1 || !data.lists || typeof data.lists !== 'object' || Array.isArray(data.lists) || typeof replace !== 'boolean') throw new Error('Use a version 1 user-list export.');
                const names = Object.keys(data.lists);
                if (!names.length || names.some(name => !Object.hasOwn(localLists, name) && !serverLists.includes(name))) throw new Error('The export contains unsupported lists.');
                const incoming = Object.fromEntries(names.map(name => [name, normalize(name, data.lists[name])]));
                const current = await request();
                if (data.channelId !== current.channelId) throw new Error('This export belongs to a different Twitch channel.');
                const updates = {};
                for (const name of names) {
                    const existing = replace ? [] : name in localLists ? readLocal(name, current.channelId) : current.lists[name];
                    updates[name] = normalize(name, [...new Set([...existing, ...incoming[name]])]);
                }
                const server = Object.fromEntries(names.filter(name => serverLists.includes(name)).map(name => [name, incoming[name]]));
                if (Object.keys(server).length) await request('POST', {version: 1, channelId: current.channelId, lists: server, replace});
                for (const name of names.filter(name => name in localLists)) {
                    const key = storageKey(name, current.channelId), oldValue = localStorage.getItem(key), newValue = JSON.stringify(updates[name]);
                    try { localStorage.setItem(key, newValue); }
                    catch (_) { throw new Error('Server lists were saved, but browser storage could not save raid lists. Free browser storage and retry the import.'); }
                    window.dispatchEvent(new StorageEvent('storage', {key, oldValue, newValue, storageArea: localStorage}));
                }
                return {channelId: current.channelId, mode: replace ? 'replace' : 'merge', counts: Object.fromEntries(names.map(name => [name, updates[name].length])), message: 'Lists imported. Reload the page to update all open panels.'};
            } finally { importing = false; }
        },
    });
    window.exportLists = async () => {
        const data = await window.ratsLists.export();
        try {
            await navigator.clipboard.writeText(data);
            return 'Lists copied. Run importLists() in the destination environment.';
        } catch (_) {
            window.prompt('Copy these lists, then run importLists() in the destination environment:', data);
            return 'Export ready to copy.';
        }
    };
    window.importLists = async (options) => {
        const data = window.prompt('Paste exported lists');
        return data === null ? 'Import cancelled.' : window.ratsLists.import(data, options);
    };
})();
