/**
 * DuckPools Coinflip Contract Configuration
 *
 * These values must match the compiled and deployed contract.
 * P2S address loaded from coinflip_deployed.json as fallback
 * when VITE_CONTRACT_P2S_ADDRESS env var is not set.
 *
 * Register layout (from coinflip_v2 — see coinflip_deployed.json):
 *   R4: Coll[Byte] — housePubKey    (33-byte compressed public key)
 *   R5: Coll[Byte] — playerPubKey   (33-byte compressed public key)
 *   R6: Coll[Byte] — commitmentHash (blake2b256(secret||choice), 32 bytes)
 *   R7: Int        — playerChoice   (0=heads, 1=tails)
 *   R8: Int        — timeoutHeight  (block height for timeout/refund)
 *   R9: Coll[Byte] — playerSecret   (32 random bytes)
 *
 * The box MUST contain the Game NFT as its first token.
 */

/**
 * P2S address of the compiled coinflip_v2 contract.
 * Falls back to the deployed contract address from coinflip_deployed.json.
 */
export const P2S_ADDRESS = import.meta.env.VITE_CONTRACT_P2S_ADDRESS ||
  '3yNMkSZ6b36YGBJJNhpavxxCFg4f2ceH5JF81hXJgzWoWozuFJSjoW8Q5JXow6fsTVNrqz48h8a9ajYSTKfwaxG16GbHzxrDcsarkBkbR6NYdGeoCZ9KgNcNMYPLV9RPkLFwBPLHxDxyTmBfqn5L75zqftETuAadKr8FHEYZrVPZ6kn6gdiZbzMwghxRy2g4wpTdby4jnxhA42UH7JJzMibgMNBW4yvzw8EaguPLVja6xsxx43yihw5DEzMGzL7HKWYUs6uVugK1C8Feh3KUX9kpea5xpLXX5oZCV47W6cnTrJfJD3';

/** ErgoTree hex of the compiled contract */
export const CONTRACT_ERGO_TREE = import.meta.env.VITE_CONTRACT_ERGO_TREE ||
  '19d8010c04000200020104000404040005c20105640400040004000564d805d601cdeee4c6a7040ed602e4c6a7090ed603e4c6a70704d604cdeee4c6a7050ed605c1a7eb02ea02ea027201d193cbb3720283010295937203730073017302e4c6a7060ed195939e7eb2cbb3db6902db6503fe72027303000473047203d801d606b2a5730500ed93c27206d0720492c172069d9c720573067307d801d606b2a5730800ed93c27206d0720192c172067205ea02ea02ea02d192a3e4c6a708047204d193c2b2a5730900d07204d192c1b2a5730a009972059d7205730b';

/** House compressed public key (33 bytes, hex) — REQUIRED for on-chain */
export const HOUSE_PUB_KEY = import.meta.env.VITE_HOUSE_PUB_KEY || '';

/** Game NFT token ID (hex) — required in the PendingBetBox */
export const GAME_NFT_ID = import.meta.env.VITE_GAME_NFT_ID || '';

/** Timeout delta (blocks until player can refund) */
export const TIMEOUT_DELTA = 100;

/** House edge in basis points (300 = 3%) */
export const HOUSE_EDGE_BPS = 300;

/**
 * Whether the on-chain flow is enabled.
 * Requires a house public key and game NFT ID.
 * P2S_ADDRESS now has a deployed fallback so only PK + NFT are required.
 *
 * Uses `process.env` style lookup via Vite's define to ensure the check
 * is not eliminated by tree-shaking. The actual string comparison happens
 * at runtime so the on-chain code path survives production builds.
 */
export function isOnChainEnabled(): boolean {
  try {
    // Access via dynamic property to prevent static tree-shaking
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const env: any = import.meta;
    const pk = String(env.env?.VITE_HOUSE_PUB_KEY ?? HOUSE_PUB_KEY);
    const nft = String(env.env?.VITE_GAME_NFT_ID ?? GAME_NFT_ID);
    return pk.length > 0 && nft.length > 0;
  } catch {
    return false;
  }
}
