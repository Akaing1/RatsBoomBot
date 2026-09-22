(() => {
    const player = document.querySelector("[data-stream-player]");
    const channel = player?.dataset.channel?.trim();
    if (!channel) return;

    const url = new URL("https://player.twitch.tv/");
    url.searchParams.set("channel", channel);
    url.searchParams.set("parent", window.location.hostname);
    url.searchParams.set("autoplay", "false");
    url.searchParams.set("muted", "true");
    player.src = url.toString();
})();
