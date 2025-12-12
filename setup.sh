#!/bin/bash
# ChainForensics Setup Script
# This script helps you set up and run ChainForensics

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           🔗 ChainForensics Setup Script                   ║"
echo "║       Privacy-Focused Blockchain Analysis Platform         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed.${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Function to get compose command
get_compose_cmd() {
    if docker compose version &> /dev/null; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

COMPOSE_CMD=$(get_compose_cmd)

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}No .env file found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  IMPORTANT: You need to configure your Bitcoin RPC        ║"
    echo "║  settings in the .env file before continuing.             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "Edit the .env file with your settings:"
    echo "  nano .env"
    echo ""
    echo "For Umbrel users, find your RPC password with:"
    echo "  cat ~/umbrel/app-data/bitcoin/data/bitcoin/.cookie"
    echo ""
    read -p "Press Enter after configuring .env to continue..."
fi

# Menu
echo ""
echo "What would you like to do?"
echo ""
echo "  1) Start ChainForensics (API + Web Dashboard)"
echo "  2) Start with MCP Server (for Claude Desktop)"
echo "  3) Stop all services"
echo "  4) View logs"
echo "  5) Run without Docker (development mode)"
echo "  6) Test Bitcoin RPC connection"
echo "  7) Exit"
echo ""
read -p "Enter your choice [1-7]: " choice

case $choice in
    1)
        echo -e "${GREEN}Starting ChainForensics...${NC}"
        $COMPOSE_CMD up -d chainforensics-api chainforensics-web
        echo ""
        echo -e "${GREEN}✓ ChainForensics is starting!${NC}"
        echo ""
        echo "  📊 Web Dashboard: http://localhost:8080"
        echo "  🔌 API Server:    http://localhost:3000"
        echo "  📚 API Docs:      http://localhost:3000/docs"
        echo ""
        echo "Run '$COMPOSE_CMD logs -f' to view logs"
        ;;
    2)
        echo -e "${GREEN}Starting all services including MCP...${NC}"
        $COMPOSE_CMD --profile mcp up -d
        echo ""
        echo -e "${GREEN}✓ All services started!${NC}"
        echo ""
        echo "For Claude Desktop integration, add to your config:"
        echo ""
        echo '  {
    "mcpServers": {
      "chainforensics": {
        "command": "docker",
        "args": ["exec", "-i", "chainforensics-mcp", "python", "server.py"]
      }
    }
  }'
        ;;
    3)
        echo -e "${YELLOW}Stopping all services...${NC}"
        $COMPOSE_CMD down
        echo -e "${GREEN}✓ All services stopped${NC}"
        ;;
    4)
        echo "Viewing logs (Ctrl+C to exit)..."
        $COMPOSE_CMD logs -f
        ;;
    5)
        echo -e "${BLUE}Starting in development mode...${NC}"
        echo ""
        
        # Check Python
        if ! command -v python3 &> /dev/null; then
            echo -e "${RED}Error: Python 3 is not installed${NC}"
            exit 1
        fi
        
        # Create virtual environment if needed
        if [ ! -d "backend/venv" ]; then
            echo "Creating virtual environment..."
            cd backend
            python3 -m venv venv
            source venv/bin/activate
            pip install -r requirements.txt
            cd ..
        else
            source backend/venv/bin/activate
        fi
        
        # Load environment
        export $(cat .env | grep -v '^#' | xargs)
        
        echo ""
        echo "Starting API server..."
        cd backend
        python -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
        ;;
    6)
        echo -e "${BLUE}Testing Bitcoin RPC connection...${NC}"
        
        # Load environment
        if [ -f .env ]; then
            export $(cat .env | grep -v '^#' | xargs)
        fi
        
        # Test connection
        echo ""
        echo "Connecting to ${BITCOIN_RPC_HOST}:${BITCOIN_RPC_PORT}..."
        
        RESPONSE=$(curl -s --user "${BITCOIN_RPC_USER}:${BITCOIN_RPC_PASS}" \
            --data-binary '{"jsonrpc":"1.0","id":"test","method":"getblockchaininfo","params":[]}' \
            -H 'content-type: text/plain;' \
            "http://${BITCOIN_RPC_HOST}:${BITCOIN_RPC_PORT}/" 2>&1)
        
        if echo "$RESPONSE" | grep -q '"blocks"'; then
            BLOCKS=$(echo "$RESPONSE" | grep -o '"blocks":[0-9]*' | cut -d: -f2)
            CHAIN=$(echo "$RESPONSE" | grep -o '"chain":"[^"]*"' | cut -d'"' -f4)
            echo -e "${GREEN}✓ Connection successful!${NC}"
            echo ""
            echo "  Chain: $CHAIN"
            echo "  Blocks: $BLOCKS"
        else
            echo -e "${RED}✗ Connection failed${NC}"
            echo ""
            echo "Response: $RESPONSE"
            echo ""
            echo "Please check your .env settings"
        fi
        ;;
    7)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
