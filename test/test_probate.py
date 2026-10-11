"""
PROBATE run for real in direct mode, against stand-ins for WILL and PULSE.

This contract holds no money and pays nobody, so the tests are about the
process: who may start it, what stops it, and whether the clock is honest.
"""

import sys
from pathlib import Path

import pytest

from test.stubs import (
    CASE_ID,
    GRACE_DAYS,
    HEIR,
    OWNER,
    PULSE_ID,
    SILENCE_DAYS,
    STRANGER,
    WILL_AT,
    WILL_ID,
    Stubs,
)

BUNDLE = str(Path(__file__).resolve().parent.parent / "contracts" / "probate_bundle.py")

OPENED = "2026-05-01T09:00:00Z"
MID_GRACE = "2026-05-08T09:00:00Z"
PAST_GRACE = "2026-05-15T09:00:00Z"


def set_date(vm, stamp):
    vm.warp(stamp)
    message = sys.modules.get("genlayer.message")
    if message is not None and isinstance(getattr(message, "raw", None), dict):
        message.raw["datetime"] = stamp
    gl = sys.modules.get("genlayer.gl")
    if gl is not None and getattr(gl, "message_raw", None) is not None:
        gl.message_raw["datetime"] = stamp


@pytest.fixture
def stubs(direct_vm):
    return Stubs().install(direct_vm)


@pytest.fixture
def probate(direct_vm, direct_deploy, stubs):
    contract = direct_deploy(BUNDLE)
    direct_vm.strict_mocks = False
    set_date(direct_vm, OPENED)
    return contract


def open_case(vm, probate, who=HEIR):
    with vm.prank(who):
        return probate.open(WILL_AT, WILL_ID)


# ----------------------------------------------------------------------
# opening
# ----------------------------------------------------------------------


def test_the_successor_can_open_probate_once_the_silence_has_run(direct_vm, probate):
    got = open_case(direct_vm, probate)

    assert got["state"] == "open"
    assert got["will_id"] == WILL_ID
    assert got["silence_days"] == str(SILENCE_DAYS)
    assert got["grace_days"] == str(GRACE_DAYS)


def test_nobody_else_may_open_it(direct_vm, probate):
    """
    Otherwise strangers could inflict a grace period on anyone at will, and
    the owner would spend their life answering it.
    """
    with direct_vm.expect_revert("only the named successor"):
        open_case(direct_vm, probate, who=STRANGER)


def test_probate_cannot_open_before_the_silence_has_run(direct_vm, probate, stubs):
    stubs.set_pulse(silent_days="40")
    with direct_vm.expect_revert("silent 40 days of the 90 required"):
        open_case(direct_vm, probate)


def test_a_silence_that_cannot_be_worked_out_blocks_probate(direct_vm, probate, stubs):
    """Not knowing how long somebody has been gone is not grounds for anything."""
    stubs.set_pulse(silent_days="-1")
    with direct_vm.expect_revert("cannot be worked out"):
        open_case(direct_vm, probate)


@pytest.mark.parametrize("state", ["paid", "cancelled"])
def test_a_will_that_is_already_over_cannot_be_probated(direct_vm, probate, stubs, state):
    stubs.set_will(state=state)
    with direct_vm.expect_revert("that will is " + state):
        open_case(direct_vm, probate)


def test_probate_cannot_be_opened_twice(direct_vm, probate):
    open_case(direct_vm, probate)
    with direct_vm.expect_revert("already open"):
        open_case(direct_vm, probate)


# ----------------------------------------------------------------------
# the clock
# ----------------------------------------------------------------------


def test_the_grace_period_has_to_run_before_anything_is_ripe(direct_vm, probate):
    open_case(direct_vm, probate)
    set_date(direct_vm, MID_GRACE)

    got = probate.verdict(CASE_ID)
    assert got["state"] == "open"
    assert got["waited_days"] == "7"


def test_once_the_grace_has_run_it_is_ripe(direct_vm, probate):
    open_case(direct_vm, probate)
    set_date(direct_vm, PAST_GRACE)

    got = probate.verdict(CASE_ID)
    assert got["state"] == "ripe"
    assert got["waited_days"] == "14"


def test_exactly_the_grace_day_is_ripe(direct_vm, probate):
    open_case(direct_vm, probate)
    set_date(direct_vm, "2026-05-15T09:00:00Z")
    assert probate.verdict(CASE_ID)["state"] == "ripe"


def test_one_day_short_is_not(direct_vm, probate):
    open_case(direct_vm, probate)
    set_date(direct_vm, "2026-05-14T23:59:59Z")
    assert probate.verdict(CASE_ID)["state"] == "open"


# ----------------------------------------------------------------------
# showing up
# ----------------------------------------------------------------------


def test_an_owner_who_comes_back_halts_it(direct_vm, probate, stubs):
    open_case(direct_vm, probate)
    stubs.set_pulse(last_alive="2026-05-02T09:00:00Z")
    set_date(direct_vm, MID_GRACE)

    got = probate.halt(CASE_ID)
    assert got["state"] == "halted"
    assert "answered during the grace period" in got["reason"]


def test_a_halted_probate_never_becomes_ripe(direct_vm, probate, stubs):
    open_case(direct_vm, probate)
    stubs.set_pulse(last_alive="2026-05-02T09:00:00Z")
    probate.halt(CASE_ID)
    set_date(direct_vm, "2027-01-01T09:00:00Z")

    assert probate.verdict(CASE_ID)["state"] == "halted"


def test_a_sign_of_life_from_before_probate_opened_does_not_halt_it(direct_vm, probate, stubs):
    """That is the very silence being complained about."""
    open_case(direct_vm, probate)
    stubs.set_pulse(last_alive="2026-01-01T09:00:00Z")
    set_date(direct_vm, MID_GRACE)

    with direct_vm.expect_revert("not been seen since probate opened"):
        probate.halt(CASE_ID)


def test_anyone_may_halt_it_because_it_can_only_ever_stop_a_handover(direct_vm, probate, stubs):
    open_case(direct_vm, probate)
    stubs.set_pulse(last_alive="2026-05-02T09:00:00Z")
    with direct_vm.prank(STRANGER):
        assert probate.halt(CASE_ID)["state"] == "halted"


def test_halting_reads_the_pulse_rather_than_taking_anyones_word(direct_vm, probate, stubs):
    open_case(direct_vm, probate)
    stubs.calls.clear()
    stubs.set_pulse(last_alive="2026-05-02T09:00:00Z")
    probate.halt(CASE_ID)
    assert "get_pulse" in stubs.calls


def test_it_cannot_be_halted_twice(direct_vm, probate, stubs):
    open_case(direct_vm, probate)
    stubs.set_pulse(last_alive="2026-05-02T09:00:00Z")
    probate.halt(CASE_ID)
    with direct_vm.expect_revert("already halted"):
        probate.halt(CASE_ID)


def test_a_halted_case_can_be_reopened_if_the_owner_goes_quiet_again(direct_vm, probate, stubs):
    """A reprieve is not immunity. The next silence starts the process afresh."""
    open_case(direct_vm, probate)
    stubs.set_pulse(last_alive="2026-05-02T09:00:00Z")
    probate.halt(CASE_ID)

    set_date(direct_vm, "2026-09-01T09:00:00Z")
    stubs.set_pulse(silent_days="120")
    got = open_case(direct_vm, probate)
    assert got["state"] == "open"
    assert got["halted"] is False


def test_the_grace_period_is_published_rather_than_implied(probate):
    assert probate.terms()["grace_days"] == str(GRACE_DAYS)
