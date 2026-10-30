import importlib.util
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('git_lock_recovery', Path('deploy/linux/recover_git_locks.py'))
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def old_lock(directory, name='HEAD.lock'):
    lock = directory / name
    lock.write_text('interrupted checkout')
    os.utime(lock, (100, 100))
    return lock


def test_old_abandoned_checkout_locks_are_removed(tmp_path):
    head = old_lock(tmp_path)
    index = old_lock(tmp_path, 'index.lock')
    unrelated = old_lock(tmp_path, 'config.lock')
    recovery.recover_checkout_locks(tmp_path, now=300, process_check=lambda: [])
    assert not head.exists() and not index.exists()
    assert unrelated.exists()


def test_active_git_process_prevents_removal(tmp_path):
    lock = old_lock(tmp_path)
    with pytest.raises(RuntimeError, match='Git processes are still running'):
        recovery.recover_checkout_locks(tmp_path, now=300, process_check=lambda: ['123'])
    assert lock.exists()


def test_recent_lock_is_preserved(tmp_path):
    lock = old_lock(tmp_path)
    with pytest.raises(RuntimeError, match='recent'):
        recovery.recover_checkout_locks(tmp_path, now=150, process_check=lambda: [])
    assert lock.exists()


def test_changed_lock_is_preserved(tmp_path):
    lock = old_lock(tmp_path)

    def replace_lock():
        lock.write_text('new Git operation')
        return []

    with pytest.raises(RuntimeError, match='changed'):
        recovery.recover_checkout_locks(tmp_path, now=300, process_check=replace_lock)
    assert lock.exists()


def test_process_inspection_error_preserves_lock(tmp_path):
    lock = old_lock(tmp_path)

    def denied():
        raise PermissionError('process inspection denied')

    with pytest.raises(PermissionError):
        recovery.recover_checkout_locks(tmp_path, now=300, process_check=denied)
    assert lock.exists()


def test_deployment_lock_precedes_recovery_and_git_operations():
    script = Path('deploy/linux/deploy-uat.sh').read_text()
    assert script.index('flock -w 60 9') < script.index('python3 "$SCRIPT_DIR/recover_git_locks.py"') < script.index('git rev-parse HEAD')
    assert script.index('git stash push') < script.index('git checkout --detach "$NEW_COMMIT"')
    assert 'git reset --hard' not in script


def test_deploy_recovers_interrupted_checkout_without_losing_tracked_edits(tmp_path):
    import subprocess

    def git(*args, cwd):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()

    origin = tmp_path / 'origin'
    origin.mkdir()
    git('init', cwd=origin)
    git('config', 'user.email', 'test@example.invalid', cwd=origin)
    git('config', 'user.name', 'Test', cwd=origin)
    (origin / 'README.md').write_text('original')
    (origin / '.gitignore').write_text('.env\n.venv/\n.data/\n')
    git('add', '.', cwd=origin)
    git('commit', '-m', 'initial', cwd=origin)
    previous = git('rev-parse', 'HEAD', cwd=origin)
    (origin / 'README.md').write_text('validated release')
    git('commit', '-am', 'release', cwd=origin)
    target = git('rev-parse', 'HEAD', cwd=origin)
    app = tmp_path / 'app'
    git('clone', str(origin), str(app), cwd=tmp_path)
    git('config', 'user.email', 'test@example.invalid', cwd=app)
    git('config', 'user.name', 'Test', cwd=app)
    git('checkout', '--detach', previous, cwd=app)
    (app / 'README.md').write_text('edits from interrupted checkout')
    (app / '.env').write_text('ENVIRONMENT=uat')
    old_lock(app / '.git')

    tools = tmp_path / 'tools'
    tools.mkdir()
    for name, source in {
        'sudo': '#!/bin/sh\nexit 0\n',
        'curl': '#!/bin/sh\nprintf \'%s\\n\' \'{"environment":"uat"}\'\n',
    }.items():
        command = tools / name
        command.write_text(source)
        command.chmod(0o755)
    python = app / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nif [ "$1" = "-c" ]; then echo 16.1.27; fi\nexit 0\n')
    python.chmod(0o755)

    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    script = scripts / 'deploy-uat.sh'
    script.write_text(Path('deploy/linux/deploy-uat.sh').read_text().replace(
        'APP_DIR="/opt/ratsboombot-uat"', f'APP_DIR="{app}"'))
    # Inject deterministic process inspection only in this isolated fixture.
    helper = Path('deploy/linux/recover_git_locks.py').read_text().replace(
        'process_check=active_git_processes', 'process_check=lambda: []')
    (scripts / 'recover_git_locks.py').write_text(helper)
    env = os.environ | {'PATH': str(tools) + os.pathsep + os.environ['PATH']}
    result = subprocess.run(['bash', str(script), target], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert git('rev-parse', 'HEAD', cwd=app) == target
    assert (app / 'README.md').read_text() == 'validated release'
    assert 'edits from interrupted checkout' in git('stash', 'show', '-p', cwd=app)
    assert (app / '.env').read_text() == 'ENVIRONMENT=uat'
    assert not (app / '.git/HEAD.lock').exists()
