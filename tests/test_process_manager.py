"""Tests for process completion racing with memory monitoring."""

import asyncio
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
