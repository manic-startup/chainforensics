# 🔗 ChainForensics

**Enterprise-Grade Blockchain Analysis Platform**

A privacy-focused UTXO forensics tool designed to work with your local Bitcoin node (Umbrel recommended). All analysis happens locally on your LAN - no external APIs, no data leakage.
Claude descktop/docker MCP integration is optional. The App works without it out of the box. 
## 📋 Features

- **UTXO Tracing** - Track funds forward (where they went) and backward (where they came from)
- **CoinJoin Detection** - Identify Whirlpool, Wasabi, JoinMarket, and PayJoin transactions
- **Privacy Scoring** - Calculate privacy scores for any UTXO
- **Timeline Visualization** - ASCII and graphical timelines of fund flows
- **Address Validation** - Validate addresses and identify types (P2PKH, P2SH, P2WPKH, P2TR)
- **Background Jobs** - Queue long-running analyses
- **MCP Integration** - Use with Claude Desktop for natural language blockchain analysis
- **KYC Privacy Check** - designed to check if **your withdrawal from a KYC exchange** (like Coinbase, Kraken, Binance, etc.) can be traced to your current holdings.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR LAN ONLY                           │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │   Claude    │    │  Web        │    │   Umbrel        │ │
│  │   Desktop   │───▶│  Dashboard  │    │   Bitcoin Node  │ │
│  └──────┬──────┘    └──────┬──────┘    └────────┬────────┘ │
│         │                  │                     │          │
│         │    ┌─────────────▼─────────────┐      │          │
│         └───▶│    ChainForensics API     │◀─────┘          │
│              │    (localhost:3000)       │                  │
│              └───────────┬───────────────┘                  │
│                          │                                  │
│              ┌───────────▼───────────────┐                  │
│              │      SQLite Database      │                  │
│              │      (local cache)        │                  │
│              └───────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Docker** and **Docker Compose**
- **Bitcoin Core** with `txindex=1` enabled (Umbrel has this by default)
- Local network access to your Bitcoin node

### Option 1: Docker (Recommended)

```bash
#1 Clone or download the project
cd chainforensics

#2 Copy and configure environment
cp .env.example .env
nano .env  # Add your Bitcoin RPC credentials

#=====Extra Info to Get Login Details from Umbrel/Bitcoin Node App==========
# You will need this info for the .env file
# =========
# BITCOIN_RPC_HOST=192.168.0.5
# BITCOIN_RPC_PORT=8332
# BITCOIN_RPC_USER=__cookie__
# BITCOIN_RPC_PASS=c3jj4j3j
# =========
# BITCOIN_RPC_HOST= will be the IP of YOUR umbrel node not the IP shown here
# BITCOIN_RPC_PORT=8332 is the default leave this as is
# BITCOIN_RPC_USER=__cookie__ leave this as is (need to work out a better way of loging in each time as theis keeps changeing after a reload)
# BITCOIN_RPC_PASS=c3jj4j3j you need to replace c3jj4j3j with your rpc password. Below are the steps to do this
# In the umbrel GUI open the bitcoin node app, go to setting -> advanced then in the "Custom bitcoin.conf overrides" section add this
rpcallowip=192.168.0.0/24
rpcbind=0.0.0.0
# note the rpcallowip= has a 192.168.0.0/24 subnet, yours maybe different, change this to mathch your subnet. You can be more spacific by using the exact IP of your machine using a /32 mask.  
# Next restart the bitcoin node app (right click on the app and select restart)(YOU MUST DO THIS STEP)
# Next on the umbrel main home screen click the settings icon at the bottom. Then "advanced settings" then "Terminal" then "umbrelOS".
# At the CLI go to cd umbrel/app-data/bitcoin/data/bitcoin and type in "cat .cookie"
# you will see something that looks like this "__cookie__:c3jj4j3j" the password is after the : symbol. Yours will be much longer than c3jj4j3j.
#========================END============================

#=====Extra Electrs Info to Get Login Details  App==========
# Electrs should be fully setup in Umbrel. In the App under "Local Network" you should have the address and port for the below config in the .env file
ELECTRS_HOST=192.168.0.5
ELECTRS_PORT=50001
# To test you can curl to the below address or just http to it in a browser
curl http://localhost:3000/api/v1/addresses/electrs/status
#========================END============================

#3a Run setup script
chmod +x setup.sh
./setup.sh

#======Useful docker comands======
docker compose build --no-cache
docker compose up -d
docker compose logs -f chainforensics-api
#===============END=====================

#3b Or start manually with Docker Compose
docker compose up -d
```

**Access:**
- 📊 Web Dashboard: http://localhost:8080
- 🔌 API Server: http://localhost:3000
- 📚 API Docs: http://localhost:3000/docs

### Option 2: Manual Setup (Development)

```bash
# Create virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp ../.env.example ../.env
nano ../.env

# Run the API server
uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
```

## 🔧 Configuration

### Finding Your Umbrel RPC Password

SSH into your Umbrel and run:

```bash
cat ~/umbrel/app-data/bitcoin/data/bitcoin/.cookie
```

The output format is `__cookie__:PASSWORD` - use the PASSWORD part.

### .env Configuration

```env
# Bitcoin Core RPC (REQUIRED)
BITCOIN_RPC_HOST=umbrel.local    # or your node's IP
BITCOIN_RPC_PORT=8332
BITCOIN_RPC_USER=umbrel
BITCOIN_RPC_PASS=your_password_here

# Optional: Electrs (for address history)
ELECTRS_HOST=umbrel.local
ELECTRS_PORT=50001
```

## 🤖 Claude Desktop Integration (MCP)

ChainForensics includes an MCP server for natural language blockchain analysis.

### Setup

1. **Start ChainForensics API first:**
   ```bash
   docker compose up -d chainforensics-api
   ```

2. **Add to Claude Desktop config** (`~/.config/claude/claude_desktop_config.json` on Linux/Mac):
   ```json
   {
     "mcpServers": {
       "chainforensics": {
         "command": "python",
         "args": ["/path/to/chainforensics/mcp/server.py"]
       }
     }
   }
   ```

3. **Restart Claude Desktop**

### Usage Examples

Once configured, you can ask Claude:

- "Trace this transaction forward: abc123..."
- "Is this a CoinJoin transaction? def456..."
- "What's the privacy score for this UTXO?"
- "Show me a timeline of where these funds went"
- "Check if this address is valid: bc1q..."

## 📊 API Endpoints

### Transactions
- `GET /api/v1/transactions/{txid}` - Get transaction details
- `GET /api/v1/transactions/{txid}/utxo/{vout}` - Check UTXO status

### Analysis
- `GET /api/v1/analysis/trace/forward` - Trace UTXO forward
- `GET /api/v1/analysis/trace/backward` - Trace inputs backward
- `GET /api/v1/analysis/coinjoin/{txid}` - Detect CoinJoin
- `GET /api/v1/analysis/privacy-score` - Calculate privacy score

### Visualizations
- `GET /api/v1/visualizations/timeline/ascii` - ASCII timeline
- `GET /api/v1/visualizations/timeline/html` - Interactive HTML timeline
- `GET /api/v1/visualizations/graph/html` - Force-directed graph

### Jobs
- `POST /api/v1/jobs/` - Create background analysis job
- `GET /api/v1/jobs/{job_id}` - Get job status

## 📈 Timeline View Example

```
================================================================================
UTXO TIMELINE
Start: abc123def456...
================================================================================

2023-01-15 │ ████████████████████ 5.0000 BTC     💰 Unspent
           │

2023-01-16 │ ██████████ 2.5000 BTC               📤 Spent
           │ ██████████ 2.5000 BTC               📤 Spent
           │

2023-02-01 │ ██ 0.5000 BTC                       📤 Spent
           │ ████████ 2.0000 BTC                 🔀 CoinJoin (85%)
           │

2023-02-01 │ █ 0.0100 BTC                        💰 Unspent

================================================================================
Unspent outputs: 2
CoinJoin transactions: 1
Total nodes: 5
================================================================================
```

## 🔒 Security

- **All traffic stays on your LAN** - No external API calls
- **No data leaves your network** - Analysis uses only your local node
- **No tracking** - Your queries are not logged externally
- **Docker isolation** - Services run in isolated containers
- **Non-root containers** - Enhanced security posture

## 🛠️ Development

### Project Structure

```
chainforensics/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── core/         # Business logic
│   │   │   ├── bitcoin_rpc.py
│   │   │   ├── tracer.py
│   │   │   ├── coinjoin.py
│   │   │   └── timeline.py
│   │   ├── workers/      # Background tasks
│   │   ├── main.py       # FastAPI app
│   │   ├── config.py     # Settings
│   │   └── database.py   # SQLAlchemy models
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── public/
│   │   └── index.html    # Dashboard
│   ├── nginx.conf
│   └── Dockerfile
├── mcp/
│   ├── server.py         # MCP server
│   └── Dockerfile
├── config/
│   └── claude_desktop_config.json
├── docker-compose.yml
├── .env.example
├── setup.sh
└── README.md
```

### Running Tests

```bash
cd backend
source venv/bin/activate
pytest
```

## ⚠️ Requirements

### Bitcoin Core Settings

Your Bitcoin node **MUST** have `txindex=1` enabled. Without this, you cannot look up arbitrary transactions.

**For Umbrel:** This is enabled by default.

**For manual Bitcoin Core:** Add to `bitcoin.conf`:
```
txindex=1
```

⚠️ If you enable `txindex` after initial sync, you must resync the entire blockchain.


## 📜 License  
AGPL-3.0. (See LICENSE file)  
Commercial licensing available—contact me for details.

## Contributing

Contributions are welcome! Help make this Bitcoin chain forensics tool better for everyone.

- Open an issue to report bugs, suggest features, or ask questions.
- Fork the repo, make your changes, and submit a pull request.
- Follow basic code style: readable commits, meaningful PR descriptions.

By contributing code, you agree that your contributions are licensed under the same license as this project (AGPL-3.0). Commercial licensing available separately—contact [your email] for details.

Thank you for helping build this project!

## 🙏 Acknowledgments

- Bitcoin Core developers
- Umbrel team
- NetworkChuck on YouTube (MCP Server) https://github.com/theNetworkChuck
- Anthropic (Claude MCP protocol)
- Samourai Wallet (Whirlpool inspiration)
- Wasabi Wallet (research reference)
- Electrs team

---

Built with ❤️ for the Bitcoin community. Your keys, your coins, your privacy.
