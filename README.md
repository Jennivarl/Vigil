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
| PULSE | [`0x9467cE5dfD80FaE1a0e958413A84396dA43b51cB`](https://explorer-studio-dev.genlayer.com/address/0x9467cE5dfD80FaE1a0e958413A84396dA43b51cB) |
| WILL | [`0x7bB9e11B20f749Cfc17B925BeeE538b4a86313fe`](https://explorer-studio-dev.genlayer.com/address/0x7bB9e11B20f749Cfc17B925BeeE538b4a86313fe) |
| PROBATE | [`0x19F9CA63f06BC1cCeaCde0CFc486CA14b551967c`](https://explorer-studio-dev.genlayer.com/address/0x19F9CA63f06BC1cCeaCde0CFc486CA14b551967c) |
| WITNESS | [`0xdeF02b8b5DCa1E03998e2B16E305E13783fFACb7`](https://explorer-studio-dev.genlayer.com/address/0xdeF02b8b5DCa1E03998e2B16E305E13783fFACb7) |
| Tests | 148, `python -m pytest -q` |

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

| step | transaction | outcome |
|---|---|---|
| Register a pulse on a real page | [`0x91d45a0f...`](https://explorer-studio-dev.genlayer.com/tx/0x91d45a0f1c5b37db954392c2576a7514d588c17d2b8dcdd5d3d5fef23515672b) | `example.com/`, marker `Example Domain` |
| Observe it | [`0x233ee53a...`](https://explorer-studio-dev.genlayer.com/tx/0x233ee53ae82b98be3774aa04e65783e64188e4f5269498b178028efc4572cdb9) | **`alive`**: `the marker is still there` |
| Register a second pulse, same page, different marker | [`0x06812d08...`](https://explorer-studio-dev.genlayer.com/tx/0x06812d08732354a68ee2eaffd350ac566410e9067136f6fdf880e1d9c8649842) | marker `the owner is still here`, which is not on that page |
| Observe it | [`0x1be72eb4...`](https://explorer-studio-dev.genlayer.com/tx/0x1be72eb47f8498dcbabf51226fb4ed277ccb639aa36bf28448cbfafa42855495) | **`silent`**: `the page loaded without the marker` |
| Register a pulse on a host that does not resolve | [`0x78ca2124...`](https://explorer-studio-dev.genlayer.com/tx/0x78ca21242e087e331149cd0660052815fa40ecf7fc17551e48cce75b8b90c124) | |
| Observe it | [`0xf91a8254...`](https://explorer-studio-dev.genlayer.com/tx/0xf91a8254608cec73e774f599951bc9514f3637d9aad30a3ecdd7f52f04f4d8c7) | **`unreachable`**: `the document could not be fetched`. Nothing advanced |
| Write a will against the live pulse | [`0x2a899522...`](https://explorer-studio-dev.genlayer.com/tx/0x2a899522ac7f106dc25464920a9777042a55bbbd6a0e0e381c30be5ef37ceee7) | 0.5 GEN held, 90 days of silence required |
| Try to open probate | [`0x516c8070...`](https://explorer-studio-dev.genlayer.com/tx/0x516c80700bc09c939bb29c14fb7295fb4bd7be50cd9cef62253ef3e1552442da) | **refused**, `only the named successor may open probate` |
| Owner cancels | [`0xa5579fe4...`](https://explorer-studio-dev.genlayer.com/tx/0xa5579fe4308645d59c86ce79bf958047541e4905a2358a65fd97b2eee73aae57) | **paid back**: 37.109701 to 37.609575 GEN, the deposit returned |

The middle rows are the design in one place. The **same page**, fetched by the same contract, is `alive` under one marker and `silent` under another, while a host that cannot be reached is neither.

The deploys, in dependency order: PULSE [`0x7b946902...`](https://explorer-studio-dev.genlayer.com/tx/0x7b946902ac498330d79e58114cc3301d98a20b1e1d563c04e901ba3d57afb8d1), WILL [`0x1b388291...`](https://explorer-studio-dev.genlayer.com/tx/0x1b388291a3428b408bc017206e0ec38fba605c47c2439ba9619c8198ca0396f4), PROBATE [`0xe1474172...`](https://explorer-studio-dev.genlayer.com/tx/0xe147417233d8878e9a4c1715a0a6edaf53fbf4d23fd68de9ac2fde7ae77ef87b), WITNESS [`0xd038a1b8...`](https://explorer-studio-dev.genlayer.com/tx/0xd038a1b8808380fc499f9a5ad38ac34baf5ca887728135e22ec4f56124044c62). The court was then bound to WILL, once and for good: [`0x32716d38...`](https://explorer-studio-dev.genlayer.com/tx/0x32716d386084546fef8aa85613c6b4ac8b9f9ea009477b7abfe0ecb6b86f41d2).

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
python -m pytest -q                    # 148 tests, no chain and no network
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
test/                       148 tests
```

GenVM loads a single source file with no access to siblings, so each bundle pastes a contract together with the pure module it imports. Comments and docstrings are stripped from the deployed copy, because a deploy costs gas per byte and a bundle over the cap returns a transaction hash and then simply does not exist. Edit the modules, never a bundle: a test regenerates them and fails if a committed copy has drifted.

## License

MIT
