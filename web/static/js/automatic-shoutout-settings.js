(() => {
    document.querySelectorAll('[data-shoutout-user-list]').forEach(panel => {
        const form = panel.querySelector('[data-shoutout-list-form]');
        const value = form.querySelector('[data-shoutout-list-value]');
        const members = panel.querySelector('[data-shoutout-list-members]');
        const template = panel.querySelector('[data-shoutout-row-template]');
        const message = panel.querySelector('[data-protected-search-message]');
        const rows = new Map([...members.querySelectorAll('[data-user-login]')].map(row => [row.dataset.userLogin, row]));
        const collator = new Intl.Collator(undefined, {sensitivity: 'base'});
        const readNames = () => value.value.split(/\s+/).filter(Boolean).sort(collator.compare);
        let logins = readNames();
        function insertionIndex(login) {
            let low = 0, high = logins.length;
            while (low < high) {
                const middle = (low + high) >>> 1;
                if (collator.compare(logins[middle], login) < 0) low = middle + 1;
                else high = middle;
            }
            return low;
        }
        const immediate = form.hasAttribute('data-shoutout-autosave');
        let savedValue = value.value;
        let saving = false;
        let queued = false;
        function save() {
            if (saving) { queued = true; return; }
            saving = true;
            queued = false;
            form.requestSubmit();
        }
        const book = panel.closest('[data-settings-book]');
        book?.addEventListener('settings-saved', event => {
            if (!immediate || event.detail.form !== form) return;
            savedValue = new Map(JSON.parse(event.detail.snapshot)).get('value') || '';
            saving = false;
            if (queued && value.value !== savedValue) queueMicrotask(save);
        });
        book?.addEventListener('settings-save-failed', event => {
            if (!immediate || event.detail.form !== form) return;
            saving = false; queued = false;
            value.value = savedValue;
            render();
            value.dispatchEvent(new Event('input', {bubbles: true}));
        });
        function render() {
            logins = readNames();
            const children = logins.map(login => {
                let row = rows.get(login);
                if (!row) {
                    row = template.content.firstElementChild.cloneNode(true);
                    row.dataset.userLogin = login;
                    row.querySelector('.user-list-identity strong').textContent = login;
                    rows.set(login, row);
                }
                return row;
            });
            if (!children.length) {
                const empty = document.createElement('div');
                empty.className = 'protected-user-empty'; empty.textContent = 'No users added.'; children.push(empty);
            }
            members.replaceChildren(...children);
        }
        function changed() {
            value.value = logins.join('\n');
            value.dispatchEvent(new Event('input', {bubbles: true}));
            if (immediate) save();
        }
        panel.addEventListener('user-search-selected', event => {
            const user = event.detail;
            const login = user.login.toLowerCase();
            const index = insertionIndex(login);
            if (logins[index] === login) return;
            if (logins.length >= 100) { message.textContent = 'Use up to 100 usernames.'; return; }
            const row = template.content.firstElementChild.cloneNode(true);
            row.dataset.userLogin = login;
            row.querySelector('.user-list-identity strong').textContent = user.display_name && user.display_name.toLowerCase() !== login
                ? `${user.display_name} (${login})` : user.display_name || login;
            row.querySelector('.user-list-identity small').textContent = user.id;
            const avatar = row.querySelector('.protected-user-avatar');
            const url = user.profile_image_url;
            if (url) {
                const image = document.createElement('img'); image.src = url; image.alt = ''; image.width = 28; image.height = 28;
                image.loading = 'lazy'; image.decoding = 'async'; image.addEventListener('error', () => { image.hidden = true; }); avatar.append(image);
            }
            rows.set(login, row);
            logins.splice(index, 0, login);
            members.querySelector('.protected-user-empty')?.remove();
            members.insertBefore(row, members.children[index] || null);
            changed();
        });
        members.addEventListener('click', event => {
            const button = event.target.closest('[data-shoutout-list-remove]');
            if (!button) return;
            const login = button.closest('[data-user-login]').dataset.userLogin;
            const index = insertionIndex(login);
            if (logins[index] !== login) return;
            logins.splice(index, 1);
            button.closest('[data-user-login]').remove();
            if (!logins.length) {
                const empty = document.createElement('div');
                empty.className = 'protected-user-empty'; empty.textContent = 'No users added.'; members.append(empty);
            }
            changed();
        });
        form.addEventListener('input', event => { if (event.target === form) render(); });
        render();
    });
})();
