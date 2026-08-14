# Clash Verge + IPFly 静态出口配置指南

> 适用场景：本机直连 IPFly 不稳定或被远端重置，需要先经过一个普通 Clash 节点，再连接 IPFly 静态 SOCKS5；同时只让 Safari、Claude Desktop、Claude CLI 和 VS Code Claude 插件使用静态出口，其他流量保持直连。

## 1. 目标链路

```text
Safari / Claude Desktop / Claude CLI / VS Code Claude 插件
    ↓
本机 Clash Verge（Mihomo）
    ↓
经过端到端验证的普通订阅节点
    ↓
IPFly 静态 SOCKS5
    ↓
目标网站看到 IPFly 分配的静态出口 IP

其他应用和 VS Code 的非 Claude 流量
    ↓
DIRECT
```

这里使用 Mihomo 的 `dialer-proxy`：IPFly 是最终代理，普通订阅节点只负责建立到 IPFly 服务器的连接。目标网站最终看到的是 IPFly 出口，而不是中间订阅节点。

当前本机验证示例：

- 普通 Clash 入口：`127.0.0.1:7897`
- Claude CLI 专用入口：`127.0.0.1:7898`
- IPFly 静态出口测试值：`117.120.0.243`

这些只是本机实例。其他人必须替换 IPFly 地址、端口、凭证、节点名称和预期静态 IP。

## 2. 前置条件

- Clash Verge Rev，内核使用 Mihomo。
- 一份可用的普通节点订阅。
- IPFly 或其他静态代理服务提供的：
  - SOCKS5 服务器地址
  - 端口
  - 用户名
  - 密码
  - 服务商声明的静态出口 IP，或可自行查询确认的出口 IP
- Clash Verge 已开启系统代理；本文示例入口为 `127.0.0.1:7897`。

不要把订阅链接、IPFly 用户名、密码或完整运行时配置提交到 Git，也不要发到公开聊天中。

## 3. 先判断是否真的需要“普通节点 → IPFly”

先直接测试 IPFly，不经过订阅节点：

```bash
curl --silent --show-error --max-time 20 \
  --proxy 'socks5h://<IPFLY_HOST>:<IPFLY_PORT>' \
  --proxy-user '<IPFLY_USERNAME>:<IPFLY_PASSWORD>' \
  https://api.ipify.org
```

判断方法：

- 返回 IPFly 分配的静态 IP：直连可用，不一定需要代理链。
- `connection reset by peer`、`Socket closed by remote peer`、超时：直连链路不可用，可以继续配置中间节点。
- 身份验证失败：优先检查账号、密码、端口和服务端白名单，不是上游节点问题。

建议使用 `socks5h://`，让域名解析也通过 SOCKS5 完成。

## 4. 为什么普通节点的延迟测试不够

Clash 的延迟或健康检查通常只验证：

```text
本机 → 普通节点 → 测试 URL
```

真正需要验证的是：

```text
本机 → 普通节点 → IPFly → 测试 URL
```

一个节点能正常打开 Google，并不代表它能连接 IPFly 的服务器和端口。运营商路由、节点出口防火墙、协议类型以及 IPFly 的风控都可能导致第二段连接失败。

因此，不能把订阅里的所有节点直接放进生产 Fallback 组。必须逐个进行端到端测试，只保留通过的节点。

## 5. 节点资格测试

### 5.1 建立临时测试组

在 Clash Verge 的全局扩展脚本中，临时创建一个手动选择组：

```javascript
const testCandidates = [
  "候选节点 A",
  "候选节点 B",
  "候选节点 C",
];

config["proxy-groups"] = [
  ...(config["proxy-groups"] || []).filter(
    (group) => group && group.name !== "IPFly-测试上游",
  ),
  {
    name: "IPFly-测试上游",
    type: "select",
    proxies: testCandidates,
  },
];
```

然后创建 IPFly 最终代理：

```javascript
config.proxies = [
  ...(config.proxies || []).filter(
    (proxy) => proxy && proxy.name !== "Claude静态出口",
  ),
  {
    name: "Claude静态出口",
    type: "socks5",
    server: "<IPFLY_HOST>",
    port: 5001,
    username: "<IPFLY_USERNAME>",
    password: "<IPFLY_PASSWORD>",
    udp: false,
    tfo: false,
    "ip-version": "ipv4-prefer",
    "dialer-proxy": "IPFly-测试上游",
  },
];
```

再增加一个只用于测试和 CLI 的本地入口：

```javascript
config.listeners = [
  ...((config.listeners || []).filter(
    (listener) => listener && listener.name !== "claude-cli",
  )),
  {
    name: "claude-cli",
    type: "mixed",
    listen: "127.0.0.1",
    port: 7898,
    proxy: "Claude静态出口",
  },
];
```

保存脚本后，在 Clash Verge 中“重新激活订阅”。

### 5.2 逐个测试候选节点

在 Clash Verge 的代理页面，把 `IPFly-测试上游` 切换到一个候选节点，然后执行：

```bash
curl --silent --show-error --max-time 25 \
  --proxy http://127.0.0.1:7898 \
  https://api.ipify.org
```

每个节点至少连续测试 3～5 次。通过标准：

1. 每次都能在超时时间内返回；
2. 返回值等于 IPFly 的静态出口 IP；
3. 没有间歇性 `reset by peer`；
4. 再测试一次 Claude API 连通性：

```bash
curl --silent --show-error --max-time 25 \
  --proxy http://127.0.0.1:7898 \
  -o /dev/null \
  -w 'HTTP %{http_code}\n' \
  https://api.anthropic.com/
```

没有携带 API 凭证时返回 `401`、`403` 或 `404` 都可能是正常结果，关键是已经收到 HTTPS 响应，而不是连接超时或被重置。

记录结果：

| 节点 | 静态 IP 正确 | 连测成功率 | Anthropic 可达 | 是否保留 |
|---|---:|---:|---:|---:|
| 候选节点 A | 是/否 | 5/5 | 是/否 | 是/否 |
| 候选节点 B | 是/否 | 3/5 | 是/否 | 是/否 |

节点名称、国家或延迟都不能代替这个测试。不同用户、不同本地运营商和不同 IPFly 入口的结果可能完全不同。

## 6. 生产配置

完成资格测试后，把测试通过的节点名称填入 `verifiedCandidateNames`。推荐使用全局扩展脚本，因为订阅更新时不会直接覆盖这段逻辑。

下面是可复用模板：

```javascript
function main(config, profileName) {
  const groups = Array.isArray(config["proxy-groups"])
    ? config["proxy-groups"]
    : [];
  const proxies = Array.isArray(config.proxies) ? config.proxies : [];

  const upstreamGroup = "IPFly-上游";
  const staticProxy = "Claude静态出口";
  const cliListener = "claude-cli";

  // 只填写经过“普通节点 → IPFly → 目标网站”端到端测试的节点。
  const verifiedCandidateNames = [
    "已验证节点 A",
    "已验证节点 B",
    "已验证节点 C",
  ];

  // 不要把真实凭证提交到 Git 或分享给他人。
  const ipfly = {
    server: "<IPFLY_HOST>",
    port: 5001,
    username: "<IPFLY_USERNAME>",
    password: "<IPFLY_PASSWORD>",
  };

  const availableProxyNames = new Set(
    proxies
      .filter((proxy) => proxy && typeof proxy.name === "string")
      .map((proxy) => proxy.name),
  );
  const verifiedCandidates = verifiedCandidateNames.filter((name) =>
    availableProxyNames.has(name),
  );

  if (verifiedCandidates.length === 0) {
    console.log(
      "[IPFly] 没有找到已验证节点；保留原配置，避免错误回退到 DIRECT。",
    );
    return config;
  }

  config.mode = "rule";
  config["find-process-mode"] = "always";
  config.dns = {
    ...(config.dns || {}),
    "respect-rules": true,
    "direct-nameserver": ["system"],
  };

  config["proxy-groups"] = [
    ...groups.filter(
      (group) => group && group.name !== upstreamGroup,
    ),
    {
      name: upstreamGroup,
      type: "fallback",
      proxies: verifiedCandidates,
      url: "https://www.gstatic.com/generate_204",
      interval: 120,
      timeout: 5000,
      lazy: false,
    },
  ];

  config.proxies = [
    ...proxies.filter(
      (proxy) => proxy && proxy.name !== staticProxy,
    ),
    {
      name: staticProxy,
      type: "socks5",
      server: ipfly.server,
      port: ipfly.port,
      username: ipfly.username,
      password: ipfly.password,
      udp: false,
      tfo: false,
      "ip-version": "ipv4-prefer",
      "dialer-proxy": upstreamGroup,
    },
  ];

  const listeners = Array.isArray(config.listeners)
    ? config.listeners
    : [];
  config.listeners = [
    ...listeners.filter(
      (listener) => listener && listener.name !== cliListener,
    ),
    {
      name: cliListener,
      type: "mixed",
      listen: "127.0.0.1",
      port: 7898,
      proxy: staticProxy,
    },
  ];

  config.rules = [
    // VS Code Claude 插件运行在 Code Helper 中。
    // 按 Claude 域名分流，不代理整个 VS Code。
    `DOMAIN-SUFFIX,anthropic.com,${staticProxy}`,
    `DOMAIN-SUFFIX,claude.ai,${staticProxy}`,

    // Safari 的所有网站都走静态出口。
    `PROCESS-NAME,Safari,${staticProxy}`,
    `PROCESS-NAME,com.apple.WebKit.Networking,${staticProxy}`,

    // Claude Desktop 及其 Helper。
    `PROCESS-NAME-WILDCARD,Claude*,${staticProxy}`,

    // 其他流量保持直连，包括 VS Code 内网调试。
    "MATCH,DIRECT",
  ];

  return config;
}
```

注意：

- `fallback` 的健康检查只能说明普通节点能够访问测试 URL，不能替代前面的 IPFly 端到端资格测试。
- 节点订阅刷新后，如果名称变化，脚本会找不到旧名称。需要重新测试并更新 `verifiedCandidateNames`。
- 不建议在组里自动加入订阅的全部节点，否则一旦切换到与 IPFly 不兼容的节点，整条静态链路会断。
- UDP、Hysteria2、TUIC、WireGuard 或特殊 TLS 节点可能不适合充当 `dialer-proxy`。最终以端到端实测为准。

## 7. 各应用如何进入 Clash

### 7.1 Safari

开启 Clash Verge 的系统代理，入口指向 `127.0.0.1:7897`。

Safari 请求会被识别为 `Safari` 或 `com.apple.WebKit.Networking`，因此全部走 `Claude静态出口`。

`com.apple.WebKit.Networking` 也可能被其他基于 WebKit 的应用使用。如果只想代理 Safari，需要在 Clash 连接页面观察实际进程，再决定是否保留这条兼容规则。

### 7.2 Claude Desktop

Claude Desktop 及其 Helper 通常命中：

```text
PROCESS-NAME-WILDCARD,Claude*
```

开启系统代理后，新连接会走静态出口。

### 7.3 Claude CLI

使用专用 `7898` 入口：

```bash
HTTP_PROXY=http://127.0.0.1:7898 \
HTTPS_PROXY=http://127.0.0.1:7898 \
claude
```

可以封装为 shell 函数，但不要把代理账号和密码写进命令；`7898` 只需要本机地址。

如果 Claude CLI 需要访问内网服务，可以在启动前按实际需求设置内网绕过方式。Claude Code 官方文档提示其代理支持对 `NO_PROXY` 有限制，因此必须实测当前版本；不要默认内网请求一定会绕过代理。

### 7.4 VS Code Claude 插件

不要使用：

```text
PROCESS-NAME,Code Helper,Claude静态出口
```

因为 `Code Helper` 同时承载 VS Code 同步、插件市场、其他插件和部分内网调试。代理整个进程容易影响无关功能。

当前方案按目标域名分流：

```text
DOMAIN-SUFFIX,anthropic.com,Claude静态出口
DOMAIN-SUFFIX,claude.ai,Claude静态出口
```

因此：

- Claude API、认证和 Anthropic 相关请求走静态出口；
- `vscode-sync.trafficmanager.net`、插件市场和内网服务继续命中 `MATCH,DIRECT`。

如果配置了自建 LLM Gateway 或 `ANTHROPIC_BASE_URL`，还需要把该网关的精确域名加入规则。不要盲目添加整个公司域名。

## 8. 生效与验证

### 8.1 保存和重新加载

1. 保存全局扩展脚本；
2. 在 Clash Verge 的订阅页面点击“重新激活订阅”；
3. 确认运行模式为 `Rule`；
4. 已经打开很久的应用可能保留旧连接，必要时重新打开应用，或在 VS Code 中执行“重新加载窗口”。

### 8.2 验证专用静态入口

```bash
curl --silent --show-error --max-time 25 \
  --proxy http://127.0.0.1:7898 \
  https://api.ipify.org
```

输出必须等于自己的 IPFly 静态出口 IP。

### 8.3 验证 Safari

在 Safari 打开任意可信 IP 查询网站，确认出口等于 IPFly 静态 IP。

不要只看 Clash Verge 首页显示的“外部 IP”。首页可能展示默认直连出口，不代表某个应用的单独请求实际走向。

### 8.4 验证 VS Code Claude 插件

1. 在 Claude 插件中发起一个新请求；
2. 打开 Clash Verge 的“连接”页面；
3. 查找进程 `Code Helper`；
4. Claude 请求应显示：

```text
目标域名：api.anthropic.com 或其他 anthropic.com/claude.ai 子域名
命中规则：DomainSuffix
策略：Claude静态出口
```

同时找一个 VS Code 同步或普通扩展请求，应显示：

```text
进程：Code Helper
命中规则：Match
策略：DIRECT
```

这两项同时满足，才说明“Claude 走静态出口、VS Code 其他功能保持直连”配置正确。

### 8.5 使用 Mihomo 本地控制接口验证

Clash Verge Rev 在 macOS 上可能使用 Unix Socket：

```bash
curl --silent \
  --unix-socket /tmp/verge/verge-mihomo.sock \
  http://localhost/rules |
  jq -r '.rules[] | [.type,.payload,.proxy] | @tsv'
```

查看当前连接：

```bash
curl --silent \
  --unix-socket /tmp/verge/verge-mihomo.sock \
  http://localhost/connections |
  jq -r '
    .connections[]
    | [
        .metadata.process,
        .metadata.host,
        .rule,
        (.chains | join(" -> "))
      ]
    | @tsv
  '
```

不同版本的 Clash Verge 可能没有这个路径，或者使用 TCP 控制端口。此时直接使用应用内“规则”和“连接”页面即可。

## 9. 常见故障

### `Socket closed by remote peer` / `connection reset by peer` / Error 54

通常表示 TCP 已连接，但远端或中间链路主动重置。常见原因：

- 本机直连 IPFly 的来源 IP 或线路不被接受；
- 普通节点无法访问 IPFly 的地址或端口；
- IPFly 账号、区域、会话或白名单限制；
- 该节点协议不适合二次拨号；
- 节点本身不稳定。

处理顺序：

1. 核对 IPFly 凭证；
2. 直接测试 IPFly；
3. 更换普通上游节点；
4. 对每个候选节点执行端到端测试；
5. 只把连续通过的节点加入生产组。

### `Policy ... doesn't exist`

一般是策略被重命名、删除，或 Clash Verge UI 仍引用旧的内部策略 ID。

处理：

1. 确认脚本中的策略名称完全一致；
2. 重新激活订阅；
3. 回到测试窗口重新选择策略；
4. 必要时重启 Clash Verge。

### `Policy doesn't support UDP relay`

IPFly SOCKS5 套餐可能只支持 TCP。本文配置使用：

```text
udp: false
```

Claude、普通 HTTPS 和大多数 API 请求使用 TCP，不需要为此开启 UDP。Safari 出现 HTTP/3/QUIC 问题时，应让其回退到 HTTPS/TCP。

### 切换普通节点后，出口 IP 也变了

正确的代理链中，目标网站应看到 IPFly 出口，而不是普通节点出口。若出口随普通节点变化，说明请求绕过了 `Claude静态出口`，直接使用了普通节点。

检查：

- 本地请求是否进入 `7898`，或命中正确规则；
- `Claude静态出口` 是否存在 `dialer-proxy: IPFly-上游`；
- Listener 的 `proxy` 是否指向 `Claude静态出口`；
- 运行时连接的最终策略是否为 `Claude静态出口`。

### Clash 关闭后全机没网

如果 macOS 系统代理仍指向 `127.0.0.1:7897`，但 Clash 已退出，本机就没有程序监听该端口。

恢复方法：

1. 重新打开 Clash Verge；或
2. 在退出 Clash 前先关闭“系统代理”；或
3. 在 macOS 当前网络的代理设置中关闭 HTTP/HTTPS 代理。

不要把系统代理故障误判成 IPFly 故障。

## 10. 节点维护流程

订阅更新或节点变得不稳定时：

1. 不要立刻把新节点加入生产 Fallback；
2. 把新节点放入 `IPFly-测试上游`；
3. 每个节点执行 3～5 次静态 IP 测试；
4. 再执行 Anthropic HTTPS 测试；
5. 记录成功率和错误类型；
6. 更新生产脚本中的 `verifiedCandidateNames`；
7. 重新激活订阅；
8. 重新验证静态 IP 和 VS Code 的 DIRECT/静态分流。

建议至少保留 2～3 个来自不同线路、且端到端验证通过的节点。节点数量不是越多越好；未经验证的节点只会增加自动切换到坏链路的概率。

## 11. 参考资料

- [Mihomo `dialer-proxy` 官方说明](https://wiki.metacubex.one/en/config/proxies/dialer-proxy/)
- [Mihomo Listener 官方说明](https://wiki.metacubex.one/en/config/inbound/listeners/)
- [Mihomo Mixed Port 官方说明](https://wiki.metacubex.one/en/config/inbound/port/)
- [Mihomo Proxy Group 官方说明](https://wiki.metacubex.one/en/config/proxy-groups/)
- [Anthropic Claude Code 企业代理与网络地址说明](https://docs.anthropic.com/en/docs/claude-code/corporate-proxy)
