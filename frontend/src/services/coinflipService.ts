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
 * BLOCKED by MAT-344: contract must be compiled before on-chain flow works.
 * When P2S_ADDRESS is empty, buildPlaceBetTx throws.
 *
 * Register layout MUST match coinflip_v2.es (compiled 2026-03-28):
 *   R4: Coll[Byte]  — house's compressed public key (33 bytes)
 *   R5: Coll[Byte]  — player's compressed public key (33 bytes)
 *   R6: Coll[Byte]  — blake2b256(secret || choice) — 32 bytes
 *   R7: Int         — player's choice: 0=heads, 1=tails
 *   R8: Int         — block height for timeout/refund
 *   R9: Coll[Byte]  — player's secret (raw bytes from crypto.getRandomValues)
 *
 * SECURITY NOTE (SEC-CRITICAL): Previous version used R4=GroupElement,
 * R8=Int(secret), R9=Int(timeout). This caused type/register mismatches
 * with the compiled contract. Fixed 2026-03-28 by Security Auditor Sr.
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

function secretToHex(secret: Uint8Array): string {
  // Convert the raw secret bytes to a hex string for SColl(SByte, ...) encoding.
  // The contract (coinflip_v2.es) reads playerSecret as Coll[Byte] from R9
  // and uses it directly in blake2b256(playerSecret ++ Coll(choiceByte)).
  // This MUST match the bytes used in generateCommitment() in CoinFlipGame.tsx.
  return Array.from(secret).map(b => b.toString(16).padStart(2, '0')).join('');
}

// ─── Build Place Bet Transaction ─────────────────────────────────

/**
 * Build an unsigned EIP-12 transaction for placing a coinflip bet.
 *
 * This creates a PendingBetBox locked by the coinflip contract with:
 * - The bet amount in nanoERG
 * - The Game NFT as the first token
 * - R4-R9 registers matching coinflip_v2.es layout
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
  // Register layout (matching coinflip_v2.es compiled 2026-03-28):
  //   R4: housePkBytes    (Coll[Byte])   — house's compressed public key
  //   R5: playerPkBytes   (Coll[Byte])   — player's compressed public key
  //   R6: commitmentHash  (Coll[Byte])   — blake2b256(secret || choice)
  //   R7: playerChoice    (Int)          — 0=heads, 1=tails
  //   R8: timeoutHeight   (Int)          — block height for timeout
  //   R9: playerSecret    (Coll[Byte])   — player's random secret (raw bytes)

  const contractAddress = ErgoAddress.fromBase58(P2S_ADDRESS);

  const betBox = new OutputBuilder(params.amountNanoErg, contractAddress, params.currentHeight)
    .addNfts(GAME_NFT_ID)
    .setAdditionalRegisters({
      R4: SColl(SByte, HOUSE_PUB_KEY),                  // housePkBytes (Coll[Byte])
      R5: SColl(SByte, params.playerPubKey),             // playerPkBytes (Coll[Byte])
      R6: SColl(SByte, params.commitment),             // commitmentHash (Coll[Byte])
      R7: SInt(params.choice),                         // playerChoice (Int)
      R8: SInt(timeoutHeight),                         // timeoutHeight (Int)
      R9: SColl(SByte, secretToHex(params.secret)),    // playerSecret (Coll[Byte])
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
