"""
WITNESS, the reference consumer, deployed and run.

An example nobody runs is a comment that rots. These deploy the file as it
ships and check the property it exists to show: the gate asks live, and it
refuses when the answer is unknown rather than waving it through.
"""

import sys
from pathlib import Path

import pytest

from test.stubs import OWNER, PULSE_AT, PULSE_ID, STRANGER, Stubs

BUNDLE = str(Path(__file__).resolve().parent.parent / "contracts" / "witness_bundle.py")
WITHIN = 60
NOW = "2026-05-01T09:00:00Z"


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
def witness(direct_vm, direct_deploy, stubs):
    set_date(direct_vm, NOW)
    stubs.set_pulse(silent_days="3")
    with direct_vm.prank(OWNER):
        contract = direct_deploy(BUNDLE, pulse=PULSE_AT, pulse_id=PULSE_ID, within_days=WITHIN)
    direct_vm.strict_mocks = False
    return contract


def test_the_gate_is_open_while_somebody_is_around(direct_vm, witness):
    with direct_vm.prank(OWNER):
        got = witness.act("signed off on a release")
    assert got["acted"] is True
    assert got["silent_days"] == "3"
    assert len(witness.actions()) == 1


def test_the_gate_shuts_once_they_have_been_quiet_too_long(direct_vm, witness, stubs):
    stubs.set_pulse(silent_days="120")
    with direct_vm.prank(OWNER):
        with direct_vm.expect_revert("past the 60 allowed"):
            witness.act("too late")
    assert witness.actions() == []


def test_a_silence_that_cannot_be_worked_out_keeps_the_gate_shut(direct_vm, witness, stubs):
    """
    Doubt is not presence. A gate that treats an unreadable clock as
    somebody being here is a gate that opens itself when the clock breaks.
    """
    stubs.set_pulse(silent_days="-1")
    with direct_vm.prank(OWNER):
        with direct_vm.expect_revert("cannot be worked out"):
            witness.act("who knows")


def test_the_gate_asks_live_rather_than_caching(direct_vm, witness, stubs):
    with direct_vm.prank(OWNER):
        witness.act("first")
    stubs.set_pulse(silent_days="500")
    with direct_vm.prank(OWNER):
        with direct_vm.expect_revert("past the"):
            witness.act("second")


def test_exactly_the_limit_is_still_open(direct_vm, witness, stubs):
    stubs.set_pulse(silent_days=str(WITHIN))
    with direct_vm.prank(OWNER):
        assert witness.act("just in time")["acted"] is True


def test_standing_reports_the_position_without_acting(direct_vm, witness, stubs):
    got = witness.standing()
    assert got["open"] is True
    assert got["within_days"] == str(WITHIN)
    stubs.set_pulse(silent_days="900")
    assert witness.standing()["open"] is False
    assert witness.actions() == []


def test_the_action_records_how_long_it_had_been(direct_vm, witness):
    with direct_vm.prank(OWNER):
        witness.act("audited later")
    assert witness.actions()[0]["silent_days"] == "3"
