/**
 * DuckPools Coinflip Contract Configuration
 *
 * These values must match the compiled and deployed contract (coinflip_v2.es).
 *
 * Register layout (from coinflip_v2.es, compiled 2026-03-28):
 *   R4: Coll[Byte]   — house's compressed public key (33 bytes)
 *   R5: Coll[Byte]   — player's compressed public key (33 bytes)
 *   R6: Coll[Byte]   — blake2b256(secret || choice) — 32 bytes
 *   R7: Int          — player's choice: 0=heads, 1=tails
 *   R8: Int          — block height for timeout/refund
 *   R9: Coll[Byte]   — player's secret (raw random bytes)
 *
 * The box MUST contain the Game NFT as its first token.
 *
 * SECURITY NOTE (SEC-CRITICAL): Previous version referenced v1 layout
 * (R8=playerSecret, R9=betId, R10=timeoutHeight). This was wrong —
 * R10 doesn't exist in Ergo. v2 fixed this. Updated 2026-03-28.
 */

/** P2S address of the compiled coinflip contract (PLACEHOLDER — MAT-344) */
export const P2S_ADDRESS = import.meta.env.VITE_CONTRACT_P2S_ADDRESS || '';

/** ErgoTree hex of the compiled contract */
export const CONTRACT_ERGO_TREE = import.meta.env.VITE_CONTRACT_ERGO_TREE || '';

/** House compressed public key (33 bytes, hex) */
export const HOUSE_PUB_KEY = import.meta.env.VITE_HOUSE_PUB_KEY || '';

/** Game NFT token ID (hex) — required in the PendingBetBox */
export const GAME_NFT_ID = import.meta.env.VITE_GAME_NFT_ID || '';

/** Timeout delta (blocks until player can refund) */
export const TIMEOUT_DELTA = 100;

/** House edge in basis points (300 = 3%) */
export const HOUSE_EDGE_BPS = 300;

/**
 * Whether the on-chain flow is enabled.
 * Requires a compiled contract (P2S_ADDRESS) and house public key.
 */
export function isOnChainEnabled(): boolean {
  return !!(P2S_ADDRESS && HOUSE_PUB_KEY && GAME_NFT_ID);
}
