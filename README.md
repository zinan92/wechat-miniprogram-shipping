<div align="center">

# Ask Park

**把原生微信小程序交付变成一条可验证、可回退、先过 QA 再交付的证据链。**

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-111827.svg)](./SKILL.md)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![QA](https://img.shields.io/badge/QA-independent-16A34A.svg)](./quality/QA-AGENT.md)
[![Visibility](https://img.shields.io/badge/repository-public-2563EB.svg)](https://github.com/zinan92/wechat-miniprogram-shipping)
[![License](https://img.shields.io/badge/license-not--specified-lightgrey.svg)](#许可)

</div>

---

```text
in  new | takeover | continuation | failure | release request
    + explicit state/receipts + repository, package, target or device evidence

out route decision + seven mental anchors + module contract
    + evidence receipt + QA verdict + next verifiable step

fail ambiguous intent/state conflict → ask Park; do not guess
fail missing/stale causal receipt → select earliest affected module and rewind
fail QA_FAIL or evidence drift → Diagnose → bounded repair → fresh QA
fail missing human/platform authority → blocked-external + named human gate
fail three repair attempts → needs-park-decision; no blind fourth attempt
```

Ask Park 是一个 Codex skill：它负责组织小程序交付，不是业务小程序模板。它不包含 AppID、环境 ID、支付资料、客户代码，也不会自动操作真实微信、CloudBase、支付、审核或正式发布系统。

## 这个 capability 解决什么问题

小程序项目常见的混乱不是“没有下一步”，而是把不同层级的证据混在一起：本地代码通过了，就误以为 CloudBase 已健康；上传了体验版，就误以为真机已验收；模拟器截图通过了，就误以为可以正式发布。

Ask Park 把这些判断拆成有顺序、有边界、有 receipt 的交付协议。它只让最早缺失或失效的模块成为当前模块，并把失败恢复、QA 和人工/平台动作放在明确的 gate 上。

## 示例输出

本仓库是 skill、纯 Python seam 和文档协议，没有 Web UI；当前没有可复用的产品截图素材。因此 README 展示真实的 deterministic CLI/read-back 形态，而不是伪造截图：

```text
ASK PARK · MINI PROGRAM SHIPPING

1. Plan               completed        [evidence valid]
2. Build              completed        [evidence valid]
3. CloudBase          completed        [evidence valid]
4. Experience         failed (current) [evidence invalid]
5. Device Acceptance  locked           [evidence absent]
6. Release            locked           [evidence absent]
7. Diagnose & Recover active           [outcome none]

Conclusion:
QA_FAIL 已进入 Diagnose；Ask Park 保持 Experience 为中断模块。
Next verifiable step:
确认根因和修复范围，再计算 causal receipt closure。
```

从 clean-clone receipt 提取的实际 canary 摘录包含：

```json
{
  "canary": {
    "router_loaded": true,
    "qa_paths_loaded": true,
    "module_contracts": 7
  },
  "missing_file": {
    "missing_file_rejected": true
  }
}
```

## 七个 mental anchors

```text
┌────────┐   ┌────────┐   ┌──────────┐   ┌────────────┐   ┌──────────────────┐   ┌─────────┐
│ Plan   │──▶│ Build  │──▶│ CloudBase│──▶│ Experience │──▶│ Device Acceptance│──▶│ Release │
└────────┘   └────────┘   └──────────┘   └────────────┘   └──────────────────┘   └─────────┘
      ▲              ▲              ▲              ▲                    ▲
      └──────────────┴──────────────┴──────────────┴────────────────────┘
                    ┌──────────────────────────────┐
                    │ Diagnose & Recover overlay   │
                    │ 保留中断模块，回退最早失效层 │
                    └──────────────────────────────┘

QA 是横向 gate，不是第八个模块。
```

用户只有一个入口：`$ask-park`。支持 slash 的宿主可以把同一个入口显示成 `/ask-park`，这不是第二条工作流。

## 快速开始

### 在当前 Codex 环境中

本机 canonical skill 已经是 `$ask-park`。直接在 Codex 中调用：

```text
使用 $ask-park，帮我从零规划一个原生微信小程序 V1。
先建立合同、风险地图和验收标准，不要操作真实支付、平台审核或任何密钥。
```

### 从 public repo 做隔离安装 proof

这一步只写入一个新建的临时 `CODEX_HOME`，不会覆盖当前 active skill：

```bash
git clone https://github.com/zinan92/wechat-miniprogram-shipping.git
cd wechat-miniprogram-shipping

CLEAN_CLONE_HOME="$(mktemp -d -t clean-clone-home-XXXXXX)"
python3 scripts/clean-clone.py \
  --repo-root . \
  --codex-home "$CLEAN_CLONE_HOME"
```

该 proof 会复制并校验完整 closure：`SKILL.md`、`agents/`、`modules/`、`quality/`、`references/`、`scripts/`、`tests/` 和 `fixtures/`。它会记录 manifest digest，加载 router、七个模块契约和 QA seams，并验证缺失依赖会失败。

这个 repo 没有应用依赖安装步骤，也没有需要填写的 `.env`；运行时 seam 以 Python 3.11+ 标准库为主。

## 常见调用场景

### 1. 新建小程序

```text
使用 $ask-park，开始一个新小程序。
目标是让用户第一次打开后完成一次核心任务。
先只做 Plan，给出 outcome、3–7 条验收标准、In/Out scope、禁区和风险地图。
```

输出是 issue-ready 的合同和六段主线适用性判断，不会直接开始写业务代码。

### 2. 接手已有项目

```text
使用 $ask-park 接管这个项目：/path/to/my-mini-program
分别核验 local、Git、DevTools、微信体验版、真机和 CloudBase。
只汇报有 receipt 支持的状态；找出最早缺失的证据。
```

它会沿用已有 state/receipts，避免因为换了一个 Agent 就从零重做。

### 3. UI 或前端包变化

```text
使用 $ask-park，检查这次 UI 修改是否可以进入体验版。
要求 Browser/DevTools 编译、before/after 截图、render matrix、source SHA 和 final compile provenance。
QA 未通过前不要交给我。
```

### 4. QA 失败或线上证据漂移

```text
使用 $ask-park，当前 QA_FAIL。
先不要直接修复，先判断根因、受影响模块和需要失效的 receipts。
最多做三次有边界的修复尝试。
```

QA 只报告观察结果；Diagnose 负责可证伪假设；Ask Park 才能失效 receipt、回退依赖和重新路由。

### 5. 发布前评估

```text
使用 $ask-park，评估当前项目是否达到 Release。
分别报告 verified-software、verified-cloud、verified-experience、verified-device，
以及仍需要我的 human gate。
```

技术访问权限不等于支付、审核、真机或正式发布授权。

## 功能一览

| 能力 | 作用 | 状态 |
| --- | --- | --- |
| Single-entry router | 从一个 `$ask-park` 入口分类 new/takeover/failure/continuation/release | 已完成 |
| Plan contract | outcome、验收标准、范围、禁区、复杂度、风险和 issue-ready stories | 已完成 |
| Build contract | mock-first、service boundary、授权 fail-closed、软件 receipt | 已完成 |
| CloudBase contract | 函数、权限、健康、Hosting、客户端契约分别核验 | 已完成 |
| Experience contract | Compile、Simulator、Upload、target read-back、Review、Release 分层 | 已完成 |
| Device Acceptance | 角色/设备/任务矩阵、像素、保护内容、弱网和过期路径 | 已完成 |
| Release contract | 支付适用性、审核、发布 read-back、smoke 和人工授权 | 已完成 |
| Diagnose & Recover | 根因假设、因果失效、最早回退、三次尝试上限 | 已完成 |
| Independent QA Agent | fresh-context evaluator、QA_PASS/FAIL/BLOCKED、human gate | 已完成 |
| Browser / DevTools QA | 截图、编译、上传、版本和 final compile provenance | 已完成 |
| Migration / cutover | clean-clone、manifest、atomic move、backup、rollback rehearsal | 已完成 |

## 证据和状态边界

每个 receipt 只证明生成它的模块，不会自动证明后续目标：

| 状态 | 可以证明 | 不能证明 |
| --- | --- | --- |
| `verified-software` | 本地代码、测试、审计、包和 source SHA | CloudBase、体验版、真机 |
| `verified-cloud` | 指定环境的后端健康、权限和 read-back | 前端包已上传或真机可用 |
| `verified-experience` | 指定 source/package 已成为可读回的体验版本 | 所有真机通过、正式发布 |
| `verified-device` | 记录中的设备/账号/任务矩阵 | 支付、审核、正式发布 |
| `QA_PASS` | 当前 QA gate 的自动化检查通过 | 全局 release 已授权 |
| `QA_BLOCKED` | 自动化通过，剩余动作确实属于人/平台/设备 | 自动化缺陷已经通过 |
| `QA_FAIL` | 存在可观察 defect 或 evidence drift | 可以直接自我修复或路由 |

模拟器截图、HTTP 200、CLI/server log 或一次设备观察，都不会自动升级为 `verified-device`。缺 Browser、DevTools 或 independent evaluator 是 `qa-prerequisite-missing`，不是 `QA_BLOCKED`。

## QA 工作流

```text
候选 source/package
        │
        ▼
QA-1：candidate + tests + Browser/DevTools render matrix
        │
        ▼
QA-2：target package + upload/read-back + final compile
        │
 ┌──────┼──────────┐
 ▼      ▼          ▼
PASS  BLOCKED     FAIL
 │      │          │
 ▼      ▼          ▼
继续   最小 human   Diagnose → 修复 → causal invalidation
主线   gate         → fresh candidate → fresh evaluator
```

独立 evaluator 不修改代码、不路由模块、不失效 receipt、不降低验收标准。三次失败仍未恢复时，结果是 `needs-park-decision`，而不是自动进行第四次尝试。

详细契约：

- [Independent QA Agent](./quality/QA-AGENT.md)
- [QA → Diagnose → Ask Park](./quality/qa-routing.md)
- [Browser QA](./quality/browser-qa.md)
- [DevTools QA](./quality/devtools-qa.md)
- [独立 forward evaluation](./quality/forward-evaluation.md)
- [孤立 end-to-end trial](./quality/isolated-trial.md)

## 升级和回滚边界

升级时先 `git pull`，再重复 clean-clone proof；不要直接覆盖一个未知的 active skill 目录。实际 installed-path 切换由 [`scripts/installed-cutover.py`](./scripts/installed-cutover.py) 负责，它要求目标是已盘点 scanned root 的直接子目录，并在移动前生成 root 外 backup。

旧 `$wechat-miniprogram-shipping` 只作为迁移历史/可恢复 backup 记录，不是 active alias。当前安装 read-back 是一个 `$ask-park`、零个启用的旧 identity。

回滚是 operator-only 流程。公共 receipt 不保存本机路径，因此不能从 README 猜路径，也不要直接调用底层文件移动函数。操作者必须先用本机 selector 和 S16C receipt 确认 legacy/canonical/backup 的作用域，再按 wrapper 的 scope checks 操作；回滚后重新运行 selector read-back、clean-clone 和 installed canary。这是 skill 安装回滚，不是小程序或平台发布回滚。

## 技术栈

| 层级 | 技术 | 用途 |
| --- | --- | --- |
| Skill host | Codex skill metadata | 暴露唯一 `$ask-park` 入口 |
| Runtime seam | Python 3.11+ 标准库 | router、state lifecycle、QA、migration、cutover |
| Contracts | Markdown + YAML + JSON | 模块输入/输出、证据、人工 gate 和 failure outcomes |
| Tests | `unittest` + hermetic fixtures | 无网络、无凭据、无外部副作用的行为验证 |
| Evidence | redacted JSON receipts | manifest、canary、selector、rollback 和 public read-back |

本仓库没有 HTTP API、MCP server 或常驻服务；它由 Codex 的 skill invocation 驱动，脚本只提供可测试的本地 seam。

## 项目结构

```text
wechat-miniprogram-shipping/
├── SKILL.md                    # Ask Park 总入口和 operating loop
├── agents/openai.yaml          # Codex skill metadata
├── modules/                    # 01 Plan ... 07 Diagnose 契约
├── references/                 # router、state、evidence、human-gate、transition
├── quality/                    # QA Agent、Browser/DevTools、trial、migration 契约
├── scripts/                    # 可执行 router、lifecycle、QA、clean-clone、cutover seam
├── fixtures/                   # state、receipt、failure、forward-eval fixtures
├── tests/                      # 模块、QA、migration、cutover 和 package tests
├── receipts/                   # sanitized installed/public read-back
├── tools/                      # final package-layout validator
├── README.md                   # 本 capability 文档
└── REGISTRY.md                 # durable handoff 和完成状态
```

## For AI Agents

把这个 repo 当作一个“有状态、证据门控的交付路由器”，而不是一个可以随意调用的代码生成模板：

```yaml
name: ask-park
version: "1"
capability:
  summary: Route WeChat Mini Program shipping through evidence-gated modules and an independent QA gate.
  in: route class + explicit state/receipts + repository/package/target/device evidence
  out: route decision + module contract + evidence receipt + QA verdict + next verifiable step
  fail:
    - ambiguous intent or conflicting state -> ask for Park decision
    - missing or stale causal receipt -> rewind to earliest affected module
    - QA_FAIL -> Diagnose, bounded repair, and fresh evaluator
    - missing human/platform authority -> blocked-external with a named gate
    - three failed repair attempts -> needs-park-decision
skill_invocation: "$ask-park"
route_classes: [new, takeover, failure, continuation, release]
sequential_modules: [plan, build, cloudbase, experience, device, release]
overlay: diagnose-and-recover
qa_verdicts: [QA_PASS, QA_FAIL, QA_BLOCKED]
```

Agent 调用应明确 route class 和证据边界：

```text
使用 $ask-park，route class = takeover。
项目路径：/path/to/project
已知证据：Build receipt、CloudBase health read-back、体验版 alias。
先读取 state 和 receipts，选择最早缺失 exit contract 的模块。
不要猜测当前模块，不要请求或打印密钥，不要在 QA_FAIL 后直接宣布可以发布。
```

每个 substantive response 都应包含四个 operator sections：`Conclusion`、`Current module and evidence`、`Decision or action needed from Park`、`Next verifiable step`。

## 开发者验证

```bash
python3 tools/validate-package-layout.py --root . --mode final --json

# 测试目录使用 installed-cutover/ 等可读名称，不依赖 unittest package discovery
python3 - <<'PY'
from pathlib import Path
import subprocess
import sys

for test_file in sorted(Path("tests").rglob("test_*.py")):
    subprocess.run([sys.executable, str(test_file)], check=True)
PY

python3 -m py_compile $(find scripts -type f -name '*.py' -print)
git diff --check
gitleaks detect --no-banner --source . --redact
```

当前 public read-back：仓库 `main`、根目录 canonical identity `$ask-park`、一个启用的 `$ask-park`、零个启用的旧 identity。完整证据见 [`receipts/public-readback.json`](./receipts/public-readback.json) 和 [`receipts/installed-cutover.json`](./receipts/installed-cutover.json)。

## 相关契约和设计

- [Ask Park 七模块架构](./docs/superpowers/specs/2026-08-20-ask-park-seven-module-architecture-design.md)
- [Independent QA Gate 设计](./docs/superpowers/specs/2026-08-24-ask-park-independent-qa-gate-design.md)
- [Implementation plan](./docs/superpowers/specs/2026-08-24-ask-park-implementation-plan.md)
- [Router contract](./references/router.md)
- [Status contract](./references/status-contract.md)
- [Evidence contract](./references/evidence-contract.md)
- [Human gates contract](./references/human-gates-contract.md)
- [Transition contract](./references/transition-contract.md)

## 当前状态

- Public repository：[`zinan92/wechat-miniprogram-shipping`](https://github.com/zinan92/wechat-miniprogram-shipping)
- Canonical invocation：`$ask-park`（宿主可显示为 `/ask-park`）
- Implementation queue：S00–S16D 完成
- Production claim：无；下一步是单独定义、人工批准的非生产 real-use trial
- GitHub handoff：[`REGISTRY.md`](./REGISTRY.md)

## 许可

当前仓库未声明特定开源许可证；在公开分发或公司内部复用前，请先补充明确许可。
