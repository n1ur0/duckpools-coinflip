/**
 * UTXO Selector
 *
 * Selects and resolves UTXOs for transaction building.
 * Handles coin selection algorithm to minimize inputs while covering amount.
 */

import type { ErgoBox } from '../types/eip12';

export interface SelectedInputs {
  inputBoxIds: string[];
  totalValue: bigint;
}

/**
 * Select UTXOs to cover a target amount + fee.
 * Uses a greedy algorithm: pick largest UTXOs first.
 *
 * @param utxos - Available UTXOs (ErgoBox from Nautilus)
 * @param targetAmount - Amount needed (bet amount)
 * @param fee - Transaction fee
 * @returns Selected input box IDs and total value
 * @throws Error if UTXOs don't cover the target
 */
export function selectUtxos(
  utxos: ErgoBox[],
  targetAmount: bigint,
  fee: bigint
): SelectedInputs {
  if (utxos.length === 0) {
    throw new Error('No UTXOs available. Fund your wallet first.');
  }

  const totalNeeded = targetAmount + fee;

  // Sort UTXOs by value (descending) - greedy algorithm
  // ErgoBox.value is a string (nanoERG), need to parse to bigint
  const sortedUtxos = [...utxos].sort((a, b) =>
    Number(BigInt(b.value) - BigInt(a.value))
  );

  const selectedBoxIds: string[] = [];
  let totalValue = 0n;

  for (const utxo of sortedUtxos) {
    selectedBoxIds.push(utxo.boxId);
    totalValue += BigInt(utxo.value);

    // Stop when we have enough
    if (totalValue >= totalNeeded) {
      break;
    }
  }

  // Check if we have enough value
  if (totalValue < totalNeeded) {
    throw new Error(
      `Insufficient balance: need ${totalNeeded} nanoERG, have ${totalValue} nanoERG`
    );
  }

  return {
    inputBoxIds: selectedBoxIds,
    totalValue,
  };
}

/**
 * Calculate how many UTXOs are needed for a transaction.
 * Useful for pre-validation UI feedback.
 *
 * @param utxos - Available UTXOs
 * @param targetAmount - Amount needed (bet amount)
 * @param fee - Transaction fee
 * @returns Number of UTXOs needed, or null if insufficient
 */
export function estimateUtxosNeeded(
  utxos: ErgoBox[],
  targetAmount: bigint,
  fee: bigint
): number | null {
  try {
    const selected = selectUtxos(utxos, targetAmount, fee);
    return selected.inputBoxIds.length;
  } catch {
    return null;
  }
}
