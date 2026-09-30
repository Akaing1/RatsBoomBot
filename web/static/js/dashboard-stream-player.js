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
    let manualPaused = false;
    let playing = false;
    let selectedChannel = channel;
    let loadedChannel = channel;

    function selectChannel(nextChannel) {
        selectedChannel = nextChannel;
        if (ready && loadedChannel !== selectedChannel) {
            twitchPlayer.setChannel(selectedChannel);
            loadedChannel = selectedChannel;
        }
    }

    function startIfAllowed() {
        if (!ready || !live || manualPaused) return;
        showStatus();
        twitchPlayer.play();
    }

    function setLive(isLive) {
        if (live === isLive) return;
        live = isLive;
        if (live) {
            startIfAllowed();
        } else {
            manualPaused = false;
            showStatus();
            if (ready && playing) twitchPlayer.pause();
        }
    }

    twitchPlayer.addEventListener(Twitch.Player.READY, () => {
        ready = true;
        selectChannel(selectedChannel);
        startIfAllowed();
    });
    twitchPlayer.addEventListener(Twitch.Player.ONLINE, () => {
        if (!testMode) setLive(true);
        else startIfAllowed();
    });
    twitchPlayer.addEventListener(Twitch.Player.OFFLINE, () => {
        if (!testMode) setLive(false);
        else showStatus("The selected test channel is offline. Choose a live channel to test playback.");
    });
    twitchPlayer.addEventListener(Twitch.Player.PLAY, () => {
        playing = true;
        manualPaused = false;
        showStatus();
    });
    twitchPlayer.addEventListener(Twitch.Player.PLAYING, () => {
        playing = true;
        manualPaused = false;
        showStatus();
    });
    twitchPlayer.addEventListener(Twitch.Player.PAUSE, () => {
        if (live && playing) manualPaused = true;
        playing = false;
    });
    twitchPlayer.addEventListener(Twitch.Player.PLAYBACK_BLOCKED, () => {
        showStatus("Autoplay was blocked. Press Play in the Twitch player to watch.");
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
        manualPaused = false;
        selectChannel(testChannel);
        live = true;
        startIfAllowed();
    });
    window.addEventListener("dashboard-stream-test-stop", event => {
        if (!testMode) return;
        testMode = false;
        manualPaused = false;
        actualLive = typeof event.detail?.isLive === "boolean" ? event.detail.isLive : actualLive;
        selectChannel(channel);
        live = !actualLive;
        setLive(actualLive);
    });
})();
