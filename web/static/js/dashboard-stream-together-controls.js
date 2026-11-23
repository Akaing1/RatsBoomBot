(() => {
    window.createStreamTogetherControls = (dialog, onSampleChange, requestEnd) => {
        const panel = dialog.querySelector('[data-stream-together-controls]');
        const status = panel.querySelector('[data-stream-controls-status]');
        const guests = panel.querySelector('[data-stream-guests]');
        const start = panel.querySelector('[data-stream-action="start"]');
        const idle = panel.querySelector('[data-stream-call-idle]');
        const end = panel.querySelector('[data-stream-action="end"]');
        const invite = panel.querySelector('[data-stream-invite]');
        const reconnect = panel.querySelector('[data-stream-reconnect]');
        const hideToggle = panel.querySelector('[data-stream-hide-offline]');
        const invitations = panel.querySelector('[data-stream-invitations]');
        const footer = panel.querySelector('.stream-call-footer');
        const cardGrid = panel.querySelector('[data-stream-cards]');
        // This controller is available only through the session owner's endpoints.
        const cards = window.createStreamTogetherCards(panel, () => {},
            guest => action('remove', {slot_id: guest.slot_id, guest_id: guest.user_id}), () => state?.is_host !== false,
            dialog.dataset.channelId);
        const callLink = panel.querySelector('.stream-together-session-actions a');
        const sharedChat = panel.querySelector('[data-shared-chat-shortcut]');
        const layout = dialog.closest('[data-stream-together-layout]');
        const chatShortcut = dialog.hasAttribute('data-stream-together-page') ? document.querySelector('.dashboard-shared-chat-link') : null;
        const hostPicker = panel.querySelector('[data-stream-host-picker]');
        const hostEvents = new AbortController();
        const ownCallUrl = callLink.href;
        const root = document.body.dataset.channelRoot || '/channel';
        const names = new Map();
        let state, request, writing = false, closed = false, snapshot, cardSnapshot, invitationSnapshot, confirmation, previewState = null;
        let guestHost = '';
        const node = (tag, text) => { const element = document.createElement(tag); if (text) element.textContent = text; return element; };
        function show(text, error = false) {
            if (status.textContent !== text) status.textContent = text;
            status.classList.toggle('is-error', error);
        }
        function cancelConfirmation() { confirmation?.remove(); confirmation = null; }
        function confirm(button, label, run) {
            cancelConfirmation();
            const tray = node('span'); tray.className = 'stream-together-confirm';
            const yes = node('button', label), no = node('button', 'Cancel');
            yes.type = no.type = 'button'; yes.className = 'button danger'; no.className = 'button secondary';
            yes.addEventListener('click', () => { cancelConfirmation(); run(); });
            no.addEventListener('click', cancelConfirmation);
            tray.append(yes, no); button.after(tray); confirmation = tray; yes.focus();
        }
        function outside(event) {
            if (confirmation && !confirmation.contains(event.target) && !event.target.closest('[data-stream-confirm]')) cancelConfirmation();
            const path = event.composedPath();
            panel.querySelectorAll('.stream-call-footer details[open]').forEach(menu => { if (!path.includes(menu)) menu.open = false; });
        }
        async function removeGuest(values) {
            const current = state;
            const session = current?.session;
            const guest = session?.guests.find(entry => String(entry.user_id) === String(values.guest_id)
                && String(entry.slot_id) === String(values.slot_id) && String(entry.slot_id) !== '0');
            if (!guest || current.is_host === false) return false;
            await cards.animateRemoval(guest.user_id);
            if (closed) return false;
            const updated = {...current, session: {...session, guests: session.guests.filter(entry => entry !== guest)}};
            if (previewState) {
                previewState = updated;
                onSampleChange?.(updated);
            }
            render(updated);
            return true;
        }
        async function action(kind, values = {}) {
            if (closed || writing) return;
            if (previewState) {
                if (kind === 'remove') {
                    writing = true;
                    try {
                        if (await removeGuest(values)) show('Test mode: participant removed from the preview.');
                    } finally { writing = false; }
                    return;
                }
                show('Test mode: no changes are sent to Twitch.');
                return;
            }
            let callWindow;
            if (kind === 'start') {
                // Open during the click; navigating after the request would lose popup permission.
                callWindow = window.open('about:blank', '_blank');
                if (!callWindow) {
                    show('Allow popups for this dashboard, then start the session again.', true);
                    return;
                }
                callWindow.opener = null;
            }
            writing = true; request?.abort(); request = null;
            panel.setAttribute('aria-busy', 'true');
            panel.querySelectorAll('button:not([data-stream-call-refresh]), input, select').forEach(control => { control.disabled = true; });
            show('Updating session…');
            try {
                const response = await fetch(`${root}/api/stream-together/control`, {method: 'POST',
                    body: new URLSearchParams({action: kind, session_id: state?.session?.id || '', csrf_token: dialog.dataset.csrfToken, ...values})});
                const data = await response.json();
                if (!closed) reconnect.hidden = !data.reconnect;
                if (!response.ok) throw new Error(data.detail || 'Could not update the session.');
                if (callWindow && !callWindow.closed) callWindow.location.replace(callLink.href);
                if (closed) return;
                if (kind === 'remove') await removeGuest(values);
                if (closed) return;
                show(kind === 'invite' ? 'Invitation sent.' : 'Session updated.');
                window.dispatchEvent(new CustomEvent('dashboard-stream-participants-changed'));
            } catch (error) {
                callWindow?.close();
                if (!closed) show(error.message, true);
            }
            finally {
                writing = false;
                if (!closed) {
                    panel.removeAttribute('aria-busy'); snapshot = null;
                    await refresh(true);
                }
            }
        }
        function slotSelect(value, available) {
            const select = node('select'); select.setAttribute('aria-label', 'Guest slot');
            for (let slot = 1; slot <= state.slot_count; slot++) {
                const option = node('option', `Slot ${slot}`); option.value = String(slot);
                option.disabled = available && !available.includes(String(slot)); select.append(option);
            }
            select.value = String(value); return select;
        }
        function syncSharedChat() {
            if (state && chatShortcut && !layout?.hidden) {
                const active = Boolean(state.session);
                const host = state.is_host !== false;
                chatShortcut.hidden = !active || Boolean(previewState);
                if (host) {
                    chatShortcut.href = ownCallUrl;
                    chatShortcut.removeAttribute('aria-disabled');
                    chatShortcut.removeAttribute('role');
                } else {
                    chatShortcut.removeAttribute('href');
                    chatShortcut.setAttribute('aria-disabled', 'true');
                    chatShortcut.setAttribute('role', 'link');
                }
                for (const shortcut of [chatShortcut, sharedChat]) {
                    shortcut.classList.toggle('is-active', state.shared_chat_active === true);
                    const label = state.shared_chat_active ? 'Shared Chat is active'
                        : host ? 'Start Shared Chat on Twitch' : 'Only the host can start Shared Chat';
                    shortcut.setAttribute('aria-label', label);
                    shortcut.title = label;
                }
            }
        }
        function render(data) {
            const next = JSON.stringify(data);
            if (snapshot === next) return;
            const restoreControls = snapshot == null;
            snapshot = next;
            state = data;
            const active = Boolean(data.session);
            const host = data.is_host !== false;
            // Only use links to Twitch's call interface returned by our endpoint.
            const callUrl = data.call_url;
            const validCallUrl = /^https:\/\/www\.twitch\.tv\/popout\/[a-z0-9_]{1,25}\/guest-star$/i.test(callUrl || '');
            callLink.href = validCallUrl ? callUrl : ownCallUrl;
            callLink.hidden = active && !host && !validCallUrl;
            idle.hidden = active;
            footer.hidden = !active;
            cardGrid.hidden = !active;
            hideToggle.hidden = !active;
            sharedChat.hidden = !active || !host || Boolean(previewState);
            syncSharedChat();
            start.hidden = active; start.disabled = false; end.hidden = !active; end.disabled = false; invite.hidden = !active || !host;
            invite.querySelectorAll('input, button').forEach(control => { control.disabled = !active; });
            hideToggle.disabled = false;
            invitations.hidden = !host || !data.invites.length;
            const participants = data.session?.guests || [];
            const nextCards = JSON.stringify([data.session?.id, host, data.host_id, participants]);
            if (restoreControls || cardSnapshot !== nextCards) {
                cardSnapshot = nextCards;
                cards.update(participants, data.host_id);
            }
            if (!active) {
                cancelConfirmation(); guests.replaceChildren(); invitationSnapshot = null;
                return;
            }
            const occupied = new Set(data.session.guests.map(guest => String(guest.slot_id)));
            const available = Array.from({length: data.slot_count}, (_, index) => String(index + 1)).filter(slot => !occupied.has(slot));
            const nextInvitations = JSON.stringify([data.session.id, host, data.slot_count, available, data.invites]);
            if (!restoreControls && invitationSnapshot === nextInvitations) return;
            invitationSnapshot = nextInvitations;
            cancelConfirmation(); guests.replaceChildren();
            for (const pending of data.invites) {
                const row = node('article'); row.className = 'stream-together-guest';
                row.append(node('strong', names.get(pending.user_id) || pending.user_display_name || `Guest ${pending.user_id}`), node('span', pending.status));
                const slot = slotSelect(available[0] || '', available); slot.disabled = !available.length;
                const assign = node('button', 'Add to call'); assign.type = 'button'; assign.className = 'button primary'; assign.disabled = pending.status !== 'READY' || !available.length;
                assign.title = pending.status !== 'READY' ? 'Waiting for the guest to be ready' : !available.length ? 'No free guest slots' : 'Add to call';
                assign.addEventListener('click', () => action('assign', {guest_id: pending.user_id, slot_id: slot.value}));
                const revoke = node('button', 'Revoke invite'); revoke.type = 'button'; revoke.className = 'button secondary'; revoke.dataset.streamConfirm = '';
                revoke.addEventListener('click', () => confirm(revoke, 'Revoke invite?', () => action('revoke', {guest_id: pending.user_id})));
                row.append(slot, assign, revoke); guests.append(row);
            }
        }
        async function refresh(keepStatus = false, manual = false) {
            if (closed || writing || request || previewState || !dialog.open || document.hidden || layout?.hidden) return;
            const controller = new AbortController(); request = controller;
            try {
                const query = new URLSearchParams();
                if (manual) query.set('refresh', 'true');
                if (guestHost) query.set('guest_host', guestHost);
                const response = await fetch(`${root}/api/stream-together/guests${query.size ? `?${query}` : ''}`, {signal: controller.signal, cache: 'no-store'});
                const data = await response.json(); if (closed || controller.signal.aborted) return;
                reconnect.hidden = !data.reconnect;
                if (!response.ok) throw new Error(data.detail || 'Session controls are unavailable.');
                render(data);
                if (!keepStatus) {
                    show(data.shared_chat_only ? 'Shared Chat is active. Showing the channels sharing chat.'
                        : data.session ? 'Session active.' : guestHost ? `Waiting for you to join @${guestHost}’s call on Twitch.` : 'No active session.');
                }
            } catch (error) {
                if (!closed && !controller.signal.aborted) {
                    snapshot = null;
                    if (!state?.session) idle.hidden = false;
                    show(error.message, true);
                    panel.querySelectorAll('button:not([data-stream-call-refresh]), input, select').forEach(control => { control.disabled = true; });
                    hostPicker?.querySelectorAll('input, button').forEach(control => { control.disabled = false; });
                }
            } finally { if (request === controller) request = null; }
        }
        if (hostPicker) {
            const form = hostPicker.querySelector('form');
            const message = hostPicker.querySelector('[data-stream-host-status]');
            function findHost(value) {
                const host = value.match(/^https:\/\/(?:www\.)?twitch\.tv\/popout\/([a-z0-9_]{1,25})\/guest-star\/?(?:[?#].*)?$/i)?.[1]
                    || value.match(/^@?([a-z0-9_]{1,25})$/i)?.[1];
                if (!host) {
                    message.textContent = 'Enter the host’s Twitch username or paste their Twitch call page link.';
                    return;
                }
                message.textContent = '';
                guestHost = host.toLowerCase();
                request?.abort(); request = null;
                refresh();
            }
            form.addEventListener('submit', event => {
                event.preventDefault();
                findHost(form.elements.query.value.trim());
            }, {capture: true, signal: hostEvents.signal});
            form.addEventListener('user-search-selected', event => findHost(event.detail.login || ''), {signal: hostEvents.signal});
        }
        function hideOffline() {
            const enabled = hideToggle.getAttribute('aria-checked') !== 'true';
            hideToggle.setAttribute('aria-checked', String(enabled));
            hideToggle.classList.remove('is-previewing');
            cards.hideOffline(enabled);
        }
        function previewVisibility() { hideToggle.classList.add('is-previewing'); }
        function resetVisibilityPreview() { hideToggle.classList.remove('is-previewing'); }
        hideToggle.addEventListener('pointerenter', previewVisibility);
        hideToggle.addEventListener('pointerleave', resetVisibilityPreview);
        hideToggle.addEventListener('focus', previewVisibility);
        hideToggle.addEventListener('blur', resetVisibilityPreview);
        hideToggle.addEventListener('click', hideOffline);
        function onStart() { action('start'); }
        function onEnd() { requestEnd(end, state); }
        function onInvite(event) { names.set(event.detail.id, event.detail.display_name || event.detail.login); action('invite', {guest_id: event.detail.id}); }
        start.addEventListener('click', onStart); end.addEventListener('click', onEnd);
        invite.addEventListener('user-search-selected', onInvite); dialog.addEventListener('click', outside);
        return {refresh, syncSharedChat, pause() {
            request?.abort(); request = null;
        }, sessionEnded() {
            request?.abort(); request = null;
            render({...state, session: null, invites: []});
            show('Call ended.');
        }, simulate(data) {
            if (writing) throw new Error('Wait for the current session update to finish before changing test mode.');
            request?.abort(); request = null; snapshot = null; cancelConfirmation(); previewState = data;
            if (data) { render(data); show('Test mode: simulated participants. No calls are started or changed.'); }
            else { show('Loading session…'); refresh(); }
        }, destroy() { closed = true; request?.abort(); hostEvents.abort(); cancelConfirmation(); cards.destroy(); hideToggle.removeEventListener('click', hideOffline); hideToggle.removeEventListener('pointerenter', previewVisibility); hideToggle.removeEventListener('pointerleave', resetVisibilityPreview); hideToggle.removeEventListener('focus', previewVisibility); hideToggle.removeEventListener('blur', resetVisibilityPreview); start.removeEventListener('click', onStart); end.removeEventListener('click', onEnd); invite.removeEventListener('user-search-selected', onInvite); dialog.removeEventListener('click', outside); }};
    };
})();
