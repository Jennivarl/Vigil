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
| PULSE | [`0xD37f94D4f12e5eE099735aF0934605fC54189cF5`](https://explorer-studio-dev.genlayer.com/address/0xD37f94D4f12e5eE099735aF0934605fC54189cF5) |
| WILL | [`0x38e6BA32d39448B0b2c6eA5e987A9d78f16cea7C`](https://explorer-studio-dev.genlayer.com/address/0x38e6BA32d39448B0b2c6eA5e987A9d78f16cea7C) |
| PROBATE | [`0x9539dD68BF410bB1d59B4aa573223dD8f803F9C8`](https://explorer-studio-dev.genlayer.com/address/0x9539dD68BF410bB1d59B4aa573223dD8f803F9C8) |
| WITNESS | [`0xd1D5cD25676288F68E317E19CB0Ce8De67d96834`](https://explorer-studio-dev.genlayer.com/address/0xd1D5cD25676288F68E317E19CB0Ce8De67d96834) |
| Tests | 143, `python -m pytest -q` |

---

## An outage is not an absence

| outcome | what happened | what it does to the clock |
|---|---|---|
| `alive` | fetched, and the marker was there | resets everything |
| `silent` | fetched, and the marker was gone | advances the run by one |
| `unreachable` | could not be fetched at all | **nothing at all** |

That third row is the whole design. Everything here is triggered by absence, and if an unreachable host counted as silence then a server having a bad afternoon would advance somebody towards losing their estate. So an unreachable observation moves nothing: not the run of silence, not the last sign of life. Nobody learned anything, and the record says so.

A validator that could not reach the host agrees only that it was unreachable, and will not attest to any other outcome however plausible.

---

## Four separate things stand between a silence and a handover

**A ping always wins.** The owner signing a transaction is a direct statement by the only person who could make it, and nothing observed on the web can contradict it. The web check exists so that being away from a wallet for a month is not the same as being gone.

**The silence threshold is the owner's.** Between 30 and 3650 days, written when the will is. Nobody can set up a handover that fires after a long weekend.

**Probate is a public event with a grace period.** Fourteen days during which one signed transaction from the owner ends the whole thing. The threshold could pass while somebody is in hospital or on a boat, and the grace is the window in which anyone who cares can tell them to sign something.

**The owner can cancel at any moment, right up to execution.** That is not a loophole. Every one of those transactions is signed by the owner, so anybody who can send one has answered the only question being asked.

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

| step | transaction | outcome |
|---|---|---|
| Deploy PULSE | [`0x908591db...`](https://explorer-studio-dev.genlayer.com/tx/0x908591dbee03f85543af3dfb9f6eade647e05dfbd31b07e4283a7e9c7b2810c9) | source byte-identical to the bundle in this repo |
| Deploy WILL | [`0x4cf24553...`](https://explorer-studio-dev.genlayer.com/tx/0x4cf245530bc2a84f065b7c0c4b2c125ae3fdf7157257ed19c484fbbd80a8830d) | |
| Deploy PROBATE | [`0x9a7a4941...`](https://explorer-studio-dev.genlayer.com/tx/0x9a7a4941306b5c37c9ef6fdbc2d0262ed784b4822aff74214b3d2e16fe6a2bc7) | |
| Deploy WITNESS | [`0xa7e29c8b...`](https://explorer-studio-dev.genlayer.com/tx/0xa7e29c8bab10fc5435f7e0e7b94de76a6a0d44062f2dfadd96432663db4f6e7d) | pointed at a live pulse |
| Register a pulse on a real page | [`0x5d59bd1f...`](https://explorer-studio-dev.genlayer.com/tx/0x5d59bd1f4498211e167c5fc9a19e424d3fe6c4e32a7bb5b876a269fd6dba8646) | `example.com/`, marker `Example Domain` |
| Observe it | [`0x11990005...`](https://explorer-studio-dev.genlayer.com/tx/0x119900056b08f4903dd5222b12d4f4b4542532b00c7aea51663f8b04d5c5d049) | **`alive`**: `the marker is still there` |
| Register a second pulse, same page, different marker | [`0x0f09d8b6...`](https://explorer-studio-dev.genlayer.com/tx/0x0f09d8b665e4075ee40cd5592f3169d858ba9e7063337bdd717a39228c8a636b) | marker `the owner is still here`, which is not on that page |
| Observe it | [`0x508b5714...`](https://explorer-studio-dev.genlayer.com/tx/0x508b5714d127870dee67cda520452cf7560a178b8fb349a5bd1f4b435cbd254f) | **`silent`**: `the page loaded without the marker` |
| Register a pulse on a host that does not resolve | [`0xc10b2d15...`](https://explorer-studio-dev.genlayer.com/tx/0xc10b2d157d3b481abae9bb78d7163aa8440703d69af5974bc09f7e783f0a0daf) | |
| Observe it | [`0x99964c39...`](https://explorer-studio-dev.genlayer.com/tx/0x99964c39c8006720a27ab1776a2b7e2b3f1bb87bf7f0c0d802d4a7cc6071e35b) | **`unreachable`**: `the document could not be fetched`. Nothing advanced |
| Write a will against the live pulse | [`0x9bcc0902...`](https://explorer-studio-dev.genlayer.com/tx/0x9bcc09027f9c5b1d0692bd643d66719a1a3b0e023cf2038ada917c015f8c0101) | 0.5 GEN held, 90 days of silence required |
| Try to open probate | [`0x3e76893f...`](https://explorer-studio-dev.genlayer.com/tx/0x3e76893f5e4ae41a596f6ec38c61e26d2ae525892d758630b054fe1d68cb8d3b) | **refused**, `only the named successor may open probate` |
| Owner cancels | [`0x9a29c0bc...`](https://explorer-studio-dev.genlayer.com/tx/0x9a29c0bc4f1fcb5c181a463bdbd78b0472e753b22465e9e3a9fdf5c034752844) | **paid back**: the owner went from 37.572677 to 38.072551 GEN, the deposit returned |

The middle three rows are the design in one place. The **same page**, fetched by the same contract, is `alive` under one marker and `silent` under another, while a host that cannot be reached is neither.

**Not shown live:** a completed handover, because it needs 90 days of real silence followed by a 14 day grace. Every step of it is covered by the test suite, including the case where the owner reappears after probate opens and the successor gets nothing.

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
python -m pytest -q                    # 143 tests, no chain and no network
```

The tests run the contracts in direct mode, in process. The watched document is answered from the test, so a test can produce states that are slow to arrange for real: years of silence, a host that is merely down, and an owner who reappears at the last possible moment.

Direct mode loads one contract per process, so WILL, PROBATE and WITNESS are tested against stubs that speak the real cross-contract protocol: the contract genuinely calls out, and the reply is genuinely calldata encoded.

To drive the live copies:

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
test/                       143 tests
```

GenVM loads a single source file with no access to siblings, so each bundle pastes a contract together with the pure module it imports. Comments and docstrings are stripped from the deployed copy, because a deploy costs gas per byte and a bundle over the cap returns a transaction hash and then simply does not exist. Edit the modules, never a bundle: a test regenerates them and fails if a committed copy has drifted.

## License

MIT
