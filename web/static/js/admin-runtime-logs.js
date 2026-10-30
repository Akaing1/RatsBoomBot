(() => {
 const viewer = document.getElementById('runtime-log-viewer');
 const search = document.getElementById('runtime-search');
 const severity = document.getElementById('runtime-level');
 const follow = document.getElementById('runtime-follow');
 let entries = [];
 let lastEntryId = 0;
 const matches = entry => entry.message.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase()) && (severity.value === 'all' || (severity.value === 'warnings' ? ['WARNING','ERROR','CRITICAL'].includes(entry.level) : ['ERROR','CRITICAL'].includes(entry.level)));
 const updateCount = () => {
  const visible = entries.filter(matches).length;
  document.getElementById('runtime-count').textContent = `${visible} of ${entries.length} buffered entries`;
  const empty = document.getElementById('runtime-empty');
  empty.hidden = visible > 0;
  empty.textContent = entries.length ? 'No entries match these filters.' : 'No entries in this view yet.';
 };
 const render = (shouldFollow = false) => {
  const scrollTop = viewer.scrollTop;
  const fragment = document.createDocumentFragment();
  for (const entry of entries.filter(matches)) {
   const row = document.createElement('div');
   row.className = `runtime-log-entry level-${entry.level.toLowerCase()}`;
   for (const [name, text] of [['time',new Date(entry.timestamp).toLocaleTimeString()],['level',entry.level],['message',entry.message]]) {
    const cell = document.createElement('span'); cell.className = `runtime-log-${name}`; cell.textContent = text; row.appendChild(cell);
   }
   fragment.appendChild(row);
  }
  viewer.replaceChildren(fragment);
  viewer.scrollTop = follow.checked && shouldFollow ? viewer.scrollHeight : scrollTop;
  updateCount();
 };
 search.addEventListener('input', () => render());
 severity.addEventListener('change', () => render());
 document.getElementById('clear-logs').addEventListener('click', () => { entries = []; render(); });
 render();
        const status = document.getElementById("logs-status");
        const toggle = document.getElementById("logs-toggle");

        let paused = false;
        let expired = false;
        let timer;
        let controller;
        let failures = 0;
        const pollLogs = async () => {
            clearTimeout(timer);
            if (paused || expired || document.hidden || controller) return;
            controller = new AbortController();
            const timeout = setTimeout(() => controller?.abort(), 8000);
            try {
                status.textContent = "Updating";
                const response = await fetch(`/admin/runtime-logs/data?after=${lastEntryId}`, {
                    cache: "no-store", signal: controller.signal, redirect: "error"
                });
                if (response.status === 401 || response.status === 403) {
                    expired = true;
                    document.getElementById("logs-sign-in").hidden = false;
                    toggle.disabled = true;
                    throw new Error("Session expired");
                }
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const payload = await response.json();
                const shouldFollow = viewer.scrollHeight - viewer.scrollTop - viewer.clientHeight < 80;
                for (const entry of payload.entries) {
                    entries.push(entry);
                    lastEntryId = Math.max(lastEntryId, entry.id);
                }
                entries = entries.slice(-1000);
                if (payload.entries.length) render(shouldFollow);
                else updateCount();
                failures = 0;
                status.textContent = "Live";
                status.classList.add("connected");
            } catch (error) {
                failures++;
                status.textContent = expired ? "Sign in required" : "Update failed · retrying";
                status.classList.remove("connected");
            } finally {
                clearTimeout(timeout);
                controller = null;
                if (paused || document.hidden) {
                    status.textContent = paused ? "Paused" : "Updates paused while hidden";
                    status.classList.remove("connected");
                } else if (!expired) {
                    timer = setTimeout(pollLogs, failures ? Math.min(30000, 5000 * 2 ** Math.min(failures, 3)) : 2000);
                }
            }
        };
        const suspend = () => {
            clearTimeout(timer);
            controller?.abort();
            status.textContent = paused ? "Paused" : "Updates paused while hidden";
            status.classList.remove("connected");
        };
        toggle.addEventListener("click", () => {
            paused = !paused;
            toggle.textContent = paused ? "Resume updates" : "Pause updates";
            toggle.setAttribute("aria-pressed", String(paused));
            if (paused) suspend(); else pollLogs();
        });
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) suspend(); else pollLogs();
        });
        window.addEventListener("pagehide", suspend);
        pollLogs();
})();
