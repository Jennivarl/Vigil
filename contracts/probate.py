# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
"""
PROBATE. The waiting, and the chance to say you are still here.

A will does not execute the moment a silence passes its threshold. Somebody
has to come forward and say so, and then a grace period runs during which
one signed transaction from the owner ends the whole thing. This contract
is that process, and nothing else: it holds no money and pays nobody.

    open(will_id)         start the clock, if the silence has already run
    halt(probate_id)      stop it, because the owner has shown up
    verdict(probate_id)   open, halted or ripe, as a free view

Two separate delays, deliberately. The silence threshold is written by the
owner and may be years. The grace period is fixed here and is short, and it
exists because the threshold could pass while somebody is in hospital, on a
boat, or simply not watching a chain. Opening probate is a public event, and
the grace is the window in which anyone who cares can tell the owner to
sign something.

`verdict` does not reach out to anything. It reports the process only. The
question of whether the owner is still silent is asked again, live, by the
contract that actually moves the money, because that is where getting it
wrong would cost somebody their estate.
"""

from dataclasses import dataclass

import genlayer as gl
from genlayer.types import *

from contracts.liveness import days_between, epoch_seconds

STATE_OPEN = "open"
STATE_HALTED = "halted"
STATE_RIPE = "ripe"

# How long after probate opens before a will can execute. Short next to any
# sensible silence threshold, and long enough for one signed transaction.
GRACE_DAYS = 14


@gl.storage.allow
@dataclass
class Probate:
    opener: Address
    will: Address
    will_id: str
    owner: Address
    successor: Address
    pulse: Address
    pulse_id: str
    silence_days: u256
    # What PULSE said when this was opened, kept so the halt is meaningful.
    last_alive_at_open: str
    opened_at: str
    halted: bool
    halted_at: str
    reason: str


class ProbateContract(gl.contract.Contract):
    # The one custody contract whose wills this court hears. Fixed at
    # deployment, so nobody can have it adjudicate a will of their own
    # invention and then wave the verdict at the real one.
    will: Address
    cases: gl.storage.TreeMap[str, Probate]
    case_ids: gl.storage.DynArray[str]

    def __init__(self, will: str):
        self.will = _address(will)

    @gl.public.write
    def open(self, will_id: str) -> dict:
        """
        Start the clock, if the owner's silence has already run its course.

        Only the named successor may open it. Anyone being able to start
        somebody else's probate would make the grace period a nuisance that
        strangers could inflict at will.
        """
        at = self.will
        key = will_id.strip().lower()
        terms = gl.contract.get_at(at).view().get_will(key)

        if str(terms["state"]) != "held":
            raise gl.vm.UserError("that will is " + str(terms["state"]))

        successor = _address(terms["successor"])
        if successor.as_hex.lower() != gl.message.sender_address.as_hex.lower():
            raise gl.vm.UserError("only the named successor may open probate")

        pulse_at = _address(terms["pulse"])
        pulse_id = str(terms["pulse_id"])
        record = gl.contract.get_at(pulse_at).view().get_pulse(pulse_id)

        silent = int(str(record["silent_days"]))
        wanted = int(str(terms["silence_days"]))
        if silent < 0:
            raise gl.vm.UserError("how long the owner has been silent cannot be worked out")
        if silent < wanted:
            raise gl.vm.UserError(f"the owner has been silent {silent} days of the {wanted} required")

        case_id = at.as_hex.lower() + "|" + key
        if case_id in self.cases and not self.cases[case_id].halted:
            raise gl.vm.UserError("probate is already open on that will")

        first_time = case_id not in self.cases
        self.cases[case_id] = Probate(
            opener=gl.message.sender_address,
            will=at,
            will_id=key,
            owner=_address(terms["owner"]),
            successor=successor,
            pulse=pulse_at,
            pulse_id=pulse_id,
            silence_days=wanted,
            last_alive_at_open=str(record["last_alive"]),
            opened_at=_stamp(),
            halted=False,
            halted_at="",
            reason=f"grace of {GRACE_DAYS} days is running; one signed transaction from the owner ends it",
        )
        if first_time:
            self.case_ids.append(case_id)
        return _as_dict(case_id, self.cases[case_id], _now())

    @gl.public.write
    def halt(self, case_id: str) -> dict:
        """
        Stop it, because the owner has shown up since it opened.

        Callable by anyone, because it can only ever stop a handover. It
        reads PULSE rather than taking anyone's word, and compares against
        the moment probate opened: a sign of life from before then is the
        very silence being complained about.
        """
        key = case_id.strip().lower()
        case = self._get(key)
        if case.halted:
            raise gl.vm.UserError("that probate is already halted")

        record = gl.contract.get_at(case.pulse).view().get_pulse(case.pulse_id)
        seen = epoch_seconds(str(record["last_alive"]))
        opened = epoch_seconds(case.opened_at)
        if seen is None or opened is None:
            raise gl.vm.UserError("a timestamp on this probate or pulse could not be read")
        if seen <= opened:
            raise gl.vm.UserError("the owner has not been seen since probate opened")

        case.halted = True
        case.halted_at = _stamp()
        case.reason = "the owner answered during the grace period"
        self.cases[key] = case
        return _as_dict(key, case, _now())

    # ----------------------------------------------------------------
    # reading
    # ----------------------------------------------------------------

    @gl.public.view
    def verdict(self, case_id: str) -> dict:
        """
        Where the process has got to. Nothing is fetched and nobody is asked.

        Deliberately narrow: this reports the clock and the halt, and says
        nothing about whether the owner is still silent right now. The
        contract that moves money asks that question itself, because that is
        where being wrong is expensive.
        """
        key = case_id.strip().lower()
        if key not in self.cases:
            raise gl.vm.UserError("no such probate: " + key)
        return _as_dict(key, self.cases[key], _now())

    @gl.public.view
    def settings(self) -> dict:
        return {"will": self.will.as_hex, "grace_days": str(GRACE_DAYS)}

    @gl.public.view
    def case_list(self) -> list:
        return [c for c in self.case_ids]

    @gl.public.view
    def terms(self) -> dict:
        return {"grace_days": str(GRACE_DAYS)}

    def _get(self, key: str) -> Probate:
        if key not in self.cases:
            raise gl.vm.UserError("no such probate: " + key)
        return self.cases[key]


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------


def _stamp() -> str:
    return str(gl.message.raw["datetime"])


def _now():
    return epoch_seconds(_stamp())


def _address(value) -> Address:
    if hasattr(value, "as_hex"):
        return value
    return Address(str(value).strip())


def _as_dict(key: str, case: Probate, now) -> dict:
    waited = days_between(epoch_seconds(case.opened_at), now)
    if case.halted:
        state = STATE_HALTED
    elif waited is not None and waited >= GRACE_DAYS:
        state = STATE_RIPE
    else:
        state = STATE_OPEN
    return {
        "case_id": key,
        "state": state,
        "opener": case.opener.as_hex,
        "will": case.will.as_hex,
        "will_id": case.will_id,
        "owner": case.owner.as_hex,
        "successor": case.successor.as_hex,
        "pulse": case.pulse.as_hex,
        "pulse_id": case.pulse_id,
        "silence_days": str(case.silence_days),
        "last_alive_at_open": case.last_alive_at_open,
        "opened_at": case.opened_at,
        "halted": case.halted,
        "halted_at": case.halted_at,
        "grace_days": str(GRACE_DAYS),
        "waited_days": str(waited if waited is not None else -1),
        "reason": case.reason,
    }
