/**
 * DuckPools Coinflip Service
 *
 * Builds unsigned EIP-12 transactions for the commit (place-bet) phase
 * using Fleet SDK. The wallet (Nautilus) then signs and submits.
 *
 * Dependencies:
 *   - @fleet-sdk/core (TransactionBuilder, OutputBuilder, BoxSelector)
 *   - @fleet-sdk/serializer (SInt, SLong, SColl, SGroupElement, SByte)
 *   - @fleet-sdk/crypto (blake2b256)
 *
 * BLOCKED by MAT-344: contract must be compiled before on-chain flow works.
 * When P2S_ADDRESS is empty, buildPlaceBetTx throws.
 *
 * CONTRACT BUG: coinflip_v1.es uses R10 (timeoutHeight) but Ergo only
 * supports non-mandatory registers R4-R9. The contract must be fixed
 * to use R9 for timeout (moving betId elsewhere) before compilation.
 */

import {
  TransactionBuilder,
  OutputBuilder,
  BoxSelector,
  ErgoAddress,
  type Box,
  type Amount,
} from '@fleet-sdk/core';
import { SInt, SColl, SGroupElement, SByte } from '@fleet-sdk/serializer';
import { blake2b256 } from '@fleet-sdk/crypto';
import {
  P2S_ADDRESS,
  HOUSE_PUB_KEY,
  GAME_NFT_ID,
  TIMEOUT_DELTA,
  isOnChainEnabled,
} from '../config/contract';

// ─── Types ────────────────────────────────────────────────────────

export interface PlaceBetParams {
  /** Player's wallet address (change address) */
  changeAddress: string;
  /** Bet amount in nanoERG */
  amountNanoErg: bigint;
  /** Player's compressed public key (33 bytes, hex) */
  playerPubKey: string;
  /** blake2b256(secret || choice) — 32 bytes hex */
  commitment: string;
  /** 0 = heads, 1 = tails */
  choice: number;
  /** Player's random secret (8 bytes) */
  secret: Uint8Array;
  /** Unique bet identifier (hex) */
  betId: string;
  /** Current blockchain height */
  currentHeight: number;
  /** Player's UTXOs (from wallet.getUtxos()) */
  utxos: Box<Amount>[];
}

export interface PlaceBetResult {
  /** The unsigned EIP-12 transaction ready for wallet.signTransaction() */
  unsignedTx: ReturnType<InstanceType<typeof TransactionBuilder>['build']> extends { toEIP12Object: () => infer R } ? R : never;
  /** The bet's timeout height */
  timeoutHeight: number;
}

// ─── Helpers ──────────────────────────────────────────────────────

function secretToInt(secret: Uint8Array): number {
  // Convert 8-byte secret to an Int that fits in 32-bit signed range.
  // Use first 4 bytes as big-endian unsigned, capped at Int32 max.
  const view = new DataView(secret.buffer, secret.byteOffset, Math.min(secret.byteLength, 4));
  const val = view.getUint32(0, false); // big-endian
  return val > 0x7fffffff ? val - 0x100000000 : val;
}

// ─── Build Place Bet Transaction ─────────────────────────────────

/**
 * Build an unsigned EIP-12 transaction for placing a coinflip bet.
 *
 * This creates a PendingBetBox locked by the coinflip contract with:
 * - The bet amount in nanoERG
 * - The Game NFT as the first token
 * - R4-R9 registers matching coinflip_v1.es layout
 *
 * NOTE: The contract currently references R10 (timeoutHeight) which does
 * not exist in the Ergo protocol (max R4-R9). This will be fixed in
 * MAT-344 when the contract is recompiled. For now, timeoutHeight is
 * stored in R9 and betId is omitted (will need contract revision).
 *
 * The returned transaction must be passed to wallet.signTransaction()
 * which triggers the Nautilus popup, then wallet.submitTransaction()
 * to broadcast.
 *
 * @throws Error if on-chain flow is not enabled (contract not compiled)
 * @throws Error if insufficient UTXOs to cover bet + fee
 */
export async function buildPlaceBetTx(params: PlaceBetParams): Promise<PlaceBetResult> {
  if (!isOnChainEnabled()) {
    throw new Error(
      'On-chain bet flow is not available. The coinflip contract has not been compiled yet (MAT-344).'
    );
  }

  const timeoutHeight = params.currentHeight + TIMEOUT_DELTA;

  // Build the contract output box with all registers
  // Register layout (matching coinflip_v1.es):
  //   R4: housePubKey    (GroupElement) — house's compressed public key
  //   R5: playerPubKey   (Coll[Byte])   — player's compressed public key
  //   R6: commitmentHash (Coll[Byte])   — blake2b256(secret || choice)
  //   R7: playerChoice   (Int)          — 0=heads, 1=tails
  //   R8: playerSecret   (Int)          — player's random secret
  //   R9: timeoutHeight  (Int)          — block height for timeout
  //
  // NOTE: betId removed from R9 to make room for timeoutHeight.
  // The contract needs to be updated to either:
  //   (a) Use a different register scheme, or
  //   (b) Remove the betId requirement from the contract
  // This will be resolved when MAT-344 (contract compilation) is done.

  const contractAddress = ErgoAddress.fromBase58(P2S_ADDRESS);

  const betBox = new OutputBuilder(params.amountNanoErg, contractAddress, params.currentHeight)
    .addNfts(GAME_NFT_ID)
    .setAdditionalRegisters({
      R4: SGroupElement(HOUSE_PUB_KEY),       // housePubKey (GroupElement)
      R5: SColl(SByte, params.playerPubKey),  // playerPubKey (Coll[Byte])
      R6: SColl(SByte, params.commitment),    // commitmentHash (Coll[Byte])
      R7: SInt(params.choice),                // playerChoice (Int)
      R8: SInt(secretToInt(params.secret)),    // playerSecret (Int)
      R9: SInt(timeoutHeight),               // timeoutHeight (Int)
    });

  // Select UTXOs to cover bet amount + fee
  const target = { nanoErgs: params.amountNanoErg };
  const selectedInputs = new BoxSelector(params.utxos as Box<bigint>[]).select(target);

  if (selectedInputs.length === 0) {
    throw new Error(
      'Insufficient ERG balance to place bet. You need at least ' +
      `${(Number(params.amountNanoErg) / 1e9).toFixed(4)} ERG.`
    );
  }

  // Build the transaction
  const txBuilder = new TransactionBuilder(params.currentHeight)
    .from(selectedInputs as Box<Amount>[])
    .to(betBox)
    .sendChangeTo(params.changeAddress)
    .payMinFee();

  const unsignedTx = txBuilder.build();

  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    unsignedTx: unsignedTx.toEIP12Object() as any,
    timeoutHeight,
  };
}

// ─── Validation ───────────────────────────────────────────────────

/**
 * Validate that the commitment matches blake2b256(secret || choice).
 * This is a client-side sanity check before sending to the node.
 */
export function verifyCommitment(
  secret: Uint8Array,
  choice: number,
  commitment: string
): boolean {
  const buf = new Uint8Array(secret.length + 1);
  buf.set(secret, 0);
  buf[secret.length] = choice;
  const hash = blake2b256(buf);
  const hex = Array.from(hash).map(b => b.toString(16).padStart(2, '0')).join('');
  return hex === commitment.toLowerCase();
}
