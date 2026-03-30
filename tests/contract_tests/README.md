# Contract Test Suite for DuckPools Coinflip

This directory contains comprehensive testing infrastructure for the DuckPools Coinflip smart contracts.

## Test Categories

The test suite includes multiple categories of tests:

### 1. Unit Tests (`test_coinflip_contract.py`)
- Basic contract logic testing
- Commitment calculation verification
- Reveal and refund scenarios
- Edge case handling
- Mock contract simulation

### 2. Sigma-Rust Integration Tests
- Contract compilation with sigma-rust compiler
- Compilation performance testing
- Output validation
- Error handling

### 3. Deployment Simulation Tests
- Mock deployment to Ergo devnet
- Transaction creation simulation
- Contract address generation
- Explorer verification

### 4. Performance Tests
- Compilation time measurements
- Gas estimation (mock)
- Memory usage analysis
- Execution time profiling

### 5. Edge Case Tests
- Different choice scenarios (heads/tails)
- Maximum/minimum parameter values
- Boundary condition testing
- Error handling verification

## Running Tests

### Prerequisites
- Python 3.8+
- pytest (`pip install pytest`)
- sigma-rust compiler (install from [Ergo Platform](https://github.com/ergoplatform/sigma-rust))

### Running All Tests
```bash
cd tests/contract_tests
python test_contract_harness.py
```

### Running Specific Test Categories
```bash
# Run unit tests only
python -m pytest test_coinflip_contract.py -v

# Run sigma-rust tests only (manual)
python test_contract_harness.py
```

### Test Results
Test results are saved to `contract_test_results.json` in the project root.

## Test Harness Features

The `test_contract_harness.py` script provides:
- Automated test execution
- Comprehensive result reporting
- Performance metrics
- Error handling and debugging
- JSON output for CI/CD integration
- Timestamped results

## Configuration

### Sigma-Rust Path
The test harness automatically detects sigma-rust in common locations:
- `/usr/local/bin/sigma-rust`
- `/opt/sigma-rust/bin/sigma-rust`
- `~/bin/sigma-rust`
- `~/.local/bin/sigma-rust`

If sigma-rust is installed in a different location, set the `SIGMA_RUST_PATH` environment variable:
```bash
export SIGMA_RUST_PATH="/path/to/sigma-rust"
```

### Test Parameters
Customize test behavior by modifying:
- Test cases in `test_coinflip_contract.py`
- Performance thresholds in `test_contract_harness.py`
- Deployment simulation parameters

## Integration with CI/CD

The test harness is designed for seamless integration with CI/CD pipelines:
- Exit codes indicate test success/failure
- JSON output format for easy parsing
- Comprehensive error reporting
- Performance regression detection

## Troubleshooting

### Common Issues

1. **sigma-rust not found**
   - Install sigma-rust: `cargo install sigma-rust`
   - Add to PATH or set `SIGMA_RUST_PATH` environment variable

2. **Compilation failures**
   - Check contract syntax in `smart-contracts/`
   - Verify sigma-rust version compatibility
   - Review error messages in test output

3. **Timeout errors**
   - Increase test timeout in `test_contract_harness.py`
   - Check for infinite loops in contract logic
   - Verify system resources

### Debugging Tips

- Run individual test files for focused debugging
- Use verbose output: `python -m pytest -v`
- Check `contract_test_results.json` for detailed results
- Review sigma-rust compiler output for syntax errors

## Contributing

To add new tests:
1. Add test functions to `test_coinflip_contract.py`
2. Update test harness categories if needed
3. Run the full test suite to verify
4. Update documentation as necessary

For deployment-related tests, modify `test_contract_harness.py` and ensure proper mock implementations.