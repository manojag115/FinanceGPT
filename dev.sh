#!/bin/bash
# FinanceGPT Local Development Script
# Runs all services in separate terminal tabs (macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/financegpt_backend"
WEB_DIR="$SCRIPT_DIR/financegpt_web"

echo "🚀 Starting FinanceGPT development environment..."
echo "   Backend: $BACKEND_DIR"
echo "   Web:     $WEB_DIR"

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is designed for macOS. For Linux, use tmux or run manually."
    echo ""
    echo "Commands to run manually:"
    echo "  Terminal 1 (Backend API):"
    echo "    cd $BACKEND_DIR && source .venv/bin/activate && uv pip install -e . && python main.py --reload"
    echo ""
    echo "  Terminal 2 (Celery Worker):"
    echo "    cd $BACKEND_DIR && source .venv/bin/activate && celery -A celery_worker.celery_app worker --loglevel=info --concurrency=1 --pool=solo"
    echo ""
    echo "  Terminal 3 (Frontend):"
    echo "    cd $WEB_DIR && pnpm run dev"
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "📦 Creating virtual environment..."
    cd "$BACKEND_DIR"
    python3 -m venv .venv
fi

# Open Terminal tabs using AppleScript
osascript <<EOF
tell application "Terminal"
    activate
    
    -- Tab 1: Backend API
    do script "cd '$BACKEND_DIR' && source .venv/bin/activate && echo '📦 Installing dependencies...' && pip install -e . && echo '🚀 Starting Backend API...' && python main.py --reload"
    
    -- Tab 2: Celery Worker
    delay 1
    tell application "System Events" to keystroke "t" using command down
    delay 0.5
    do script "cd '$BACKEND_DIR' && source .venv/bin/activate && echo '⏳ Waiting for dependencies...' && sleep 5 && echo '🔄 Starting Celery Worker...' && celery -A celery_worker.celery_app worker --loglevel=info --concurrency=1 --pool=solo" in front window
    
    -- Tab 3: Frontend
    delay 1
    tell application "System Events" to keystroke "t" using command down
    delay 0.5
    do script "cd '$WEB_DIR' && echo '🌐 Starting Frontend...' && pnpm run dev" in front window
    
end tell
EOF

echo ""
echo "✅ Development environment started in Terminal tabs!"
echo ""
echo "Services:"
echo "  📡 Backend API:    http://localhost:8000"
echo "  📚 API Docs:       http://localhost:8000/docs"
echo "  🌐 Frontend:       http://localhost:3000"
echo ""
echo "Press Ctrl+C in each tab to stop the services."
