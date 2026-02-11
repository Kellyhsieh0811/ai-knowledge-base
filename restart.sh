#!/bin/bash
echo "🛑 停止舊的 Flask 進程..."
# Kill all python processes related to app.py to ensure clean slate
lsof -ti:5005 | xargs kill -9 2>/dev/null || true
pkill -f "python.*src/app.py" || true
pkill -f "python.*app.py" || true
sleep 2

echo "🧹 清除 Python 快取..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

echo "🚀 啟動 Flask (Port 5005)..."
# 使用 nohup 和 stdin 重定向防止進程被暫掛 (Background Process Suspension)
nohup python3 src/app.py > app.log 2>&1 < /dev/null &

echo "✅ 服務已在背景啟動。"
echo "📝 查看日誌: tail -f app.log"
