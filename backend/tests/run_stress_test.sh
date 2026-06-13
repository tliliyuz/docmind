#!/bin/bash
# DocMind RAG 系统压测 — 全流程执行脚本
#
# 对齐 TESTING.md §8.1 定义的 4 场景：
#   1. 基准 (1 user, 2min)
#   2. 日常 (5 users, 5min)
#   3. 峰值 (10 users, 5min)
#   4. 极限 (20 users, 2min)
#
# 用法:
#   export STRESS_AUTH_TOKEN="your_jwt_token"
#   bash tests/run_stress_test.sh
#
# 可选环境变量:
#   STRESS_HOST          后端地址（默认 http://localhost:8000）
#   STRESS_KB_ID         知识库 ID（默认 1）
#   STRESS_AUTH_TOKEN    JWT Token（必须设置）

set -e

# ---- 配置 ----
HOST="${STRESS_HOST:-http://localhost:8000}"
LOCUSTFILE="tests/locustfile.py"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="results/stress_test_${TIMESTAMP}"

# ---- 前置检查 ----
if [ -z "$STRESS_AUTH_TOKEN" ]; then
    echo "错误: 请设置 STRESS_AUTH_TOKEN 环境变量"
    echo "  可通过以下方式获取:"
    echo "  curl -X POST ${HOST}/api/auth/login \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"username\": \"admin\", \"password\": \"xxx\"}'"
    exit 1
fi

if ! command -v locust &> /dev/null; then
    echo "错误: 未安装 locust，请运行: pip install locust"
    exit 1
fi

echo "============================================="
echo "  DocMind RAG 系统压测"
echo "  时间: ${TIMESTAMP}"
echo "  目标: ${HOST}"
echo "  KB ID: ${STRESS_KB_ID:-1}"
echo "  结果目录: ${RESULTS_DIR}"
echo "============================================="
echo ""

# ---- 创建结果目录 ----
mkdir -p "$RESULTS_DIR"

# ---- 健康检查 ----
echo ">>> 健康检查..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${STRESS_AUTH_TOKEN}" \
    "${HOST}/api/auth/me" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
    echo "错误: 后端服务不可达 (HTTP ${HTTP_CODE})"
    echo "  请确认服务已启动: docker compose up -d"
    exit 1
fi
echo "  后端服务正常 (HTTP ${HTTP_CODE})"
echo ""

# ---- 场景 1: 基准测试 ----
echo "=== [1/4] 基准测试 (1 user, 2min) ==="
echo "  目的: 测量无竞争下的基线延迟"
locust -f "$LOCUSTFILE" --host "$HOST" \
    --users 1 --spawn-rate 1 --run-time 2m \
    --csv "$RESULTS_DIR/baseline" --headless --only-summary
echo ""

echo ">>> 冷却 3 分钟..."
sleep 180
echo ""

# ---- 场景 2: 日常负载 ----
echo "=== [2/4] 日常负载 (5 users, 5min) ==="
echo "  目的: 模拟小团队日常使用"
locust -f "$LOCUSTFILE" --host "$HOST" \
    --users 5 --spawn-rate 1 --run-time 5m \
    --csv "$RESULTS_DIR/daily" --headless --only-summary
echo ""

echo ">>> 冷却 5 分钟..."
sleep 300
echo ""

# ---- 场景 3: 峰值负载 ----
echo "=== [3/4] 峰值负载 (10 users, 5min) ==="
echo "  目的: 模拟周一早晨集中使用"
locust -f "$LOCUSTFILE" --host "$HOST" \
    --users 10 --spawn-rate 2 --run-time 5m \
    --csv "$RESULTS_DIR/peak" --headless --only-summary
echo ""

echo ">>> 冷却 5 分钟..."
sleep 300
echo ""

# ---- 场景 4: 极限测试 ----
echo "=== [4/4] 极限测试 (20 users, 2min) ==="
echo "  目的: 找到系统吞吐上限"
locust -f "$LOCUSTFILE" --host "$HOST" \
    --users 20 --spawn-rate 5 --run-time 2m \
    --csv "$RESULTS_DIR/stress" --headless --only-summary
echo ""

# ---- 完成 ----
echo "============================================="
echo "  压测完成！"
echo "  结果保存在: ${RESULTS_DIR}/"
echo ""
echo "  输出文件:"
ls -la "$RESULTS_DIR"/
echo ""
echo "  下一步:"
echo "  1. 查看 CSV 中的 P50/P99/RPS/Failure% 数据"
echo "  2. 从 Trace 系统查询 Token 消耗统计"
echo "  3. 参照 STRESS_TEST_PLAN.md §8 推算限流阈值"
echo "  4. 更新 config.py 中的 RATE_LIMIT_* 配置"
echo "============================================="
