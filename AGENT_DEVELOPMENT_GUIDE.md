# DuckPools CoinFlip - Agent Development Guide

## Overview

This guide provides comprehensive instructions for agent developers working on the DuckPools CoinFlip project. The project is a proof-of-concept decentralized gambling application built on the Ergo blockchain using the commit-reveal pattern.

## Agent Development Fundamentals

### Core Agent Roles

1. **Smart Contract Developer Agent**: Develop and maintain ErgoScript smart contracts
2. **Backend Developer Agent**: Implement API endpoints and off-chain services
3. **Frontend Developer Agent**: Build user interface components
4. **DevOps Engineer Agent**: Manage deployment and infrastructure
5. **Security Auditor Agent**: Conduct security audits and vulnerability assessments
6. **Testing Agent**: Execute automated tests and quality assurance

### Agent Development Environment

#### Prerequisites
- **Paperclip Platform**: Access to Hermes A2A communication
- **Local Development**: Docker, Node.js, Python 3.9+
- **Ergo Node**: Local testnet node (http://localhost:9052)
- **Knowledge Broker**: Access to http://127.0.0.1:9100

#### Local Setup
```bash
# Clone repository
git clone https://github.com/duckpools/duckpools-coinflip.git
cd duckpools-coinflip

# Start services
docker-compose up -d
```

## Agent Development Workflow

### Task Assignment and Management

1. **Check Assigned Issues**: 
   ```bash
   curl -s "http://127.0.0.1:3100/api/companies/c3a27363-6930-45ad-b684-a6116c0f3313/issues?assigneeAgentId=YOUR_AGENT_ID" | jq .
   ```

2. **Filter Active Tasks**: Work only on issues with status "todo" (ignore "done" and "cancelled")

3. **Claim Workspaces**: Use assigned workspace IDs for execution
   ```bash
   # Checkout workspace
   paperclip checkout WORKSPACE_ID
   ```

### A2A Communication Protocols

#### Peer Communication
```bash
# Ask a peer for help
a2a ask "Agent Name" "I'm working on ISSUE_ID and need help with..."

# Send progress update
a2a send "EM - DeFi & Bankroll" "Working on ISSUE_ID: Current status and next steps"

# Broadcast important announcements
a2a broadcast "Critical update: System maintenance scheduled for..."
```

#### Knowledge Synchronization
```bash
# Before starting any task
curl -s -X POST "http://127.0.0.1:9100/api/discover" -H "Content-Type: application/json" -d '{"query":"<task keywords>","agent_id":"YOUR_AGENT_ID"}'

# After completing work
curl -s -X POST "http://127.0.0.1:9100/api/report" -H "Content-Type: application/json" -d '{"agent_id":"YOUR_AGENT_ID","summary":"[solved] <what you built/fixed>","tags":["<component>","<feature>","<integration-point>"]}'
```

### Development Process

1. **Read Issue Details**: Understand requirements and acceptance criteria
2. **Checkout Workspace**: Use assigned workspace for execution
3. **Perform Knowledge Sync**: Query broker for relevant context
4. **Execute Work**: Implement solution in project directory
5. **Test Thoroughly**: Run all relevant tests
6. **Mark Complete**: Update issue status
7. **Report Results**: Post comments and notify stakeholders

## Smart Contract Development for Agents

### Contract Structure
- `smart-contracts/coinflip_v1.es`: Main smart contract implementation
- Registers: R4-R9 with specific types and purposes

### Key Registers
| Register | Type | Content |
|----------|------|---------|
| R4 | Coll[Byte] | House compressed public key |
| R5 | Coll[Byte] | Player compressed public key |
| R6 | Coll[Byte] | Commitment hash (blake2b256(secret || choice)) |
| R7 | Int | Player choice (0=heads, 1=tails) |
| R8 | Int | Timeout height for refund |
| R9 | Coll[Byte] | Player secret |

### Development Steps
1. Write ErgoScript code in `smart-contracts/coinflip_v1.es`
2. Test compilation: `ergo-cli compile coinflip_v1.es`
3. Deploy to testnet
4. Update contract address in backend configuration
5. Test end-to-end flow

### Agent-Specific Testing
```python
# Test contract compilation
def test_contract_compilation():
    result = subprocess.run(['ergo-cli', 'compile', 'coinflip_v1.es'], capture_output=True)
    assert result.returncode == 0, f"Compilation failed: {result.stderr}"

# Test register layout
def test_register_layout():
    # Verify register types and constraints
    pass
```

## Backend Development for Agents

### API Endpoints
- `POST /place-bet`: Create new bet
- `GET /history/{address}`: Get player bet history
- `GET /player/stats/{address}`: Get player statistics
- `GET /player/comp/{address}`: Get player compensation
- `GET /leaderboard`: Get game leaderboard
- `GET /bets/expired`: List expired bets
- `POST /bets/{bet_id}/refund-record`: Record refund

### Database Schema
- `_bets`: Stores bet information (status, amount, choice, etc.)
- `_players`: Player statistics and history
- `_config`: System configuration

### Agent-Specific Security
```python
# Implement proper authentication for bot endpoints
@app.post("/bot/execute")
async def execute_bot_action(request: BotRequest, api_key: str = Header(...)):
    if api_key != os.getenv("BOT_API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validate bot action
    validate_bot_action(request.action)
    
    # Execute action
    result = await execute_bot_task(request.action, request.parameters)
    return {"status": "success", "result": result}
```

## Frontend Development for Agents

### Key Components
- `pages/CoinflipPage.tsx`: Coinflip game UI
- `pages/DicePage.tsx`: Dice game UI
- `components/BetForm.tsx`: Input form for bet amount and choice
- `components/Leaderboard.tsx`: Game leaderboard display
- `components/GameHistory.tsx`: Player bet history
- `contexts/WalletContext.tsx`: Wallet connection and signing
- `wallet/useErgoWallet.ts`: Ergo wallet hook (EIP-12)
- `wallet/useWalletManager.ts`: Wallet adapter management
- `stores/gameStore.ts`, `stores/betStore.ts`: Zustand state stores

### Wallet Integration
- Uses `ergo-connector` (EIP-12 standard) via Nautilus wallet
- Implement `connect()`, `get_balance()`, `signTransaction()`, `submitTransaction()`
- Handle wallet connection errors and user feedback
- Backend wallet mode available for automated house operations

### State Management
- Use Zustand for global state
- Manage wallet connection status
- Track game state and bet history

## Testing Procedures for Agents

### Unit Testing
```python
# Backend unit tests
def test_place_bet_endpoint():
    # Test bet placement with valid parameters
    response = client.post("/place-bet", json={"amount": 1000, "choice": 0})
    assert response.status_code == 200
    assert "bet_id" in response.json()

# Frontend unit tests
test('renders bet form correctly', () => {
  render(<BetForm />);
  expect(screen.getByLabelText('Bet Amount')).toBeInTheDocument();
});
```

### Integration Testing
- Test API endpoints with real database
- Verify wallet integration
- Test contract deployment and interaction
- Validate end-to-end game flow

### E2E Testing
- Use Playwright for browser automation
- Test complete user journeys
- Verify wallet connections and transactions
- Test error handling and edge cases

## Deployment for Agents

### Local Development
- Use Docker Compose for easy setup
- Run `docker-compose up -d` to start all services
- Access frontend at http://localhost:3000
- Access backend API at http://localhost:8000

### Production Deployment
- Use Docker containers for all services
- Configure proper environment variables
- Set up monitoring and logging
- Implement security hardening (CSP, headers)

### Environment Variables
- `NODE_URL`: Ergo node endpoint
- `VITE_NODE_URL`: Node URL for frontend
- `NODE_API_KEY`: API key for node
- `BOT_API_KEY`: API key for bot endpoints
- `DATABASE_URL`: PostgreSQL connection string

## Agent Best Practices

### Security
- Follow the project's security guidelines
- Document all trust assumptions
- Test for common vulnerabilities
- Keep dependencies up to date

### Code Quality
- Follow PEP 8 (Python) and ESLint (TypeScript) guidelines
- Write clear, maintainable code
- Add proper documentation
- Use meaningful variable and function names

### Performance
- Optimize database queries
- Minimize API calls
- Cache frequently accessed data
- Monitor application performance

### Collaboration
- Communicate clearly with team members
- Document decisions and trade-offs
- Share knowledge and best practices
- Help onboard new team members

## Agent Troubleshooting

### Common Issues

1. **Ergo Node Not Running**
   ```bash
   # Check node logs
   docker-compose logs ergo
   
   # Verify node configuration
   curl -s http://localhost:9052/info
   ```

2. **Database Connection Issues**
   ```bash
   # Check PostgreSQL logs
   docker-compose logs postgres
   
   # Verify database credentials
   psql -h localhost -U user -d duckpools -c "SELECT 1"
   ```

3. **Frontend Build Failures**
   ```bash
   # Clear npm cache
   npm cache clean --force
   
   # Reinstall dependencies
   npm install
   
   # Check TypeScript configuration
   tsc --noEmit
   ```

4. **Smart Contract Compilation Errors**
   ```bash
   # Verify ErgoScript syntax
   ergo-cli compile coinflip_v1.es
   
   # Check register layout and types
   ergo-cli analyze coinflip_v1.es
   ```

5. **A2A Communication Failures**
   ```bash
   # Check Hermes sidecar status
   pkill -9 -f "hermes chat"
   bash ~/.paperclip/hermes-a2a/scripts/start-all-sidecars.sh
   
   # Verify broker connectivity
   curl -s http://127.0.0.1:9100/health
   ```

### Error Recovery Procedures

1. **Workspace Corruption**
   ```bash
   # Clean workspace
   paperclip cleanup WORKSPACE_ID
   
   # Recreate workspace
   paperclip create WORKSPACE_ID
   ```

2. **Test Failures**
   ```python
   # Run specific test suite
   pytest tests/ -k "test_contract"
   
   # Generate test report
   pytest tests/ --junitxml=report.xml
   ```

3. **Deployment Issues**
   ```bash
   # Rollback deployment
   docker-compose down
   
   # Rebuild containers
   docker-compose build --no-cache
   docker-compose up -d
   ```

## Agent Resources

- **Agent Quick Reference**: [AGENTS.md](AGENTS.md) -- hierarchy, git workflow, coding conventions
- **Project Documentation**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Security Guidelines**: [SECURITY.md](SECURITY.md)
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Docker Guide**: [DOCKER.md](DOCKER.md)
- **Knowledge Broker**: http://127.0.0.1:9100
- **Paperclip API**: http://127.0.0.1:3100/api

## Agent Contact Information

For questions or support, contact:
- Project Manager: [EM - DeFi & Bankroll](mailto:em@duckpools.com)
- Technical Lead: [DeFi Architect Sr](mailto:lead@duckpools.com)
- Development Team: [Slack Channel](https://duckpools.slack.com)
- Hermes Broker: [Knowledge Broker](http://127.0.0.1:9100)

---

*This documentation is a living document and should be updated as the project evolves. Agents should regularly check for updates and contribute to improving this guide.*