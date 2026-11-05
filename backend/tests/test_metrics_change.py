"""Observed read-change computation."""

from __future__ import annotations

from types import SimpleNamespace

from app.repositories.articles import observed_read_change


def _m(read):
    return SimpleNamespace(read_count=read)


def test_fewer_than_two_observations():
    assert observed_read_change([]) == (None, None)
    assert observed_read_change([_m(100)]) == (None, None)


def test_two_valid_observations():
    delta, rate = observed_read_change([_m(100), _m(150)])
    assert delta == 50
    assert rate == 50.0


def test_previous_zero_no_rate():
    delta, rate = observed_read_change([_m(0), _m(150)])
    assert delta == 150
    assert rate is None


def test_missing_previous_ignored():
    # Only one non-null reading -> no change.
    assert observed_read_change([_m(None), _m(150)]) == (None, None)
