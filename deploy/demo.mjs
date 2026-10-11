// The live contracts, one step per run, so every result is checked before the next.
//
//   npm install
//   export GENLAYER_KEYSTORE=~/.genlayer/keystores/mykey.json
//   export GENLAYER_PASSWORD=...           # never stored in this repo
//
//   node deploy/demo.mjs show
//   node deploy/demo.mjs register <name> <host> <path> "<marker>"
//   node deploy/demo.mjs observe  <pulse_id>
//   node deploy/demo.mjs ping     <pulse_id>
//   node deploy/demo.mjs write    <pulse_id> <successor> <silence_days> <GEN>
//   node deploy/demo.mjs cancel   <will_id>
//   node deploy/demo.mjs open     <will_id>
//   node deploy/demo.mjs execute  <case_id> <will_id>
//
// Addresses come from live.json, written by deploy/deploy.mjs.
import { readFileSync } from "node:fs";
import {
  MESSAGE_ALLOCATION_ROOT_PARENT_INDEX,
  MessageType,
  encodeExternalMessageFeeParams,
} from "genlayer-js";
import { balance, connect, estimateFees, fmt, gen, txUrl, waitFor } from "./chain.mjs";

const live = JSON.parse(readFileSync(new URL("./live.json", import.meta.url), "utf8"));
const { pulse: PULSE, will: WILL, probate: PROBATE } = live;
if (!PULSE || !WILL || !PROBATE) throw new Error("deploy/live.json has no addresses yet");

const { account, client } = await connect();
const view = (address, fn, args = []) => client.readContract({ address, functionName: fn, args });

const PAYOUT_GAS_LIMIT = 200_000n;
const PAYOUT_MAX_GAS_PRICE = 400_000_000n;

/**
 * The fee a payout needs reserved before value can leave a contract.
 *
 * Paying a wallet is an external message, and a transaction that does not
 * reserve a budget for one dies with `out_of message_fee total # external`.
 * Neither estimator produces the allocation on its own, so it is declared
 * here and priced by the generic estimate, which is the only one that fills
 * `totalMessageFees`.
 */
function payoutAllocation(recipient) {
  return {
    messageType: MessageType.External,
    onAcceptance: false,
    parentIndex: MESSAGE_ALLOCATION_ROOT_PARENT_INDEX,
    recipient,
    budget: PAYOUT_GAS_LIMIT * PAYOUT_MAX_GAS_PRICE,
    feeParams: encodeExternalMessageFeeParams({
      gasLimit: PAYOUT_GAS_LIMIT,
      maxGasPrice: PAYOUT_MAX_GAS_PRICE,
    }),
  };
}

async function write(address, functionName, args, value = 0n, payTo = undefined) {
  const allocations = payTo ? [payoutAllocation(payTo)] : undefined;
  const fees = await estimateFees(client, {
    address,
    functionName,
    args,
    value,
    ...(allocations ? { messageAllocations: allocations } : {}),
  });
  const txId = await client.writeContract({
    address,
    functionName,
    args,
    value,
    // Each observation is one web fetch per validator, and a rotation costs a round.
    consensusMaxRotations: 8,
    ...(fees ? { fees: { ...fees, ...(allocations ? { messageAllocations: allocations } : {}) } } : {}),
  });
  const receipt = await waitFor(client, txId);
  console.log("  ", txUrl(txId));
  if (!receipt.ok) console.log("   returned nothing:", receipt.outcome);
  return receipt;
}

async function show() {
  for (const id of await view(PULSE, "pulse_list")) {
    const p = await view(PULSE, "get_pulse", [id]);
    console.log(`pulse ${id}`);
    console.log(`   ${p.url}  marker "${p.marker}"`);
    console.log(`   last ${p.last_outcome || "never observed"} | silent ${p.silent_days}d | runs ${p.silent_runs} | ${p.note}`);
  }
  for (const id of await view(WILL, "will_list")) {
    const w = await view(WILL, "get_will", [id]);
    console.log(`will ${id}\n   [${w.state}] ${w.amount} after ${w.silence_days}d | ${w.reason || "-"}`);
  }
  console.log("committed", (await view(WILL, "reserves")).committed);
}

const [step, ...rest] = process.argv.slice(2);
console.log("wallet", account.address, fmt(await balance(account.address)), "\n");

if (step === "register") {
  await write(PULSE, "register", [rest[0], rest[1], rest[2], rest[3]]);
} else if (step === "observe") {
  await write(PULSE, "observe", [rest[0]]);
  const p = await view(PULSE, "get_pulse", [rest[0]]);
  console.log(`\n=> ${p.last_outcome.toUpperCase()}: ${p.note}`);
  console.log(`   ${p.url}  silent_runs=${p.silent_runs} last_alive=${p.last_alive}`);
} else if (step === "ping") {
  await write(PULSE, "ping", [rest[0]]);
} else if (step === "write") {
  const [pulseId, successor, days, amount] = rest;
  await write(WILL, "write", [PULSE, pulseId, successor, Number(days)], gen(amount));
} else if (step === "cancel") {
  const before = await view(WILL, "get_will", [rest[0]]);
  console.log("owner before", fmt(await balance(before.owner)));
  await write(WILL, "cancel", [rest[0]], 0n, before.owner);
  const after = await view(WILL, "get_will", [rest[0]]);
  console.log("owner after ", fmt(await balance(before.owner)));
  console.log(`=> ${after.state}: ${after.reason}`);
} else if (step === "open") {
  await write(PROBATE, "open", [WILL, rest[0]]);
} else if (step === "execute") {
  const [caseId, willId] = rest;
  const before = await view(WILL, "get_will", [willId]);
  console.log("successor before", fmt(await balance(before.successor)));
  await write(WILL, "execute", [PROBATE, caseId, willId], 0n, before.successor);
  const after = await view(WILL, "get_will", [willId]);
  console.log("successor after ", fmt(await balance(before.successor)));
  console.log(`=> ${after.state}: ${after.reason}`);
} else if (step !== "show") {
  console.log("steps: show, register, observe, ping, write, cancel, open, execute");
  process.exit(1);
}

console.log("");
await show();
