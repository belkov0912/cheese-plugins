---
name: zrec-debug
description: zrec-model 的远程调试闭环——「本地改 → git 同步 → 远程服务器跑 ./run.sh 验证 → 报错回本地改 → 再同步重测」。Use when working in the zrec-model project and the user wants to 同步到远程 / 推上去测试 / 远程跑一下 / 上服务器测一下 / 远程报错帮我调 / deploy and test on the server / run ./run.sh remotely / debug the remote run. SSH host 默认用 ssh config 里的 v11_x2，若未配置则让用户输入 IP/host。调用时可附带两个可选参数：debug 信息（要排查的报错或上下文）、IP/host（覆盖默认）。触发示例：「同步到远程测试」「推上去跑 run.sh」「远程报了 shape mismatch 帮我调」「用 10.x.x.x 这台跑」。
argument-hint: [报错/上下文] [host=<IP或别名，默认 v11_x2>]
---

# zrec-debug

zrec-model 的远程调试闭环。把本地改动同步到远程服务器跑 `./run.sh`，
报错就回本地改、再同步重测，直到跑通或需要你做决定时停下问你。

## 可选参数（implicit params）

用户调用时可在后面附带，能识别就用，识别不到就走默认：

- **debug 信息**：要排查的报错文本 / 上下文 / 这轮想验证什么。有就作为本轮起点直接定位，
  没有就先跑一遍 `run.sh` 看输出。
- **host**：覆盖默认远程主机。可写裸值或 `host=` 前缀，值是 ssh config 别名（如 `v11_x2`）或裸 IP。
  没传就用下面「SSH host 解析」的默认。

## SSH host 解析

1. 用户**显式传了 host**（裸值或 `host=` 前缀）→ 用它（裸 IP 用 `ssh jeeves@<IP>`，别名用 `ssh <别名>`）。
2. 否则默认别名 **`v11_x2`**；先确认它在 ssh config 里配好了：
   `ssh -G v11_x2 2>/dev/null | grep -q "^hostname " && echo ok`（或 `grep -A1 "Host v11_x2" ~/.ssh/config`）。
3. **没配置** → 用 `AskUserQuestion` 让用户给一个 IP 或 host 别名，再继续。不要瞎猜。

下文用 `$HOST` 代表最终确定的远程主机。

## 固定环境

- **本地仓库**：`/Users/zhihu/Work/project/zhihu/zrec-model`（用户通常在此目录启动 CLI）
- **远程 run 目录**：`/home/jeeves/project`（`./run.sh` 在这里）
- **远程仓库目录**：`/home/jeeves/project/zrec-model`（在这里 `git pull`）
- **推送目标**：`origin`（用户 fork：liujianan01/zrec-model），分支用**本地当前分支**

## 前置检查

1. 确认当前在 zrec-model 仓库：`git rev-parse --show-toplevel` 且 `git remote -v` 含 `zrec-model`。
   不在 → 停下，提醒用户进 zrec-model 目录。
2. 记录分支：`BRANCH=$(git branch --show-current)`。远程必须切到同一分支。
3. 解析 `$HOST`（见上）。

## 工作流

### 步骤 1 · 本地提交并推送

- `git status` 看有无未提交改动。
- 有改动：
  - 优先用 `commit-push-pr` skill 提交推送（用户首选）。
  - 快速迭代轮也可直接：`git add -A && git commit -m "<本轮改动简述>" && git push origin HEAD`。
  - commit message 一句话说清这轮改了什么；不确定先 `git diff` / `git diff --cached` 看。
- 无改动且远程已是最新 → 跳过推送，直接去步骤 3 重测。

### 步骤 2 · 远程同步代码

```bash
ssh $HOST "cd /home/jeeves/project/zrec-model && \
  git fetch origin && \
  (git checkout $BRANCH 2>/dev/null || git checkout -b $BRANCH origin/$BRANCH) && \
  git pull origin $BRANCH"
```

- 拉取若有冲突/报错（远程本地手改、未提交等）→ **不要强推/强覆盖**，停下把远程状态报给用户问怎么处理。

### 步骤 3 · 远程执行 run.sh

```bash
ssh $HOST "cd /home/jeeves/project && ./run.sh" 2>&1 | tee /tmp/zrec_run.log
```

- **首次先搞清 run.sh 性质**：`ssh $HOST "cat /home/jeeves/project/run.sh"`。
  - 跑完即退出的脚本 → 等退出，取 exit code + 全部输出。
  - 常驻训练/服务（不退出）→ 用 `timeout 300 ssh ...` 或后台跑 + tail 日志，靠**启动成功标志**或**错误关键字**判断，别死等。

### 步骤 4 · 判定结果

- **成功**：exit code = 0 且无错误关键字 → 汇报关键指标/日志尾部，结束本轮。
- **失败**：exit code ≠ 0，或命中 `Traceback` / `Error` / `Exception` / `FAILED` / `core dumped` / `ImportError` / `OOM` 等 → 进步骤 5。
- 把关键报错段（不是整篇日志）摘出来给用户看。

### 步骤 5 · 报错回本地修（迭代）

1. 把远程报错定位到 zrec-model 的具体文件/代码行（结合用户传入的 debug 信息）。
2. **改法唯一且明确**（拼写、import、shape、明显 bug）→ 直接本地改，回步骤 1。
3. **改法有多个合理选择，或涉及建模/产品取舍、删数据、改配置/checkpoint** → 用
   `AskUserQuestion` 把选项列清楚问用户，等回复再改。
4. 每轮改动后必须重跑步骤 1–4，不要盲改连推。
5. **最多 5 轮**仍未跑通 → 停下，汇报：试过什么、卡在哪、下一步建议。

## 暂停条件（Pause if）

- SSH host 未配置且用户没给 IP/host。
- 修法有多个合理选择，或涉及模型结构/特征/超参等建模取舍。
- 需要改远程配置、删数据、动 checkpoint、改 `run.sh` 本身。
- 报错指向环境/权限/资源/依赖（OOM、磁盘满、CUDA、缺包），非改本地代码能解决。
- git pull 在远程冲突，或远程目录状态异常。
- 连续多轮同一个错没有进展。

## 完成条件（Stop when）

- `run.sh` 在远程跑通（exit 0 或常驻任务出现启动成功标志），无错误关键字 → 汇报结果，结束。
- 或：达到 5 轮上限 / 命中暂停条件 → 汇报现状与卡点，交回用户。
