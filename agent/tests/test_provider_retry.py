"""Tests for provider-call resilience (rate-limit / quota / transient errors)."""

import contentops_agent as ca
import pytest


class _Transient(Exception):
    pass


class _Quota(Exception):
    def __str__(self):
        return "Error code: 429 - insufficient_quota: you exceeded your plan"


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    # Treat our stand-in as retryable and never actually sleep.
    monkeypatch.setattr(ca, "_PROVIDER_RETRY_EXC", (_Transient, _Quota))
    monkeypatch.setattr(ca.time, "sleep", lambda *_: None)


def test_retries_transient_then_succeeds():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _Transient("rate limited")
        return "ok"

    assert ca._call_model(fn) == "ok"
    assert len(calls) == 3  # retried twice


def test_gives_up_after_max_attempts():
    calls = []

    def fn():
        calls.append(1)
        raise _Transient("still rate limited")

    with pytest.raises(_Transient):
        ca._call_model(fn)
    assert len(calls) == ca._PROVIDER_MAX_ATTEMPTS


def test_quota_exhaustion_is_not_retried():
    calls = []

    def fn():
        calls.append(1)
        raise _Quota()

    with pytest.raises(_Quota):
        ca._call_model(fn)
    assert len(calls) == 1  # insufficient_quota fails fast — retrying won't help
