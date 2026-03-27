// API request/response types
export interface PlaceBetRequest {
  address: string;
  amount: string;       // nanoERG
  choice: number;       // 0 or 1
  commitment: string;   // hex hash
  secret: number;       // player secret
  betId: string;        // UUID
}

export interface PlaceBetResponse {
  success: boolean;
  txId?: string;
  boxId?: string;
  error?: string;
}

export interface BuildRevealTxRequest {
  boxId: string;
  playerSecret: number;
  playerChoice: number;
}

export interface BuildRevealTxResponse {
  success: boolean;
  tx?: Record<string, unknown>;
  error?: string;
}

export interface PoolDepositRequest {
  amount: string;  // nanoERG
}

export interface PoolWithdrawRequest {
  amount: string;  // nanoERG
}

export interface ApiInfo {
  name: string;
  version: string;
  status: string;
  endpoints: string[];
}

export interface HealthResponse {
  status: string;
  blockchain_connected: boolean;
  current_height: number;
}
