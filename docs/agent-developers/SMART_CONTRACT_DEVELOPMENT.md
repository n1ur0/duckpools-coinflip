# DuckPools CoinFlip - Smart Contract Development Guide

This guide provides detailed information about developing and working with DuckPools CoinFlip smart contracts.

## Contract Overview

The DuckPools CoinFlip system uses ErgoScript smart contracts implementing the commit-reveal pattern for fair gambling.

### Main Contracts

- `coinflip_v1.es`: Primary coinflip contract (current version)
- `coinflip_v2.es`: Alternative contract version
- `coinflip_v3.es`: Experimental contract version
- `dice_v1.es`: Dice game contract
- `plinko_v1.es`: Plinko game contract

## Contract Architecture

### Commit-Reveal Pattern

The system uses a commit-reveal pattern where:

1. **Commit Phase**: Player creates a bet by locking ERG in a contract box
   - Player generates a secret (8 bytes, random)
   - Player commits to a choice (heads=0, tails=1)
   - Commitment hash = blake2b256(secret || choice)

2. **Reveal Phase**: House reveals the outcome
   - House fetches current block hash from node
   - RNG outcome = (block_hash_bytes[0] % 2)
   - House proves fairness by using on-chain block hash
   - Contract verifies: blake2b256(secret || choice) == R6[CommitmentHash]

3. **Refund Phase**: Player timeout protection
   - If currentHeight > R10[TimeoutHeight], player can spend commit box
   - Player receives bet amount minus 2% fee
   - House reclaims game NFT

### Register Layout

| Register | Type | Content | Size |
|----------|------|---------|------|
| R4 | Coll[Byte] | House compressed public key | 33 bytes |
| R5 | Coll[Byte] | Player compressed public key | 33 bytes |
| R6 | Coll[Byte] | Commitment hash | 32 bytes |
| R7 | Int | Player choice (0=heads, 1=tails) | 4 bytes |
| R8 | Int | Timeout height | 4 bytes |
| R9 | Coll[Byte] | Player secret | 32 bytes |

## Development Setup

### Prerequisites

- Ergo CLI (version 5.0+)
- Java 11+
- Git

### Install Ergo CLI

```bash
# Download and install Ergo CLI
wget https://github.com/ergoplatform/ergo/releases/download/v5.0.11/ergo-5.0.11.zip
unzip ergo-5.0.11.zip
cd ergo-5.0.11

# Add to PATH
export PATH=$PATH:$(pwd)
```

### Contract Compilation

```bash
# Compile contract
ergo-cli compile coinflip_v1.es

# View compiled contract
ergo-cli print compiled_contract.json
```

### Contract Deployment

```bash
# Deploy contract (example)
./deploy_commit_reveal.sh

# Check deployment
ergo-cli get-boxes-by-token-id <NFT_ID>
```

## Contract Testing

### Unit Tests

```bash
# Run ErgoScript tests
ergo-cli test coinflip_commit_reveal_tests.rs

# Run specific test
ergo-cli test -t "commitment verification" coinflip_commit_reveal_tests.rs
```

### Test Contract

```ergoscript
# coinflip_commit_reveal_tests.rs example
#[test]
fn test_commitment_verification() {
    let secret = 12345678;
    let choice = 0; // heads
    let commitment = blake2b256(secret ++ choice);
    
    // Test commitment verification
    assert(blake2b256(secret ++ choice) == commitment);
}
```

## Contract Interaction

### Creating a Bet (Commit)

```python
from ergo_py_sdk import ErgoClient

# Connect to node
client = ErgoClient("http://localhost:9052", "api_key")

# Create commit transaction
tx = client.build_commit_tx(
    player_address="your_address",
    amount=1000000,  # 1 ERG
    choice=0,        # heads
    secret="random_32_byte_secret"
)

# Sign and submit
signed_tx = client.sign_tx(tx)
client.submit_tx(signed_tx)
```

### Revealing Bet (House)

```python
# Get current block hash
block_hash = client.get_block_hash(current_height)

# Generate outcome
outcome = block_hash[0] % 2  # 0=heads, 1=tails

# Build reveal transaction
reveal_tx = client.build_reveal_tx(
    bet_id="your_bet_id",
    outcome=outcome,
    block_hash=block_hash
)

# Sign and submit
signed_reveal_tx = client.sign_tx(reveal_tx)
client.submit_tx(signed_reveal_tx)
```

### Refunding Bet (Player)

```python
# Check if timeout has occurred
if current_height >= timeout_height:
    # Build refund transaction
    refund_tx = client.build_refund_tx(
        bet_id="your_bet_id"
    )
    
    # Sign and submit
    signed_refund_tx = client.sign_tx(refund_tx)
    client.submit_tx(signed_refund_tx)
```

## Contract Security

### Security Considerations

1. **Player Secret Visibility**: Player secret is stored in R9 register and visible on-chain
   - **Impact**: House can peek at player's choice before reveal
   - **Mitigation**: Use ZK-proof or commitment scheme where secret is not stored in box

2. **No Payout Amount Enforcement**: Contract doesn't verify payout amount during reveal
   - **Impact**: Malicious house could underpay player
   - **Mitigation**: Add contract guard for payout amount

3. **Block Hash Selection**: House chooses which block height/hash to use for RNG
   - **Impact**: House could grind blocks for favorable outcome
   - **Mitigation**: Add house commitment to block height or use oracle

4. **Only House Can Reveal**: Player cannot self-reveal if house goes offline
   - **Impact**: Player must wait for timeout to claim refund
   - **Mitigation**: Add player-initiated reveal path with on-chain RNG

### Security Best Practices

- Always validate inputs and outputs
- Use proper error handling
- Implement timeout protection
- Ensure NFT preservation during refunds
- Test edge cases thoroughly
- Consider third-party security audits

## Contract Optimization

### Performance Considerations

1. **Gas Optimization**: Minimize complex operations in contracts
2. **State Management**: Efficient use of registers
3. **Transaction Size**: Keep transactions as small as possible
4. **Validation Logic**: Place critical validations early in execution

### Optimization Techniques

```ergoscript
# Example: Efficient commitment verification
val commitmentOk: Boolean = blake2b256(R9[Secret] ++ R7[Choice]) == R6[CommitmentHash]

# Example: Early exit on failure
if (!commitmentOk) {
    false
}
```

## Contract Upgrades

### Versioning Strategy

- `coinflip_v1.es`: Initial implementation
- `coinflip_v2.es`: Security improvements
- `coinflip_v3.es`: Performance optimizations

### Upgrade Process

1. Deploy new contract version
2. Migrate existing bets (if necessary)
3. Update frontend and backend references
4. Monitor for issues

### Migration Example

```python
# Migrate bets from v1 to v2
def migrate_bets():
    # Get all pending bets
    pending_bets = get_pending_bets()
    
    # Migrate each bet
    for bet in pending_bets:
        migrate_bet(bet, "v2")
    
    # Update configuration
    update_contract_reference("coinflip_v2.es")
```

## Contract Documentation

### Documentation Standards

- Use clear and concise comments
- Document register purposes
- Explain guard clauses
- Include usage examples
- Document security considerations

### Example Documentation

```ergoscript
# coinflip_v1.es
# DuckPools CoinFlip Contract
# 
# This contract implements the commit-reveal pattern for fair coinflip games.
# 
# Registers:
# R4: House public key (33 bytes)
# R5: Player public key (33 bytes)
# R6: Commitment hash (32 bytes)
# R7: Player choice (0=heads, 1=tails)
# R8: Timeout height
# R9: Player secret (32 bytes)
# 
# Guard Clauses:
# - Commitment verification: blake2b256(R9[Secret] ++ R7[Choice]) == R6[CommitmentHash]
# - RNG: blake2b256(prevBlockHash ++ R9[Secret])[0] % 2
```

## Troubleshooting

### Common Issues

1. **Compilation Errors**: Check syntax and register layout
2. **Deployment Failures**: Verify node connection and wallet balance
3. **Transaction Failures**: Check input boxes and spending conditions
4. **Timeout Issues**: Verify block height calculations

### Debugging Tips

1. **Enable verbose logging**: Use `--verbose` flag with Ergo CLI
2. **Check node responses**: Monitor node API responses
3. **Review transaction details**: Examine transaction inputs and outputs
4. **Test with testnet**: Use testnet for development and testing

## Further Resources

- [ErgoScript Documentation](https://ergoplatform.org/en/ergoscript/)
- [Ergo CLI Documentation](https://github.com/ergoplatform/ergo/blob/master/docs/CLI.md)
- [DuckPools Architecture](../ARCHITECTURE.md)
- [Security Audit Preparation](smart-contracts/SECURITY_AUDIT_PREPARATION.md)

--- 
*Contract development requires careful consideration of security and performance. Always test thoroughly before deployment.*