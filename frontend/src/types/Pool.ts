export interface PoolState {
  totalLiquidity: string;   // Total liquidity in the pool (nanoERG)
  totalBets: number;       // Total number of bets placed
  houseEdge: number;       // House edge percentage
  totalVolume: string;     // Total betting volume (nanoERG)
  totalPayout: string;     // Total amount paid out (nanoERG)
  activeDeposits: number;  // Number of active deposits
}