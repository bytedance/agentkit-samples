#!/bin/bash
# install-video-clip-mcp.sh

echo "Installing @pickstar-2002/video-clip-mcp..."
npm install -g @pickstar-2002/video-clip-mcp@latest

if [ $? -eq 0 ]; then
    echo "✅ Installation succeeded!"
    echo "Install location: $(which video-clip-mcp)"
    echo "Version info: $(video-clip-mcp --version 2>/dev/null || echo 'Run video-clip-mcp --version to check')"
else
    echo "❌ Installation failed!"
    exit 1
fi
