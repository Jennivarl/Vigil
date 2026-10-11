"""
The arithmetic VIGIL rests on, tested on its own.

No chain and no network. If any of this is wrong, somebody's estate moves
on a bad clock or a misread page, which is the one failure this design
exists to prevent.
"""

import datetime

import pytest

from contracts.liveness import (
    ALIVE,
    SILENT,
    UNREACHABLE,
    days_between,
    epoch_seconds,
    marker_present,
    url_for,
    valid_host,
    valid_marker,
    valid_name,
    valid_path,
)


def test_the_three_outcomes_are_distinct():
    assert len({ALIVE, SILENT, UNREACHABLE}) == 3


@pytest.mark.parametrize("host", ["example.com", "www.githubstatus.com", "a.b.c.co.uk"])
def test_real_hostnames_are_accepted(host):
    assert valid_host(host) is True


@pytest.mark.parametrize(
    "host", ["https://example.com", "example.com/path", "localhost", "host:8080", "", ".a.com", "a..b.com"]
)
def test_anything_that_could_smuggle_a_host_is_refused(host):
    assert valid_host(host) is False


@pytest.mark.parametrize("path", ["/", "/status", "/a/b/c.json", "/~me/alive.txt"])
def test_ordinary_paths_are_accepted(path):
    assert valid_path(path) is True


@pytest.mark.parametrize("path", ["status", "/../etc", "/a?b=1", "/a#b", "//evil.com/x", "/" + "x" * 300])
def test_paths_that_could_leave_themselves_are_refused(path):
    assert valid_path(path) is False


@pytest.mark.parametrize("marker", ["still here", "ALIVE", "a" * 200])
def test_a_marker_is_one_line_of_text(marker):
    assert valid_marker(marker) is True


@pytest.mark.parametrize("marker", ["", "   ", "two\nlines", "a" * 201])
def test_a_marker_that_could_not_be_matched_is_refused(marker):
    assert valid_marker(marker) is False


def test_a_marker_is_required_rather_than_optional():
    """
    Treating "the page loaded" as proof of life would let a parked domain
    or a hosting placeholder keep somebody alive forever.
    """
    assert valid_marker("") is False


def test_the_marker_is_matched_anywhere_in_the_page():
    """
    The opposite choice from a proof token, on purpose: here a false
    negative costs somebody their estate, so matching is forgiving.
    """
    assert marker_present("<html><body>  still here  </body></html>", "still here") is True
    assert marker_present("nothing of the sort", "still here") is False


def test_the_url_is_built_by_the_contract():
    assert url_for(" Example.COM ", "/alive.txt") == "https://example.com/alive.txt"


@pytest.mark.parametrize("name", ["estate", "my-key_1", "a"])
def test_names_are_simple(name):
    assert valid_name(name) is True


@pytest.mark.parametrize("name", ["", "has space", "has/slash", "x" * 41])
def test_odd_names_are_refused(name):
    assert valid_name(name) is False


# ----------------------------------------------------------------------
# dates, checked against the standard library the chain cannot import
# ----------------------------------------------------------------------


def reference(stamp: str) -> int:
    return int(datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())


@pytest.mark.parametrize(
    "stamp",
    [
        "1970-01-01T00:00:00Z",
        "2000-02-29T12:00:00Z",
        "1900-03-01T00:00:00Z",
        "2024-02-29T23:59:59Z",
        "2026-10-11T14:42:50Z",
        "2026-12-31T23:59:59Z",
        "2100-03-01T00:00:00Z",
    ],
)
def test_a_timestamp_reads_as_the_same_instant_the_standard_library_sees(stamp):
    assert epoch_seconds(stamp) == reference(stamp)


def test_the_fractional_seconds_the_network_writes_are_truncated():
    assert epoch_seconds("2026-10-11T14:42:50.790497Z") == epoch_seconds("2026-10-11T14:42:50Z")


@pytest.mark.parametrize(
    "stamp",
    ["", "x", "2026-10-11", "2026-13-02T00:00:00Z", "2026-02-29T00:00:00Z", "2026-10-11T25:00:00Z", None],
)
def test_a_timestamp_that_cannot_be_read_is_none_rather_than_zero(stamp):
    """Zero would be 1970, which would make everyone look silent for decades."""
    assert epoch_seconds(stamp) is None


def test_whole_days_between_two_instants():
    a = epoch_seconds("2026-01-01T00:00:00Z")
    assert days_between(a, epoch_seconds("2026-01-31T00:00:00Z")) == 30
    assert days_between(a, epoch_seconds("2026-01-01T23:59:59Z")) == 0
    assert days_between(a, epoch_seconds("2027-01-01T00:00:00Z")) == 365


def test_days_between_is_none_when_either_end_is_unreadable():
    """Which a caller must treat as unknown, never as a long time."""
    assert days_between(None, 100) is None
    assert days_between(100, None) is None


def test_a_clock_that_runs_backwards_gives_zero_not_a_negative():
    a = epoch_seconds("2026-02-01T00:00:00Z")
    b = epoch_seconds("2026-01-01T00:00:00Z")
    assert days_between(a, b) == 0
