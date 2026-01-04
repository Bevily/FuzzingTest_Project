import os
import subprocess
import sysv_ipc
import random
import time

# --- 配置参数 ---
TARGET = "/app/target/target_instrumented"
MAP_SIZE = 65536
SEED_DIR = "/app/seeds"
OUT_DIR = "/app/out"


class GreyBoxFuzzer:
    def __init__(self, target_path):
        self.target_path = target_path

        # 1. 建立共享内存 (SHM)
        # 与 AFL 类似，我们使用 sysv_ipc 来开辟内存空间，供 C 程序写入覆盖率
        try:
            self.shm = sysv_ipc.SharedMemory(None, flags=sysv_ipc.IPC_CREAT | sysv_ipc.IPC_EXCL, mode=0o600,
                                             size=MAP_SIZE)
        except sysv_ipc.ExistentialError:
            # 如果清理不当导致已存在，则报错，通常需要手动清理或重启
            print("[!] SHM 已存在，请清理。")
            exit(1)

        self.env = os.environ.copy()
        self.env["__AFL_SHM_ID"] = str(self.shm.id)

        # 2. 状态跟踪
        self.corpus = []
        self.global_visited_indices = set()
        self.exec_count = 0
        self.start_time = time.time()

        # 3. 初始化语料库 (Corpus)
        if not os.path.exists(SEED_DIR):
            os.makedirs(SEED_DIR)

        for filename in os.listdir(SEED_DIR):
            file_path = os.path.join(SEED_DIR, filename)
            if os.path.isfile(file_path):
                with open(file_path, "rb") as f:
                    self.corpus.append(f.read())

        if not self.corpus:
            self.corpus = [b"a"]  # 基础种子

        self.stats_file = "/app/out/fuzz_stats.csv"
        with open(self.stats_file, "w") as f:
            f.write("timestamp,exec_count,coverage\n")

    def mutate(self, data):
        """变异算法：混合了确定性变异和随机破坏"""
        res = bytearray(data)
        if not res: res = bytearray(b"a")

        # 变异强度：随机决定变异几次
        iterations = random.randint(1, 8)

        for _ in range(iterations):
            idx = random.randint(0, len(res) - 1)
            choice = random.random()

            if choice < 0.3:
                # 1. 位翻转 (Bitflip)
                res[idx] ^= (1 << random.randint(0, 7))
            elif choice < 0.6:
                # 2. 算术微调 (Arithmetic)
                delta = random.choice([-1, 1])
                res[idx] = (res[idx] + delta) % 256
            elif choice < 0.8:
                # 3. 结构变异 (Insertion/Deletion)
                if random.random() > 0.5:
                    res.insert(idx, random.randint(32, 126))
                elif len(res) > 1:
                    res.pop(idx)
            else:
                # 4. 字典/魔数注入 (Interesting Values)
                interesting = [0, 1, 255, ord('c'), ord('r'), ord('a'), ord('s'), ord('h')]
                res[idx] = random.choice(interesting)

        return bytes(res)

    def run_target(self, input_data):
        """执行目标程序并获取覆盖率反馈"""
        # 每次运行前清空 SHM 位图
        self.shm.write(b'\x00' * MAP_SIZE)

        proc = subprocess.Popen(
            [self.target_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env
        )

        try:
            # 喂入变异后的数据
            stdout, stderr = proc.communicate(input=input_data, timeout=0.5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return set(), -1  # 超时视为无效执行

        # 读取位图并找出被标记过的“边” (Edges)
        bitmap = self.shm.read(MAP_SIZE)
        current_indices = set(i for i, byte in enumerate(bitmap) if byte > 0)

        return current_indices, proc.returncode

    def start(self):
        """主循环：Seed -> Mutate -> Run -> Feedback"""
        print(f"[+] Fuzzing 启动！目标: {self.target_path}")
        print(f"[+] 共享内存 ID: {self.shm.id} | 初始语料数: {len(self.corpus)}")
        print("-" * 50)

        while True:
            # 1. 选择种子
            seed = random.choice(self.corpus)

            # 2. 变异
            candidate = self.mutate(seed)

            # 3. 运行并获取反馈
            current_indices, returncode = self.run_target(candidate)
            self.exec_count += 1

            # 4. 评估覆盖率：是否发现了新的“边”
            if current_indices and not current_indices.issubset(self.global_visited_indices):
                new_edges_count = len(current_indices - self.global_visited_indices)
                self.global_visited_indices.update(current_indices)
                self.corpus.append(candidate)

                # 保存新发现的种子到硬盘
                seed_id = len(self.corpus)
                with open(os.path.join(SEED_DIR, f"id_{seed_id:06d}"), "wb") as f:
                    f.write(candidate)

                print(
                    f"\n[*] 发现新路径! 种子: {candidate[:20]!r}... | 新增边: {new_edges_count} | 总边数: {len(self.global_visited_indices)}")

            # 5. 检查是否触发崩溃 (Crash)
            # returncode < 0 捕捉 SIGSEGV 等信号，returncode == 66 捕捉我们手动设置的 exit(66)
            if (returncode is not None and returncode < 0) or (returncode == 66):
                print(f"\n\n{'!' * 20}")
                print(f"[★] 捕获漏洞崩溃！")
                print(f"[★] 触发输入: {candidate!r}")
                print(f"{'!' * 20}\n")

                if not os.path.exists(OUT_DIR): os.makedirs(OUT_DIR)
                with open(os.path.join(OUT_DIR, f"crash_{int(time.time())}.txt"), "wb") as f:
                    f.write(candidate)
                break

            # 6. 打印统计信息
            if self.exec_count % 100 == 0:
                elapsed = time.time() - self.start_time
                # 记录数据到 CSV
                with open(self.stats_file, "a") as f:
                    f.write(f"{elapsed:.2f},{self.exec_count},{len(self.global_visited_indices)}\n")


if __name__ == "__main__":
    fuzzer = GreyBoxFuzzer(TARGET)
    try:
        fuzzer.start()
    except KeyboardInterrupt:
        print("\n[+] 用户手动停止。")
    finally:
        # 清理资源，防止内存泄露
        print("[+] 正在清理共享内存...")
        fuzzer.shm.detach()
        fuzzer.shm.remove()