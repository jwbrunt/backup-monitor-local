#!/bin/bash
set -e

echo "🚀 Pushing backup-monitor v2.0 to GitHub"
echo ""
echo "First, make sure the repository exists at:"
echo "  https://github.com/jwbrunt/backup-monitor"
echo ""
echo "If not, create it at: https://github.com/new"
echo "  - Name: backup-monitor"
echo "  - Description: Local-only backup monitoring with email reports"
echo "  - Public or Private: your choice"
echo "  - Do NOT initialize with README"
echo ""
read -p "Press Enter when repository is ready..."

echo ""
echo "Choose authentication method:"
echo "  1) SSH (recommended - requires SSH key setup)"
echo "  2) HTTPS with token"
read -p "Choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    echo "Using SSH..."
    git remote set-url origin git@github.com:jwbrunt/backup-monitor.git
    git push -u origin main
    git push --tags
elif [ "$choice" = "2" ]; then
    echo "Using HTTPS with token..."
    echo "Get your token from: https://github.com/settings/tokens"
    echo "You'll be prompted for username (jwbrunt) and token as password"
    git push -u origin main
    git push --tags
else
    echo "Invalid choice"
    exit 1
fi

echo ""
echo "✅ Done! View at: https://github.com/jwbrunt/backup-monitor"
