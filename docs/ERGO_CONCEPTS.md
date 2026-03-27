# Ergo Blockchain Concepts

This document explains Ergo-specific blockchain concepts that you need to understand for the DuckPools Coinflip project.

## Table of Contents

1. [UTXO Model](#utxo-model)
2. [ErgoTree](#ergotree)
3. [Registers (R4-R9)](#registers-r4-r9)
4. [Sigma Types and Serialization](#sigma-types-and-serialization)
5. [Box Serialization](#box-serialization)
6. [Address Encoding](#address-encoding)
7. [Ergo Node API](#ergo-node-api)
8. [Wallets (Nautilus)](#wallets-nautilus)

---

## UTXO Model

Ergo uses the **Unspent Transaction Output (UTXO)** model, similar to Bitcoin but enhanced with state.

### Key Concepts

**Transaction Output (Box)**:
- Contains: ERG (nanoERG), tokens, ErgoTree (script), registers (R4-R9)
- Represents "state" that can be spent by providing valid inputs

**Transaction Input**:
- References an unspent box ID
- Provides context data to satisfy the box's ErgoTree

**Ergo vs Bitcoin UTXO**:
| Feature | Bitcoin | Ergo |
|---------|---------|------|
| Scripts | Script (limited) | ErgoTree (Turing-complete) |
| State | No custom state | Registers (R4-R9) store arbitrary data |
| Complexity | O(1) spending | Complex spending conditions possible |
| Smart Contracts | None | Native smart contracts via ErgoTree |

### Example: Betting Box

A PendingBet box represents a committed bet:
- **Value**: Bet amount (e.g., 1 ERG = 1,000,000,000 nanoERG)
- **Tokens**: Coinflip NFT (identifies the game)
- **ErgoTree**: Script that governs how box can be spent
- **Registers**:
  - R4: Player's ErgoTree
  - R5: Commitment hash
  - R6: Bet choice (0/1)
  - R7: Player's secret
  - R8: Bet ID

### Box Lifecycle

```
Created by Tx1 (committed bet)
    ↓
Spent by Tx2 (reveal/settlement)
    ↓
New boxes created (payout to winner + house)
```

---

## ErgoTree

**ErgoTree** is Ergo's scripting language for smart contracts. It's a functional language that runs on the blockchain.

### Structure

ErgoTree is serialized byte code that represents a boolean predicate:
```
ErgoTree = SigmaProp  (can be spent if SigmaProp evaluates to true)
```

### SigmaProp

A **SigmaProp** is a proposition that can be:
- **P2PK**: Signature required from specific public key
- **P2SH**: Hash of script
- **P2S**: Full ErgoTree (complex contract)
- **Combined**: AND/OR logic with multiple conditions

### Example ErgoTree for P2PK

The simplest ErgoTree is a P2PK (Pay-to-Public-Key) script:

```
Context: Player must sign with their private key
ErgoTree: SigmaProp(ProveDlog(generatedPublicKey))
```

When you spend this box, you provide a signature that proves knowledge of the private key corresponding to the public key.

### PendingBet Contract ErgoTree

The PendingBet contract is more complex:

```ergoscript
// Simplified logic
{
  // Can be spent by house to reveal
  proveDlog(HousePK) && 
  (
    // Refund after timeout
    HEIGHT > timeoutHeight ||
    // Reveal path (if implemented)
    validRevealProof
  )
}
```

**What this enforces on-chain**:
- Only house can spend to reveal
- OR house cannot spend until timeout (refund for player)
- OR valid reveal proof allows spending

**What happens off-chain**:
- Bot monitors PendingBet boxes
- Calculates RNG after block confirmation
- Builds reveal transaction on behalf of house

### Compiling ErgoTree

```python
import sigma.ast as ast

# P2PK contract
pk = bytes.fromhex("03...")  # 33-byte compressed public key
tree = ast.SigmaProp(ast.ProveDlog(ast.Point(pk)))
```

### ErgoTree Length

ErgoTree can be large (400-700 bytes for complex contracts). This affects:
- **Address length**: Long ErgoTrees produce long P2S addresses (800+ characters)
- **API limits**: `/wallet/payment/send` may fail with long contracts
- **Solution**: Use `/wallet/transaction/send` with raw `ergoTree` field

---

## Registers (R4-R9)

Ergo boxes have **6 registers** (R4-R9) that store arbitrary state. Each register holds an **SValue** (Sigma value).

### Register Types

Each register can hold one SValue type:
- `Coll[Byte]`: Byte array (most common for hashes, IDs)
- `Int`: 32-bit signed integer
- `Long`: 64-bit signed integer
- `Coll[SValue]`: Array of Sigma values
- `Tuple`: Fixed-size collection of different types

### PendingBet Box Registers

| Register | Type | Content | Purpose |
|----------|------|---------|---------|
| R4 | Coll[Byte] | Player's ErgoTree (32 bytes) | Knows who placed bet |
| R5 | Coll[Byte] | Commitment hash (32 bytes) | Prevents front-running |
| R6 | Int | Bet choice (0=heads, 1=tails) | Player's prediction |
| R7 | Int | Player's secret (32-bit) | Revealed later |
| R8 | Coll[Byte] | Bet ID (32 bytes) | Unique identifier |
| R9 | (unused) | - | - |

### Register Keys in API

Different API endpoints use different key names:

| Endpoint | Register Key | Notes |
|----------|--------------|-------|
| `/wallet/payment/send` | `registers` | Simple payment endpoint |
| `/wallet/transaction/send` | `additionalRegisters` | Full tx builder endpoint |

**WARNING**: Mixing these up causes silent register drops.

---

## Sigma Types and Serialization

When sending register values to `/wallet/transaction/send`, they must be **Sigma-state encoded** (not raw hex).

### Type Tags

| Type | Tag | Format |
|------|-----|--------|
| IntConstant | 0x02 | `02` + VLQ(zigzag_i32) |
| LongConstant | 0x04 | `04` + VLQ(zigzag_i64) |
| Coll[Byte] | 0x0E | `0e` + `01` + VLQ(len) + bytes |

### VLQ Encoding

**Variable-Length Quantity** (VLQ) encodes integers in 7-bit groups with MSB continuation flag.

```
Value: 0x7F (127)  →  0x7F  (no continuation)
Value: 0x80 (128)  →  0x80 0x01  (continuation, then low 7 bits)
Value: 0x3FFF     →  0xFF 0x7F  (two bytes)
```

### ZigZag Encoding

Maps signed integers to unsigned for efficient VLQ:

```
ZigZag(n) = (n << 1) ^ (n >> 31)  // for i32
ZigZag(n) = (n << 1) ^ (n >> 63)  // for i64

Examples:
 0 → 0
 1 → 2
-1 → 1
 2 → 4
-2 → 3
```

### Serialization Examples

```python
def serialize_int(value: int) -> str:
    """Serialize IntConstant: 02 + VLQ(zigzag)"""
    zigzag = (value << 1) ^ (value >> 31)
    vlq = encode_vlq(zigzag)
    return f"02{vlq}"

def serialize_long(value: int) -> str:
    """Serialize LongConstant: 04 + VLQ(zigzag)"""
    zigzag = (value << 1) ^ (value >> 63)
    vlq = encode_vlq(zigzag)
    return f"04{vlq}"

def serialize_coll_byte(data: bytes) -> str:
    """Serialize Coll[Byte]: 0e + 01 + VLQ(len) + hex"""
    vlq_len = encode_vlq(len(data))
    return f"0e01{vlq_len}{data.hex()}"
```

### Specific Values

```
Int(0)    = "0200"
Int(1)    = "0202"
Int(10)   = "0214"
Int(-1)   = "0201"

Long(0)   = "0400"
Long(1)   = "0402"
Long(100) = "04c8"

Coll[Byte](32 bytes) = "0e0120" + 64 hex chars
```

### Why This Matters

If you send raw hex without type tags:
```json
{
  "additionalRegisters": {
    "R4": "deadbeef..."  // WRONG: Missing type tag!
  }
}
```

The node will accept it silently, but the register will contain garbage. Always use proper encoding.

Reference implementation: `off-chain-bot/sigma_serializer.py`

---

## Box Serialization

When you need to include specific boxes as transaction inputs, you may need to serialize an ErgoBox.

### Box ID vs Serialized Box

**Box ID**: 32-byte hash of box content (for queries)
```
GET /blockchain/box/byId/{box_id}
```

**Serialized Box**: Full ErgoBox bytes (for `inputsRaw` field)
```
POST /wallet/transaction/send
{
  "inputsRaw": ["<serialized_box_bytes>"]
}
```

### When to Use Each

| Scenario | Use | Method |
|----------|-----|--------|
| Query box data | Box ID | `GET /blockchain/box/byId/{id}` |
| Include as input | Serialized box | `inputsRaw` in tx |
| Let wallet select | Omit both | Auto-selection |

### Modern Approach: `rawInputBoxes`

On Lithos v6.0.3, you can use `rawInputBoxes` with box IDs (no serialization needed):

```json
{
  "rawInputBoxes": ["box_id_1", "box_id_2", "contract_box_id"]
}
```

This works for:
- Wallet P2PK boxes
- Contract boxes (PendingBet, GameState)

---

## Address Encoding

Ergo addresses are Base58-encoded representations of ErgoTree content.

### Address Prefixes

| Network | Prefix | Example |
|---------|--------|---------|
| Mainnet P2PK | `3` | `3Wz...` |
| Mainnet P2S | `9h` | `9hF...` |
| Testnet P2PK | `3W` | `3Wy...` |
| Testnet P2S | `3W` | `3W...` |

**IMPORTANT**: Both testnet AND default config use `addressPrefix=16`, so `3W` addresses ARE valid on testnet. Don't flag `3W` addresses as "mainnet" when node is testnet!

### Address Structure

```
Address = Base58(Prefix || Content || Checksum)
```

- **Prefix**: 1 byte (network + type)
- **Content**: Raw bytes (ErgoTree for P2S, PK for P2PK)
- **Checksum**: 4 bytes = `blake2b256(prefix || content)[:4]`

### Example: P2PK Address

```python
# Testnet P2PK
prefix = 0x11  # testnet + P2PK
content = 33-byte compressed public key
checksum = blake2b256(prefix + content)[:4]
address = Base58(prefix + content + checksum)  # e.g., "3WybUX..."
```

### Address to ErgoTree

```bash
GET /script/addressToBytes/{address}
```

Returns the raw ErgoTree bytes for the address.

---

## Ergo Node API

The Ergo node exposes a REST API for interacting with the blockchain.

### Common Endpoints

#### Node Info
```bash
GET /info
# Returns: {fullHeight, difficulty, isMining, ...}
```

#### Wallet Management
```bash
POST /wallet/unlock
# Body: {"pass": "password"}
# Headers: {"api_key": "hello"}

GET /wallet/status
# Returns: {isInitialized, isUnlocked, height, ...}

GET /wallet/addresses
# Returns: [{address}, ...]

GET /wallet/balances
# Returns: {height, balance, assets: {...}}
# NOTE: NOT [{nanoErgs: N}]!
```

#### Box Queries
```bash
GET /wallet/boxes/unspent
# Returns: Wallet's unspent boxes

GET /blockchain/box/unspent/byTokenId/{token_id}
# Returns: Unspent boxes containing specific token

GET /blockchain/box/byId/{box_id}
# Returns: Full box data with registers
```

#### Transactions
```bash
POST /wallet/transaction/send
# Body: {"requests": [...], "rawInputBoxes": [...], "additionalRegisters": {...}}
# Submits transaction to mempool

GET /blockchain/transaction/byId/{tx_id}
# Returns: Confirmed transaction

GET /transactions/unconfirmed/byTransactionId/{tx_id}
# Returns: Pending transaction (if not yet confirmed)
```

### Authentication

Most endpoints require `api_key` header:

```bash
curl -H "api_key: hello" http://localhost:9052/info
```

The key is verified against `ergo.conf` `apiKeyHash`:
```python
hash = blake2b256("hello").hexdigest()
# Must match: 324dcf027dd4a30a932c441f365a25e86b173defa4b8e58948253471b81b72cf
```

---

## Wallets (Nautilus)

**Nautilus** is the most popular Ergo browser wallet, supporting **EIP-12** protocol.

### EIP-12 Protocol

EIP-12 defines a standardized communication protocol between dApps and Ergo wallets.

### Connecting to Nautilus

```javascript
// Connect wallet
const isConnected = await window.ergoConnector.nautilus.connect();

// Get address
const address = await ergo.get_change_address();

// Get balance
const balance = await ergo.get_balance();
```

### Signing Transactions

```javascript
// Build transaction with FleetSDK
const txBuilder = new ErgoTxBuilder()
  .from(inputs)
  .to(outputs)
  .payMinFee();
const unsignedTx = txBuilder.build();

// Sign via Nautilus
const signedTx = await ergo.sign_tx(unsignedTx.toEIP12Object());

// Submit to node
const txId = await ergo.submit_tx(signedTx);
```

### User Experience

1. User clicks "Connect Wallet" in dApp
2. Nautilus popup: "Allow access to wallet?"
3. User approves
4. dApp can now request address, balance, and sign transactions
5. Each signature requires user approval (popup)

### Alternative Wallets

- **SAFEW**: Hardware wallet support
- **Minotaur**: Alternative desktop wallet
- **Mobile wallets**: Yoroi, Ergo Wallet App

---

## Summary

Understanding these concepts is critical for working with DuckPools Coinflip:

1. **UTXO Model**: Boxes represent state, transactions transform state
2. **ErgoTree**: Smart contract code that governs box spending
3. **Registers**: Custom state storage (R4-R9)
4. **Sigma Serialization**: Type tags + VLQ for register values
5. **Box Serialization**: Full box bytes for transaction inputs
6. **Address Encoding**: Base58(prefix + content + checksum)
7. **Node API**: REST endpoints for blockchain interaction
8. **Nautilus**: EIP-12 wallet for signing transactions

Always use the **node API** or **MCP tools** (ergo-mcp-server, deepwiki) to verify Ergo concepts - never guess!

---

## Further Reading

- [Ergo Platform Documentation](https://ergoplatform.org/docs/)
- [ErgoScript Reference](https://github.com/ergoplatform/ergoscript)
- [FleetSDK Documentation](https://fleet-sdk.github.io/)
- [EIP-12 Specification](https://github.com/ergoplatform/eips/blob/master/eip-0012.md)
