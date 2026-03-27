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
} from './BankrollPool';
export type { PoolState, WithdrawalRequest } from './BankrollPool';

export { PoolManager } from './PoolManager';
export { HttpPoolClient, PoolFormatters } from './PoolClient';
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
} from './types';
