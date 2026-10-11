# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
"""
WILL. What is held, for whom, and after how long a silence.

Custody only. This contract never decides anything: it holds the deposit,
remembers the terms, and pays out on a verdict PROBATE reached. Keeping the
money and the judgement in different contracts means the thing that can be
argued about is not the thing holding the funds.

    write(pulse, pulse_id, successor, silence_days)   payable
    top_up(will_id)                                   payable
    cancel(will_id)        the owner takes it back, any time they are here
    execute(will_id)       pay the successor, on a ripe probate

The owner can cancel at any moment right up to execution, and that is the
point rather than a loophole. Every one of these transactions is signed by
the owner, so an owner who can cancel is an owner who is demonstrably still
here, which is the only question the whole system is asking.
"""

from dataclasses import dataclass

import genlayer as gl
from genlayer.types import *

from contracts.liveness import epoch_seconds

STATE_HELD = "held"
STATE_PAID = "paid"
STATE_CANCELLED = "cancelled"

# Nobody should be able to write a will that executes after a long weekend.
MIN_SILENCE_DAYS = 30
MAX_SILENCE_DAYS = 3650


@gl.storage.allow
@dataclass
class Will:
    owner: Address
    successor: Address
    amount: u256
    pulse: Address
    pulse_id: str
    silence_days: u256
    written_at: str
    state: str
    decided_at: str
    reason: str


class WillContract(gl.contract.Contract):
    wills: gl.storage.TreeMap[str, Will]
    will_ids: gl.storage.DynArray[str]
    committed: u256

    def __init__(self):
        self.committed = 0

    @gl.public.write.payable
    def write(self, pulse: str, pulse_id: str, successor: str, silence_days: int) -> dict:
        """
        Put something aside, against your own silence.

        The pulse has to be yours. Writing a will against somebody else's
        liveness would be betting on a stranger rather than providing for
        anyone.
        """
        amount = gl.message.value
        if amount <= 0:
            raise gl.vm.UserError("send the deposit with this call")

        days = int(silence_days)
        if days < MIN_SILENCE_DAYS or days > MAX_SILENCE_DAYS:
            raise gl.vm.UserError(f"silence must be between {MIN_SILENCE_DAYS} and {MAX_SILENCE_DAYS} days")

        at = _address(pulse)
        key = pulse_id.strip().lower()
        record = gl.contract.get_at(at).view().get_pulse(key)

        owner = gl.message.sender_address
        if str(record["owner"]).lower() != owner.as_hex.lower():
            raise gl.vm.UserError("that pulse belongs to somebody else")

        heir = _address(successor)
        if heir.as_hex.lower() == "0x" + "00" * 20:
            raise gl.vm.UserError("a payout to the zero address would burn the deposit")
        if heir.as_hex.lower() == owner.as_hex.lower():
            # It would still work, and it would mean nothing: the owner
            # would be inheriting from themselves after their own silence.
            raise gl.vm.UserError("name somebody other than yourself")

        will_id = owner.as_hex.lower() + "|" + key
        if will_id in self.wills and self.wills[will_id].state == STATE_HELD:
            raise gl.vm.UserError("that pulse already has a will; cancel it first")

        first_time = will_id not in self.wills
        self.wills[will_id] = Will(
            owner=owner,
            successor=heir,
            amount=amount,
            pulse=at,
            pulse_id=key,
            silence_days=days,
            written_at=_stamp(),
            state=STATE_HELD,
            decided_at="",
            reason="",
        )
        if first_time:
            self.will_ids.append(will_id)
        self.committed = self.committed + amount
        return _as_dict(will_id, self.wills[will_id])

    @gl.public.write.payable
    def top_up(self, will_id: str) -> dict:
        """Add to a will you wrote. Another signed act, so another sign of life."""
        key = will_id.strip().lower()
        will = self._held(key)
        if will.owner.as_hex.lower() != gl.message.sender_address.as_hex.lower():
            raise gl.vm.UserError("only the owner may add to a will")
        amount = gl.message.value
        if amount <= 0:
            raise gl.vm.UserError("send something with this call")
        will.amount = will.amount + amount
        self.wills[key] = will
        self.committed = self.committed + amount
        return _as_dict(key, will)

    @gl.public.write
    def cancel(self, will_id: str) -> dict:
        """
        Take it back. Owner only, and allowed right up to execution.

        Not a loophole. This transaction is signed by the owner, so anyone
        who can send it has answered the only question being asked.
        """
        key = will_id.strip().lower()
        will = self._held(key)
        if will.owner.as_hex.lower() != gl.message.sender_address.as_hex.lower():
            raise gl.vm.UserError("only the owner may cancel a will")

        amount = int(will.amount)
        will.state = STATE_CANCELLED
        will.decided_at = _stamp()
        will.reason = "the owner cancelled it"
        self.wills[key] = will
        self.committed = self.committed - amount
        # State first, then value.
        _pay(will.owner, amount)
        return _as_dict(key, will)

    @gl.public.write
    def execute(self, probate: str, probate_id: str, will_id: str) -> dict:
        """
        Pay the successor, on a verdict this contract did not reach.

        Reads PROBATE for the verdict and then asks PULSE again, here,
        whether the owner is still silent. The process contract reports the
        clock; it does not get the last word on whether somebody is gone.
        Checking again in the contract that moves the money means a halt
        nobody bothered to record still cannot cost an owner their estate.

        Callable by anyone, because nothing the caller supplies changes the
        answer: the terms are here, the silence is in PULSE, and the
        judgement is in PROBATE.
        """
        key = will_id.strip().lower()
        will = self._held(key)

        verdict = gl.contract.get_at(_address(probate)).view().verdict(probate_id.strip().lower())

        # Pin the probate to this will, without the contract needing to know
        # its own address: the id, the owner and the pulse must all line up.
        if str(verdict["will_id"]).lower() != key:
            raise gl.vm.UserError("that probate is about a different will")
        if str(verdict["owner"]).lower() != will.owner.as_hex.lower():
            raise gl.vm.UserError("that probate names a different owner")
        if str(verdict["pulse_id"]).lower() != will.pulse_id:
            raise gl.vm.UserError("that probate watches a different pulse")

        state = str(verdict["state"])
        if state != "ripe":
            return self._undecided(key, will, "the probate is " + state + ": " + str(verdict["reason"]))

        # The question that actually matters, asked again and asked here.
        record = gl.contract.get_at(will.pulse).view().get_pulse(will.pulse_id)
        seen = epoch_seconds(str(record["last_alive"]))
        opened = epoch_seconds(str(verdict["opened_at"]))
        if seen is None or opened is None:
            return self._undecided(key, will, "a timestamp on this pulse could not be read")
        if seen > opened:
            return self._undecided(
                key, will, "the owner has been seen since probate opened, so nothing is owed"
            )

        amount = int(will.amount)
        will.state = STATE_PAID
        will.decided_at = _stamp()
        will.reason = "the silence ran and nobody answered"
        self.wills[key] = will
        self.committed = self.committed - amount
        _pay(will.successor, amount)
        return _as_dict(key, will)

    # ----------------------------------------------------------------
    # reading
    # ----------------------------------------------------------------

    @gl.public.view
    def get_will(self, will_id: str) -> dict:
        key = will_id.strip().lower()
        if key not in self.wills:
            raise gl.vm.UserError("no such will: " + key)
        return _as_dict(key, self.wills[key])

    @gl.public.view
    def will_list(self) -> list:
        return [w for w in self.will_ids]

    @gl.public.view
    def reserves(self) -> dict:
        return {"committed": str(self.committed)}

    @gl.public.view
    def terms(self) -> dict:
        return {
            "min_silence_days": str(MIN_SILENCE_DAYS),
            "max_silence_days": str(MAX_SILENCE_DAYS),
        }

    def _held(self, key: str) -> Will:
        if key not in self.wills:
            raise gl.vm.UserError("no such will: " + key)
        will = self.wills[key]
        if will.state != STATE_HELD:
            raise gl.vm.UserError("that will is already " + will.state)
        return will

    def _undecided(self, key: str, will: Will, why: str) -> dict:
        """Record why nothing moved, and leave the will held."""
        will.reason = why
        self.wills[key] = will
        return _as_dict(key, will)


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------


def _stamp() -> str:
    return str(gl.message.raw["datetime"])


def _address(value) -> Address:
    if hasattr(value, "as_hex"):
        return value
    return Address(str(value).strip())


@gl.evm.contract_interface
class _Wallet:
    """A plain account on the EVM side: nothing to call, only to pay."""

    class View:
        pass

    class Write:
        pass


def _pay(to: Address, amount: int) -> None:
    """
    The one place value leaves this contract.

    Through the EVM interface, which is what actually reaches a plain
    wallet. The transaction must also reserve a fee for that outgoing
    message; see deploy/chain.mjs.
    """
    _Wallet(to).emit_transfer(value=amount)


def _as_dict(key: str, will: Will) -> dict:
    return {
        "will_id": key,
        "owner": will.owner.as_hex,
        "successor": will.successor.as_hex,
        "amount": str(will.amount),
        "pulse": will.pulse.as_hex,
        "pulse_id": will.pulse_id,
        "silence_days": str(will.silence_days),
        "written_at": will.written_at,
        "state": will.state,
        "decided_at": will.decided_at,
        "reason": will.reason,
    }
