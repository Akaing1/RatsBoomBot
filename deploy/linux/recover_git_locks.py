#!/usr/bin/env python3
"""Recover old checkout locks only when no Git process is running on the host."""
from pathlib import Path
import sys
import time

MINIMUM_LOCK_AGE = 120


def active_git_processes():
    processes = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / 'comm').read_text().strip()
        except FileNotFoundError:
            continue  # Process exited while we inspected it.
        # Fail closed if process inspection is denied.
        if name == 'git' or name.startswith('git-'):
            processes.append(entry.name)
    return processes


def recover_checkout_locks(git_directory, *, now=None, process_check=active_git_processes):
    now = time.time() if now is None else now
    candidates = []
    for name in ('HEAD.lock', 'index.lock'):
        lock = git_directory / name
        try:
            stat = lock.lstat()
        except FileNotFoundError:
            continue
        if lock.is_symlink() or not lock.is_file() or now - stat.st_mtime < MINIMUM_LOCK_AGE:
            raise RuntimeError(f'{lock} is recent or not a regular file; refusing automatic removal. Retry later after checking for active Git operations.')
        candidates.append((lock, stat))

    if not candidates:
        return
    pids = process_check()
    if pids:
        raise RuntimeError(f'Git processes are still running (PIDs: {", ".join(pids)}); refusing to remove checkout locks.')

    for lock, original in candidates:
        # Recheck immediately before unlinking; never remove a replaced lock.
        current = lock.lstat()
        if (current.st_ino, current.st_mtime_ns, current.st_size) != (
            original.st_ino, original.st_mtime_ns, original.st_size
        ):
            raise RuntimeError(f'{lock} changed during inspection; refusing removal.')
        lock.unlink()
        print(f'[UAT Deploy] Removed stale checkout lock: {lock.name}', flush=True)


if __name__ == '__main__':
    try:
        directory = Path(sys.argv[1])
        if not directory.is_dir() or not Path('/proc').is_dir():
            raise RuntimeError('Git directory and Linux process information are required.')
        recover_checkout_locks(directory)
    except (OSError, RuntimeError) as error:
        print(f'[UAT Deploy] ERROR: {error}', file=sys.stderr)
        sys.exit(1)
