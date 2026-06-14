@echo off
REM DocMind RAG 系统压测 — Windows 版全流程执行脚本
REM
REM 用法:
REM   set STRESS_AUTH_TOKEN=your_jwt_token
REM   tests\performance\run_stress_test.bat
REM
REM 可选环境变量:
REM   STRESS_HOST          后端地址（默认 http://localhost:8000）
REM   STRESS_KB_ID         知识库 ID（默认 1）
REM   STRESS_AUTH_TOKEN    JWT Token（必须设置）

setlocal enabledelayedexpansion

REM ---- 配置 ----
if "%STRESS_HOST%"=="" set STRESS_HOST=http://localhost:8000
set LOCUSTFILE=tests\performance\locustfile.py

REM 生成时间戳
for /f "tokens=1-6 delims=/-: " %%a in ('%SystemRoot%\System32\wbem\wmic.exe OS Get localdatetime ^| find "."') do (
    set dt=%%a
)
set TIMESTAMP=%dt:~0,8%_%dt:~8,6%
set RESULTS_DIR=results\stress_test_%TIMESTAMP%

REM ---- 前置检查 ----
if "%STRESS_AUTH_TOKEN%"=="" (
    echo 错误: 请设置 STRESS_AUTH_TOKEN 环境变量
    echo   可通过以下方式获取:
    echo   curl -X POST %STRESS_HOST%/api/auth/login ^
    echo     -H "Content-Type: application/json" ^
    echo     -d "{\"username\": \"admin\", \"password\": \"xxx\"}"
    exit /b 1
)

where locust >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: 未安装 locust，请运行: pip install locust
    exit /b 1
)

echo =============================================
echo   DocMind RAG 系统压测
echo   时间: %TIMESTAMP%
echo   目标: %STRESS_HOST%
echo   KB ID: %STRESS_KB_ID% (默认 1^)
echo   结果目录: %RESULTS_DIR%
echo =============================================
echo.

REM ---- 创建结果目录 ----
mkdir "%RESULTS_DIR%" 2>nul

REM ---- 健康检查 ----
echo ^>^>^> 健康检查...
curl -s -o nul -w "%%{http_code}" -H "Authorization: Bearer %STRESS_AUTH_TOKEN%" "%STRESS_HOST%/api/auth/me" > _health_check.tmp 2>nul
set /p HTTP_CODE=<_health_check.tmp
del _health_check.tmp 2>nul

if "%HTTP_CODE%" neq "200" (
    echo 错误: 后端服务不可达 ^(HTTP %HTTP_CODE%^)
    echo   请确认服务已启动: docker compose up -d
    exit /b 1
)
echo   后端服务正常 (HTTP %HTTP_CODE%^)
echo.

REM ---- 场景 1: 基准测试 ----
echo === [1/4] 基准测试 (1 user, 2min^) ===
echo   目的: 测量无竞争下的基线延迟
locust -f %LOCUSTFILE% --host %STRESS_HOST% --users 1 --spawn-rate 1 --run-time 2m --csv "%RESULTS_DIR%\baseline" --headless --only-summary
echo.
echo ^>^>^> 冷却 3 分钟...
timeout /t 180 /nobreak >nul
echo.

REM ---- 场景 2: 日常负载 ----
echo === [2/4] 日常负载 (5 users, 5min^) ===
echo   目的: 模拟小团队日常使用
locust -f %LOCUSTFILE% --host %STRESS_HOST% --users 5 --spawn-rate 1 --run-time 5m --csv "%RESULTS_DIR%\daily" --headless --only-summary
echo.
echo ^>^>^> 冷却 5 分钟...
timeout /t 300 /nobreak >nul
echo.

REM ---- 场景 3: 峰值负载 ----
echo === [3/4] 峰值负载 (10 users, 5min^) ===
echo   目的: 模拟周一早晨集中使用
locust -f %LOCUSTFILE% --host %STRESS_HOST% --users 10 --spawn-rate 2 --run-time 5m --csv "%RESULTS_DIR%\peak" --headless --only-summary
echo.
echo ^>^>^> 冷却 5 分钟...
timeout /t 300 /nobreak >nul
echo.

REM ---- 场景 4: 极限测试 ----
echo === [4/4] 极限测试 (20 users, 2min^) ===
echo   目的: 找到系统吞吐上限
locust -f %LOCUSTFILE% --host %STRESS_HOST% --users 20 --spawn-rate 5 --run-time 2m --csv "%RESULTS_DIR%\stress" --headless --only-summary
echo.

REM ---- 完成 ----
echo =============================================
echo   压测完成！
echo   结果保存在: %RESULTS_DIR%\
echo.
echo   下一步:
echo   1. 查看 CSV 中的 P50/P99/RPS/Failure%% 数据
echo   2. 从 Trace 系统查询 Token 消耗统计
echo   3. 参照 STRESS_TEST_PLAN.md 推算限流阈值
echo   4. 更新 config.py 中的 RATE_LIMIT_* 配置
echo =============================================

endlocal
