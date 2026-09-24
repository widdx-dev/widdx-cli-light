from unittest.mock import Mock

import pytest

from core.provider_reliability import PartialProviderError, ReliableProvider


def test_partial_stream_failure_is_not_success_or_replayed():
    provider = Mock()
    provider.name = "mock"
    provider.stream.return_value = iter([{"type": "content", "data": "partial"}])
    rp = ReliableProvider.__new__(ReliableProvider)
    rp._pool = Mock()
    rp._pool.get_provider.return_value = provider
    rp._max_retries = 3
    rp._base_delay = 0
    rp.model = "mock"
    rp._checkpoint = Mock()

    with pytest.raises(PartialProviderError):
        rp.chat([], [])

    provider.stream.assert_called_once()
    provider.chat.assert_not_called()
    rp._pool.mark_success.assert_not_called()
