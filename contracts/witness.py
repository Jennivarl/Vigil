# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
"""
WITNESS. The whole of what it takes to use this from another contract.

Not part of the system: this is the reference consumer, here so nobody has
to read WILL to work out the pattern. It is a lock that is open only while
somebody is still around, which is the other half of what a liveness record
is good for. A will acts on absence; this acts on presence.

    watch(pulse, pulse_id, within_days)   name whose presence opens the lock
    act(note)                             anyone may, while they are here
    standing()                            how things are right now

The gate is three lines, and the third is the one worth copying:

    record = gl.contract.get_at(self.pulse).view().get_pulse(self.pulse_id)
    days = int(str(record["silent_days"]))
    if days < 0 or days > self.within_days: refuse

A negative answer means PULSE could not work out how long it has been, and
that is refused rather than waved through. Not knowing how long somebody has
been silent is not the same as them being here, and a gate that treats doubt
as presence is a gate that opens itself when the clock breaks.
"""

from dataclasses import dataclass

import genlayer as gl
from genlayer.types import *


@gl.storage.allow
@dataclass
class Act:
    actor: Address
    note: str
    at: str
    silent_days: str


class Witness(gl.contract.Contract):
    operator: Address
    pulse: Address
    pulse_id: str
    within_days: u256
    acts: gl.storage.DynArray[Act]

    def __init__(self, pulse: str, pulse_id: str, within_days: int):
        self.operator = gl.message.sender_address
        self.pulse = _address(pulse)
        self.pulse_id = pulse_id.strip().lower()
        days = int(within_days)
        if days <= 0:
            raise gl.vm.UserError("name a positive number of days")
        self.within_days = days

    @gl.public.write
    def act(self, note: str) -> dict:
        """
        Do the gated thing, while the watched person is still around.

        Asks PULSE live. Nothing is cached, because a cached answer is
        exactly how a lock stays open after the person it was watching for
        has gone.
        """
        record = gl.contract.get_at(self.pulse).view().get_pulse(self.pulse_id)
        days = int(str(record["silent_days"]))
        if days < 0:
            raise gl.vm.UserError("how long they have been silent cannot be worked out, so this stays shut")
        if days > int(self.within_days):
            raise gl.vm.UserError(f"silent for {days} days, which is past the {int(self.within_days)} allowed")

        entry = Act(
            actor=gl.message.sender_address,
            note=note.strip()[:200],
            at=_stamp(),
            silent_days=str(days),
        )
        self.acts.append(entry)
        return {"acted": True, "by": entry.actor.as_hex, "silent_days": entry.silent_days, "at": entry.at}

    @gl.public.view
    def standing(self) -> dict:
        record = gl.contract.get_at(self.pulse).view().get_pulse(self.pulse_id)
        days = int(str(record["silent_days"]))
        return {
            "pulse": self.pulse.as_hex,
            "pulse_id": self.pulse_id,
            "within_days": str(self.within_days),
            "silent_days": str(days),
            "open": 0 <= days <= int(self.within_days),
        }

    @gl.public.view
    def actions(self) -> list:
        return [
            {"actor": a.actor.as_hex, "note": a.note, "at": a.at, "silent_days": a.silent_days}
            for a in self.acts
        ]


def _stamp() -> str:
    return str(gl.message.raw["datetime"])


def _address(value) -> Address:
    if hasattr(value, "as_hex"):
        return value
    return Address(str(value).strip())
