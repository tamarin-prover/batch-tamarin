"""
Tests for the cache command module.

This module tests the CLI-facing CacheCommand helpers, including the
prune operation that removes the cache directory without instantiating
diskcache.
"""

# pyright: basic

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from _pytest.monkeypatch import MonkeyPatch

from batch_tamarin.commands.cache import CacheCommand


class TestCacheCommand:
    """Test cases for the cache command helpers."""

    def test_prune_removes_cache_directory(
        self, tmp_dir: Path, monkeypatch: MonkeyPatch
    ):
        """Test that prune deletes the cache directory."""
        cache_dir = tmp_dir / ".batch-tamarin" / "cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "entry.bin").write_bytes(b"cached data")

        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_dir)

        CacheCommand.prune()

        assert not cache_dir.exists()

    def test_prune_is_idempotent_for_missing_directory(
        self, tmp_dir: Path, monkeypatch: MonkeyPatch
    ):
        """Test that prune succeeds when the cache directory is already gone."""
        cache_dir = tmp_dir / ".batch-tamarin" / "cache"

        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_dir)

        CacheCommand.prune()

        assert not cache_dir.exists()

    def test_prune_reports_failure(self, tmp_dir: Path, monkeypatch: MonkeyPatch):
        """Test that prune exits with an error when deletion fails."""
        cache_dir = tmp_dir / ".batch-tamarin" / "cache"
        cache_dir.mkdir(parents=True)

        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_dir)

        with patch(
            "batch_tamarin.commands.cache.shutil.rmtree",
            side_effect=PermissionError("permission denied"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                CacheCommand.prune()

        assert exc_info.value.exit_code == 1
