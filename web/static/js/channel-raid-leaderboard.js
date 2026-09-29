(() => {
    const panel = document.getElementById("raid-contributor-panel");
    const boss = document.getElementById("raid-contributor-boss");
    const list = document.getElementById("raid-contributor-list");
    const state = document.getElementById("raid-contributor-state");

    if (!panel || !boss || !list) {
        return;
    }

    const number = new Intl.NumberFormat();

    function makeEmptyRow(message) {
        const empty = document.createElement("li");
        empty.className = "raid-contributor-empty";
        empty.textContent = message;
        return empty;
    }

    function render(data) {
        const contributors = Array.isArray(data.contributors) ? data.contributors : [];

        panel.hidden = false;

        if (!data.active) {
            state.textContent = "Idle";
            boss.textContent = "No active boss.";
            list.replaceChildren(makeEmptyRow("No active encounter yet."));
            return;
        }

        state.textContent = "Live";
        boss.textContent = `${data.boss_name} · ${number.format(data.current_hp)}/${number.format(data.max_hp)} HP`;
        if (contributors.length === 0) {
            list.replaceChildren();
            list.append(makeEmptyRow("No contributors yet."));
            return;
        }

        list.replaceChildren(...contributors.map((contributor) => {
            const row = document.createElement("li");
            row.className = "raid-contributor-row";

            const rank = document.createElement("span");
            rank.className = "raid-contributor-rank";
            rank.textContent = `#${contributor.rank}`;

            const name = document.createElement("strong");
            name.className = "raid-contributor-name";
            name.textContent = contributor.user_label || contributor.username;

            const damage = document.createElement("span");
            damage.className = "raid-contributor-damage";
            damage.textContent = `${number.format(contributor.damage)} damage`;

            row.append(rank, name, damage);
            return row;
        }));
        panel.hidden = false;
    }

    async function refresh() {
        try {
            const response = await fetch("/channel/api/raid-contributors", {
                headers: {"Accept": "application/json"},
                cache: "no-store"
            });

            if (response.ok) {
                render(await response.json());
            }
        } catch (_error) {
            // Keep the most recent successful data visible during a transient refresh failure.
        }
    }

    window.setInterval(refresh, 15000);
})();
