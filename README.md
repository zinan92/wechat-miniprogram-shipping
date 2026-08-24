<div align="center">

# Ask Park

**把微信小程序交付变成一条可验证、可回退、先过 QA 再交付的证据链。**

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-111827.svg)](./SKILL.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![QA](https://img.shields.io/badge/QA-independent-16A34A.svg)](./quality/QA-AGENT.md)
[![License](https://img.shields.io/badge/license-not--specified-lightgrey.svg)](#许可)

</div>

---

```text
in  新建 | 接手 | 继续 | 失败恢复 | 发布的小程序任务 + 显式状态/证据
out Ask Park 路由 + 七个 mental anchors + receipts + 独立 QA 结果

fail 身份/权限/平台动作缺失 → blocked-external 或 human gate
fail QA_FAIL / stale receipt / 版本漂移 → Diagnose → 修复 → fresh QA
fail 三次修复仍失败 → needs-park-decision，拒绝盲目第四次
fail 只有模拟器或上传证据 → 不声称 verified-device / 正式发布
```

Ask Park 是一个 Codex skill，不是业务小程序模板。它不包含 AppID、环境 ID、支付资料、客户代码，也不会自动操作真实微信、CloudBase、支付或审核系统。

## 什么时候使用

- 新建小程序：从目标和边界开始，生成 Plan → Build → CloudBase → Experience → Device Acceptance → Release 路径。
- 接手已有项目：读取仓库、状态和 receipts，找出最早缺失或失效的证据，不从零重做。
- UI 或前端包变化：要求 Browser/DevTools 编译、截图、矩阵、source SHA 和 final compile provenance。
- 后端变化：分别核验函数、权限、健康检查、Hosting 和客户端契约，不把后端部署当成前端已生效。
- 失败恢复：QA 只给事实和 advisory；Diagnose 确认原因；Ask Park 才能 invalidation、rewind 和路由。
- 账号、真机、提审、支付、发布动作：停在最小 human gate，技术访问不等于授权。

## 七个 mental anchors

```text
1 Plan ─▶ 2 Build ─▶ 3 CloudBase ─▶ 4 Experience ─▶ 5 Device Acceptance ─▶ 6 Release
  ▲              ▲                 ▲                  ▲
  └──────────────┴──────── Diagnose & Recover overlay ─┘
```

QA 是横向 gate，不是第八个模块；`/ask-park`（或 `$ask-park`）是唯一用户入口。

## 示例输出

```text
ASK PARK · MINI PROGRAM SHIPPING

1. Plan               completed        [evidence valid]
2. Build              completed        [evidence valid]
3. CloudBase          completed        [evidence valid]
4. Experience         failed (current) [evidence invalid]
5. Device Acceptance  locked           [evidence absent]
6. Release            locked           [evidence absent]
7. Diagnose & Recover active           [outcome none]

结论：QA_FAIL 已进入 Diagnose；Ask Park 保持 Experience 为中断模块。
下一步：确认根因和修复范围，再计算 causal receipt closure。
```

## 安装

匿名 clean clone 后，按下面命令复制完整 closure。`CODEX_HOME` 可指向隔离目录；默认是 `$HOME/.codex`。

```bash
git clone https://github.com/zinan92/wechat-miniprogram-shipping.git
cd wechat-miniprogram-shipping

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
INSTALL_ROOT="$CODEX_HOME/skills/ask-park"
mkdir -p "$INSTALL_ROOT"
cp -R SKILL.md agents modules quality references scripts tests fixtures "$INSTALL_ROOT/"

CLEAN_CLONE_HOME="$(mktemp -d)"
python3 scripts/clean-clone.py --repo-root . --codex-home "$CLEAN_CLONE_HOME"
```

安装 closure 包含：`SKILL.md`、`agents/openai.yaml`、`modules/`、`quality/`、`references/`、`scripts/`、`tests/`、`fixtures/`。不要只复制 README 或单个 SKILL.md。

## 调用

```text
使用 $ask-park，帮我从零规划一个原生微信小程序 V1。
先建立合同、风险地图和验收标准，不要操作真实支付、平台审核或任何密钥。
```

接手已有项目：

```text
使用 $ask-park 接管这个项目。
分别核验 local、Git、DevTools、微信体验版、真机和 CloudBase，
只汇报有 receipt 支持的状态；QA 未通过前不要交给我。
```

## 证据与状态边界

| 结果 | 可以证明 | 不能证明 |
|---|---|---|
| `verified-software` | 本地测试、审计、包和 source SHA | CloudBase/体验版/真机 |
| `verified-cloud` | 指定环境后端健康与权限结果 | 前端包已上传 |
| `verified-experience` | 指定体验版本可读回 | 所有真机通过 |
| `verified-device` | 记录中的设备/账号矩阵 | 支付、审核、正式发布 |
| `QA_PASS` | 当前 gate 的自动化检查通过 | 全局 release 已授权 |
| `QA_BLOCKED` | 自动化通过，剩余动作确实人/平台专属 | 自动化缺陷或缺工具 |
| `QA_FAIL` | 有可观察 defect/evidence drift | 不能直接路由或自我修复 |

模拟器截图永远不会升级为 `verified-device`。缺 DevTools、Browser 或 independent evaluator 是 `qa-prerequisite-missing`，不是 `QA_BLOCKED`。

## QA 工作流

1. QA-1：候选 commit、测试、Browser/DevTools render matrix。
2. QA-2：目标包/体验版本、live asset、upload note、read-back、final compile。
3. QA_FAIL：finding/advisory → Diagnose → Ask Park causal invalidation → 新 candidate → fresh evaluator。
4. QA_BLOCKED：只有自动化完全通过后，才能准备 human gate。

详细契约：

- [QA Agent](./quality/QA-AGENT.md)
- [QA → Diagnose → Ask Park](./quality/qa-routing.md)
- [Browser QA](./quality/browser-qa.md)
- [DevTools QA](./quality/devtools-qa.md)
- [独立 forward evaluation](./quality/forward-evaluation.md)
- [孤立 end-to-end trial](./quality/isolated-trial.md)
- [migration / rollback](./quality/migration.md)

## 开发者验证

```bash
python3 tools/validate-package-layout.py --root . --mode final --json
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile $(find scripts -type f -name '*.py' -print)
git diff --check
gitleaks detect --no-banner --source . --redact
```

`scripts/clean-clone.py` 会在隔离 `CODEX_HOME` 中记录每个安装文件 digest、加载 router/七个模块/QA seams，并验证缺失依赖会失败。`scripts/migration.py` 只用于 staging/inventory；S16C 才处理实际 installed-path canary 和可回退 cutover。

## 许可

当前仓库未声明特定开源许可证；请在公开分发前补充明确许可。
