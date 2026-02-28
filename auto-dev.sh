#!/bin/bash

# Auto-Dev Launcher Script
# This script starts the continuous development loop

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_DEV_DIR="$SCRIPT_DIR/auto-dev"

echo "🚀 Auto-Dev Launcher"
echo "===================="

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Navigate to auto-dev directory
cd "$AUTO_DEV_DIR"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Run the auto-dev loop
echo ""
echo "🔄 Starting continuous development loop..."
echo "   --once   : Run a single task and exit"
echo "   --status : Show current task status"
echo ""

npm run start "$@"
