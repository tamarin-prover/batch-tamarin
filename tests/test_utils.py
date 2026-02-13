"""
Tests for utility functions.
"""

import pytest

from batch_tamarin.utils.system_resources import get_human_readable_volume_size


@pytest.mark.parametrize(
    ("volume_size", "start_unit", "expected"),
    [
        (1024, "bytes", "1.00 kB"),
        (1024, "kB", "1.00 MB"),
        (2048, "bytes", "2.00 kB"),
        (1024 * 1024, "bytes", "1.00 MB"),
        (1024 * 1024, "kB", "1.00 GB"),
        (1, "GB", "1.00 GB"),
    ],
)
def test_get_human_readable_volume_size(
    volume_size: int | float, start_unit: str, expected: str
) -> None:
    """Test the function that creates human-readable volume size units"""

    assert get_human_readable_volume_size(volume_size, start_unit) == expected
