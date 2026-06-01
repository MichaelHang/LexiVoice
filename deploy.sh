#!/bin/bash
# =============================================================
# LexiVoice 部署更新脚本
# 用法：bash deploy.sh [选项]
#   无参数        → 拉取最新代码 + 重建镜像 + 重启容器（完整更新）
#   -r / --restart → 仅重启容器（不重建镜像，适合改了挂载的文件）
#   -b / --build   → 仅重建镜像（不拉取代码）
#   -l / --logs    → 查看实时日志
#   -s / --status  → 查看容器状态
# =============================================================

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# 检查 docker compose 命令
if docker compose version &>/dev/null 2>&1; then
    COMPOSE="docker compose"
elif docker-compose version &>/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    err "未找到 docker compose，请先安装 Docker"
fi

# ---- 子命令处理 ----

do_logs() {
    log "查看实时日志（Ctrl+C 退出）"
    $COMPOSE logs -f
}

do_status() {
    log "容器状态："
    $COMPOSE ps
    echo ""
    log "镜像信息："
    docker images | grep lexivoice || docker images | head -5
}

do_restart() {
    log "重启容器（不重建镜像）..."
    $COMPOSE restart
    log "重启完成！"
    $COMPOSE ps
}

do_build() {
    warn "清理旧构建缓存..."
    docker system prune -f

    log "重新构建镜像..."
    $COMPOSE build --no-cache

    log "重启容器..."
    $COMPOSE up -d

    log "构建完成！"
    $COMPOSE ps
}

do_full_update() {
    log "===== 开始完整更新 ====="

    # 1. 拉取最新代码
    if [ -d ".git" ]; then
        log "拉取最新代码..."
        git pull
    else
        warn "当前目录不是 git 仓库，跳过 git pull"
    fi

    # 2. 清理旧缓存
    warn "清理旧构建缓存..."
    docker system prune -f

    # 3. 重新构建并启动
    log "重新构建镜像并启动容器..."
    $COMPOSE up -d --build

    # 4. 等待几秒让服务启动
    sleep 3

    # 5. 检查状态
    log "===== 更新完成 ====="
    $COMPOSE ps

    echo ""
    log "查看启动日志（最近20行）："
    $COMPOSE logs --tail=20
}

# ---- 参数解析 ----

case "${1:-}" in
    -r|--restart)
        do_restart
        ;;
    -b|--build)
        do_build
        ;;
    -l|--logs)
        do_logs
        ;;
    -s|--status)
        do_status
        ;;
    ""| -f|--full)
        do_full_update
        ;;
    *)
        echo "用法：bash deploy.sh [选项]"
        echo ""
        echo "  无参数 / -f    完整更新（git pull + 重建镜像 + 重启）"
        echo "  -r / --restart 仅重启容器（不重建镜像）"
        echo "  -b / --build   仅重建镜像"
        echo "  -l / --logs    查看实时日志"
        echo "  -s / --status  查看容器状态"
        ;;
esac
