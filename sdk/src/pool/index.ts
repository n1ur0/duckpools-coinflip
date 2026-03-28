/**
 * DuckPools SDK - Pool Module
 * Public API for liquidity pool operations
 *
 * MAT-15: Tokenized bankroll and liquidity pool
 */

export {
  BANKROLL_POOL_SCRIPT,
  WITHDRAW_REQUEST_SCRIPT,
  POOL_CONFIG,
  LP_TOKEN_INFO,
  calculatePricePerShare,
  calculateDepositShares,
  calculateWithdrawErg,
  calculateAPY,
} from './BankrollPool.js';
export type { PoolState, WithdrawalRequest } from './BankrollPool.js';

export { PoolManager } from './PoolManager.js';
export { HttpPoolClient, PoolFormatters } from './PoolClient.js';
export type {
  PoolConfig,
  PoolStateResponse,
  APYResponse,
  EstimateResponse,
  LPBalanceResponse,
  TxResponse,
  DepositRequest,
  WithdrawRequestCreate,
  WithdrawExecuteRequest,
  WithdrawCancelRequest,
  WithdrawalInfo,
  WithdrawalStatus,
  PoolClient,
} from './types.js';
