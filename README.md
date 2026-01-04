测试方法：
* 在app# 输入 ./run_fuzz_task.sh 后回车

进入Ubuntu系统：
* docker ps -a
* docker start nju_fuzzer(或者在上一步完成之后的ID里选择一个复制)
* docker exec -it nju_fuzzer(同上) /bin/bash