# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
"""
PULSE. A record of somebody still being here.

Two ways to say so, because the whole system turns on this record and one
way is not enough:

    ping()               the owner signs a transaction. Cheap, certain, and
                         impossible for anyone else to do on their behalf
    observe(pulse_id)    anyone triggers a consensus fetch of a document the
                         owner keeps alive, so being away from a wallet for
                         a month is not the same as being gone

    register(name, host, path, marker)   fix the document, immutably
    get_pulse(pulse_id)                  what consensus agreed, as a view

A ping always wins. It is a direct statement by the only person who could
make it, and nothing observed on the web can contradict it.

The three outcomes are kept apart because everything downstream is
triggered by absence:

    alive        fetched, and the marker was there
    silent       fetched, and the marker was gone
    unreachable  could not be fetched at all

`unreachable` advances nothing. It is not a miss, it is the absence of an
observation, and the run of silence stays exactly where it was. Counting an
outage as silence would hand somebody's estate to their successor because a
server had a bad afternoon.

No model is involved anywhere. Validators fetch and compare strings.
"""

from dataclasses import dataclass

import genlayer as gl
from genlayer.types import *

from contracts.liveness import (
    ALIVE,
    SILENT,
    UNREACHABLE,
    epoch_seconds,
    marker_present,
    url_for,
    valid_host,
    valid_marker,
    valid_name,
    valid_path,
)


@gl.storage.allow
@dataclass
class Pulse:
    owner: Address
    name: str
    url: str
    marker: str
    registered_at: str
    # The last moment anybody could tell the owner was here, by either route.
    last_alive: str
    # How that was established: "ping" or "observed".
    last_by: str
    # Consecutive observations that found the marker gone. A ping resets it,
    # and an unreachable host never touches it.
    silent_runs: u256
    last_observed: str
    last_outcome: str
    note: str


class PulseContract(gl.contract.Contract):
    pulses: gl.storage.TreeMap[str, Pulse]
    pulse_ids: gl.storage.DynArray[str]

    def __init__(self):
        pass

    # ----------------------------------------------------------------
    # registering
    # ----------------------------------------------------------------

    @gl.public.write
    def register(self, name: str, host: str, path: str, marker: str) -> dict:
        """
        Fix the document that speaks for you, and the text that must be in it.

        Immutable once set. That is the guarantee anyone relying on this
        needs: the page checked next year is built from the same host and
        the same path as the one checked today, so nobody can quietly point
        their own liveness at something easier to keep alive.
        """
        label = name.strip().lower()
        if not valid_name(label):
            raise gl.vm.UserError("a name is letters, digits, hyphen or underscore")
        clean_host = host.strip().lower()
        if not valid_host(clean_host):
            raise gl.vm.UserError("host must be a bare hostname, with no scheme, port or path")
        clean_path = path.strip()
        if not valid_path(clean_path):
            raise gl.vm.UserError("path must start at / and cannot leave itself")
        text = marker.strip()
        if not valid_marker(text):
            raise gl.vm.UserError("a marker is one line of text that must be present while you are here")

        owner = gl.message.sender_address
        pulse_id = owner.as_hex.lower() + ":" + label
        if pulse_id in self.pulses:
            raise gl.vm.UserError("that pulse already exists and cannot be changed")

        now = _stamp()
        self.pulses[pulse_id] = Pulse(
            owner=owner,
            name=label,
            url=url_for(clean_host, clean_path),
            marker=text,
            registered_at=now,
            # Registering is itself a signed act by the owner, so it counts.
            last_alive=now,
            last_by="ping",
            silent_runs=0,
            last_observed="",
            last_outcome="",
            note="registered",
        )
        self.pulse_ids.append(pulse_id)
        return _as_dict(pulse_id, self.pulses[pulse_id], _now())

    # ----------------------------------------------------------------
    # saying you are here
    # ----------------------------------------------------------------

    @gl.public.write
    def ping(self, pulse_id: str) -> dict:
        """
        Say so directly. Owner only, and it clears any run of silence.

        This is the route that cannot be faked or mistaken. Everything the
        web check does is a fallback for someone who cannot sign today.
        """
        key = pulse_id.strip().lower()
        pulse = self._get(key)
        if pulse.owner.as_hex.lower() != gl.message.sender_address.as_hex.lower():
            raise gl.vm.UserError("only the owner may ping their own pulse")

        pulse.last_alive = _stamp()
        pulse.last_by = "ping"
        pulse.silent_runs = 0
        pulse.note = "the owner signed"
        self.pulses[key] = pulse
        return _as_dict(key, pulse, _now())

    @gl.public.write
    def observe(self, pulse_id: str) -> dict:
        """
        Fetch the document and record what consensus agreed it said.

        Callable by anyone, because nobody can influence the answer: the URL
        and the marker come from the registry, and the only thing a caller
        supplies is which pulse to look at.
        """
        key = pulse_id.strip().lower()
        pulse = self._get(key)
        url = pulse.url
        marker = pulse.marker

        def leader_fn():
            return _probe(url, marker)

        def validator_fn(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            leader = leaders_res.calldata
            if not isinstance(leader, dict) or "outcome" not in leader:
                return False
            mine = _probe(url, marker)

            # I could not reach it, so the only honest agreement is that it
            # could not be reached.
            if mine["outcome"] == UNREACHABLE:
                return str(leader["outcome"]) == UNREACHABLE
            # I reached it, so it was not unreachable whatever the leader says.
            if str(leader["outcome"]) == UNREACHABLE:
                return False
            return str(leader["outcome"]) == mine["outcome"] and str(leader["note"]) == mine["note"]

        agreed = gl.vm.run_nondet(leader_fn, validator_fn)

        outcome = str(agreed["outcome"])
        if outcome not in (ALIVE, SILENT, UNREACHABLE):
            raise gl.vm.UserError("unknown observation")

        now = _stamp()
        pulse.last_observed = now
        pulse.last_outcome = outcome
        pulse.note = str(agreed["note"])

        if outcome == ALIVE:
            pulse.last_alive = now
            pulse.last_by = "observed"
            pulse.silent_runs = 0
        elif outcome == SILENT:
            pulse.silent_runs = pulse.silent_runs + 1
        # An unreachable host advances nothing at all. Not the run of
        # silence, not the last sign of life. Nobody learned anything.

        self.pulses[key] = pulse
        return _as_dict(key, pulse, _now())

    # ----------------------------------------------------------------
    # reading
    # ----------------------------------------------------------------

    @gl.public.view
    def get_pulse(self, pulse_id: str) -> dict:
        key = pulse_id.strip().lower()
        if key not in self.pulses:
            raise gl.vm.UserError("no such pulse: " + key)
        return _as_dict(key, self.pulses[key], _now())

    @gl.public.view
    def silent_days(self, pulse_id: str) -> str:
        """
        How long since anybody could tell the owner was here, in whole days.

        "-1" when it cannot be worked out, which a caller must treat as
        "unknown" and never as "a long time".
        """
        key = pulse_id.strip().lower()
        if key not in self.pulses:
            return "-1"
        return _as_dict(key, self.pulses[key], _now())["silent_days"]

    @gl.public.view
    def pulse_list(self) -> list:
        return [p for p in self.pulse_ids]

    @gl.public.view
    def count(self) -> int:
        return len(self.pulse_ids)

    def _get(self, key: str) -> Pulse:
        if key not in self.pulses:
            raise gl.vm.UserError("no such pulse: " + key)
        return self.pulses[key]


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------


def _stamp() -> str:
    """The transaction's own datetime, identical for every validator."""
    return str(gl.message.raw["datetime"])


def _now():
    return epoch_seconds(_stamp())


def _probe(url: str, marker: str) -> dict:
    """
    Fetch once and say exactly what happened.

    Returns primitives only, so the whole result is comparable field by
    field between validators. The note is compared too, so two validators
    cannot agree on an outcome while disagreeing about why.
    """
    try:
        resp = gl.nondet.web.get(url)
        status = int(resp.status)
        body = (resp.body or b"").decode("utf-8", errors="replace")
    except Exception:
        return {"outcome": UNREACHABLE, "note": "the document could not be fetched"}

    # 404 is the one failure that is an answer: the page the owner promised
    # to keep up is gone, which is exactly what this is watching for.
    if status == 404:
        return {"outcome": SILENT, "note": "the page is gone"}
    if status < 200 or status >= 300:
        return {"outcome": UNREACHABLE, "note": "the host answered " + str(status)}

    if marker_present(body, marker):
        return {"outcome": ALIVE, "note": "the marker is still there"}
    return {"outcome": SILENT, "note": "the page loaded without the marker"}


def _as_dict(key: str, pulse: Pulse, now) -> dict:
    seen = epoch_seconds(pulse.last_alive)
    days = -1
    if seen is not None and now is not None and now >= seen:
        days = (now - seen) // 86400
    return {
        "pulse_id": key,
        "owner": pulse.owner.as_hex,
        "name": pulse.name,
        "url": pulse.url,
        "marker": pulse.marker,
        "registered_at": pulse.registered_at,
        "last_alive": pulse.last_alive,
        "last_by": pulse.last_by,
        "silent_runs": str(pulse.silent_runs),
        "last_observed": pulse.last_observed,
        "last_outcome": pulse.last_outcome,
        "note": pulse.note,
        "silent_days": str(days),
    }
