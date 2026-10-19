"""
PULSE run for real in direct mode.

The document the owner keeps alive is answered from here, so a test can put
it into states that are tedious to arrange: gone, changed, and merely down.
The validator side matters most, because the lie that counts is one that
makes a living person look absent.
"""

import sys
from pathlib import Path

import pytest

BUNDLE = str(Path(__file__).resolve().parent.parent / "contracts" / "pulse_bundle.py")

OWNER = b"\xa0" * 20
STRANGER = b"\xb0" * 20

HOST = "example.com"
PATH = "/alive.txt"
MARKER = "still here"
NAME = "estate"
PULSE_ID = "0x" + OWNER.hex() + ":" + NAME

ALIVE, SILENT, UNREACHABLE = "alive", "silent", "unreachable"

DAY0 = "2026-01-01T09:00:00Z"
DAY10 = "2026-01-11T09:00:00Z"
DAY40 = "2026-02-10T09:00:00Z"


def set_date(vm, stamp):
    vm.warp(stamp)
    message = sys.modules.get("genlayer.message")
    if message is not None and isinstance(getattr(message, "raw", None), dict):
        message.raw["datetime"] = stamp
    gl = sys.modules.get("genlayer.gl")
    if gl is not None and getattr(gl, "message_raw", None) is not None:
        gl.message_raw["datetime"] = stamp


def serve(vm, body, status=200):
    vm.clear_mocks()
    vm.mock_web(r"example\.com/alive\.txt", {"status": status, "body": body})


@pytest.fixture
def pulse(direct_vm, direct_deploy):
    contract = direct_deploy(BUNDLE)
    direct_vm.strict_mocks = False
    set_date(direct_vm, DAY0)
    with direct_vm.prank(OWNER):
        contract.register(NAME, HOST, PATH, MARKER)
    return contract


def leader(outcome, note):
    return {"outcome": outcome, "note": note}


def test_registering_counts_as_being_here(direct_vm, pulse):
    """It is a signed act by the owner, so it is a sign of life like any other."""
    got = pulse.get_pulse(PULSE_ID)
    assert got["last_alive"] == DAY0
    assert got["last_by"] == "ping"
    assert got["silent_days"] == "0"
    assert got["url"] == "https://example.com/alive.txt"


def test_a_pulse_cannot_be_changed_once_registered(direct_vm, pulse):
    with direct_vm.prank(OWNER):
        with direct_vm.expect_revert("cannot be changed"):
            pulse.register(NAME, "somewhere-easier.example", PATH, MARKER)


def test_only_the_owner_may_ping(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    with direct_vm.prank(STRANGER):
        with direct_vm.expect_revert("only the owner"):
            pulse.ping(PULSE_ID)


def test_a_ping_moves_the_clock(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    with direct_vm.prank(OWNER):
        got = pulse.ping(PULSE_ID)
    assert got["last_alive"] == DAY10
    assert got["silent_days"] == "0"


def test_silence_is_counted_in_whole_days(direct_vm, pulse):
    set_date(direct_vm, DAY40)
    assert pulse.silent_days(PULSE_ID) == "40"


# ----------------------------------------------------------------------
# observing
# ----------------------------------------------------------------------


def test_a_page_still_carrying_the_marker_is_alive(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "<html>" + MARKER + "</html>")
    got = pulse.observe(PULSE_ID)

    assert got["last_outcome"] == ALIVE
    assert got["last_alive"] == DAY10
    assert got["last_by"] == "observed"
    assert direct_vm.run_validator() is True


def test_a_page_without_the_marker_is_silent(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "<html>under new management</html>")
    got = pulse.observe(PULSE_ID)

    assert got["last_outcome"] == SILENT
    assert got["silent_runs"] == "1"
    assert got["last_alive"] == DAY0
    assert direct_vm.run_validator() is True


def test_a_page_that_is_gone_is_silent(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "Not Found", status=404)
    assert pulse.observe(PULSE_ID)["last_outcome"] == SILENT


@pytest.mark.parametrize("status", [500, 503, 429])
def test_a_host_that_is_down_is_unreachable(direct_vm, pulse, status):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "oh dear", status=status)
    assert pulse.observe(PULSE_ID)["last_outcome"] == UNREACHABLE


def test_an_unreachable_host_advances_nothing_at_all(direct_vm, pulse):
    """
    The safety property the whole system rests on. An outage is not a miss:
    nobody learned anything, so the run of silence stays where it was.
    """
    set_date(direct_vm, DAY10)
    serve(direct_vm, "gone")
    pulse.observe(PULSE_ID)
    assert pulse.get_pulse(PULSE_ID)["silent_runs"] == "1"

    serve(direct_vm, "oh dear", status=503)
    got = pulse.observe(PULSE_ID)
    assert got["silent_runs"] == "1"
    assert got["last_alive"] == DAY0
    assert direct_vm.run_validator() is True


def test_runs_of_silence_accumulate_and_a_ping_clears_them(direct_vm, pulse):
    set_date(direct_vm, "2026-01-11T09:00:00Z")
    serve(direct_vm, "gone")
    pulse.observe(PULSE_ID)
    set_date(direct_vm, "2026-01-11T11:00:00Z")
    pulse.observe(PULSE_ID)
    assert pulse.get_pulse(PULSE_ID)["silent_runs"] == "2"

    with direct_vm.prank(OWNER):
        got = pulse.ping(PULSE_ID)
    assert got["silent_runs"] == "0"


def test_anyone_may_observe_because_nobody_can_influence_it(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, MARKER)
    with direct_vm.prank(STRANGER):
        assert pulse.observe(PULSE_ID)["last_outcome"] == ALIVE


# ----------------------------------------------------------------------
# what a validator will and will not agree to
# ----------------------------------------------------------------------


def test_a_validator_rejects_a_leader_who_reports_a_living_person_silent(direct_vm, pulse):
    """The lie that matters: it starts the clock on somebody who is here."""
    set_date(direct_vm, DAY10)
    serve(direct_vm, MARKER)
    pulse.observe(PULSE_ID)
    assert direct_vm.run_validator(leader_result=leader(SILENT, "the page loaded without the marker")) is False


def test_a_validator_rejects_a_leader_who_reports_an_absent_person_alive(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "gone")
    pulse.observe(PULSE_ID)
    assert direct_vm.run_validator(leader_result=leader(ALIVE, "the marker is still there")) is False


def test_a_validator_rejects_a_leader_who_calls_a_down_host_silence(direct_vm, pulse):
    """
    Reported as silence, an outage would advance a run towards somebody
    losing their estate over a bad afternoon.
    """
    set_date(direct_vm, DAY10)
    serve(direct_vm, "oh dear", status=503)
    pulse.observe(PULSE_ID)
    assert direct_vm.run_validator(leader_result=leader(SILENT, "the page is gone")) is False


def test_a_validator_that_cannot_reach_it_agrees_only_to_unreachable(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "oh dear", status=503)
    pulse.observe(PULSE_ID)
    assert direct_vm.run_validator(leader_result=leader(UNREACHABLE, "the host answered 503")) is True
    assert direct_vm.run_validator(leader_result=leader(ALIVE, "the marker is still there")) is False
    assert direct_vm.run_validator(leader_result=leader(SILENT, "the page is gone")) is False


def test_a_validator_rejects_a_leader_that_errored(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, MARKER)
    pulse.observe(PULSE_ID)
    assert direct_vm.run_validator(leader_error=Exception("boom")) is False


def test_validators_must_agree_on_the_reason_not_only_the_outcome(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "Not Found", status=404)
    pulse.observe(PULSE_ID)
    assert direct_vm.run_validator(leader_result=leader(SILENT, "the page is gone")) is True
    assert direct_vm.run_validator(leader_result=leader(SILENT, "the page loaded without the marker")) is False


# ----------------------------------------------------------------------
# what counts as a confirmed silence
# ----------------------------------------------------------------------


def test_a_pulse_nobody_observed_has_confirmed_nothing(direct_vm, pulse):
    """However old it gets. This is the whole point of tracking runs."""
    set_date(direct_vm, "2027-06-01T09:00:00Z")
    got = pulse.get_pulse(PULSE_ID)
    assert got["silent_days"] == "516"
    assert got["silent_runs"] == "0"
    assert got["silence_age_seconds"] == "-1"
    assert got["silence_confirmed"] is False


def confirm_silence(vm, pulse, start_hour=11):
    """Three confirmations, an hour apart, which is what the contract counts."""
    for i in range(3):
        set_date(vm, f"2026-01-{start_hour // 24 + 11:02d}T{(start_hour + i * 2) % 24:02d}:00:00Z")
        serve(vm, "gone")
        pulse.observe(PULSE_ID)


def test_silence_is_confirmed_only_after_enough_observations(direct_vm, pulse):
    set_date(direct_vm, "2026-01-11T09:00:00Z")
    serve(direct_vm, "gone")
    pulse.observe(PULSE_ID)
    assert pulse.get_pulse(PULSE_ID)["silence_confirmed"] is False

    set_date(direct_vm, "2026-01-11T11:00:00Z")
    pulse.observe(PULSE_ID)
    assert pulse.get_pulse(PULSE_ID)["silence_confirmed"] is False

    set_date(direct_vm, "2026-01-11T13:00:00Z")
    pulse.observe(PULSE_ID)

    got = pulse.get_pulse(PULSE_ID)
    assert got["silent_runs"] == "3"
    assert got["silence_confirmed"] is True
    assert got["last_silent_at"] == "2026-01-11T13:00:00Z"


# ----------------------------------------------------------------------
# confirmations have to be spread out
#
# Three fetches seconds apart are three consensus rounds, but they can all
# catch one transient glitch: a cached error page, a brief deploy, a moment
# of nonsense from a CDN. That must not be enough to start a succession.
# ----------------------------------------------------------------------


def test_three_observations_in_one_instant_count_once(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "gone")
    pulse.observe(PULSE_ID)
    pulse.observe(PULSE_ID)
    pulse.observe(PULSE_ID)

    got = pulse.get_pulse(PULSE_ID)
    assert got["silent_runs"] == "1"
    assert got["silence_confirmed"] is False


def test_an_observation_that_is_too_soon_says_so(direct_vm, pulse):
    set_date(direct_vm, DAY10)
    serve(direct_vm, "gone")
    pulse.observe(PULSE_ID)
    set_date(direct_vm, "2026-01-11T09:10:00Z")
    got = pulse.observe(PULSE_ID)

    assert got["silent_runs"] == "1"
    assert "600 seconds ago" in got["note"]
    assert "3600 apart" in got["note"]


def test_exactly_an_hour_apart_counts(direct_vm, pulse):
    set_date(direct_vm, "2026-01-11T09:00:00Z")
    serve(direct_vm, "gone")
    pulse.observe(PULSE_ID)
    set_date(direct_vm, "2026-01-11T10:00:00Z")

    assert pulse.observe(PULSE_ID)["silent_runs"] == "2"


def test_a_glitch_cannot_be_read_three_times_into_a_handover(direct_vm, pulse):
    """
    The point of the gap. A page that is briefly broken, hammered by a
    successor in a hurry, still only ever counts once.
    """
    set_date(direct_vm, DAY10)
    serve(direct_vm, "Not Found", status=404)
    for _ in range(10):
        pulse.observe(PULSE_ID)

    got = pulse.get_pulse(PULSE_ID)
    assert got["silent_runs"] == "1"
    assert got["silence_confirmed"] is False


def test_an_owner_returning_is_never_delayed_by_the_gap(direct_vm, pulse):
    """Letting somebody prove they are here is always the safe direction."""
    set_date(direct_vm, DAY10)
    serve(direct_vm, "gone")
    pulse.observe(PULSE_ID)
    serve(direct_vm, MARKER)
    got = pulse.observe(PULSE_ID)

    assert got["last_outcome"] == ALIVE
    assert got["silent_runs"] == "0"
    assert got["last_silent_at"] == ""


def test_the_gap_is_published_rather_than_implied(pulse):
    assert pulse.get_pulse(PULSE_ID)["confirmations_at_least_seconds_apart"] == "3600"


def test_an_unreachable_host_leaves_the_confirmation_exactly_where_it_was(direct_vm, pulse):
    """
    Neither advancing nor destroying it. An outage teaches nobody anything,
    so it must not push a handover forward, and it must not let a host that
    goes down undo evidence already agreed.
    """
    confirm_silence(direct_vm, pulse)
    before = pulse.get_pulse(PULSE_ID)

    serve(direct_vm, "oh dear", status=503)
    pulse.observe(PULSE_ID)
    after = pulse.get_pulse(PULSE_ID)

    assert after["silent_runs"] == before["silent_runs"]
    assert after["last_silent_at"] == before["last_silent_at"]
    assert after["last_outcome"] == UNREACHABLE


def test_the_owner_coming_back_destroys_the_confirmation(direct_vm, pulse):
    confirm_silence(direct_vm, pulse)
    assert pulse.get_pulse(PULSE_ID)["silence_confirmed"] is True

    with direct_vm.prank(OWNER):
        pulse.ping(PULSE_ID)
    got = pulse.get_pulse(PULSE_ID)
    assert got["silence_confirmed"] is False
    assert got["last_silent_at"] == ""


def test_a_confirmation_goes_stale_on_its_own(direct_vm, pulse):
    """A week old is fresh. A month old is a claim about last month."""
    confirm_silence(direct_vm, pulse)
    assert pulse.get_pulse(PULSE_ID)["silence_confirmed"] is True

    set_date(direct_vm, "2026-02-20T09:00:00Z")
    assert pulse.get_pulse(PULSE_ID)["silence_confirmed"] is False
