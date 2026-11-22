(() => {
    window.createStreamTogetherCards = (panel, onSelect, onKick, canKick = () => true, ownId) => {
        const grid = panel.querySelector('[data-stream-cards]');
        const stage = panel.querySelector('[data-stream-call-stage]') || grid.parentElement;
        const cards = new Map();
        const animations = new Set();
        let transitioning = false, transitionVersion = 0;
        let entries = [], selected, hideOffline = false, focused = false, closed = false;
        const order = window.createDashboardParticipantOrder(grid, '.stream-call-card', element => element.dataset.userId,
            layout, element => element.dataset.userId !== ownId && (!focused || element.dataset.userId !== selected));
        function syncPlayers() {
            const active = focused && !transitioning ? cards.get(selected) : null;
            const rect = active && !active.videoHidden && !active.element.hidden && !active.guest.test_mode
                && active.guest.is_streaming === true && active.guest.user_login && active.media.getBoundingClientRect();
            const playing = rect && rect.width >= 400 && rect.height >= 300 ? active : null;
            cards.forEach(card => syncPlayer(card, card === playing));
        }
        function syncPlayer(card, allowed) {
            if (!allowed && card.player) { card.player.destroy(); card.player = null; }
            card.playerHost.hidden = !allowed;
            if (allowed && !card.player) {
                card.element.classList.add('is-player-starting');
                card.player = window.createRaidPreviewPlayer(card.playerHost, card.guest.user_login, () => {
                    card.element.classList.remove('is-player-starting');
                });
            }
            if (!allowed) card.element.classList.remove('is-player-starting');
        }
        function updateVideo(card) {
            const guest = card.guest;
            const thumbnail = !card.videoHidden && guest.is_streaming === true ? guest.thumbnail_url : '';
            card.poster.hidden = !thumbnail;
            if (thumbnail && card.poster.getAttribute('src') !== thumbnail) card.poster.src = thumbnail;
            card.avatar.hidden = Boolean(thumbnail) || !guest.profile_image_url;
            card.portrait.hidden = !thumbnail || !guest.profile_image_url;
            for (const image of [card.avatar, card.portrait]) {
                if (guest.profile_image_url && image.getAttribute('src') !== guest.profile_image_url) image.src = guest.profile_image_url;
            }
            card.hide.textContent = card.videoHidden ? 'Show video' : 'Hide video';
            const live = guest.is_streaming === true;
            card.element.classList.toggle('is-live', live);
            if (live) card.select.setAttribute('aria-description', 'Live on Twitch');
            else card.select.removeAttribute('aria-description');
        }
        const observer = new ResizeObserver(() => {
            stopTransition();
            layout();
        });
        observer.observe(stage);
        function stopTransition() {
            transitionVersion++;
            animations.forEach(animation => animation.cancel()); animations.clear();
            transitioning = false;
        }
        function changeView(change) {
            const before = new Map([...cards].filter(([, card]) => !card.element.hidden)
                .map(([id, card]) => [id, card.element.getBoundingClientRect()]));
            stopTransition();
            transitioning = !matchMedia('(prefers-reduced-motion: reduce)').matches;
            change(); layout();
            if (!transitioning) return;
            const version = transitionVersion;
            cards.forEach((card, id) => {
                const from = before.get(id), to = card.element.getBoundingClientRect();
                if (card.element.hidden || !from?.width || !to.width || !to.height) return;
                const animation = card.element.animate([
                    {transform: `translate(${from.left - to.left}px, ${from.top - to.top}px) scale(${from.width / to.width}, ${from.height / to.height})`, transformOrigin: 'top left'},
                    {transform: 'none', transformOrigin: 'top left'}
                ], {duration: 180, easing: 'cubic-bezier(.2,.7,.2,1)'});
                animations.add(animation);
            });
            // Start Twitch only after the animated ancestors are fully visible
            // and untransformed, as required for embedded autoplay.
            Promise.all([...animations].map(animation => animation.finished.catch(() => {}))).then(() => {
                if (closed || version !== transitionVersion) return;
                animations.clear(); transitioning = false; syncPlayers();
            });
        }
        function choose(id) {
            if (focused && selected === id) { showGrid(); return; }
            changeView(() => { selected = id; focused = true; });
            onSelect(cards.get(id)?.guest);
        }
        function labelPreview(card) {
            const label = focused && card.guest.user_id === selected
                ? 'Return to split view' : `Expand ${card.name.textContent}`;
            if (card.select.getAttribute('aria-label') !== label) card.select.setAttribute('aria-label', label);
        }
        function layout() {
            const hasVideo = guest => guest.is_streaming === true && !cards.get(guest.user_id)?.videoHidden;
            const visible = entries.filter(guest => !hideOffline || (guest.is_streaming !== false && !cards.get(guest.user_id)?.videoHidden))
                .sort((left, right) => Number(right.user_id === ownId) - Number(left.user_id === ownId)
                    || Number(hasVideo(right)) - Number(hasVideo(left)));
            order.sort(visible, guest => guest.user_id);
            visible.sort((left, right) => Number(right.user_id === ownId) - Number(left.user_id === ownId));
            const focusedControl = document.activeElement;
            for (const [index, guest] of visible.entries()) {
                const card = cards.get(guest.user_id);
                if (grid.children[index] === card.element) continue;
                if (card.player) {
                    // Move the preceding cards around the playing iframe to keep it mounted.
                    while (grid.children[index] !== card.element) {
                        grid.insertBefore(grid.children[index], card.element.nextElementSibling);
                    }
                } else grid.insertBefore(card.element, grid.children[index] || null);
            }
            if (grid.contains(focusedControl) && document.activeElement !== focusedControl) focusedControl.focus({preventScroll: true});
            const visibleIds = new Set(visible.map(guest => guest.user_id));
            if (!visibleIds.has(selected)) selected = visible[0]?.user_id;
            if (!visible.length) focused = false;
            grid.classList.toggle('is-focused', focused);
            grid.dataset.count = String(visible.length);
            const columns = visible.length <= 1 ? 1 : visible.length <= 4 ? 2 : 3;
            const gap = 8;
            const width = stage.clientWidth;
            const height = Math.max(0, stage.clientHeight - 4);
            grid.style.setProperty('--stream-call-columns', String(columns));
            const rows = Math.ceil(visible.length / columns) || 1;
            const cardWidth = Math.max(0, Math.min((width - 4 - gap * (columns - 1)) / columns,
                ((height - gap * (rows - 1)) / rows - 4) * 16 / 9 + 4));
            grid.style.setProperty('--stream-call-card-width', `${cardWidth}px`);
            grid.style.width = focused ? '100%' : `${columns * cardWidth + gap * (columns - 1)}px`;
            grid.style.setProperty('--stream-call-grid-height', `${height}px`);
            const others = Math.max(1, visible.length - 1);
            const rowWidth = Math.max(4, (width - 4 - gap * (others - 1)) / others);
            const reservedRowHeight = Math.min(height * .24, (rowWidth - 4) * 9 / 16 + 4);
            const selectedHeight = height - (visible.length > 1 ? reservedRowHeight + gap : 0);
            const selectedWidth = Math.max(4, Math.min(width - 4, (selectedHeight - 4) * 16 / 9 + 4));
            const videoHeight = (selectedWidth - 4) * 9 / 16 + 4;
            const miniWidth = Math.max(4, Math.min(rowWidth, (height - videoHeight - gap - 4) * 16 / 9 + 4));
            const miniHeight = (miniWidth - 4) * 9 / 16 + 4;
            grid.style.setProperty('--stream-call-mini-width', `${miniWidth}px`);
            grid.style.setProperty('--stream-call-mini-height', `${miniHeight}px`);
            grid.style.setProperty('--stream-call-selected-width', `${selectedWidth}px`);
            grid.style.setProperty('--stream-call-selected-height', `${videoHeight}px`);
            cards.forEach((card, id) => {
                card.element.hidden = !visibleIds.has(id);
                card.element.classList.toggle('is-selected', id === selected);
                card.select.setAttribute('aria-pressed', String(id === selected));
                labelPreview(card);
            });
            syncPlayers();
        }
        function update(next, hostId) {
            const incoming = next.filter(guest => /^\d+$/.test(String(guest.user_id)))
                .map(guest => ({...guest, user_id: String(guest.user_id)}));
            const layoutChanged = entries.length !== incoming.length || incoming.some((guest, index) =>
                guest.user_id !== entries[index].user_id || guest.is_streaming !== entries[index].is_streaming);
            const previousPreview = cards.get(selected)?.guest;
            if (layoutChanged) stopTransition();
            entries = incoming;
            const ids = new Set(entries.map(guest => guest.user_id));
            cards.forEach((card, id) => {
                if (ids.has(id)) return;
                card.exitAnimation?.cancel();
                card.player?.destroy();
                card.menu.remove();
                card.element.remove();
                cards.delete(id);
            });
            for (const guest of entries) {
                let card = cards.get(guest.user_id);
                if (!card) {
                    const element = document.createElement('article'); element.className = 'stream-call-card'; element.dataset.userId = guest.user_id;
                    const media = document.createElement('div'); media.className = 'stream-call-media';
                    const poster = document.createElement('img'); poster.className = 'stream-call-poster'; poster.alt = ''; poster.decoding = 'async';
                    poster.addEventListener('error', () => { poster.hidden = true; });
                    const avatar = document.createElement('img'); avatar.className = 'stream-call-avatar'; avatar.alt = ''; avatar.decoding = 'async';
                    avatar.addEventListener('error', () => { avatar.hidden = true; });
                    const playerHost = document.createElement('div'); playerHost.className = 'stream-call-player'; playerHost.hidden = true;
                    const portrait = document.createElement('img'); portrait.className = 'stream-call-portrait'; portrait.alt = ''; portrait.decoding = 'async';
                    portrait.addEventListener('error', () => { portrait.hidden = true; });
                    const more = document.createElement('button'); more.type = 'button'; more.className = 'stream-call-more'; more.textContent = '⋮'; more.setAttribute('aria-haspopup', 'menu'); more.setAttribute('aria-expanded', 'false');
                    const menu = document.createElement('div'); menu.className = 'stream-call-participant-menu'; menu.popover = 'auto'; menu.setAttribute('role', 'menu');
                    const hide = document.createElement('button'); hide.type = 'button'; hide.setAttribute('role', 'menuitem'); menu.append(hide);
                    const kick = document.createElement('button'); kick.type = 'button'; kick.setAttribute('role', 'menuitem'); kick.className = 'danger'; menu.append(kick);
                    panel.append(menu);
                    const select = document.createElement('button'); select.type = 'button'; select.className = 'stream-call-card-name';
                    const name = document.createElement('strong'), state = document.createElement('small'); select.append(name, state);
                    media.append(poster, avatar, playerHost, portrait, more); element.append(media, select); grid.append(element);
                    card = {element, media, poster, avatar, playerHost, portrait, more, menu, hide, kick, select, name, state, player: null, videoHidden: false};
                    const current = card;
                    more.addEventListener('click', event => {
                        event.stopPropagation();
                        if (menu.matches(':popover-open')) { menu.hidePopover(); return; }
                        kick.textContent = 'Kick'; kick.dataset.confirming = '';
                        const rect = more.getBoundingClientRect();
                        menu.style.left = `${Math.max(4, Math.min(rect.right - 160, window.innerWidth - 164))}px`;
                        menu.style.top = `${Math.max(4, Math.min(rect.bottom + 4, window.innerHeight - 100))}px`;
                        menu.showPopover();
                    });
                    menu.addEventListener('toggle', () => more.setAttribute('aria-expanded', String(menu.matches(':popover-open'))));
                    hide.addEventListener('click', () => { current.videoHidden = !current.videoHidden; updateVideo(current); menu.hidePopover(); layout(); });
                    kick.addEventListener('click', () => {
                        if (!kick.dataset.confirming) { kick.dataset.confirming = 'true'; kick.textContent = 'Confirm kick'; return; }
                        menu.hidePopover(); onKick?.(current.guest);
                    });
                    cards.set(guest.user_id, card);
                    element.addEventListener('click', () => choose(guest.user_id));
                }
                if (card.guest?.user_login !== guest.user_login) { card.player?.destroy(); card.player = null; }
                card.guest = guest;
                const name = guest.user_display_name || guest.user_login || guest.user_id;
                if (card.name.textContent !== name) {
                    card.name.textContent = name;
                    card.more.setAttribute('aria-label', `${name} options`);
                }
                const isHost = hostId ? guest.user_id === hostId : String(guest.slot_id) === '0';
                const label = isHost ? 'Host' : guest.slot_id != null ? `Slot ${guest.slot_id}` : '';
                if (card.state.textContent !== label) card.state.textContent = label;
                card.select.disabled = card.more.disabled = card.hide.disabled = card.kick.disabled = false;
                card.kick.hidden = !onKick || !canKick() || !/^\d+$/.test(String(guest.slot_id)) || String(guest.slot_id) === '0';
                updateVideo(card);
                if (!layoutChanged) labelPreview(card);
            }
            if (layoutChanged) layout();
            const preview = cards.get(selected)?.guest;
            if (!layoutChanged && (preview?.user_login !== previousPreview?.user_login
                || preview?.test_mode !== previousPreview?.test_mode)) syncPlayers();
            return preview;
        }
        function showGrid() { changeView(() => { focused = false; }); }
        function animateRemoval(id) {
            const card = cards.get(String(id));
            if (!card || card.element.hidden || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
            if (card.exitAnimation) return card.exitAnimation.finished.catch(() => {});
            card.element.inert = true;
            card.exitAnimation = card.element.animate([
                {opacity: 1, scale: '1'},
                {opacity: 0, scale: '.92'}
            ], {duration: 180, easing: 'ease-in', fill: 'forwards'});
            return card.exitAnimation.finished.catch(() => {});
        }
        return {update, animateRemoval, hideOffline(value) { stopTransition(); hideOffline = value; layout(); onSelect(cards.get(selected)?.guest); }, destroy() {
            closed = true; order.destroy(); stopTransition(); observer.disconnect();
            cards.forEach(card => { card.exitAnimation?.cancel(); card.player?.destroy(); card.menu.remove(); }); cards.clear(); grid.replaceChildren();
        }};
    };
})();
