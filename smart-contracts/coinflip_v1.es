/**
 * DuckPools Coinflip Game Contract v1
 *
 * LEGACY — DO NOT DEPLOY
 *
 * This contract uses ErgoScript 3.x syntax (fromSelf, R10, GroupElement in R4)
 * that is INCOMPATIBLE with Ergo 6.0.x (Lithos). It cannot compile on the
 * current node version.
 *
 * The CANONICAL contract is coinflip_v2_final.es (R4-R9, SELF, decodePoint).
 *
 * Original issues (documented for reference):
 *   - Uses `fromSelf` (removed in ErgoScript 4.0+, replaced by `SELF`)
 *   - Uses R10 register (unsupported in ErgoScript 6.0.3 Lithos, R4-R9 only)
 *   - Stores housePubKey as GroupElement in R4 (should be Coll[Byte] PK)
 *   - Player secret as Int in R8 (should be Coll[Byte] for proper hashing)
 *   - No reveal window constraint (house could grind blocks indefinitely)
 *   - No payout amount enforcement on reveal path
 *   - Truncated code in verification functions (corrupted file)
 *
 * Security trade-offs documented in original:
 *   - MAT-348: Player secret visible on-chain
 *   - MAT-336: No payout enforcement, block hash selection by house, house-only reveal
 *
 * See ARCHITECTURE.md and AUDIT_REPORT.md for full analysis.
 * See coinflip_v2_final.es for the current production contract.
 *
 * If v1 compatibility is ever needed, it must be rewritten using v2_final
 * patterns: SELF, R4-R9, decodePoint, Coll[Byte] PKs, reveal window.
 */

// This file is intentionally not compilable.
// It is preserved as documentation of the original v1 design decisions.
// See coinflip_v2_final.es for the working contract.
