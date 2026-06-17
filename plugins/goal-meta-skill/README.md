# goal-meta-skill

把一个模糊任务,收敛成可以持续执行、可以验证、知道何时停止和何时暂停的 `/goal` 指令。

改编自 [joeseesun/qiaomu-goal-meta-skill](https://github.com/joeseesun/qiaomu-goal-meta-skill),
MIT(© 向阳乔木)。本插件只**生成 goal 指令**,默认不替你执行目标本身。

## 技能

- **`goal-meta-skill`** — 给定一句模糊需求,先产出一段可直接复制的「推荐执行版」
  `/goal`(中文场景默认中文正文 + 英文兼容镜像),包含成果、验证、约束、写入边界、
  迭代策略、完成条件与暂停条件;需求太模糊时改为给编号选择题让你快速收敛。

## 何时用

要把「帮我做个 X / 修一下这个 / 优化一下」这类话,变成一份 Agent 能安全执行、有
验证、有边界、有暂停条件的任务合同时。

## 自带工具

- `scripts/lint_goal_command.py` — 轻量校验:拦截不可执行前缀、占位符、`make sure
  it works` 之类空验证。对文件型产物可在收尾前跑一遍。
