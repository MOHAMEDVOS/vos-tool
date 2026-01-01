#!/bin/bash

# VOS Tool - Cleanup Unused Packages
# Removes unused packages to free up disk space

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "  VOS Tool - Cleaning Up Unused Packages"
echo "========================================"
echo ""

echo -e "${BLUE}[INFO]${NC} This will remove the following unused packages:"
echo "  - vosk (replaced by AssemblyAI)"
echo "  - openai-whisper (replaced by AssemblyAI, saves ~5-10GB)"
echo "  - jellyfish (not used in codebase)"
echo ""

read -p "Continue with cleanup? (y/n): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}[INFO]${NC} Cleanup cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}[INFO]${NC} Checking installed packages..."
echo ""

# Check if packages are installed
VOSK_FOUND=0
WHISPER_FOUND=0
JELLYFISH_FOUND=0

if pip show vosk >/dev/null 2>&1 || pip3 show vosk >/dev/null 2>&1; then
    echo -e "${BLUE}[INFO]${NC} Found: vosk"
    VOSK_FOUND=1
else
    echo -e "${BLUE}[INFO]${NC} Not found: vosk"
fi

if pip show openai-whisper >/dev/null 2>&1 || pip3 show openai-whisper >/dev/null 2>&1; then
    echo -e "${BLUE}[INFO]${NC} Found: openai-whisper"
    WHISPER_FOUND=1
else
    echo -e "${BLUE}[INFO]${NC} Not found: openai-whisper"
fi

if pip show jellyfish >/dev/null 2>&1 || pip3 show jellyfish >/dev/null 2>&1; then
    echo -e "${BLUE}[INFO]${NC} Found: jellyfish"
    JELLYFISH_FOUND=1
else
    echo -e "${BLUE}[INFO]${NC} Not found: jellyfish"
fi

echo ""
echo -e "${BLUE}[INFO]${NC} Starting cleanup..."
echo ""

# Determine pip command
if command -v pip3 >/dev/null 2>&1; then
    PIP_CMD=pip3
elif command -v pip >/dev/null 2>&1; then
    PIP_CMD=pip
else
    echo -e "${YELLOW}[ERROR]${NC} pip not found. Please install pip first."
    exit 1
fi

if [ $VOSK_FOUND -eq 1 ]; then
    echo -e "${BLUE}[INFO]${NC} Uninstalling vosk..."
    $PIP_CMD uninstall -y vosk
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS]${NC} vosk uninstalled"
    else
        echo -e "${YELLOW}[WARNING]${NC} Failed to uninstall vosk"
    fi
fi

if [ $WHISPER_FOUND -eq 1 ]; then
    echo -e "${BLUE}[INFO]${NC} Uninstalling openai-whisper (this may take a moment)..."
    $PIP_CMD uninstall -y openai-whisper
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS]${NC} openai-whisper uninstalled (~5-10GB freed)"
    else
        echo -e "${YELLOW}[WARNING]${NC} Failed to uninstall openai-whisper"
    fi
fi

if [ $JELLYFISH_FOUND -eq 1 ]; then
    echo -e "${BLUE}[INFO]${NC} Uninstalling jellyfish..."
    $PIP_CMD uninstall -y jellyfish
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS]${NC} jellyfish uninstalled"
    else
        echo -e "${YELLOW}[WARNING]${NC} Failed to uninstall jellyfish"
    fi
fi

echo ""
echo "========================================"
echo -e "${GREEN}[INFO]${NC} Cleanup completed!"
echo "========================================"
echo ""
echo -e "${BLUE}[INFO]${NC} Estimated space freed:"
echo "  - vosk: ~100MB"
echo "  - openai-whisper: ~5-10GB (models)"
echo "  - jellyfish: ~1MB"
echo ""
echo -e "${BLUE}[INFO]${NC} You can verify with: $PIP_CMD list"
echo ""

