# cheese-plugins

> *经常闻一闻奶酪,你就会知道它什么时候开始变质;越早放下旧奶酪,就越早尝到新奶酪。随着奶酪的移动而移动。*
>
> *—— 斯宾塞·约翰逊,《谁动了我的奶酪?》*

我的个人 Agent 插件工作区,用来寻找属于自己的那块奶酪。

`cheese-plugins` 是一个小而实用的工作区,用来收集可复用的 Agent 构件:插件、
技能、斜杠命令、agent、模板,以及维护脚本。名字取自《谁动了我的奶酪》——这个
仓库就是我自己找奶酪、试奶酪、打包奶酪的工作台。

## 安装

本仓库采用官方的 `.claude-plugin/` 市场格式,**Claude Code 和 codex 都能读**
——一套清单,两个运行时通用。

市场只需注册一次:

```bash
# Claude Code:在会话里执行
/plugin marketplace add git@github.com:belkov0912/cheese-plugins.git

# codex:在终端执行
codex plugin marketplace add git@github.com:belkov0912/cheese-plugins.git
```

本地开发(还没推送时),把上面的 Git 地址换成工作树的绝对路径直接注册即可。

之后浏览、安装、更新、卸载都走交互界面:输入 `/plugins`(Claude Code 或
codex),选中 `cheese-plugins`,对想要的插件操作即可。现有插件:`cheese-core`、
`equity-research`、`serenity-skill`、`goal-meta-skill`、`stock-selection-rules`。

重新安装后请开一个新会话,新技能和插件元数据才会被加载。

## 目录结构

```text
cheese-plugins/
  .claude-plugin/
    marketplace.json        # 插件市场索引(Claude Code + codex 共用)
  plugins/                  # 可安装的插件包
    cheese-core/
      .claude-plugin/
        plugin.json         # 插件清单
      skills/               # 每个技能就是 skills/<name>/SKILL.md
  scripts/
    validate.sh
    new-skill.sh
    new-plugin.sh
    bump.sh                 # Set all plugins to one shared version
```

技能在两个运行时之间是共享的:一个技能就是 `skills/<name>/SKILL.md`,带上
`name` 和 `description` 两个 frontmatter 字段。只有当插件确实附带 `commands/`
或 `agents/` 时,才给它加这些目录。

## 现有插件

- `plugins/`:按工作流分组的可安装插件包。每个插件的技能放在各自的
  `plugins/<plugin-name>/skills/` 下。
- 不设顶层 `skills/` 源副本。插件包本身就是唯一来源(source of truth)。

| 插件 | 范围 | 包含的技能 |
| --- | --- | --- |
| `cheese-core` | 核心推理 | `zongju-thinking` |
| `equity-research` | 晨会、行业研究、竞争格局、选题、催化剂、论点跟踪、个股消息面 | `morning-note`、`idea-generation`、`sector-overview`、`competitive-analysis`、`catalyst-calendar`、`thesis-tracker`、`market-researcher`、`stock-pulse` 及配套工作流。改编自 Anthropic FSI 的 `equity-research` |
| `serenity-skill` | Serenity 式供应链卡点研究 | 来自 [muxuuu/serenity-skill](https://github.com/muxuuu/serenity-skill),MIT |
| `goal-meta-skill` | 把模糊任务收敛成强 `/goal` 指令 | 改编自 [joeseesun/qiaomu-goal-meta-skill](https://github.com/joeseesun/qiaomu-goal-meta-skill),MIT(© 向阳乔木) |
| `stock-selection-rules` | A股选股与交易过程复盘 | `r0-data`、`r0-breakout`、`r1-mainline`、`r7-reset`、`r9-reclaim`、`r-stock-rating`、`trade-review` |

## 新增技能

```bash
scripts/new-skill.sh equity-research my-skill "Short description of when to use it"
```

然后编辑:

```text
plugins/equity-research/skills/my-skill/SKILL.md
```

参考上面的插件表选择合适的插件。如果这个技能会开启一条新的工作流,就新建一个
插件,而不是塞进 `cheese-core`。

`SKILL.md` 保持精简,只放 agent 运行时真正用得上的指令。

## 新增插件

```bash
scripts/new-plugin.sh my-plugin "Short plugin description" general
```

第三个参数是市场分类(默认 `general`)。它会创建:

```text
plugins/my-plugin/.claude-plugin/plugin.json
plugins/my-plugin/skills/
```

同时把该插件追加登记到 `.claude-plugin/marketplace.json`。

## 校验

执行:

```bash
scripts/validate.sh
```

校验器会检查:

- `.claude-plugin/marketplace.json` 和各插件清单都是合法 JSON
- 每个市场条目都有字符串 `source`、`description`、`category`,且指向一个含
  `.claude-plugin/plugin.json` 的真实插件
- `plugins/` 下的每个插件都已登记进市场
- 插件清单的 `name` 与所在目录名、市场条目名一致
- 插件清单包含 `version`、`description`、`author.name`
- 技能的 frontmatter 含 `name` 和 `description`,且 `name` 与所在目录一致
- 没有遗留明显的占位符

## 同步来源

仓库之外可能还散着旧的独立技能副本,比如 `~/.claude/skills/` 或
`~/.codex/skills/` 下。从这些位置导入时,把技能拷进对应的
`plugins/<plugin-name>/skills/` 目录,不要新建顶层 `skills/` 副本。

## 命名约定

- 一律小写 kebab-case:`zongju-thinking`、`cheese-core`。
- 插件目录名必须与 `.claude-plugin/plugin.json` 的 `name` 一致。
- 技能目录名应与 `SKILL.md` frontmatter 的 `name` 一致。
- 避免 `helper`、`tool`、`workflow` 这类泛化名,除非范围确实很宽。

## 版本

所有插件**共用同一个版本号**。任何改动后,用 `scripts/bump.sh <版本>` 把所有插件的
`version` 一起往上 bump 一次——这样 Claude Code / codex 会把每个已安装插件都当成升级、
重新拉取最新内容(只改内容不 bump 版本,已安装的副本不会更新)。`validate.sh` 会强制
所有版本一致。当前:`1.11.0`。

```bash
scripts/bump.sh 1.2.0
```
