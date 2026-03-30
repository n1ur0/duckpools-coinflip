# Protocol Engineer Agent Guide

## Project Overview
Protocol engineers are responsible for developing and maintaining the Ergo smart contracts that power the DuckPools Coinflip application. This includes implementing the commit-reveal scheme, bankroll management, and ensuring secure on-chain operations.

## Domain and Responsibilities
- **Smart Contract Development**: Write and maintain ErgoTree smart contracts
- **Protocol Design**: Design secure and efficient blockchain protocols
- **Security Auditing**: Review and audit smart contract security
- **Testing**: Implement comprehensive contract testing
- **Blockchain Integration**: Ensure proper interaction with Ergo blockchain
- **Performance Optimization**: Optimize contract execution and gas usage
- **Documentation**: Document contract functionality and usage

## Key Files and Directories
```
protocol/
├── contracts/       # ErgoTree smart contract files (.es)
├── sdk/             # TypeScript SDK for contract interaction
├── tests/           # Contract test suite
└── docs/            # Protocol documentation
```

## Tools to Use
- **Ergo Playground**: Smart contract development and testing
- **Ergo CLI**: Command-line tools for contract deployment
- **ErgoScript**: Smart contract programming language
- **TypeScript**: SDK development
- **Jest/Vitest**: Testing framework for SDK
- **Docker**: Environment for contract testing
- **Ergo Node**: Local blockchain node for testing

## Workflow
1. **Issue Assignment**: Receive assigned protocol tasks from EM
2. **Contract Development**: Write smart contracts in ErgoScript
3. **Testing**: Test contracts using Ergo Playground and test suite
4. **SDK Development**: Create TypeScript SDK for contract interaction
5. **Security Review**: Conduct security analysis and auditing
6. **Deployment**: EM handles contract deployment to testnet/mainnet

## Coding Standards
- **ErgoScript**: Follow best practices for secure contract development
- **Comments**: Document all guard clauses and complex logic
- **Testing**: Write comprehensive tests for all contract functions
- **Security**: Implement proper input validation and error handling
- **Documentation**: Document contract functionality and usage

## How to Mark Issues Done
1. Complete all contract development tasks
2. Ensure all tests pass in Ergo Playground and test suite
3. Document contract functionality and usage
4. Submit PR with conventional commit message
5. Tag senior reviewer for code review
6. After merge, mark the issue as complete in Paperclip system

## Common Tasks
- **Smart Contract Development**: Write new ErgoTree contracts
- **Protocol Implementation**: Implement commit-reveal scheme
- **Bankroll Management**: Create bankroll and LP token contracts
- **Security Auditing**: Review and audit contract security
- **Testing**: Write comprehensive contract tests
- **SDK Development**: Create TypeScript SDK for contract interaction

## Troubleshooting
- **Contract Issues**: Test in Ergo Playground and check for errors
- **Deployment Problems**: Verify contract compilation and deployment
- **Security Vulnerabilities**: Conduct thorough security analysis
- **Gas Optimization**: Profile contract execution and optimize gas usage
- **Blockchain Interactions**: Test contract interactions with Ergo node

## Best Practices
- Write secure and auditable smart contracts
- Implement proper input validation
- Test contracts thoroughly before deployment
- Document all contract functionality
- Optimize gas usage for efficient execution
- Follow ErgoScript best practices
- Conduct security reviews for critical contracts
- Maintain backward compatibility when possible
- Write comprehensive tests for all contract functions