#!/bin/bash

# LexiVoice 启动脚本

echo "🎙️ LexiVoice 单词音频生成器"
echo "============================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python3，请先安装"
    exit 1
fi

# 检查 FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️ 警告: 未找到 FFmpeg，某些功能可能无法正常工作"
    echo "   macOS: brew install ffmpeg"
    echo "   Ubuntu: sudo apt install ffmpeg"
fi

# 安装依赖
echo "📦 安装依赖..."
pip install -r requirements.txt

# 创建必要目录
mkdir -p generated_audio temp_files

echo ""
echo "🚀 启动服务..."
echo "🌐 访问 http://localhost:8080"
echo ""
python3 app.py
