export interface SimpleOutput {
  address: string;
  value: string;  // nanoERG
  tokens?: Array<{ tokenId: string; amount: string }>;
  registers?: Record<string, string>;
}

export async function buildSimpleSelfTransfer(
  _inputs: any[],
  _changeAddress: string,
  _fee: number = 1000000
): Promise<any> {
  throw new Error('buildSimpleSelfTransfer not implemented - use FleetSDK directly');
}

export async function buildPaymentTx(
  _outputs: SimpleOutput[],
  _changeAddress: string,
): Promise<any> {
  throw new Error('buildPaymentTx not implemented - use FleetSDK directly');
}

export async function buildBetCommitTx(
  _betAmount: string,
  _choice: number,
  _commitment: string,
  _secret: number,
  _betId: string,
  _playerErgoTree: string,
  _changeAddress: string,
  _pendingBetScript: string,
  _nftId: string,
): Promise<any> {
  throw new Error('buildBetCommitTx not implemented - use FleetSDK directly');
}

export function selectUtxos(utxos: any[], targetNanoErg: string): any[] {
  // Simple greedy UTXO selection
  const target = BigInt(targetNanoErg);
  let accumulated = 0n;
  const selected: any[] = [];
  for (const utxo of utxos) {
    selected.push(utxo);
    accumulated += BigInt(utxo.value || utxo.nanoErgs || 0);
    if (accumulated >= target) break;
  }
  return selected;
}
