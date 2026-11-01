(() => {

        const formatBytes = (value) => {
            if (value === null || value === undefined) return "Unavailable";
            const units = ["B", "KB", "MB", "GB", "TB"];
            let amount = Number(value);
            let unit = 0;
            while (amount >= 1024 && unit < units.length - 1) {
                amount /= 1024;
                unit += 1;
            }
            return `${amount.toFixed(unit < 2 ? 0 : 1)} ${units[unit]}`;
        };

        const formatUptime = (value) => {
            if (value === null || value === undefined) return "Unavailable";
            const seconds = Math.floor(value);
            const days = Math.floor(seconds / 86400);
            const hours = Math.floor((seconds % 86400) / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${days}d ${hours}h ${minutes}m`;
        };

        const setProgress = (id, value) => {
            document.getElementById(id).style.width = `${Math.max(0, Math.min(value || 0, 100))}%`;
        };

        const updateMetrics = (metrics) => {
            const cpu = metrics.cpu_percent;
            document.getElementById("cpu-percent").textContent = cpu == null ? "Sampling" : `${cpu}%`;
            document.getElementById("cpu-detail").textContent = metrics.cpu_temperature_celsius == null ? "Temperature unavailable" : `${metrics.cpu_temperature_celsius}°C`;
            setProgress("cpu-progress", cpu);

            document.getElementById("memory-percent").textContent = metrics.memory_percent == null ? "Unavailable" : `${metrics.memory_percent}%`;
            document.getElementById("memory-detail").textContent = `${formatBytes(metrics.memory_used_bytes)} used · ${formatBytes(metrics.memory_available_bytes)} available`;
            setProgress("memory-progress", metrics.memory_percent);

            document.getElementById("disk-percent").textContent = metrics.disk_percent == null ? "Unavailable" : `${metrics.disk_percent}%`;
            document.getElementById("disk-detail").textContent = `${formatBytes(metrics.disk_free_bytes)} free of ${formatBytes(metrics.disk_total_bytes)}`;
            setProgress("disk-progress", metrics.disk_percent);

            document.getElementById("process-memory").textContent = formatBytes(metrics.process_memory_bytes);
            document.getElementById("system-uptime").textContent = formatUptime(metrics.system_uptime_seconds);
            document.getElementById("load-average").textContent = metrics.load_average ? metrics.load_average.join(" / ") : "Unavailable";
        };


        const status = document.getElementById("metrics-status");
        const toggle = document.getElementById("metrics-toggle");
        const updated = document.getElementById("metrics-updated");
        let paused = false;
        let expired = false;
        let timer;
        let controller;
        let failures = 0;
        const refreshMetrics = async () => {
            clearTimeout(timer);
            if (paused || expired || document.hidden || controller) return;
            controller = new AbortController();
            const timeout = setTimeout(() => controller?.abort(), 8000);
            try {
                status.textContent = "Updating";
                const response = await fetch("/admin/performance/data", {
                    cache: "no-store", signal: controller.signal, redirect: "error"
                });
                if (response.status === 401 || response.status === 403) {
                    expired = true;
                    document.getElementById("metrics-sign-in").hidden = false;
                    toggle.disabled = true;
                    throw new Error("Session expired");
                }
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                updateMetrics(await response.json());
                updated.textContent = `Last updated ${new Date().toLocaleTimeString()}`;
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
                    timer = setTimeout(refreshMetrics, failures ? Math.min(30000, 5000 * 2 ** Math.min(failures, 3)) : 5000);
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
            if (paused) suspend(); else refreshMetrics();
        });
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) suspend(); else refreshMetrics();
        });
        window.addEventListener("pagehide", suspend);
        refreshMetrics();
})();
