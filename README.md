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
| WILL | [`0xC791E55bAde7150054808Aeb76e02116d9aC70c4`](https://explorer-studio-dev.genlayer.com/address/0xC791E55bAde7150054808Aeb76e02116d9aC70c4) |
| PROBATE | [`0x1996c8E230202CEf61fb0e4f417757CC3cfEf7Cd`](https://explorer-studio-dev.genlayer.com/address/0x1996c8E230202CEf61fb0e4f417757CC3cfEf7Cd) |
| WITNESS | [`0xDfc3b94f0c2b060A3EdEF9eeBB9e1bCE901E990C`](https://explorer-studio-dev.genlayer.com/address/0xDfc3b94f0c2b060A3EdEF9eeBB9e1bCE901E990C) |
| Tests | 177, `python -m pytest -q` |

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

## A verdict is about one version of one will

A steward found the next hole. Cancelling and writing again on the same pulse reused the same will id, and `execute` only checked that a verdict named that id, owner and pulse. So a probate that had ripened against a will the owner later cancelled could pay out the replacement, without the replacement ever having its own grace period.

Every will now carries a **version**: 1 when first written, one more each time it is written again after a cancel. PROBATE reads the version when a case opens, keeps it, puts it in the case id (`…|v2`), and reports it in every verdict. `execute` pays only when the verdict's version is the one WILL holds now. A rewritten will starts its own case from nothing, and an old ripe case can never move its money. The regression is `test_cancel_then_rewrite_then_the_old_verdict_cannot_execute`.

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
| Write a will against the live pulse | [`0x2dca366a...`](https://explorer-studio-dev.genlayer.com/tx/0x2dca366ae4d2a1ef2c5228fb8773cc7dcb133173dbb4fd9acf103e3a82bf1ec9) | 0.05 GEN held, 90 days of silence required. **Version 1** |
| The successor tries to open probate | [`0x712d081c...`](https://explorer-studio-dev.genlayer.com/tx/0x712d081cdae77cd8743ff1ef25d1d098f4db54dbeab506d28159a95077872d76) | **refused**: `the owner has been silent 9 days of the 90 required` |
| Owner cancels | [`0x5e88dfad...`](https://explorer-studio-dev.genlayer.com/tx/0x5e88dfaded48b0e616eb63859cd013ac09b18e6769b5bc05ef5e70890c337493) | **paid back**: the deposit returned to the owner in [`0x59e28208...`](https://explorer-studio-dev.genlayer.com/tx/0x59e28208ed9643d0173e3f2f20dbf5539e845e2b5caba1f36626a5e27e678cc6) |
| Owner writes it again | [`0x21380185...`](https://explorer-studio-dev.genlayer.com/tx/0x213801852dd9692130319498403ccc5c24b05542ebd2c034fd5f73db16a33480) | the same will id, now **version 2** |
| The successor tries again | [`0xba93f555...`](https://explorer-studio-dev.genlayer.com/tx/0xba93f5554498ff6421d6441675f01c23db587760667394f2a5df9ec68dcd7480) | **refused**, on the same grounds |
| Owner cancels version 2 | [`0xb341e297...`](https://explorer-studio-dev.genlayer.com/tx/0xb341e2973a80cc22a7da5f3da9c4417b64b2be7ae98196c1646939ef424a5b2f) | **paid back** in [`0x5e5e9d75...`](https://explorer-studio-dev.genlayer.com/tx/0x5e5e9d75a80d80f70fdbb01cd60de15a950b6c48027a5325e5005978f524e596), `committed` back to `0` |

These rows carry the design.

**The same page is `alive` under one marker and `silent` under another**, fetched by the same contract minutes apart, while a host that cannot be reached is neither. A fetch that fails is not evidence of anything.

**The second observation did not count.** Four observations of the silent pulse are on chain and the contract's counter reads three, because the second came 49 seconds after the first. Three fetches in a minute are three consensus rounds that can all catch one transient glitch; only observations an hour or more apart confirm anything. The two that counted came two hours apart each.

**The payout path moved real value**, twice, and it moved it back to the owner, which is the path that must work even when nobody has died. The second will shares the first one's id and carries version 2, which is what keeps any verdict about the first from ever paying out the second.

The deploys, in dependency order: PULSE [`0xc3f5b668...`](https://explorer-studio-dev.genlayer.com/tx/0xc3f5b668b6a76ff39791899bc98d2a6dc2e1280eacc7ce66a85dbbcf1e7181c2), WILL [`0x6391b26b...`](https://explorer-studio-dev.genlayer.com/tx/0x6391b26b6e002fa1355632073fe81686b3bfd69ced1936e6006fb1766e34712f), PROBATE [`0x2dcf1a98...`](https://explorer-studio-dev.genlayer.com/tx/0x2dcf1a9893888deb9f3bbb22a37889e7432555997acf1467617ff46323dc9a48), WITNESS [`0x4cd789e0...`](https://explorer-studio-dev.genlayer.com/tx/0x4cd789e036ddecdce7f9bede94fa23955199cdc0339f9fb60295cbc15bd401a3). The court was then bound to WILL, once and for good: [`0x41da2ba9...`](https://explorer-studio-dev.genlayer.com/tx/0x41da2ba95fda4e276fd9fcaf7d92bce5f804ffcd92f95dfd0a1ea1f300372340).

**Not shown live:** a completed handover, because it needs 90 days of real silence followed by 14 of grace. Every step of it is covered by the test suite, including the case where the owner reappears after probate opens and the successor gets nothing, and the case where a will is cancelled and rewritten after a probate on the old one has ripened.

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
python -m pytest -q                    # 177 tests, no chain and no network
```

The tests run the contracts in direct mode, in process. The watched document is answered from the test, so a test can produce states that are slow to arrange for real: years of silence, a host that is merely down, and an owner who reappears at the last possible moment.

Direct mode loads one contract per process, so WILL, PROBATE and WITNESS are tested against stubs that speak the real cross-contract protocol: the contract genuinely calls out, and the reply is genuinely calldata encoded.

To drive the live copies:

Deployment order matters, because each contract is told who it trusts, and the court is bound once afterwards:

```sh
node deploy/deploy.mjs contracts/pulse_bundle.py
node deploy/deploy.mjs contracts/will_bundle.py    <pulse address>
node deploy/deploy.mjs contracts/probate_bundle.py <will address>
node deploy/demo.mjs bind                         # once, from the deploying account
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
test/                       177 tests
```

GenVM loads a single source file with no access to siblings, so each bundle pastes a contract together with the pure module it imports. Comments and docstrings are stripped from the deployed copy, because a deploy costs gas per byte and a bundle over the cap returns a transaction hash and then simply does not exist. Edit the modules, never a bundle: a test regenerates them and fails if a committed copy has drifted.

## License

MIT
