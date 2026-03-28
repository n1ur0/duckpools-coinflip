/**
 * DuckPools Coinflip Service
 *
 * Builds unsigned EIP-12 transactions for all three coinflip phases
 * using Fleet SDK. The wallet (Nautilus) then signs and submits.
 *
 * Phases:
 *   1. COMMIT (buildPlaceBetTx)  — player locks ERG in contract box
 *   2. REVEAL (buildRevealTx)    — house spends box, pays winner via RNG
 *   3. REFUND (buildRefundTx)    — player reclaims after timeout
 *
 * Dependencies:
 *   - @fleet-sdk/core (TransactionBuilder, OutputBuilder, BoxSelector)
 *   - @fleet-sdk/serializer (SInt, SColl, SByte)
 *   - @fleet-sdk/crypto (blake2b256)
 *
 * Register layout MUST match coinflip_v2.es (compiled 2026-03-28):
 *   R4: Coll[Byte]  — house's compressed public key (33 bytes)
 *   R5: Coll[Byte]  — player's compressed public key (33 bytes)
 *   R6: Coll[Byte]  — blake2b256(secret || choice) — 32 bytes
 *   R7: Int         — player's choice: 0=heads, 1=tails
 *   R8: Int         — block height for timeout/refund
 *   R9: Coll[Byte]  — player's secret (raw bytes from crypto.getRandomValues)
 *
 * NOTE: coinflip_v2.es does NOT check for tokens. The NFT is optional
 * and only included for off-chain box indexing convenience.
 */

import {
  TransactionBuilder,
  OutputBuilder,
  BoxSelector,
  ErgoAddress,
  type Box,
  type Amount,
} from '@fleet-sdk/core';
import { SInt, SColl, SByte } from '@fleet-sdk/serializer';
import { blake2b256 } from '@fleet-sdk/crypto';
import {
  P2S_ADDRESS,
  CONTRACT_ERGO_TREE,
  HOUSE_PUB_KEY,
  HOUSE_ADDRESS,
  GAME_NFT_ID,
  TIMEOUT_DELTA,
  NODE_URL,
  isOnChainEnabled,
} from '../config/contract';

// ─── Types ────────────────────────────────────────────────────────

export interface PlaceBetParams {
  /** Player's wallet address (change address) */
  changeAddress: string;
  /** Bet amount in nanoERG */
  amountNanoErg: bigint;
  /** Player's compressed public key (33 bytes, hex) */
  playerPubKey: string;
  /** blake2b256(secret || choice) — 32 bytes hex */
  commitment: string;
  /** 0 = heads, 1 = tails */
  choice: number;
  /** Player's random secret (8 bytes) */
  secret: Uint8Array;
  /** Unique bet identifier (hex) */
  betId: string;
  /** Current blockchain height */
  currentHeight: number;
  /** Player's UTXOs (from wallet.getUtxos()) */
  utxos: Box<Amount>[];
}

export interface PlaceBetResult {
  /** The unsigned EIP-12 transaction ready for wallet.signTransaction() */
  unsignedTx: ReturnType<InstanceType<typeof TransactionBuilder>['build']> extends { toEIP12Object: () => infer R } ? R : never;
  /** The bet's timeout height */
  timeoutHeight: number;
}

// ─── Helpers ──────────────────────────────────────────────────────

function secretToHex(secret: Uint8Array): string {
  // Convert the raw secret bytes to a hex string for SColl(SByte, ...) encoding.
  // The contract (coinflip_v2.es) reads playerSecret as Coll[Byte] from R9
  // and uses it directly in blake2b256(playerSecret ++ Coll(choiceByte)).
  // This MUST match the bytes used in generateCommitment() in CoinFlipGame.tsx.
  return Array.from(secret).map(b => b.toString(16).padStart(2, '0')).join('');
}

// ─── Build Place Bet Transaction ─────────────────────────────────

/**
 * Build an unsigned EIP-12 transaction for placing a coinflip bet.
 *
 * This creates a PendingBetBox locked by the coinflip contract with:
 * - The bet amount in nanoERG
 * - Optional Game NFT as the first token (for off-chain indexing only)
 * - R4-R9 registers matching coinflip_v2.es layout
 *
 * The returned transaction must be passed to wallet.signTransaction()
 * which triggers the Nautilus popup, then wallet.submitTransaction()
 * to broadcast.
 *
 * @throws Error if on-chain flow is not enabled (contract not configured)
 * @throws Error if insufficient UTXOs to cover bet + fee
 */
export async function buildPlaceBetTx(params: PlaceBetParams): Promise<PlaceBetResult> {
  if (!isOnChainEnabled()) {
    throw new Error(
      'On-chain bet flow is not available. Configure VITE_CONTRACT_P2S_ADDRESS and VITE_HOUSE_PUB_KEY in .env.local.'
    );
  }

  const timeoutHeight = params.currentHeight + TIMEOUT_DELTA;

  // Build the contract output box with all registers
  // Register layout (matching coinflip_v2.es compiled 2026-03-28):
  //   R4: housePkBytes    (Coll[Byte])   — house's compressed public key
  //   R5: playerPkBytes   (Coll[Byte])   — player's compressed public key
  //   R6: commitmentHash  (Coll[Byte])   — blake2b256(secret || choice)
  //   R7: playerChoice    (Int)          — 0=heads, 1=tails
  //   R8: timeoutHeight   (Int)          — block height for timeout
  //   R9: playerSecret    (Coll[Byte])   — player's random secret (raw bytes)

  const contractAddress = ErgoAddress.fromBase58(P2S_ADDRESS);

  const betBox = new OutputBuilder(params.amountNanoErg, contractAddress, params.currentHeight);
  if (GAME_NFT_ID) {
    betBox.addNfts(GAME_NFT_ID);
  }
  betBox.setAdditionalRegisters({
    R4: SColl(SByte, HOUSE_PUB_KEY),                  // housePkBytes (Coll[Byte])
    R5: SColl(SByte, params.playerPubKey),             // playerPkBytes (Coll[Byte])
    R6: SColl(SByte, params.commitment),             // commitmentHash (Coll[Byte])
    R7: SInt(params.choice),                         // playerChoice (Int)
    R8: SInt(timeoutHeight),                         // timeoutHeight (Int)
    R9: SColl(SByte, secretToHex(params.secret)),    // playerSecret (Coll[Byte])
  });

  // Select UTXOs to cover bet amount + fee
  const target = { nanoErgs: params.amountNanoErg };
  const selectedInputs = new BoxSelector(params.utxos as Box<bigint>[]).select(target);

  if (selectedInputs.length === 0) {
    throw new Error(
      'Insufficient ERG balance to place bet. You need at least ' +
      `${(Number(params.amountNanoErg) / 1e9).toFixed(4)} ERG.`
    );
  }

  // Build the transaction
  const txBuilder = new TransactionBuilder(params.currentHeight)
    .from(selectedInputs as Box<Amount>[])
    .to(betBox)
    .sendChangeTo(params.changeAddress)
    .payMinFee();

  const unsignedTx = txBuilder.build();

  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    unsignedTx: unsignedTx.toEIP12Object() as any,
    timeoutHeight,
  };
}

// ─── Validation ───────────────────────────────────────────────────

/**
 * Validate that the commitment matches blake2b256(secret || choice).
 * This is a client-side sanity check before sending to the node.
 */
export function verifyCommitment(
  secret: Uint8Array,
  choice: number,
  commitment: string
): boolean {
  const buf = new Uint8Array(secret.length + 1);
  buf.set(secret, 0);
  buf[secret.length] = choice;
  const hash = blake2b256(buf);
  const hex = Array.from(hash).map(b => b.toString(16).padStart(2, '0')).join('');
  return hex === commitment.toLowerCase();
}

// ─── Types for Reveal & Refund ──────────────────────────────────

/** A commit box sitting at the P2S address (fetched from node or wallet) */
export interface CommitBox {
  /** Box ID (hex) */
  boxId: string;
  /** Box value in nanoERG */
  value: bigint;
  /** Creation height */
  creationHeight: number;
  /** Transaction ID that created this box */
  txId: string;
  /** Index of this box in the creating transaction's outputs */
  index: number;
  /** Tokens in this box (optional NFT for indexing) */
  tokens?: Array<{ tokenId: string; amount: bigint }>;
}

export interface RevealParams {
  /** The commit box to spend */
  commitBox: CommitBox;
  /** Player's P2PK address (for payout when player wins) */
  playerAddress: string;
  /** Current blockchain height */
  currentHeight: number;
  /** House UTXOs to pay the fee (house signs this tx) */
  houseUtxos: Box<Amount>[];
  /** House change address */
  houseChangeAddress: string;
}

export interface RevealResult {
  /** The unsigned EIP-12 transaction for house wallet.signTransaction() */
  unsignedTx: ReturnType<InstanceType<typeof TransactionBuilder>['build']> extends { toEIP12Object: () => infer R } ? R : never;
  /** Whether the player won (determined by on-chain RNG) */
  playerWins: boolean;
  /** Payout amount in nanoERG */
  payoutAmount: bigint;
  /** The block hash used as RNG seed */
  blockHash: string;
}

export interface RefundParams {
  /** The commit box to spend */
  commitBox: CommitBox;
  /** Player's UTXOs to pay the fee */
  playerUtxos: Box<Amount>[];
  /** Player's change address */
  changeAddress: string;
  /** Current blockchain height (must be >= timeoutHeight in R8) */
  currentHeight: number;
}

export interface RefundResult {
  /** The unsigned EIP-12 transaction for player wallet.signTransaction() */
  unsignedTx: ReturnType<InstanceType<typeof TransactionBuilder>['build']> extends { toEIP12Object: () => infer R } ? R : never;
  /** Refund amount in nanoERG (98% of bet) */
  refundAmount: bigint;
}

// ─── Node API Helpers ───────────────────────────────────────────

/**
 * Fetch the current block header from the Ergo node.
 * Returns the header ID (parent block hash) used as RNG seed.
 */
async function fetchBlockHeaderId(height: number): Promise<string> {
  const resp = await fetch(`${NODE_URL}/blocks/at/${height}`);
  if (!resp.ok) throw new Error(`Failed to fetch block at height ${height}: ${resp.status}`);
  const block = await resp.json();
  // block.headerId is the ID of the block AT this height.
  // CONTEXT.preHeader.parentId is the PREVIOUS block's ID.
  // So for RNG seed we need the header of the block BEFORE the reveal height.
  // The contract uses CONTEXT.preHeader.parentId which is the block at (height-1).
  return block.headerId as string;
}

/**
 * Fetch a box by its ID from the Ergo node.
 */
export async function fetchBoxById(boxId: string): Promise<CommitBox> {
  const resp = await fetch(`${NODE_URL}/utxo/byBoxId/${boxId}`);
  if (!resp.ok) throw new Error(`Failed to fetch box ${boxId}: ${resp.status}`);
  const box = await resp.json();
  return {
    boxId: box.boxId,
    value: BigInt(box.value),
    creationHeight: box.creationHeight,
    txId: box.transactionId,
    index: box.index,
    tokens: box.assets?.map((a: { tokenId: string; amount: string }) => ({
      tokenId: a.tokenId,
      amount: BigInt(a.amount),
    })),
  };
}

/**
 * Fetch unspent boxes locked by the coinflip contract.
 * Used to find pending commit boxes.
 */
export async function fetchContractBoxes(limit = 50): Promise<CommitBox[]> {
  const encodedTree = encodeURIComponent(CONTRACT_ERGO_TREE);
  const resp = await fetch(
    `${NODE_URL}/utxo/boxes/unspent/${encodedTree}?limit=${limit}&orderBy=creationHeight&order=desc`
  );
  if (!resp.ok) throw new Error(`Failed to fetch contract boxes: ${resp.status}`);
  const boxes = await resp.json();
  return boxes.items.map((b: { boxId: string; value: number; creationHeight: number; transactionId: string; index: number; assets?: Array<{ tokenId: string; amount: string }> }) => ({
    boxId: b.boxId,
    value: BigInt(b.value),
    creationHeight: b.creationHeight,
    txId: b.transactionId,
    index: b.index,
    tokens: b.assets?.map((a: { tokenId: string; amount: string }) => ({
      tokenId: a.tokenId,
      amount: BigInt(a.amount),
    })),
  }));
}

// ─── Build Reveal Transaction ───────────────────────────────────

/**
 * Build an unsigned EIP-12 transaction for the house to reveal a coinflip.
 *
 * The contract (coinflip_v2.es) requires:
 * - houseProp: house's SigmaProp proof (house wallet signs)
 * - commitmentOk: blake2b256(R9_secret ++ R7_choice) == R6_commitment (verified on-chain)
 * - If player wins: OUTPUTS(0) to player with >= winPayout (bet * 97/50)
 * - If house wins: OUTPUTS(0) to house with >= betAmount
 *
 * RNG: blake2b256(prevBlockHash ++ playerSecret)[0] % 2
 * The prevBlockHash comes from CONTEXT.preHeader.parentId.
 *
 * @throws Error if on-chain flow not enabled or house address not configured
 */
export async function buildRevealTx(params: RevealParams): Promise<RevealResult> {
  if (!isOnChainEnabled()) {
    throw new Error('On-chain flow is not available.');
  }
  if (!HOUSE_ADDRESS) {
    throw new Error('VITE_HOUSE_ADDRESS not configured. Cannot build reveal tx.');
  }

  const { commitBox, playerAddress, currentHeight, houseUtxos, houseChangeAddress } = params;
  const betAmount = commitBox.value;

  // On-chain value calculations (matching coinflip_v2.es lines 53-57):
  //   winPayout    = betAmount * 97 / 50  (1.94x)
  //   refundAmount = betAmount - betAmount / 50  (0.98x)
  const winPayout = (betAmount * 97n) / 50n;

  // Fetch the block header at (currentHeight - 1) for the RNG seed.
  // CONTEXT.preHeader.parentId = header of the block at (height - 1).
  const prevBlockHeaderId = await fetchBlockHeaderId(currentHeight - 1);

  // We need the player's secret from the commit box to compute the RNG.
  // The commit box has R9 = playerSecret (Coll[Byte]).
  // Fetch the full box with registers from the node.
  const boxResp = await fetch(`${NODE_URL}/utxo/byBoxId/${commitBox.boxId}`);
  const boxData = await boxResp.json();
  const registers = boxData.additionalRegisters as Record<string, string>;
  const r9Encoded = registers?.R9;
  if (!r9Encoded) {
    throw new Error('Commit box missing R9 (playerSecret) register.');
  }

  // Decode R9: Coll[Byte] encoding from node API.
  // Format: "0e 01 VLQ(len) data" or "0e VLQ(len) data"
  const r9Bytes = decodeCollByte(r9Encoded);

  // Decode R7: Int (player choice)
  const r7Encoded = registers?.R7;
  if (!r7Encoded) {
    throw new Error('Commit box missing R7 (playerChoice) register.');
  }
  const playerChoice = decodeInt(r7Encoded);

  // Simulate the on-chain RNG to determine outcome.
  // Contract: blake2b256(prevBlockHash ++ playerSecret)[0] % 2
  const prevBlockBytes = hexToBytes(prevBlockHeaderId);
  const rngInput = new Uint8Array(prevBlockBytes.length + r9Bytes.length);
  rngInput.set(prevBlockBytes, 0);
  rngInput.set(r9Bytes, prevBlockBytes.length);
  const rngHash = blake2b256(rngInput);
  const flipResult = rngHash[0] % 2;
  const playerWins = flipResult === playerChoice;

  // Build the appropriate output based on outcome.
  const outputAddress = playerWins ? playerAddress : HOUSE_ADDRESS;
  const outputValue = playerWins ? winPayout : betAmount;

  const payoutBox = new OutputBuilder(outputValue, ErgoAddress.fromBase58(outputAddress), currentHeight);

  // If the commit box had tokens (NFT), pass them to the first output.
  if (commitBox.tokens && commitBox.tokens.length > 0) {
    for (const token of commitBox.tokens) {
      payoutBox.addTokens({ tokenId: token.tokenId, amount: token.amount });
    }
  }

  // Build the transaction: spend commit box, create payout box.
  // The commit box is a P2S box — it doesn't need a signing wallet input for data inputs.
  // But Fleet SDK's TransactionBuilder needs it as an input.
  // The house's UTXOs are needed to pay the transaction fee.
  const commitInput = {
    boxId: commitBox.boxId,
    value: commitBox.value,
    ergoTree: CONTRACT_ERGO_TREE,
    creationHeight: commitBox.creationHeight,
    assets: commitBox.tokens?.map(t => ({ tokenId: t.tokenId, amount: t.amount as bigint })) || [],
    additionalRegisters: {} as Record<string, unknown>,
    transactionId: commitBox.txId,
    index: commitBox.index,
  };

  // Select house UTXOs for the fee
  const feeTarget = { nanoErgs: 1_000_000n }; // minimum fee
  const selectedHouseInputs = new BoxSelector(houseUtxos as Box<bigint>[]).select(feeTarget);

  if (selectedHouseInputs.length === 0) {
    throw new Error('House wallet has no UTXOs to pay the reveal transaction fee.');
  }

  const txBuilder = new TransactionBuilder(currentHeight)
    .from([commitInput as Box<Amount>, ...selectedHouseInputs] as Box<Amount>[])
    .to(payoutBox)
    .sendChangeTo(houseChangeAddress)
    .payMinFee();

  const unsignedTx = txBuilder.build();

  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    unsignedTx: unsignedTx.toEIP12Object() as any,
    playerWins,
    payoutAmount: outputValue,
    blockHash: prevBlockHeaderId,
  };
}

// ─── Build Refund Transaction ───────────────────────────────────

/**
 * Build an unsigned EIP-12 transaction for a player to refund their bet.
 *
 * The contract (coinflip_v2.es) requires:
 * - HEIGHT >= timeoutHeight (R8)
 * - playerProp: player's SigmaProp proof (player wallet signs)
 * - OUTPUTS(0) to player with >= refundAmount (bet - bet/50 = 98%)
 *
 * The player calls this via wallet.signTransaction() + wallet.submitTransaction()
 * after the timeout height has passed.
 *
 * @throws Error if current height < timeout height
 * @throws Error if player has no UTXOs for the fee
 */
export async function buildRefundTx(params: RefundParams): Promise<RefundResult> {
  if (!isOnChainEnabled()) {
    throw new Error('On-chain flow is not available.');
  }

  const { commitBox, playerUtxos, changeAddress, currentHeight } = params;
  const betAmount = commitBox.value;

  // Refund amount: betAmount - betAmount / 50 (98% of bet, 2% fee)
  // Matching coinflip_v2.es line 57: val refundAmount = betAmount - betAmount / 50L
  const refundAmount = betAmount - betAmount / 50n;

  // Build the commit box as an input for Fleet SDK
  const commitInput = {
    boxId: commitBox.boxId,
    value: commitBox.value,
    ergoTree: CONTRACT_ERGO_TREE,
    creationHeight: commitBox.creationHeight,
    assets: commitBox.tokens?.map(t => ({ tokenId: t.tokenId, amount: t.amount as bigint })) || [],
    additionalRegisters: {} as Record<string, unknown>,
    transactionId: commitBox.txId,
    index: commitBox.index,
  };

  // Build the refund output box: goes to the player
  const refundBox = new OutputBuilder(
    refundAmount,
    ErgoAddress.fromBase58(changeAddress),
    currentHeight
  );

  // If the commit box had tokens (NFT), pass them to the refund output.
  if (commitBox.tokens && commitBox.tokens.length > 0) {
    for (const token of commitBox.tokens) {
      refundBox.addTokens({ tokenId: token.tokenId, amount: token.amount });
    }
  }

  // Select player UTXOs for the transaction fee
  const feeTarget = { nanoErgs: 1_000_000n };
  const selectedInputs = new BoxSelector(playerUtxos as Box<bigint>[]).select(feeTarget);

  if (selectedInputs.length === 0) {
    throw new Error('Insufficient UTXOs to pay the refund transaction fee.');
  }

  const txBuilder = new TransactionBuilder(currentHeight)
    .from([commitInput as Box<Amount>, ...selectedInputs] as Box<Amount>[])
    .to(refundBox)
    .sendChangeTo(changeAddress)
    .payMinFee();

  const unsignedTx = txBuilder.build();

  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    unsignedTx: unsignedTx.toEIP12Object() as any,
    refundAmount,
  };
}

// ─── Sigma Encoding Helpers ─────────────────────────────────────

/**
 * Decode a Coll[Byte] register value from the Ergo node API.
 * Node API formats:
 *   (A) "0e 01 VLQ(len) data" — with SByte 0x01 tag
 *   (B) "0e VLQ(len) data"   — without SByte tag
 */
function decodeCollByte(encoded: string): Uint8Array {
  const bytes = hexToBytes(encoded);
  // bytes[0] = 0x0e (Coll constant), bytes[1] = element type
  let offset = 2; // skip 0x0e + element type byte
  if (bytes[1] === 0x01) {
    // SByte element type — offset stays at 2 (type byte is separate from length)
    offset = 2;
  }
  // Decode VLQ length
  let len = 0;
  let shift = 0;
  while (offset < bytes.length) {
    const b = bytes[offset++];
    len |= (b & 0x7f) << shift;
    if ((b & 0x80) === 0) break;
    shift += 7;
  }
  // Extract the raw bytes
  return bytes.slice(offset, offset + len);
}

/**
 * Decode an Int register value from the Ergo node API.
 * Int encoding: 0x02 + VLQ(zigzag_i32)
 */
function decodeInt(encoded: string): number {
  const bytes = hexToBytes(encoded);
  // bytes[0] = 0x02 (Int constant)
  // Decode zigzag VLQ starting at byte 1
  let value = 0;
  let shift = 0;
  for (let i = 1; i < bytes.length; i++) {
    const b = bytes[i];
    value |= (b & 0x7f) << shift;
    if ((b & 0x80) === 0) break;
    shift += 7;
  }
  // Zigzag decode: (n >>> 1) ^ -(n & 1)
  return (value >>> 1) ^ -(value & 1);
}

/** Convert a hex string to a Uint8Array. */
function hexToBytes(hex: string): Uint8Array {
  const clean = hex.replace(/^0x/, '');
  const bytes = new Uint8Array(clean.length / 2);
  for (let i = 0; i < clean.length; i += 2) {
    bytes[i / 2] = parseInt(clean.substring(i, i + 2), 16);
  }
  return bytes;
}