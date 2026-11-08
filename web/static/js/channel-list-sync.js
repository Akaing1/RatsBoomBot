(() => {
    'use strict';
    const localLists = {raidFavorites: 'raid-favorites', raidBlacklist: 'raid-blacklist'};
    const serverLists = ['automaticShoutouts', 'incomingRaidBlacklist', 'queueBlacklist'];
    const labels = {raidFavorites: 'Raid favorites', raidBlacklist: 'Raid browser blacklist', automaticShoutouts: 'Automatic shoutouts',
        incomingRaidBlacklist: 'Incoming raid blacklist', queueBlacklist: 'Queue blacklist'};
    const status = message => console.info(`[User lists] ${message}`);
    const reportCounts = counts => Object.entries(counts).forEach(([name, count]) => status(`${labels[name]}: ${count} entries`));
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
            try {
                status('Export: fetching saved lists…');
                const result = await request();
                status('Export: reading raid favorites and blacklist from this browser…');
                for (const name of Object.keys(localLists)) result.lists[name] = readLocal(name, result.channelId);
                reportCounts(Object.fromEntries(Object.entries(result.lists).map(([name, users]) => [name, users.length])));
                status('Export data ready.');
                return JSON.stringify(result, null, 2);
            } catch (error) { console.error('[User lists] Export failed:', error.message); throw error; }
        },
        async import(source, {replace = false} = {}) {
            if (importing) throw new Error('Wait for the current list import to finish.');
            importing = true;
            try {
                status(`Import: validating ${replace ? 'replacement' : 'merge'} data…`);
                let data = source;
                if (typeof source === 'string') {
                    try { data = JSON.parse(source); }
                    catch (_) { throw new Error('The export is incomplete or invalid JSON. Re-export the original lists; for long lists, use exportLists({file: true}) and importLists({file: true}). No lists were changed.'); }
                }
                if (!data || data.version !== 1 || !data.lists || typeof data.lists !== 'object' || Array.isArray(data.lists) || typeof replace !== 'boolean') throw new Error('Use a version 1 user-list export.');
                const names = Object.keys(data.lists);
                if (!names.length || names.some(name => !Object.hasOwn(localLists, name) && !serverLists.includes(name))) throw new Error('The export contains unsupported lists.');
                const incoming = Object.fromEntries(names.map(name => [name, normalize(name, data.lists[name])]));
                status('Import: checking the destination channel and existing lists…');
                const current = await request();
                if (data.channelId !== current.channelId) throw new Error('This export belongs to a different Twitch channel.');
                const updates = {};
                for (const name of names) {
                    const existing = replace ? [] : name in localLists ? readLocal(name, current.channelId) : current.lists[name];
                    updates[name] = normalize(name, [...new Set([...existing, ...incoming[name]])]);
                }
                const server = Object.fromEntries(names.filter(name => serverLists.includes(name)).map(name => [name, incoming[name]]));
                if (Object.keys(server).length) {
                    status('Import: saving shoutout and blacklist settings on the server…');
                    await request('POST', {version: 1, channelId: current.channelId, lists: server, replace});
                    status('Import: server settings saved.');
                }
                if (names.some(name => name in localLists)) status('Import: saving raid lists in this browser…');
                for (const name of names.filter(name => name in localLists)) {
                    const key = storageKey(name, current.channelId), oldValue = localStorage.getItem(key), newValue = JSON.stringify(updates[name]);
                    try { localStorage.setItem(key, newValue); }
                    catch (_) { throw new Error('Server lists were saved, but browser storage could not save raid lists. Free browser storage and retry the import.'); }
                    window.dispatchEvent(new StorageEvent('storage', {key, oldValue, newValue, storageArea: localStorage}));
                }
                const counts = Object.fromEntries(names.map(name => [name, updates[name].length]));
                reportCounts(counts);
                status('Import successful. Reload the page to update all open panels.');
                return {channelId: current.channelId, mode: replace ? 'replace' : 'merge', counts, message: 'Lists imported. Reload the page to update all open panels.'};
            } catch (error) { console.error('[User lists] Import failed:', error.message); throw error; }
            finally { importing = false; }
        },
    });
    function download(data) {
        const url = URL.createObjectURL(new Blob([data], {type: 'application/json'}));
        const link = document.createElement('a');
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        link.href = url; link.download = `ratsboombot-lists-${JSON.parse(data).channelId}-${timestamp}.json`;
        document.body.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    function chooseFile() {
        return new Promise((resolve, reject) => {
            const input = document.createElement('input');
            input.type = 'file'; input.accept = '.json,application/json'; input.hidden = true;
            input.addEventListener('change', () => {
                const file = input.files[0]; input.remove();
                if (file) file.text().then(resolve, reject); else resolve(null);
            }, {once: true});
            input.addEventListener('cancel', () => { input.remove(); resolve(null); }, {once: true});
            document.body.append(input);
            try { input.click(); } catch (error) { input.remove(); reject(error); }
        });
    }
    window.exportLists = async ({file = false} = {}) => {
        const data = await window.ratsLists.export();
        if (file) { status('Export: creating JSON download…'); download(data); status('Export successful: JSON download started.'); return 'Lists downloaded. Run importLists({file: true}) in the destination environment.'; }
        try {
            status('Export: copying to clipboard…');
            await navigator.clipboard.writeText(data);
            status('Export successful: lists copied to clipboard.');
            return 'Lists copied. Run importLists() in the destination environment.';
        } catch (_) {
            console.warn('[User lists] Clipboard unavailable. Copy the export from the prompt.');
            window.prompt('Copy these lists, then run importLists() in the destination environment:', data);
            return 'Export ready to copy.';
        }
    };
    window.importLists = async (options = {}) => {
        status(options.file ? 'Import: waiting for you to select a JSON file…' : 'Import: waiting for pasted JSON…');
        const data = options.file ? await chooseFile() : window.prompt('Paste exported lists');
        if (data === null) { status('Import cancelled. No lists changed.'); return 'Import cancelled.'; }
        const result = await window.ratsLists.import(data, options);
        const counts = Object.entries(result.counts).map(([name, count]) => `${labels[name]}: ${count}`).join('\n');
        window.alert(`Lists imported successfully (${result.mode}).\n\n${counts}\n\nReload the page to update all open panels.`);
        return result;
    };
})();
