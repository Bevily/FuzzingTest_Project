import os, subprocess, sysv_ipc, random, time

TARGET = "/app/target/target_instrumented"
MAP_SIZE = 65536


class GreyBoxFuzzer:
    def __init__(self, target_path):
        self.target_path = target_path
        # 1. 初始化共享内存
        self.shm = sysv_ipc.SharedMemory(None, flags=sysv_ipc.IPC_CREAT | sysv_ipc.IPC_EXCL, mode=0o600, size=MAP_SIZE)
        self.env = os.environ.copy()
        self.env["__AFL_SHM_ID"] = str(self.shm.id)

        # 2. 核心：全局位图索引记录（记录所有见过的“边”）
        self.global_visited_indices = set()
        self.corpus = []
        self.exec_count = 0
        self.start_time = time.time()

        # 3. 加载种子
        if not os.path.exists("/app/seeds"): os.makedirs("/app/seeds")
        for f in os.listdir("/app/seeds"):
            with open(os.path.join("/app/seeds", f), "rb") as bio:
                self.corpus.append(bio.read())
        if not self.corpus: self.corpus = [b"a"]

    def mutate(self, data):
        """温和变异：确保更有可能保留已有的正确前缀"""
        res = bytearray(data)
        if not res: return b"a"

        # 随机选择一种变异方式
        choice = random.random()
        idx = random.randint(0, len(res) - 1)

        if choice < 0.4:  # 40% 概率：位翻转
            res[idx] ^= (1 << random.randint(0, 7))
        elif choice < 0.7:  # 30% 概率：算术微调 (+1 或 -1)
            res[idx] = (res[idx] + random.choice([-1, 1])) % 256
        elif choice < 0.9:  # 20% 概率：插入/删除
            if random.random() > 0.5:
                res.insert(idx, random.randint(32, 126))
            elif len(res) > 1:
                res.pop(idx)
        else:  # 10% 概率：替换为有趣字符
            res[idx] = ord(random.choice("crash123\x00\xff"))

        return bytes(res)

    def run_target(self, input_data):
        self.shm.write(b'\x00' * MAP_SIZE)  # 清空白板
        proc = subprocess.Popen([self.target_path], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)
        try:
            proc.communicate(input=input_data, timeout=0.1)
        except subprocess.TimeoutExpired:
            proc.kill();
            proc.wait()
            return set(), 0

        # 获取当前运行触发的所有索引
        bitmap = self.shm.read(MAP_SIZE)
        current_indices = set(i for i, b in enumerate(bitmap) if b > 0)
        return current_indices, proc.returncode

    def start(self):
        print("[+] Fuzzer 启动！正在通过位图反馈进化...")
        while True:
            # 1. 挑选种子并变异
            seed = random.choice(self.corpus)
            candidate = self.mutate(seed)

            # 2. 跑一遍程序
            current_indices, ret = self.run_target(candidate)
            self.exec_count += 1

            # 3. 【核心逻辑】只要发现了任何一个以前没见过的索引，就是新路径！
            if current_indices and not current_indices.issubset(self.global_visited_indices):
                new_edges = current_indices - self.global_visited_indices
                self.global_visited_indices.update(current_indices)
                self.corpus.append(candidate)

                # 保存这个优秀的种子
                with open(f"/app/seeds/id_{len(self.corpus)}", "wb") as f:
                    f.write(candidate)

                print(f"\n[*] 发现新路径! 种子: {candidate} | 新增索引: {new_edges} | 语料库: {len(self.corpus)}")

            # 4. 检查崩溃
            if ret is not None and ret < 0:
                print(f"\n[!!!] 捕获崩溃! 输入: {candidate}")
                with open(f"/app/out/crash_{int(time.time())}.txt", "wb") as f:
                    f.write(candidate)
                break

            if self.exec_count % 100 == 0:
                speed = int(self.exec_count / (time.time() - self.start_time))
                print(f" 执行数: {self.exec_count} | 速度: {speed}/s | 已发现边: {len(self.global_visited_indices)}",
                      end='\r')


if __name__ == "__main__":
    if not os.path.exists("/app/out"): os.makedirs("/app/out")
    fuzzer = GreyBoxFuzzer(TARGET)
    try:
        fuzzer.start()
    except KeyboardInterrupt:
        print("\n[+] 用户停止")
    finally:
        fuzzer.shm.detach()
        fuzzer.shm.remove()