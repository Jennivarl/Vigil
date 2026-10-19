# VIGIL

Acting on silence, carefully.

Almost everything built on a blockchain triggers on something happening. The hard problems are the other way round: an inheritance, a key recovery, a dormant account, a founder who stops showing up. Those all trigger on nothing happening, and nothing happening is the one signal that looks exactly like a broken network.

VIGIL is four contracts that act on an absence without ever mistaking an outage for one.

| contract | what it does |
|---|---|
| **PULSE** | A record of somebody still being here, by their own signature or by a document they keep alive. |
| **WILL** | Custody. Holds a deposit against a named successor and a silence threshold. |
| **PROBATE** | The waiting. Opens a clock once the silence has run, and stops dead if the owner answers. |
| **WITNESS** | The reference consumer: a lock that is open only *while* somebody is here. |

No model is involved anywhere. Validators fetch and compare strings.

| | |
|---|---|
| Network | GenLayer Studio Next, chain id 61997, `https://studio-next.genlayer.com/api` |
| Engine | Consensus v0.6, GenVM v0.3, runner `py-genlayer:5jycge...` |
| PULSE | [`0xEc6CBF2BEf5B2164BdfF1Eb9bB3568183644712F`](https://explorer-studio-dev.genlayer.com/address/0xEc6CBF2BEf5B2164BdfF1Eb9bB3568183644712F) |
| WILL | [`0xb9A506104fDb50A4Ade941D17547F233F26c39a8`](https://explorer-studio-dev.genlayer.com/address/0xb9A506104fDb50A4Ade941D17547F233F26c39a8) |
| PROBATE | [`0x9B67188bd422c1eeED5645dBd7eb7F0bc5952447`](https://explorer-studio-dev.genlayer.com/address/0x9B67188bd422c1eeED5645dBd7eb7F0bc5952447) |
| WITNESS | [`0xDfc3b94f0c2b060A3EdEF9eeBB9e1bCE901E990C`](https://explorer-studio-dev.genlayer.com/address/0xDfc3b94f0c2b060A3EdEF9eeBB9e1bCE901E990C) |
| Tests | 165, `python -m pytest -q` |

---

## Time passing is not evidence

The first version of this got the central thing wrong, and a steward caught it. Eligibility was computed from the age of a stored `last_alive` timestamp, which grows on its own. A pulse that was registered and then **never looked at by anybody** would quietly become claimable, purely because it got old. That is absence of evidence doing the work of evidence of absence, and it is the only failure here that would actually lose somebody their estate.

A handover now requires consensus to have agreed, repeatedly and recently, that the marker is really gone:

| requirement | why |
|---|---|
| **three** consecutive observations found the marker gone | one bad fetch is not a death |
| the most recent of them is **less than 7 days old** | eligibility resting on last year's observation confirms nothing about now |
| the owner has been silent for the threshold they chose | the arrangement they actually wrote |

All three, every time. And each of the three is checked twice: once by PROBATE before the clock can start, and again by WILL before any money moves.

| observation | runs | last confirmed silence | effect on a handover |
|---|---|---|---|
| `alive` | reset to 0 | cleared | blocks it entirely |
| `silent` | +1 | set to now | the only thing that advances it |
| `unreachable` | **unchanged** | **unchanged** | advances nothing, destroys nothing |

That last row is the one the whole design turns on. An unreachable host teaches nobody anything. It must not push a handover forward, and equally it must not let a site going down erase evidence that was already agreed.

A validator that could not reach the host agrees only that it was unreachable, and will not attest to any other outcome however plausible.

---

## Four separate things stand between a silence and a handover

**A ping always wins.** The owner signing a transaction is a direct statement by the only person who could make it, and nothing observed on the web can contradict it. The web check exists so that being away from a wallet for a month is not the same as being gone.

**The silence threshold is the owner's.** Between 30 and 3650 days, written when the will is. Nobody can set up a handover that fires after a long weekend.

**Probate is a public event with a grace period.** Fourteen days during which one signed transaction from the owner ends the whole thing. The threshold could pass while somebody is in hospital or on a boat, and the grace is the window in which anyone who cares can tell them to sign something.

**The owner can cancel at any moment, right up to execution.** That is not a loophole. Every one of those transactions is signed by the owner, so anybody who can send one has answered the only question being asked.

---

## Nothing chooses who it believes at call time

This is the most important thing in the design, and it is here because an audit of this very code found it missing.

An earlier version of `WILL.execute` took the court's address as an argument. A stranger could deploy a contract whose `verdict` returned `ripe` with any `opened_at` it liked, pass that address, and drain a living owner's will to the successor on demand. It was reproduced against the real bundle: the owner had pinged minutes before, the threshold was ninety days, and the deposit still moved.

Every cross-contract address is now fixed when the contract is deployed and can never be an argument.

| contract | reads | fixed how |
|---|---|---|
| WILL | PULSE | constructor |
| WILL | PROBATE | named once, by the deployer, and never again |
| PROBATE | WILL | constructor |
| WITNESS | PULSE | constructor |

The court is named afterwards rather than in the constructor only because the two contracts have to know each other, and something has to be deployed first. `bind_probate` refuses anyone but the deployer, refuses a second call, and `execute` refuses to run at all until it has been set. `settings()` on both publishes what they trust.

A contract that lets its caller choose who it believes has no guarantees at all, only the appearance of them.

---

## WILL does not take PROBATE's word for it

PROBATE reports the clock. It does not get the last word on whether somebody is gone.

Before paying anyone, `WILL.execute` reads PULSE **again, itself**, and refuses if the owner has been seen since probate opened. So a halt that nobody bothered to record still cannot cost an owner their estate, and the contract that moves the money is the one that asks the question that matters.

It also pins the verdict to this exact will by three separate fields, so a probate about somebody else's affairs cannot be pointed at your deposit.

---

## What consensus derived, and what was copied

| stored field | where it comes from | derived or copied |
|---|---|---|
| `last_outcome` | each validator fetched the document itself and classified its own response | derived |
| `note` | the reason, which validators must also agree on, not just the outcome | derived |
| `last_alive` | the transaction's own `datetime`, either of a ping or of an agreed observation | derived |
| `silent_runs` | the contract's own count, advanced only by an agreed `silent` | derived |
| `url`, `marker` | fixed by the owner at registration, immutably, and built into a URL by the contract | the owner's own commitment |
| `silence_days` | the owner's choice, bounded by the contract | the owner's own commitment |

---

## What a dishonest leader can try

| the lie | what it would buy | what happens | test |
|---|---|---|---|
| report a living person silent | starts the clock on somebody who is here | rejected | `test_a_validator_rejects_a_leader_who_reports_a_living_person_silent` |
| report an absent person alive | keeps a dormant estate frozen forever | rejected | `test_a_validator_rejects_a_leader_who_reports_an_absent_person_alive` |
| call a down host silence | **advances a handover over an outage** | rejected | `test_a_validator_rejects_a_leader_who_calls_a_down_host_silence` |
| crash instead of answering | stalls the round | rejected: a malformed result is a disagreement, not an exception | `test_a_validator_rejects_a_leader_that_errored` |
| agree the outcome, differ on the reason | quietly changes what the record says happened | rejected | `test_validators_must_agree_on_the_reason_not_only_the_outcome` |

---

## One deliberate inconsistency, and why

ATTEST, the sibling project, matches a published proof token **line by line and exactly**, because there the danger is a page echoing an attacker's text into a proof that was never made.

VIGIL matches its marker as a **plain substring, anywhere in the page**. The danger runs the other way here: a false negative costs somebody their estate, so the test is as forgiving as it can be while still meaning something.

A marker is required rather than optional for the same reason in reverse. Treating "the page loaded" as proof of life would let a parked domain, a hosting placeholder or a 404 styled as a 200 keep somebody alive forever.

---

## Verified live on Studio Next

Every address in [`deploy/live.json`](deploy/live.json) runs the exact bundle committed here, which `deploy/verify.mjs` proves by fetching each deploy transaction's `contract_code`, hashing it and comparing against the local file.

| step | transaction | outcome |
|---|---|---|
| Register a pulse whose marker is not on the page | [`0x5a462071...`](https://explorer-studio-dev.genlayer.com/tx/0x5a462071209bd6f295943328e099036238b5abada777ae26f22aa0e7db6b1f42) | `example.com/`, marker `the owner is still here` |
| Observe it, 16:52:14 | [`0xdef1eb0b...`](https://explorer-studio-dev.genlayer.com/tx/0xdef1eb0bfd3e23160903177dc767c90e0b172e442bd240d08727d8182a969a59) | **`silent`**: `the page loaded without the marker`. Confirmed runs: **1** |
| Observe it again, 16:53:03 | [`0x32ad5461...`](https://explorer-studio-dev.genlayer.com/tx/0x32ad546139dbddd232bba61270eb3a12b24e3ae5f59133be2699416e6d6d44b4) | **49 seconds later, so it did not count.** Confirmed runs: still **1** |
| Register a pulse on the same page with a marker that is there | [`0x39d38132...`](https://explorer-studio-dev.genlayer.com/tx/0x39d38132cb5de6ce7b32309e02ce70632ea778d094cd423aef8ab979adf6eb3e) | `example.com/`, marker `Example Domain` |
| Observe it | [`0x875c0273...`](https://explorer-studio-dev.genlayer.com/tx/0x875c027319dcfba6eb5bf40710dd61dce4eb63f4da4fb0b3deb0d26ea1b40298) | **`alive`**: `the marker is still there` |
| Register a pulse on a host that does not resolve | [`0x0f5291ad...`](https://explorer-studio-dev.genlayer.com/tx/0x0f5291adb0d6d61fc1a93564e3820a5de913a8e3240c98b0d66c2461a28ad49f) | `no-such-host-vigil-demo.example/alive.txt` |
| Observe it | [`0x888e9615...`](https://explorer-studio-dev.genlayer.com/tx/0x888e96156614de7000cde19a1809d79f8f7aaa6516444013c4dc6fd7fb6bcae2) | **`unreachable`**: `the document could not be fetched`. Nothing advanced |
| Observe the silent pulse, 18:51:03 | [`0x2df8f73e...`](https://explorer-studio-dev.genlayer.com/tx/0x2df8f73e76ab2e25fa27c1684e2b8ef7a53d2000715412845974c245986e04ca) | Two hours clear, so it counts. Confirmed runs: **2** |
| Observe it, 20:51:27 | [`0x0a7dfc44...`](https://explorer-studio-dev.genlayer.com/tx/0x0a7dfc444048b85507fd777541191f164b5e6b913c28e0d1b848882a56c94505) | Two hours clear again. Confirmed runs: **3** |
| Write a will against the live pulse | [`0xe8d6266b...`](https://explorer-studio-dev.genlayer.com/tx/0xe8d6266ba8e78a7d0a3fe1a126d1282f56986cbe4865903e072a323cbd74255e) | 0.5 GEN held, 90 days of silence required |
| Try to open probate | [`0x2a52a7ea...`](https://explorer-studio-dev.genlayer.com/tx/0x2a52a7ea1edc571c35ace0bf2b54d0141a2fc81b553b84b7a50946c788cc4cfb) | **refused**: the owner is alive and the caller is not the named successor |
| Owner cancels | [`0x8a44f5e2...`](https://explorer-studio-dev.genlayer.com/tx/0x8a44f5e239ade52b3f2aa8d3ac1a00f4839a6cc37e1302b7bb8b062554544b5d) | **paid back**: 36.788099 → 37.287973 GEN, the whole deposit returned, `committed` back to `0` |

Four rows carry the design.

**The same page is `alive` under one marker and `silent` under another**, fetched by the same contract minutes apart, while a host that cannot be reached is neither. A fetch that fails is not evidence of anything.

**The second observation did not count.** Four observations of the silent pulse are on chain and the contract's counter reads three, because the second came 49 seconds after the first. Three fetches in a minute are three consensus rounds that can all catch one transient glitch; only observations an hour or more apart confirm anything. The two that counted came two hours apart each.

**The payout path moved real value**, and it moved it back to the owner, which is the path that must work even when nobody has died.

The deploys, in dependency order: PULSE [`0xc3f5b668...`](https://explorer-studio-dev.genlayer.com/tx/0xc3f5b668b6a76ff39791899bc98d2a6dc2e1280eacc7ce66a85dbbcf1e7181c2), WILL [`0x3820587e...`](https://explorer-studio-dev.genlayer.com/tx/0x3820587e1d28db4fcfe32105460dba44d887ea59200b0bc95973cc25f82593ff), PROBATE [`0x28896741...`](https://explorer-studio-dev.genlayer.com/tx/0x28896741a1636eb30a19fde3a70b2cd3f64c479a51ccee319553e6f705dc12ff), WITNESS [`0x4cd789e0...`](https://explorer-studio-dev.genlayer.com/tx/0x4cd789e036ddecdce7f9bede94fa23955199cdc0339f9fb60295cbc15bd401a3). The court was then bound to WILL, once and for good: [`0xd4d28fbc...`](https://explorer-studio-dev.genlayer.com/tx/0xd4d28fbc828241d83f7f536022092048d75ade6e9392b4e644733469a5df4f1e).

**Not shown live:** a completed handover, because it needs 90 days of real silence followed by 14 of grace. Every step of it is covered by the test suite, including the case where the owner reappears after probate opens and the successor gets nothing.

---

## Limits, stated plainly

- **A handover takes months by design.** The shortest possible is 30 days of silence plus 14 of grace. Anything faster would not be safe, and this is not the tool for anything faster.
- **The web check is only as good as the page.** Anyone who can edit the document can keep somebody looking alive, which includes a hosting provider. The ping exists because of that, and a ping cannot be faked by anyone but the owner.
- **Nobody is paid to watch.** Observations and probate are permissionless, but somebody has to care enough to send the transaction. The successor has the obvious incentive.
- **A lost key looks exactly like a death**, and this will transfer the deposit either way. That is the intended behaviour, and it is worth saying out loud before anyone relies on it.
- **One will per pulse at a time.** Register a second pulse for a second arrangement.
- **Silence is counted in whole days**, so an arrangement is never decided by an hour's rounding.

---

## Running it

```sh
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
python -m deploy.build_bundle          # the four files that actually deploy
python -m pytest -q                    # 165 tests, no chain and no network
```

The tests run the contracts in direct mode, in process. The watched document is answered from the test, so a test can produce states that are slow to arrange for real: years of silence, a host that is merely down, and an owner who reappears at the last possible moment.

Direct mode loads one contract per process, so WILL, PROBATE and WITNESS are tested against stubs that speak the real cross-contract protocol: the contract genuinely calls out, and the reply is genuinely calldata encoded.

To drive the live copies:

Deployment order matters, because each contract is told who it trusts, and the court is bound once afterwards:

```sh
node deploy/deploy.mjs contracts/pulse_bundle.py
node deploy/deploy.mjs contracts/will_bundle.py    <pulse address>
node deploy/deploy.mjs contracts/probate_bundle.py <will address>
# then, once, from the deploying account:
#   WILL.bind_probate(<probate address>)
```

```sh
npm install
export GENLAYER_KEYSTORE=~/.genlayer/keystores/mykey.json
export GENLAYER_PASSWORD=...
node deploy/demo.mjs register alive example.com / "Example Domain"
node deploy/demo.mjs observe <pulse_id>
```

Addresses live in [`deploy/live.json`](deploy/live.json). The password is read from the environment and is never stored in this repo.

---

## Layout

```
contracts/liveness.py       the pure part: validation, matching, day arithmetic
contracts/pulse.py          the liveness record, under consensus
contracts/will.py           custody, and the payout
contracts/probate.py        the waiting and the grace period
contracts/witness.py        reference consumer: a lock open only while somebody is here
contracts/*_bundle.py       what actually deploys. Generated, never edited
deploy/build_bundle.py      builds them; a test fails if a committed one is stale
deploy/chain.mjs            network, signing and payout fee allocations
deploy/deploy.mjs           deploy one bundle
deploy/verify.mjs           prove a live contract runs this exact bundle
deploy/demo.mjs             drive the live copies
test/                       165 tests
```

GenVM loads a single source file with no access to siblings, so each bundle pastes a contract together with the pure module it imports. Comments and docstrings are stripped from the deployed copy, because a deploy costs gas per byte and a bundle over the cap returns a transaction hash and then simply does not exist. Edit the modules, never a bundle: a test regenerates them and fails if a committed copy has drifted.

## License

MIT
