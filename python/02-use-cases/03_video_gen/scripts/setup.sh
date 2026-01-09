#!/bin/bash
# install-video-clip-mcp.sh

echo "开始安装 @pickstar-2002/video-clip-mcp..."
npm install -g @pickstar-2002/video-clip-mcp@latest

if [ $? -eq 0 ]; then
    echo "✅ 安装成功！"
    echo "安装位置: $(which video-clip-mcp)"
    echo "版本信息: $(video-clip-mcp --version 2>/dev/null || echo '运行 video-clip-mcp --version 查看')"
else
    echo "❌ 安装失败！"
    exit 1
fi