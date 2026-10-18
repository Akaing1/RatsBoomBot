(() => {
    let sequence = 0;
    window.createRaidPreviewPlayer = (host, channel, report = () => {}) => {
        const mount = document.createElement('div');
        mount.className = 'raid-preview-player'; mount.id = `raid-preview-player-${++sequence}`;
        host.append(mount);
        let active = true, player = null, ready = false, started = false, frame = 0, lastSize = '';
        function scheduleStart() {
            if (active && !started && !frame) frame = requestAnimationFrame(startWhenVisible);
        }
        function startWhenVisible() {
            frame = 0;
            if (!active || started) return;
            const rect = host.getBoundingClientRect();
            const style = getComputedStyle(host);
            if (document.hidden || rect.width < 400 || rect.height < 300
                || style.visibility !== 'visible' || style.display === 'none' || Number(style.opacity) === 0
                || (host.checkVisibility && !host.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))) {
                lastSize = ''; return;
            }
            // Opening the dialog and fitting its width can take multiple layouts.
            const size = `${rect.width}:${rect.height}`;
            if (lastSize !== size) { lastSize = size; scheduleStart(); return; }
            started = true;
            observer?.disconnect();
            document.removeEventListener('visibilitychange', scheduleStart);
            const Player = window.Twitch?.Player;
            if (!Player) {
                const iframe = document.createElement('iframe');
                const url = new URL('https://player.twitch.tv/');
                url.search = new URLSearchParams({channel, parent: window.location.hostname, autoplay: 'true', muted: 'true'}).toString();
                iframe.src = url.href; iframe.title = `${channel} stream`; iframe.allow = 'autoplay; fullscreen';
                mount.append(iframe);
                return;
            }
            // Twitch owns autoplay; READY must not restart initial playback.
            player = new Player(mount.id, {channel, parent: [window.location.hostname], width: '100%', height: '100%', autoplay: true, muted: true});
            player.addEventListener(Player.READY, () => {
                if (!active || ready) return;
                ready = true;
            });
            player.addEventListener(Player.PLAYING, () => {
                if (active) report('');
            });
            player.addEventListener(Player.PLAYBACK_BLOCKED, () => {
                if (active) report('Autoplay was blocked. Press Play in the video.');
            });
        }
        const observer = window.ResizeObserver ? new window.ResizeObserver(scheduleStart) : null;
        observer?.observe(host);
        document.addEventListener('visibilitychange', scheduleStart);
        scheduleStart();
        return {destroy() {
            if (!active) return;
            active = false; cancelAnimationFrame(frame);
            observer?.disconnect(); document.removeEventListener('visibilitychange', scheduleStart);
            if (ready) { try { player.pause(); } catch (_) { /* Frame removal still stops playback. */ } }
            mount.replaceChildren(); mount.remove();
        }};
    };
})();
