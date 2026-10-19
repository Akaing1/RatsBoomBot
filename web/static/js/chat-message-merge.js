(() => {
    function valid(ids) {
        return ids && typeof ids.twitch === 'string' && ids.twitch.startsWith('twitch:')
            && typeof ids.youtube === 'string' && ids.youtube.startsWith('youtube:');
    }
    window.confirmDashboardChatSend = result => {
        if (!result?.sent?.includes('twitch') || !result.sent.includes('youtube')
            || Object.keys(result.errors || {}).length || !valid(result.message_ids)) return;
        document.dispatchEvent(new CustomEvent('dashboard-chat-send-confirmed', {detail: result.message_ids}));
    };
    window.createChatMessageMerger = ({allows, onChange = () => {}}) => {
        const rows = new Map(), pairs = new Map();
        function sync(pair) {
            const twitch = rows.get(pair.twitch), youtube = rows.get(pair.youtube);
            const twitchAllowed = twitch && allows(twitch), youtubeAllowed = youtube && allows(youtube);
            const merged = twitchAllowed && youtubeAllowed
                && !twitch.classList.contains('is-deleted') && !youtube.classList.contains('is-deleted');
            if (twitch) twitch.hidden = !twitchAllowed;
            if (youtube) youtube.hidden = Boolean(merged) || !youtubeAllowed;
            if (!twitch) return;
            let badge = twitch.querySelector('.live-chat-merged-platform');
            if (merged && !badge) {
                badge = document.createElement('span'); badge.className = 'live-chat-platform youtube live-chat-merged-platform';
                badge.textContent = 'YT'; badge.title = 'Also sent to YouTube';
                const heading = twitch.querySelector('.live-chat-message-heading');
                heading.insertBefore(badge, heading.children[1] || null);
            }
            if (badge) badge.hidden = !merged;
            if (merged) twitch.dataset.mergedMessageId = pair.youtube;
            else delete twitch.dataset.mergedMessageId;
        }
        function unlink(pair) {
            pairs.delete(pair.twitch); pairs.delete(pair.youtube);
            for (const id of [pair.twitch, pair.youtube]) {
                const row = rows.get(id);
                if (!row) continue;
                row.hidden = !allows(row);
                row.querySelector('.live-chat-merged-platform')?.remove();
                delete row.dataset.mergedMessageId;
            }
        }
        return {
            register(ids) {
                if (!valid(ids)) return;
                if (pairs.get(ids.twitch)?.youtube === ids.youtube) return;
                for (const id of [ids.twitch, ids.youtube]) if (pairs.has(id)) unlink(pairs.get(id));
                const pair = {twitch: ids.twitch, youtube: ids.youtube};
                pairs.set(pair.twitch, pair); pairs.set(pair.youtube, pair);
                while (pairs.size > 300) unlink(pairs.values().next().value);
                sync(pair); onChange();
            },
            track(row) {
                rows.set(row.dataset.messageId, row);
                const pair = pairs.get(row.dataset.messageId);
                if (pair) sync(pair);
            },
            forget(row) {
                const pair = pairs.get(row.dataset.messageId);
                if (pair) unlink(pair);
                rows.delete(row.dataset.messageId);
            },
            refresh(messageId) {
                if (messageId !== undefined) {
                    const pair = pairs.get(messageId);
                    if (pair) sync(pair);
                } else new Set(pairs.values()).forEach(sync);
            },
            destroy() { new Set(pairs.values()).forEach(unlink); rows.clear(); }
        };
    };
})();
