(() => {
    const mount = document.querySelector("[data-stream-player]");
    const channel = mount?.dataset.channel?.trim();
    if (!channel) return;

    const status = document.querySelector("[data-stream-playback-status]");
    function showStatus(message = "") {
        if (!status) return;
        status.textContent = message;
        status.hidden = !message;
    }

    if (!window.Twitch?.Player) {
        showStatus("The Twitch player could not load. Refresh the page to try again.");
        return;
    }

    const twitchPlayer = new Twitch.Player(mount.id, {
        channel,
        parent: [window.location.hostname],
        width: "100%",
        height: "100%",
        autoplay: false,
        muted: true
    });
    let ready = false;
    let live = mount.dataset.isLive === "true";
    let actualLive = live;
    let testMode = false;
    let playing = false;
    let selectedChannel = channel;
    let loadedChannel = channel;

    function updatePlaybackPrompt() {
        if (!ready) return;
        // The user must press Twitch's own Play control, not a scripted button,
        // so Twitch recognizes manual playback for background viewing.
        showStatus(live && !playing ? "Press Play in the Twitch player to start the preview." : "");
    }

    function selectChannel(nextChannel) {
        selectedChannel = nextChannel;
        if (ready && loadedChannel !== selectedChannel) {
            if (playing) twitchPlayer.pause();
            playing = false;
            twitchPlayer.setChannel(selectedChannel);
            loadedChannel = selectedChannel;
        }
    }

    function setLive(isLive) {
        live = isLive;
        if (!live && ready && playing) {
            playing = false;
            twitchPlayer.pause();
        }
        updatePlaybackPrompt();
    }

    twitchPlayer.addEventListener(Twitch.Player.READY, () => {
        ready = true;
        selectChannel(selectedChannel);
        updatePlaybackPrompt();
    });
    twitchPlayer.addEventListener(Twitch.Player.ONLINE, () => {
        if (!testMode) setLive(true);
        else updatePlaybackPrompt();
    });
    twitchPlayer.addEventListener(Twitch.Player.OFFLINE, () => {
        if (!testMode) setLive(false);
        else showStatus("The selected test channel is offline. Choose a live channel to test playback.");
    });
    twitchPlayer.addEventListener(Twitch.Player.PLAY, () => {
        playing = true;
        showStatus();
    });
    twitchPlayer.addEventListener(Twitch.Player.PLAYING, () => {
        playing = true;
        showStatus();
    });
    twitchPlayer.addEventListener(Twitch.Player.PAUSE, () => {
        playing = false;
        if (live) showStatus("Preview paused. Press Play in the Twitch player to resume.");
        else showStatus();
    });
    twitchPlayer.addEventListener(Twitch.Player.PLAYBACK_BLOCKED, () => {
        playing = false;
        showStatus("Playback was blocked. Press Play in the Twitch player to watch.");
    });
    window.addEventListener("dashboard-stream-live-changed", event => {
        if (typeof event.detail?.isLive !== "boolean") return;
        actualLive = event.detail.isLive;
        if (!testMode) setLive(actualLive);
    });
    window.addEventListener("dashboard-stream-test-start", event => {
        const testChannel = event.detail?.channel;
        if (typeof testChannel !== "string") return;
        testMode = true;
        selectChannel(testChannel);
        setLive(true);
    });
    window.addEventListener("dashboard-stream-test-stop", event => {
        if (!testMode) return;
        testMode = false;
        actualLive = typeof event.detail?.isLive === "boolean" ? event.detail.isLive : actualLive;
        selectChannel(channel);
        setLive(actualLive);
    });
})();
