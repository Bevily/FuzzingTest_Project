#!/bin/bash

# --- 1. 环境清理 ---
echo "[1/4] 正在清理旧的测试数据..."
rm -rf /app/seeds/id_*
rm -rf /app/out/*
# 确保 CSV 文件头部正确
echo "timestamp,exec_count,coverage" > /app/out/fuzz_stats.csv

# --- 2. 编译目标 ---
echo "[2/4] 正在使用 afl-cc 重新编译目标程序..."
afl-cc /app/target/target.c -o /app/target/target_instrumented

# --- 3. 运行 Fuzzer ---
echo "[3/4] Fuzzer 启动！"
echo "提示：请让它运行一段时间（比如 1 分钟）。当你觉得差不多了，按 Ctrl+C 停止测试，脚本会自动开始生成报告。"
echo "--------------------------------------------------"

# 运行 Python Fuzzer
python3 fuzzer/main.py

# --- 4. 生成报告 ---
echo "--------------------------------------------------"
echo "[4/4] 检测到 Fuzzer 已停止，正在分析数据并生成报告..."

# 检查是否有 pandas 和 matplotlib，没有就装一下
pip install pandas matplotlib -i https://pypi.tuna.tsinghua.edu.cn/simple

# 运行可视化脚本
python3 fuzzer/analyze.py

echo "=== 任务完成！报告已生成在 /app/out/ 目录下 ==="