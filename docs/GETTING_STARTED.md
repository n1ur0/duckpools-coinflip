# Getting Started Guide

Welcome to DuckPools Coinflip! This guide will help you set up the development environment and run the project locally.

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Java     | 11+    | Run Ergo node (ergo.jar) |
| Python   | 3.12+  | Backend API, off-chain bot |
| Node.js  | 18+    | Frontend build tools |
| npm      | 9+     | Package manager for frontend |

### Install on macOS

```bash
# Java (via Homebrew)
brew install openjdk@11

# Python (via pyenv recommended)
brew install pyenv
pyenv install 3.12.0
pyenv global 3.12.0

# Node.js (via nvm recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18
```

### Install on Linux (Ubuntu/Debian)

```bash
# Java
sudo apt update
sudo apt install -y openjdk-11-jdk

# Python
sudo apt install -y python3.12 python3.12-venv python3-pip

# Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

## Project Structure

```
duckpools-coinflip/
├── backend/           # FastAPI server
│   ├── api_server.py
│   ├── services/
│   └── .env
├── frontend/          # React app
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── utils/
│   └── package.json
├── off-chain-bot/     # Bet resolution bot
│   ├── main.py
│   └── sigma_serializer.py
└── sdk/              # TypeScript SDK
    └── index.ts
```

## Step 1: Ergo Node Setup

### Clone and Build Ergo Node

```bash
cd ~/Documents/git
git clone https://github.com/ergoplatform/ergo.git
cd ergo
git checkout v6.0.3
# Apply Lithos PR #2252 changes if needed
sbt clean assembly
```

### Configure Ergo Node

Create `ergo.conf` in your node directory:

```conf
ergo {
  networkType = "testnet"
  
  node {
    mining = true
    useExternalMiner = false
  }
}

scorex {
  restApi {
    bindAddress = "0.0.0.0:9052"
    apiKeyHash = "324dcf027dd4a30a932c441f365a25e86b173defa4b8e58948253471b81b72cf"
  }
}
```

**Note**: The `apiKeyHash` is `blake2b256("hello")`. This matches the `API_KEY=hello` in your `.env` files.

### Start the Node

```bash
cd ~/Documents/git/ergo-testnet/
java -jar ergo.jar -c ergo.conf
```

### Verify Node is Running

```bash
# Check node height
curl -s http://localhost:9052/info | jq '.fullHeight'

# Unlock wallet (replace with your password)
curl -s -X POST http://localhost:9052/wallet/unlock \
  -H "Content-Type: application/json" \
  -H "api_key: hello" \
  -d '{"pass":"1231231230"}'

# Check wallet status
curl -s http://localhost:9052/wallet/status -H "api_key: hello" | jq .
```

### Fund Your Wallet (Testnet)

Visit the Ergo testnet faucet:
https://testnet.ergoplatform.com/faucet

## Step 2: Backend API Setup

### Install Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configure Environment

Create `.env` file in `backend/` directory:

```env
NODE_URL=http://localhost:9052
COINFLIP_NFT_ID=b0a111d06ccf32fa10c6b36f615233212bc725d8707575ccacc0c02267b27332
HOUSE_ADDRESS=3WybUXMjv722ebGYh69bQGQMsb7yb3LJ1EWqPp22UDH2RFNKgcRi
CORS_ORIGINS_STR=http://localhost:3000,http://localhost:3001
LOG_LEVEL=INFO
```

**Important**: After deploying the contract, update `COINFLIP_NFT_ID` with the actual minted NFT ID.

### Start the Backend

```bash
cd backend
source venv/bin/activate
python api_server.py
```

Backend will run on `http://localhost:8000`.

### Verify Backend Health

```bash
curl -s http://localhost:8000/health | jq .
```

## Step 3: Frontend Setup

### Install Dependencies

```bash
cd frontend
npm install
```

### Configure Environment

Create `.env` file in `frontend/` directory:

```env
VITE_NETWORK=testnet
VITE_API_ENDPOINT=http://localhost:8000
VITE_EXPLORER_URL=https://testnet.ergoplatform.com
VITE_NODE_URL=http://localhost:9052
```

### Start Frontend

```bash
npm run dev
```

Frontend will run on `http://localhost:3000`.

### Open in Browser

Visit http://localhost:3000 in your browser.

## Step 4: Deploy Smart Contracts (First Run)

Before you can place bets, you need to deploy the game contracts:

```bash
# Ensure Ergo node is running and wallet is funded
python deploy_coinflip.py
```

This script will:
1. Mint the Coinflip NFT
2. Create the GameState box
3. Output the NFT ID (update your `.env` files)

## Step 5: Off-chain Bot (Optional)

The off-chain bot automatically monitors and settles bets. Run it in a separate terminal:

```bash
cd off-chain-bot
python main.py
```

## Testing the System

### 1. Verify All Services

```bash
# Ergo node
curl -s http://localhost:9052/info | jq '.fullHeight'

# Backend
curl -s http://localhost:8000/health

# Frontend
curl -s http://localhost:3000 | head -20
```

### 2. Test a Bet

1. Open http://localhost:3000 in browser
2. Connect Nautilus wallet (install extension if needed)
3. Select bet amount and choice (heads/tails)
4. Click "Place Bet"
5. Approve transaction in Nautilus popup
6. Wait for block confirmation
7. Bot will automatically reveal and settle

### 3. Check Transaction on Explorer

Use the transaction ID from the frontend to view details:
https://testnet.ergoplatform.com/en/transactions/{tx_id}

## Common Issues

### Node Wallet Not Unlocking

Ensure your password matches the one set when creating the wallet:
```bash
curl -s -X POST http://localhost:9052/wallet/unlock \
  -H "Content-Type: application/json" \
  -H "api_key: hello" \
  -d '{"pass":"YOUR_WALLET_PASSWORD"}'
```

### "api_key" Errors

Verify your `ergo.conf` `apiKeyHash` matches your request header. The hash is computed as:
```python
import hashlib
print(hashlib.blake2b(b"hello").hexdigest())
# Should output: 324dcf027dd4a30a932c441f365a25e86b173defa4b8e58948253471b81b72cf
```

### Frontend Can't Connect to Backend

Check that:
1. Backend is running on port 8000
2. CORS origins in `backend/.env` include `http://localhost:3000`
3. `VITE_API_ENDPOINT` in `frontend/.env` is correct

### Nautilus Wallet Not Appearing

1. Ensure Nautilus extension is installed
2. Check it's on testnet network
3. Try refreshing the page
4. Check browser console for errors

## Next Steps

- Read [Architecture Overview](ARCHITECTURE.md) to understand system design
- Learn [Ergo Concepts](ERGO_CONCEPTS.md) for blockchain fundamentals
- Follow [Contributing Guide](CONTRIBUTING.md) to start contributing

## Support

For issues or questions:
1. Check existing GitHub issues
2. Review documentation in `/docs` directory
3. Ask in project discussions

Happy coding! 🚀
