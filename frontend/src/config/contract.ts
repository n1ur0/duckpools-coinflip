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
 * NOTE: coinflip_v2.es does NOT check for tokens/NFTs. The contract guard
 * is purely based on SigmaProp proofs and register values. An NFT can be
 * optionally included in the PendingBetBox for easier off-chain indexing,
 * but it is NOT required for the contract to function.
 *
 * SECURITY NOTE (SEC-CRITICAL): Previous version referenced v1 layout
 * (R8=playerSecret, R9=betId, R10=timeoutHeight). This was wrong —
 * R10 doesn't exist in Ergo. v2 fixed this. Updated 2026-03-28.
 */

/** P2S address of the compiled coinflip contract */
export const P2S_ADDRESS = import.meta.env.VITE_CONTRACT_P2S_ADDRESS || '';

/** ErgoTree hex of the compiled contract */
export const CONTRACT_ERGO_TREE = import.meta.env.VITE_CONTRACT_ERGO_TREE || '';

/** House compressed public key (33 bytes, hex) */
export const HOUSE_PUB_KEY = import.meta.env.VITE_HOUSE_PUB_KEY || '';

/** House wallet P2PK address (for reveal payouts when house wins) */
export const HOUSE_ADDRESS = import.meta.env.VITE_HOUSE_ADDRESS || '';

/** Ergo node REST API URL (for fetching block headers, box info) */
export const NODE_URL = import.meta.env.VITE_NODE_URL || 'http://127.0.0.1:9052';

/** Game NFT token ID (hex) — optional, for off-chain box indexing only */
export const GAME_NFT_ID = import.meta.env.VITE_GAME_NFT_ID || '';

/** Timeout delta (blocks until player can refund) */
export const TIMEOUT_DELTA = 100;

/** House edge in basis points (300 = 3%) */
export const HOUSE_EDGE_BPS = 300;

/**
 * Whether the on-chain flow is enabled.
 * Requires a compiled contract (P2S_ADDRESS) and house public key.
 * NFT is optional — coinflip_v2.es does not check for tokens.
 *
 * Uses dynamic import.meta access to prevent Vite/Rollup tree-shaking
 * from eliminating the on-chain code path when env vars are empty at
 * build time. Without this guard, the entire on-chain branch (including
 * Fleet SDK TransactionBuilder) would be dead-code eliminated.
 */
export function isOnChainEnabled(): boolean {
  try {
    // Dynamic property access prevents static analysis / tree-shaking
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const env: any = import.meta;
    const p2s = String(env.env?.VITE_CONTRACT_P2S_ADDRESS ?? P2S_ADDRESS);
    const pk = String(env.env?.VITE_HOUSE_PUB_KEY ?? HOUSE_PUB_KEY);
    return p2s.length > 0 && pk.length > 0;
  } catch {
    return false;
  }
}