#!/bin/bash
# FinanceGPT - Quick Start Script

echo "=================================="
echo "FinanceGPT - Quick Start"
echo "=================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✓ Docker is running"
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.quickstart.yml" ]; then
    echo "❌ Error: docker-compose.quickstart.yml not found"
    echo "   Please run this script from the FinanceGPT root directory"
    exit 1
fi

echo "Starting FinanceGPT with Docker Compose..."
echo ""

# Pull latest images
echo "📥 Pulling latest images..."
docker compose -f docker-compose.quickstart.yml pull

echo ""
echo "🚀 Starting services..."
docker compose -f docker-compose.quickstart.yml up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check if containers are running
if docker ps | grep -q financegpt; then
    echo ""
    echo "=================================="
    echo "✅ FinanceGPT is running!"
    echo "=================================="
    echo ""
    echo "🌐 Frontend: http://localhost:3000"
    echo "🔧 Backend API: http://localhost:8000"
    echo "📊 API Docs: http://localhost:8000/docs"
    echo ""
    echo "📝 To upload financial statements:"
    echo "   1. Go to http://localhost:3000"
    echo "   2. Create an account / Log in"
    echo "   3. Upload your CSV/OFX files from Chase, Fidelity, etc."
    echo "   4. Ask questions about your finances!"
    echo ""
    echo "🛑 To stop: docker compose -f docker-compose.quickstart.yml down"
    echo "📋 View logs: docker compose -f docker-compose.quickstart.yml logs -f"
    echo ""
else
    echo ""
    echo "❌ Failed to start FinanceGPT"
    echo "   Check logs with: docker compose -f docker-compose.quickstart.yml logs"
    exit 1
fi
