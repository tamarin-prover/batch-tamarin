"""Tests for process completion racing with memory monitoring."""

import asyncio
import signal
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import psutil
import pytest

from batch_tamarin.model.executable_task import MemoryStats
from batch_tamarin.modules.process_manager import ProcessManager


@pytest.mark.parametrize("return_code", [0, 7])
@pytest.mark.parametrize("monitor_error", [psutil.NoSuchProcess, psutil.AccessDenied])
async def test_monitor_finishing_before_output_preserves_process_result(
    return_code, monitor_error
):
    manager = ProcessManager()
    output_ready = asyncio.Event()

    async def communicate():
        await output_ready.wait()
        return b"process output", b"process stderr"

    process = Mock(pid=12345, returncode=return_code)
    process.communicate = AsyncMock(side_effect=communicate)
    real_wait = asyncio.wait

    async def wait_then_release_output(*args, **kwargs):
        result = await real_wait(*args, **kwargs)
        # Force the watcher to finish while communicate() is still pending.
        output_ready.set()
        return result

    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch("psutil.Process", side_effect=monitor_error(process.pid)),
        patch("asyncio.wait", side_effect=wait_then_release_output),
    ):
        result = await manager.run_command(Path("command"), [], timeout=1.0)

    assert result == (return_code, "process output", "process stderr", None)
    process.terminate.assert_not_called()
    process.kill.assert_not_called()
    assert manager.get_active_processes_count() == 0


async def test_early_monitor_completion_keeps_original_timeout():
    manager = ProcessManager()
    never_finishes = asyncio.Event()
    process = Mock(pid=12345, returncode=None)
    process.communicate = AsyncMock(side_effect=never_finishes.wait)
    process.wait = AsyncMock(return_value=0)
    stats = MemoryStats(peak_memory_mb=2.0, avg_memory_mb=1.0)
    real_wait = asyncio.wait
    timeouts = []

    async def record_wait(*args, **kwargs):
        timeouts.append(kwargs["timeout"])
        return await real_wait(*args, **kwargs)

    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch.object(manager, "_monitor_memory", AsyncMock(return_value=stats)),
        patch("asyncio.wait", side_effect=record_wait),
    ):
        result = await manager.run_command(Path("command"), [], timeout=0.05)

    assert result[:3] == (-1, "", "Process timed out")
    assert len(timeouts) == 2
    assert 0 < timeouts[1] < timeouts[0] == 0.05
    process.terminate.assert_called_once()
    assert manager.get_active_processes_count() == 0


@pytest.mark.parametrize("return_code", [0, 7])
async def test_short_subprocess(return_code):
    manager = ProcessManager()
    result = await manager.run_command(
        Path(sys.executable),
        [
            "-c",
            f"import sys; print('output'); print('stderr', file=sys.stderr); sys.exit({return_code})",
        ],
        timeout=5.0,
    )

    assert result[:3] == (return_code, "output\n", "stderr\n")
    assert manager.get_active_processes_count() == 0


async def test_memory_limit_still_terminates_process():
    manager = ProcessManager()
    monitored_process = Mock()
    monitored_process.memory_info.return_value.rss = 2 * 1024 * 1024
    monitored_process.children.return_value = []

    with patch("psutil.Process", return_value=monitored_process):
        result = await manager.run_command(
            Path(sys.executable),
            ["-c", "import time; time.sleep(30)"],
            timeout=5.0,
            memory_limit_mb=1.0,
        )

    assert result[:3] == (-2, "", "Process exceeded memory limit")
    assert result[3] == MemoryStats(peak_memory_mb=2.0, avg_memory_mb=2.0)
    assert manager.get_active_processes_count() == 0


async def test_memory_limit_preserves_stats_when_output_finishes_first():
    manager = ProcessManager()
    terminated = asyncio.Event()
    finish_wait = asyncio.Event()
    process = Mock(pid=12345, returncode=None)
    monitored_process = Mock()
    monitored_process.memory_info.return_value.rss = 2 * 1024 * 1024
    monitored_process.children.return_value = []

    def terminate():
        process.returncode = -signal.SIGTERM
        terminated.set()

    async def communicate():
        await terminated.wait()
        return b"", b""

    async def wait_for_exit():
        await finish_wait.wait()
        return process.returncode

    process.terminate.side_effect = terminate
    process.communicate = AsyncMock(side_effect=communicate)
    process.wait = AsyncMock(side_effect=wait_for_exit)
    real_wait = asyncio.wait

    async def wait_then_finish_watcher(*args, **kwargs):
        result = await real_wait(*args, **kwargs)
        # communicate() has finished, but the watcher is still awaiting wait().
        finish_wait.set()
        return result

    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch("psutil.Process", return_value=monitored_process),
        patch("asyncio.wait", side_effect=wait_then_finish_watcher),
    ):
        result = await manager.run_command(
            Path("command"), [], timeout=5.0, memory_limit_mb=1.0
        )

    assert result == (
        -2,
        "",
        "Process exceeded memory limit",
        MemoryStats(peak_memory_mb=2.0, avg_memory_mb=2.0),
    )
    process.terminate.assert_called_once()
    assert manager.get_active_processes_count() == 0


async def test_cancellation_while_collecting_memory_limit_stats_propagates():
    manager = ProcessManager()
    collecting_stats = asyncio.Event()
    process = Mock(pid=12345, returncode=-signal.SIGTERM)
    process.communicate = AsyncMock(return_value=(b"", b""))
    stats = MemoryStats(peak_memory_mb=2.0, avg_memory_mb=2.0)

    async def monitor(process, memory_limit_mb, process_id):
        manager._memory_exceeded_processes[process_id] = True
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return stats

    real_wait = asyncio.wait

    async def wait_then_signal(*args, **kwargs):
        result = await real_wait(*args, **kwargs)
        collecting_stats.set()
        return result

    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch.object(manager, "_monitor_memory", side_effect=monitor),
        patch("asyncio.wait", side_effect=wait_then_signal),
    ):
        command = asyncio.create_task(manager.run_command(Path("command"), []))
        try:
            await asyncio.wait_for(collecting_stats.wait(), timeout=1.0)
            command.cancel()
            with pytest.raises(asyncio.CancelledError):
                await command
            assert manager.get_active_processes_count() == 0
            assert manager._memory_exceeded_processes == {}
        finally:
            command.cancel()
            await asyncio.gather(command, return_exceptions=True)


@pytest.mark.parametrize(
    ("monitor_finishes_early", "ignore_sigterm"),
    [(False, False), (True, False), (False, True)],
)
async def test_cancellation_reaps_subprocess_and_monitor(
    tmp_path, monitor_finishes_early, ignore_sigterm
):
    if ignore_sigterm and sys.platform == "win32":
        pytest.skip("SIGTERM handling requires POSIX")
    manager = ProcessManager()
    ready_file = tmp_path / "ready"
    captured = {}
    real_monitor = manager._monitor_memory

    async def monitor(process, *args):
        captured["process"] = process
        captured["monitor"] = asyncio.current_task()
        if monitor_finishes_early:
            return None
        return await real_monitor(process, *args)

    async def wait_until_ready():
        while not ready_file.exists() or "process" not in captured:
            await asyncio.sleep(0.01)

    code = (
        "import pathlib, signal, sys, time; "
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN); " if ignore_sigterm else "")
        + "pathlib.Path(sys.argv[1]).touch(); time.sleep(30)"
    )
    with patch.object(manager, "_monitor_memory", side_effect=monitor):
        command = asyncio.create_task(
            manager.run_command(
                Path(sys.executable), ["-c", code, str(ready_file)], timeout=20.0
            )
        )
        try:
            await asyncio.wait_for(wait_until_ready(), timeout=5.0)
            process = captured["process"]
            output_task = manager._active_processes["cmd_0"].task
            command.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(command, timeout=10.0)

            assert process.returncode is not None
            if ignore_sigterm:
                assert process.returncode == -signal.SIGKILL
            assert output_task.done()
            assert captured["monitor"].done()
            assert manager.get_active_processes_count() == 0
            assert manager._memory_exceeded_processes == {}
        finally:
            # Reap the child even when exercising the unfixed implementation.
            command.cancel()
            await asyncio.gather(command, return_exceptions=True)
            if "process" in captured:
                process = captured["process"]
                if process.returncode is None:
                    process.kill()
                await process.wait()
                captured["monitor"].cancel()
                await asyncio.gather(captured["monitor"], return_exceptions=True)


async def test_repeated_cancellation_waits_for_cleanup():
    manager = ProcessManager()
    monitor_started = asyncio.Event()
    termination_started = asyncio.Event()
    allow_exit = asyncio.Event()
    process = Mock(pid=12345, returncode=None)
    process.communicate = AsyncMock(side_effect=asyncio.Event().wait)
    background_tasks = []

    async def monitor(*args):
        background_tasks.append(asyncio.current_task())
        monitor_started.set()
        await asyncio.Event().wait()

    async def wait_for_exit():
        termination_started.set()
        await allow_exit.wait()
        process.returncode = -15
        return process.returncode

    process.wait = AsyncMock(side_effect=wait_for_exit)
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch.object(manager, "_monitor_memory", side_effect=monitor),
    ):
        command = asyncio.create_task(manager.run_command(Path("command"), []))
        try:
            await asyncio.wait_for(monitor_started.wait(), timeout=1.0)
            background_tasks.append(manager._active_processes["cmd_0"].task)
            command.cancel()
            await asyncio.wait_for(termination_started.wait(), timeout=1.0)
            command.cancel()
            await asyncio.sleep(0)
            assert not command.done()
            assert manager.get_active_processes_count() == 1
            allow_exit.set()
            with pytest.raises(asyncio.CancelledError):
                await command
            assert all(task.done() for task in background_tasks)
            assert manager.get_active_processes_count() == 0
        finally:
            allow_exit.set()
            command.cancel()
            await asyncio.gather(command, return_exceptions=True)
            for task in background_tasks:
                task.cancel()
            await asyncio.gather(*background_tasks, return_exceptions=True)


async def test_cancellation_during_memory_stats_collection_propagates():
    manager = ProcessManager()
    collecting_stats = asyncio.Event()
    process = Mock(pid=12345, returncode=0)
    process.communicate = AsyncMock(return_value=(b"output", b""))
    captured = {}

    async def monitor(*args):
        captured["monitor"] = asyncio.current_task()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            collecting_stats.set()
            await asyncio.Event().wait()

    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch.object(manager, "_monitor_memory", side_effect=monitor),
    ):
        command = asyncio.create_task(manager.run_command(Path("command"), []))
        try:
            await asyncio.wait_for(collecting_stats.wait(), timeout=1.0)
            command.cancel()
            with pytest.raises(asyncio.CancelledError):
                await command
            assert captured["monitor"].done()
            assert manager.get_active_processes_count() == 0
        finally:
            command.cancel()
            await asyncio.gather(command, return_exceptions=True)


async def test_timeout_preserves_final_memory_sample():
    manager = ProcessManager()
    process = Mock(pid=12345, returncode=None)
    process.communicate = AsyncMock(side_effect=asyncio.Event().wait)
    process.wait = AsyncMock(return_value=0)
    stats = MemoryStats(peak_memory_mb=2.0, avg_memory_mb=1.0)

    async def monitor(*args):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return stats

    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch.object(manager, "_monitor_memory", side_effect=monitor),
    ):
        result = await manager.run_command(Path("command"), [], timeout=0.01)

    assert result == (-1, "", "Process timed out", stats)
