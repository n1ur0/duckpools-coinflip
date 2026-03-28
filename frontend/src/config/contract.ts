/**
 * DuckPools Coinflip Contract Configuration
 *
 * These values must match the compiled and deployed contract.
 * BLOCKED by MAT-344: coinflip_v1.es has NOT been compiled yet,
 * so P2S_ADDRESS is a placeholder.
 *
 * Register layout (from coinflip_v1.es):
 *   R4:  housePubKey    (GroupElement) — house's compressed public key (33 bytes)
 *   R5:  playerPubKey   (Coll[Byte])   — player's compressed public key
 *   R6:  commitmentHash (Coll[Byte])   — blake2b256(secret || choice)
 *   R7:  playerChoice   (Int)          — 0=heads, 1=tails
 *   R8:  playerSecret   (Int)          — player's random secret
 *   R9:  betId          (Coll[Byte])   — unique bet identifier
 *   R10: timeoutHeight  (Int)          — block height for timeout/refund
 *
 * The box MUST contain the Game NFT as its first token.
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
