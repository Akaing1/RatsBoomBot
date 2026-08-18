import os
import shutil
import threading
from pathlib import Path
from time import time

from config.settings import settings


class SystemMetricsCollector:

    def __init__(self) -> None:
        self.previous_cpu_sample: tuple[int, int] | None = None
        self.lock = threading.Lock()

    def collect(self) -> dict[str, object]:
        disk_path = self.get_disk_path()
        disk = shutil.disk_usage(disk_path)
        memory = self.read_memory()

        return {
            "timestamp": int(time()),
            "cpu_percent": self.read_cpu_percent(),
            "cpu_temperature_celsius": self.read_cpu_temperature(),
            "load_average": self.read_load_average(),
            "memory_total_bytes": memory.get("total"),
            "memory_available_bytes": memory.get("available"),
            "memory_used_bytes": memory.get("used"),
            "memory_percent": memory.get("percent"),
            "disk_path": str(disk_path),
            "disk_total_bytes": disk.total,
            "disk_used_bytes": disk.used,
            "disk_free_bytes": disk.free,
            "disk_percent": round((disk.used / disk.total) * 100, 1) if disk.total else 0,
            "process_memory_bytes": self.read_process_memory(),
            "system_uptime_seconds": self.read_system_uptime()
        }

    @staticmethod
    def get_disk_path() -> Path:
        database_path = Path(settings.DATABASE_PATH).resolve()

        if database_path.parent.exists():
            return database_path.parent

        return Path.cwd()

    def read_cpu_percent(self) -> float | None:
        try:
            first_line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
            values = [int(value) for value in first_line.split()[1:]]
        except (OSError, ValueError, IndexError):
            return None

        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values)

        with self.lock:
            previous_sample = self.previous_cpu_sample
            self.previous_cpu_sample = (idle, total)

        if previous_sample is None:
            return None

        previous_idle, previous_total = previous_sample
        total_delta = total - previous_total
        idle_delta = idle - previous_idle

        if total_delta <= 0:
            return None

        return round((1 - idle_delta / total_delta) * 100, 1)

    @staticmethod
    def read_memory() -> dict[str, int | float]:
        try:
            lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
            values = {line.split(":", 1)[0]: int(line.split()[1]) * 1024 for line in lines if ":" in line}
            total = values["MemTotal"]
            available = values["MemAvailable"]
        except (OSError, ValueError, KeyError, IndexError):
            return {}

        used = max(total - available, 0)

        return {
            "total": total,
            "available": available,
            "used": used,
            "percent": round((used / total) * 100, 1) if total else 0
        }

    @staticmethod
    def read_process_memory() -> int | None:
        try:
            lines = Path("/proc/self/status").read_text(encoding="utf-8").splitlines()
            resident_line = next(line for line in lines if line.startswith("VmRSS:"))
            return int(resident_line.split()[1]) * 1024
        except (OSError, ValueError, StopIteration, IndexError):
            return None

    @staticmethod
    def read_system_uptime() -> float | None:
        try:
            return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def read_cpu_temperature() -> float | None:
        temperature_paths = (
            Path("/sys/class/thermal/thermal_zone0/temp"),
            Path("/sys/class/hwmon/hwmon0/temp1_input")
        )

        for temperature_path in temperature_paths:
            try:
                raw_temperature = float(temperature_path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue

            temperature = raw_temperature / 1000 if raw_temperature > 200 else raw_temperature
            return round(temperature, 1)

        return None

    @staticmethod
    def read_load_average() -> list[float] | None:
        try:
            return [round(value, 2) for value in os.getloadavg()]
        except (AttributeError, OSError):
            return None


system_metrics = SystemMetricsCollector()
