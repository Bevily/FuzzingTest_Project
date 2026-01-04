import pandas as pd
import matplotlib.pyplot as plt
import os


def generate_report():
    csv_file = "/app/out/fuzz_stats.csv"
    if not os.path.exists(csv_file):
        print("错误：找不到统计数据文件！")
        return

    # 1. 读取数据
    df = pd.read_csv(csv_file)

    # 2. 绘制覆盖率增长曲线
    plt.figure(figsize=(10, 6))
    plt.plot(df['timestamp'], df['coverage'], label='Edges Found', color='blue', linewidth=2)
    plt.title('Fuzzing Coverage Growth', fontsize=15)
    plt.xlabel('Time (seconds)', fontsize=12)
    plt.ylabel('Total Edges Discovered', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()

    # 保存图片
    plot_path = "/app/out/coverage_plot.png"
    plt.savefig(plot_path)
    print(f"[+] 可视化图表已保存至: {plot_path}")

    # 3. 生成 Markdown 报告总结
    total_time = df['timestamp'].iloc[-1]
    total_execs = df['exec_count'].iloc[-1]
    max_cov = df['coverage'].iloc[-1]

    report = f"""
# Fuzzing 测试任务报告

## 1. 核心统计数据
- **测试总时长**: {total_time:.2f} 秒
- **总执行次数**: {total_execs} 次
- **平均执行速度**: {int(total_execs / total_time)} execs/s
- **最终覆盖边数**: {max_cov}

## 2. 结论分析
- 如果曲线在后期趋于平缓，说明 Fuzzer 遇到了难以突破的逻辑门槛。
- 捕获的 Crash 文件已保存在 `/app/out/` 目录下。

![覆盖率曲线](coverage_plot.png)
"""
    with open("/app/out/report.md", "w") as f:
        f.write(report)
    print("[+] 测试报告 (Markdown) 已生成！")


if __name__ == "__main__":
    generate_report()