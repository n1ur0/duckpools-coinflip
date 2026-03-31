/**
 * DuckPools Coinflip Service
 *
 * Builds unsigned EIP-12 transactions for the commit (place-bet) phase
 * using Fleet SDK. The wallet (Nautilus) then signs and submits.
 *
 * Dependencies:
 *   - @fleet-sdk/core (TransactionBuilder, OutputBuilder, BoxSelector)
 *   - @fleet-sdk/serializer (SInt, SColl, SByte)
 *   - @fleet-sdk/crypto (blake2b256)
 *
 * Register layout must match coinflip_v2 (coinflip_deployed.json):
 *   R4: Coll[Byte] — house compressed PK (33 bytes)
 *   R5: Coll[Byte] — player compressed PK (33 bytes)
 *   R6: Coll[Byte] — commitment blake2b256(secret||choice) (32 bytes)
 *   R7: Int        — player choice (0=heads, 1=tails)
 *   R8: Int        — timeout height (block number)
 *   R9: Coll[Byte] — player secret (32 random bytes)
 */

import {
  TransactionBuilder,
  OutputBuilder,
  BoxSelector,
  ErgoAddress,
  type Box,
  type Amount,
} from '@fleet-sdk/core';
import { SInt, SColl, SByte } from '@fleet-sdk/serializer';
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
  /** Player's random secret (32 bytes, raw) */
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

// ─── Build Place Bet Transaction ─────────────────────────────────

/**
 * Build an unsigned EIP-12 transaction for placing a coinflip bet.
 *
 * This creates a PendingBetBox locked by the coinflip_v2 contract with:
 * - The bet amount in nanoERG
 * - The Game NFT as the first token
 * - R4-R9 registers matching coinflip_deployed.json layout
 *
 * The returned transaction must be passed to wallet.signTransaction()
 * which triggers the Nautilus popup, then wallet.submitTransaction()
 * to broadcast.
 *
 * @throws Error if on-chain flow is not enabled (contract not configured)
 * @throws Error if insufficient UTXOs to cover bet + fee
 */
export async function buildPlaceBetTx(params: PlaceBetParams): Promise<PlaceBetResult> {
  if (!isOnChainEnabled()) {
    throw new Error(
      'On-chain bet flow is not available. Configure VITE_CONTRACT_P2S_ADDRESS, ' +
      'VITE_HOUSE_PUB_KEY, and VITE_GAME_NFT_ID in your .env file.'
    );
  }

  const timeoutHeight = params.currentHeight + TIMEOUT_DELTA;

  // Build the contract output box with all registers
  // Register layout (matching coinflip_v2 — see coinflip_deployed.json):
  //   R4: Coll[Byte] — housePubKey    (33-byte compressed public key)
  //   R5: Coll[Byte] — playerPubKey   (33-byte compressed public key)
  //   R6: Coll[Byte] — commitmentHash (blake2b256(secret||choice), 32 bytes)
  //   R7: Int        — playerChoice   (0=heads, 1=tails)
  //   R8: Int        — timeoutHeight  (block height for timeout/refund)
  //   R9: Coll[Byte] — playerSecret   (32 random bytes)

  const contractAddress = ErgoAddress.fromBase58(P2S_ADDRESS);

  const betBox = new OutputBuilder(params.amountNanoErg, contractAddress, params.currentHeight)
    .addNfts(GAME_NFT_ID)
    .setAdditionalRegisters({
      R4: SColl(SByte, HOUSE_PUB_KEY),         // housePubKey (Coll[Byte])
      R5: SColl(SByte, params.playerPubKey),    // playerPubKey (Coll[Byte])
      R6: SColl(SByte, params.commitment),      // commitmentHash (Coll[Byte])
      R7: SInt(params.choice),                  // playerChoice (Int)
      R8: SInt(timeoutHeight),                  // timeoutHeight (Int)
      R9: SColl(SByte, params.secret),          // playerSecret (Coll[Byte])
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
