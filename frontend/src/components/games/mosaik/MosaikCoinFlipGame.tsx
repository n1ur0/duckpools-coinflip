/**
 * MosaikCoinFlipGame — DEPRECATED
 *
 * This component previously used sigma-rust WASM for on-chain transaction building.
 * The WASM module is not available, so this now re-exports CoinFlipGame which uses
 * Fleet SDK (the recommended approach per MAT-371).
 *
 * @deprecated Use CoinFlipGame from '../CoinFlipGame' instead.
 */
import CoinFlipGame from '../CoinFlipGame';
export default CoinFlipGame;
