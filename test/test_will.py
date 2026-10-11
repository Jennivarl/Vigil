"""
WILL run for real in direct mode, against stand-ins for PULSE and PROBATE.

Every test here is about money: who can put it in, who can take it out, and
above all what it takes to move it to somebody else. The last group is the
important one, because WILL does not trust PROBATE's verdict on its own.
"""

import sys
from pathlib import Path

import pytest

from test.stubs import (
    CASE_ID,
    DEPOSIT,
    EVM_PAY,
    HEIR,
    OWNER,
    PROBATE_AT,
    PULSE_AT,
    PULSE_ID,
    SILENCE_DAYS,
    STRANGER,
    WILL_ID,
    Stubs,
)

BUNDLE = str(Path(__file__).resolve().parent.parent / "contracts" / "will_bundle.py")

NOW = "2026-01-01T10:00:00Z"
LATER = "2026-05-15T10:00:00Z"


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
def will(direct_vm, direct_deploy, stubs):
    set_date(direct_vm, NOW)
    with direct_vm.prank(OWNER):
        contract = direct_deploy(BUNDLE, pulse=PULSE_AT)
    direct_vm.strict_mocks = False
    with direct_vm.prank(OWNER):
        contract.bind_probate(PROBATE_AT)
    return contract


def write_will(vm, will, who=OWNER, amount=DEPOSIT, successor=None, days=SILENCE_DAYS):
    vm.value = amount
    try:
        with vm.prank(who):
            return will.write(PULSE_ID, successor or ("0x" + HEIR.hex()), days)
    finally:
        vm.value = 0


# ----------------------------------------------------------------------
# writing one
# ----------------------------------------------------------------------


def test_an_owner_can_set_something_aside_against_their_own_silence(direct_vm, will):
    got = write_will(direct_vm, will)

    assert got["state"] == "held"
    assert got["amount"] == str(DEPOSIT)
    assert got["silence_days"] == str(SILENCE_DAYS)
    assert will.reserves()["committed"] == str(DEPOSIT)


def test_a_will_cannot_be_written_against_somebody_elses_pulse(direct_vm, will):
    """That would be betting on a stranger rather than providing for anyone."""
    with direct_vm.expect_revert("belongs to somebody else"):
        write_will(direct_vm, will, who=STRANGER)


def test_a_will_with_no_deposit_is_refused(direct_vm, will):
    with direct_vm.expect_revert("send the deposit"):
        write_will(direct_vm, will, amount=0)


@pytest.mark.parametrize("days", [0, 1, 29, 3651])
def test_a_silence_threshold_outside_the_allowed_range_is_refused(direct_vm, will, days):
    """Nobody should be able to write a will that executes after a long weekend."""
    with direct_vm.expect_revert("silence must be between"):
        write_will(direct_vm, will, days=days)


def test_naming_yourself_is_refused(direct_vm, will):
    with direct_vm.expect_revert("other than yourself"):
        write_will(direct_vm, will, successor="0x" + OWNER.hex())


def test_naming_the_zero_address_is_refused(direct_vm, will):
    with direct_vm.expect_revert("burn the deposit"):
        write_will(direct_vm, will, successor="0x" + "00" * 20)


def test_one_pulse_carries_one_will_at_a_time(direct_vm, will):
    write_will(direct_vm, will)
    with direct_vm.expect_revert("already has a will"):
        write_will(direct_vm, will)


def test_an_owner_can_add_to_their_own_will(direct_vm, will):
    write_will(direct_vm, will)
    direct_vm.value = 500
    try:
        with direct_vm.prank(OWNER):
            got = will.top_up(WILL_ID)
    finally:
        direct_vm.value = 0
    assert got["amount"] == str(DEPOSIT + 500)
    assert will.reserves()["committed"] == str(DEPOSIT + 500)


# ----------------------------------------------------------------------
# taking it back
# ----------------------------------------------------------------------


def test_an_owner_can_cancel_and_is_paid_back(direct_vm, will, stubs):
    """
    Not a loophole. The transaction is signed by the owner, so anyone who
    can send it has answered the only question the system is asking.
    """
    write_will(direct_vm, will)
    with direct_vm.prank(OWNER):
        got = will.cancel(WILL_ID)

    assert got["state"] == "cancelled"
    assert stubs.transfers == [{"to": OWNER, "value": DEPOSIT, "kind": EVM_PAY}]
    assert will.reserves()["committed"] == "0"


def test_nobody_else_can_cancel_it(direct_vm, will):
    write_will(direct_vm, will)
    with direct_vm.prank(HEIR):
        with direct_vm.expect_revert("only the owner"):
            will.cancel(WILL_ID)


def test_a_cancelled_will_cannot_be_executed(direct_vm, will, stubs):
    write_will(direct_vm, will)
    with direct_vm.prank(OWNER):
        will.cancel(WILL_ID)
    with direct_vm.expect_revert("already cancelled"):
        will.execute(CASE_ID, WILL_ID)
    assert len(stubs.transfers) == 1


# ----------------------------------------------------------------------
# executing, where WILL refuses to take PROBATE's word for it
# ----------------------------------------------------------------------


def test_a_ripe_probate_pays_the_successor(direct_vm, will, stubs):
    write_will(direct_vm, will)
    set_date(direct_vm, LATER)

    got = will.execute(CASE_ID, WILL_ID)
    assert got["state"] == "paid"
    assert stubs.transfers == [{"to": HEIR, "value": DEPOSIT, "kind": EVM_PAY}]
    assert will.reserves()["committed"] == "0"


@pytest.mark.parametrize("state", ["open", "halted"])
def test_a_probate_that_is_not_ripe_pays_nobody(direct_vm, will, stubs, state):
    write_will(direct_vm, will)
    stubs.set_verdict(state=state)
    set_date(direct_vm, LATER)

    got = will.execute(CASE_ID, WILL_ID)
    assert got["state"] == "held"
    assert stubs.transfers == []


def test_an_owner_seen_since_probate_opened_keeps_their_money(direct_vm, will, stubs):
    """
    The check that matters, and the reason it lives here. PROBATE reports
    the clock; it does not get the last word on whether somebody is gone.
    A halt nobody bothered to record still cannot cost an owner an estate.
    """
    write_will(direct_vm, will)
    stubs.set_verdict(state="ripe", opened_at="2026-05-01T09:00:00Z")
    stubs.set_pulse(last_alive="2026-05-02T09:00:00Z")  # they came back
    set_date(direct_vm, LATER)

    got = will.execute(CASE_ID, WILL_ID)
    assert got["state"] == "held"
    assert "seen since probate opened" in got["reason"]
    assert stubs.transfers == []


def test_a_probate_about_a_different_will_is_refused(direct_vm, will, stubs):
    """A real will, and a verdict that is about somebody else's."""
    write_will(direct_vm, will)
    stubs.set_verdict(will_id="0x" + STRANGER.hex() + "|someone-else")
    with direct_vm.expect_revert("different will"):
        will.execute(CASE_ID, WILL_ID)


def test_a_probate_naming_a_different_owner_is_refused(direct_vm, will, stubs):
    write_will(direct_vm, will)
    stubs.set_verdict(owner="0x" + STRANGER.hex())
    with direct_vm.expect_revert("different owner"):
        will.execute(CASE_ID, WILL_ID)


def test_a_probate_watching_a_different_pulse_is_refused(direct_vm, will, stubs):
    write_will(direct_vm, will)
    stubs.set_verdict(pulse_id="0xdead:other")
    with direct_vm.expect_revert("different pulse"):
        will.execute(CASE_ID, WILL_ID)


def test_an_unreadable_timestamp_pays_nobody(direct_vm, will, stubs):
    write_will(direct_vm, will)
    stubs.set_pulse(last_alive="not a timestamp")
    set_date(direct_vm, LATER)

    got = will.execute(CASE_ID, WILL_ID)
    assert got["state"] == "held"
    assert stubs.transfers == []


def test_a_will_pays_out_exactly_once(direct_vm, will, stubs):
    write_will(direct_vm, will)
    set_date(direct_vm, LATER)
    will.execute(CASE_ID, WILL_ID)

    with direct_vm.expect_revert("already paid"):
        will.execute(CASE_ID, WILL_ID)
    with direct_vm.prank(OWNER):
        with direct_vm.expect_revert("already paid"):
            will.cancel(WILL_ID)
    assert len(stubs.transfers) == 1


def test_anyone_may_execute_because_nothing_they_supply_changes_it(direct_vm, will, stubs):
    write_will(direct_vm, will)
    set_date(direct_vm, LATER)
    with direct_vm.prank(STRANGER):
        assert will.execute(CASE_ID, WILL_ID)["state"] == "paid"
    assert stubs.transfers == [{"to": HEIR, "value": DEPOSIT, "kind": EVM_PAY}]


def test_the_limits_are_published_rather_than_implied(will):
    got = will.terms()
    assert got["min_silence_days"] == "30"
    assert got["max_silence_days"] == "3650"


# ----------------------------------------------------------------------
# the contracts this one believes
#
# An earlier version took the court's address as an argument to `execute`,
# and a stranger could pass a contract of their own that returned a ripe
# verdict, draining a living owner's will on demand. These hold the fix in
# place.
# ----------------------------------------------------------------------


def test_the_court_and_the_pulse_are_fixed_not_chosen_by_a_caller(direct_vm, will):
    got = will.settings()
    assert got["pulse"].lower() == PULSE_AT
    assert got["probate"].lower() == PROBATE_AT


def test_the_court_can_only_be_named_once(direct_vm, will):
    with direct_vm.prank(OWNER):
        with direct_vm.expect_revert("already named"):
            will.bind_probate("0x" + "99" * 20)


def test_nobody_but_the_deployer_may_name_the_court(direct_vm, direct_deploy, stubs):
    set_date(direct_vm, NOW)
    with direct_vm.prank(OWNER):
        fresh = direct_deploy(BUNDLE, pulse=PULSE_AT)
    direct_vm.strict_mocks = False
    with direct_vm.prank(STRANGER):
        with direct_vm.expect_revert("only whoever deployed this"):
            fresh.bind_probate(PROBATE_AT)


def test_nothing_executes_before_a_court_is_named(direct_vm, direct_deploy, stubs):
    set_date(direct_vm, NOW)
    with direct_vm.prank(OWNER):
        fresh = direct_deploy(BUNDLE, pulse=PULSE_AT)
    direct_vm.strict_mocks = False
    direct_vm.value = DEPOSIT
    try:
        with direct_vm.prank(OWNER):
            fresh.write(PULSE_ID, "0x" + HEIR.hex(), SILENCE_DAYS)
    finally:
        direct_vm.value = 0
    with direct_vm.expect_revert("no court has been named"):
        fresh.execute(CASE_ID, WILL_ID)
    assert stubs.transfers == []
