"""
Stand-ins for the contracts VIGIL reads.

Direct mode loads one contract per process, so WILL, PROBATE and WITNESS
cannot be tested against the real PULSE in the same test. This answers the
cross-contract call with the protocol the chain uses, dispatching on the
method name exactly as separate contracts would, and records every transfer
so a test can assert on money rather than on log lines.

What a stub buys is states that are slow to produce for real: years of
silence, a host that is merely down, and an owner who reappears at the last
possible moment.
"""

OWNER = b"\xa0" * 20
HEIR = b"\xb0" * 20
STRANGER = b"\xc0" * 20

PULSE_AT = "0x" + ("dd" * 20)
WILL_AT = "0x" + ("ee" * 20)
PROBATE_AT = "0x" + ("ff" * 20)

NAME = "estate"
PULSE_ID = "0x" + OWNER.hex() + ":" + NAME
WILL_ID = "0x" + OWNER.hex() + "|" + PULSE_ID
CASE_ID = WILL_AT.lower() + "|" + WILL_ID

DEPOSIT = 1_000_000
SILENCE_DAYS = 90
GRACE_DAYS = 14
MIN_SILENT_RUNS = 3
SILENCE_FRESH_SECONDS = 7 * 24 * 3600

# An EVM transfer, which is how value reaches a plain wallet.
EVM_PAY = "EmitExternalMessage"


class Stubs:
    """One hook answering for PULSE, WILL and PROBATE."""

    def __init__(self):
        self.pulse = {
            "pulse_id": PULSE_ID,
            "owner": "0x" + OWNER.hex(),
            "name": NAME,
            "url": "https://example.com/alive.txt",
            "marker": "still here",
            "registered_at": "2026-01-01T09:00:00Z",
            "last_alive": "2026-01-01T09:00:00Z",
            "last_by": "ping",
            "silent_runs": "3",
            "last_observed": "",
            "last_outcome": "",
            "note": "registered",
            "silent_days": "120",
            # Consensus has agreed, three times and recently, that the
            # marker is gone. Eligibility needs this; the age of
            # `last_alive` on its own is not enough.
            "last_silent_at": "2026-04-30T09:00:00Z",
            "silence_age_seconds": "3600",
            "silence_confirmed": True,
            "runs_required": "3",
            "confirmations_at_least_seconds_apart": "3600",
            "silence_fresh_for_seconds": str(7 * 24 * 3600),
        }
        self.will = {
            "will_id": WILL_ID,
            "owner": "0x" + OWNER.hex(),
            "successor": "0x" + HEIR.hex(),
            "amount": str(DEPOSIT),
            "pulse": PULSE_AT,
            "pulse_id": PULSE_ID,
            "silence_days": str(SILENCE_DAYS),
            "written_at": "2026-01-01T10:00:00Z",
            "state": "held",
            "decided_at": "",
            "reason": "",
        }
        self.verdict = {
            "case_id": CASE_ID,
            "state": "ripe",
            "opener": "0x" + HEIR.hex(),
            "will": WILL_AT,
            "will_id": WILL_ID,
            "owner": "0x" + OWNER.hex(),
            "successor": "0x" + HEIR.hex(),
            "pulse": PULSE_AT,
            "pulse_id": PULSE_ID,
            "silence_days": str(SILENCE_DAYS),
            "last_alive_at_open": "2026-01-01T09:00:00Z",
            "opened_at": "2026-05-01T09:00:00Z",
            "halted": False,
            "halted_at": "",
            "grace_days": str(GRACE_DAYS),
            "waited_days": "30",
            "reason": "the grace period ran",
        }
        self.transfers = []
        self.calls = []

    def set_pulse(self, **changes):
        self.pulse = {**self.pulse, **changes}

    def set_will(self, **changes):
        self.will = {**self.will, **changes}

    def set_verdict(self, **changes):
        self.verdict = {**self.verdict, **changes}

    def install(self, vm):
        def hook(_vm, request):
            # Imported here rather than at install time: the SDK only exists
            # once a contract has been loaded, and the stub is installed first.
            from gltest.direct.sdk_compat import import_calldata

            calldata = import_calldata()

            for kind in ("PostMessage", "EthSend", EVM_PAY):
                if kind in request:
                    msg = request[kind]
                    self.transfers.append(
                        {"to": bytes(msg["address"].as_bytes), "value": int(msg["value"]), "kind": kind}
                    )
                    return {"ok": None}

            if "CallContract" not in request:
                return None
            call = request["CallContract"]
            method = call["calldata"][""]
            self.calls.append(method)
            if method == "get_pulse":
                answer = self.pulse
            elif method == "get_will":
                answer = self.will
            elif method == "verdict":
                answer = self.verdict
            else:
                answer = {}
            return bytes([0]) + calldata.encode(answer)

        vm._gl_call_hook = hook
        return self
