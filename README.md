<div align="center">

# WeChat Mini Program Shipping

**用可验证的发布闸门规划、构建和交付原生微信小程序，清楚分开代码、CloudBase、体验版、真机、支付与平台审核。**

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-111827.svg)](./SKILL.md)
[![WeChat Mini Program](https://img.shields.io/badge/WeChat-Mini%20Program-07C160.svg)](https://developers.weixin.qq.com/miniprogram/dev/framework/)
[![CloudBase](https://img.shields.io/badge/CloudBase-Release%20Gates-006EFF.svg)](https://cloud.tencent.com/product/tcb)
[![License](https://img.shields.io/badge/license-not%20specified-lightgrey.svg)](#license)

</div>

---

```text
in  小程序意图 | 现有项目 + 发布目标 + 平台约束
out milestone 合同 + 五层发布路径 + 验证矩阵 + 可审计证据包

fail 身份、AppID 或环境不明确 → blocked-external，停止发布动作并请求人工确认
fail CloudBase 健康检查或权限验证失败 → 保持受保护资源关闭，不降级为公开访问
fail 只有模拟器、上传或 mock 证据 → 不声称真机、支付、审核或正式发布已完成
fail 工作树无法由命名 commit 复现 → 停止交付并修复版本与证据链
```

## 这是什么

`wechat-miniprogram-shipping` 是一个面向 AI Agent 和项目负责人的发布工作流 skill。它把微信小程序交付拆成两个相连但不能混淆的管线：

- 前端：本地代码 → 微信开发者工具编译 → 上传 → 体验版 → 审核 → 发布；
- 后端：云函数、数据库、存储与权限 → CloudBase 部署 → 健康检查。

它帮助你定义 V1、建立 milestone 合同、设计权限和支付状态机、准备发布证据，并在外部条件不足时明确停下。

它不是：

- 可直接运行的小程序模板；
- 微信开发者工具或 CloudBase CLI 的替代品；
- 自动获取 AppID、OpenID、支付密钥或平台审核结果的工具；
- “测试通过就等于已上线”的发布捷径。

## 示例输出

当一个项目已通过本地验证和 CloudBase 部署，但尚未完成体验版与真机验收时，skill 应输出类似结论：

```text
结论：后端部署已验证，产品尚未达到用户可用状态。

状态：
- verified-software
- verified-cloud
- blocked-external: formal AppID / experience upload / device acceptance

需要负责人处理：
1. 在微信公众平台确认正式 AppID 与项目主体关联。
2. 使用微信开发者工具上传命名版本并保存体验版回执。
3. 由管理员账号和普通成员账号分别完成 iOS / Android 真机验收。

证据：
- commit: <named SHA>
- cloud health: <redacted receipt path>
- release checklist: <issue or local artifact path>
```

这里的关键不是措辞，而是证据边界：`verified-cloud` 不能替代 `verified-experience`，模拟器不能替代真机，mock 支付不能替代真实支付与结算。

## 五层发布模型

```text
┌────────────────────┐
│ 1. Local project   │  WXML / WXSS / JS / tests / cloudfunctions
└─────────┬──────────┘
          │ commit + named SHA
          ▼
┌────────────────────┐
│ 2. Git remote      │  可复现源码与审计历史
└─────────┬──────────┘
          │ compile exact local tree
          ▼
┌────────────────────┐
│ 3. DevTools        │  编译、模拟器检查、清缓存、上传
└─────────┬──────────┘
          │ upload version + note
          ▼
┌────────────────────┐
│ 4. WeChat platform │  体验版、审核、正式发布
└────────────────────┘

┌────────────────────┐
│ 5. CloudBase       │  云函数、数据库、存储、规则、健康检查
└────────────────────┘
```

前端页面变更走 `local → DevTools Compile → Simulator → DevTools Upload → WeChat experience`。后端变更走 `cloudfunctions → CloudBase deploy → health check`。如果前后端契约同时改变，两条管线都必须更新并分别取证。

## 快速开始

### 安装到 Codex

```bash
# 1. 克隆公共仓库
git clone https://github.com/zinan92/wechat-miniprogram-shipping.git

# 2. 安装 skill
mkdir -p "$HOME/.codex/skills/wechat-miniprogram-shipping"
cp -R wechat-miniprogram-shipping/SKILL.md \
  wechat-miniprogram-shipping/agents \
  wechat-miniprogram-shipping/references \
  "$HOME/.codex/skills/wechat-miniprogram-shipping/"

# 3. 确认文件完整
find "$HOME/.codex/skills/wechat-miniprogram-shipping" -maxdepth 2 -type f | sort
```

预期至少看到：

```text
.../wechat-miniprogram-shipping/SKILL.md
.../wechat-miniprogram-shipping/agents/openai.yaml
.../wechat-miniprogram-shipping/references/project-lessons.md
```

### 调用 skill

在新的 Codex 任务中明确写出：

```text
使用 $wechat-miniprogram-shipping，帮我规划这个原生微信小程序的 V1。
先建立 milestone 合同和风险地图，不要操作真实支付、平台审核或任何密钥。
```

接手已有项目时，可以这样调用：

```text
使用 $wechat-miniprogram-shipping 接管这个项目。
请分别核验本地代码、Git commit、开发者工具、微信体验版和 CloudBase，
只汇报有证据支持的状态，并列出 blocked-external 项。
```

## 工作流

| 阶段 | 关键动作 | 通过证据 | 必须停止的情况 |
|---|---|---|---|
| 合同 | 定义用户结果、V1、milestone、验收标准和禁区 | 独立 issue/合同 | 意图或范围仍不清楚 |
| Mock-first | 用同一服务边界跑通浏览、锁定内容和作者/会员主路径 | 可重复测试与确定性 seed data | mock 与 cloud 接口不一致 |
| 安全设计 | 明确身份、权限、内容、订单与幂等状态机 | fail-closed 规则与状态转移 | 客户端可决定角色、金额或支付成功 |
| CloudBase | 部署函数、集合、索引、存储规则和配置 | 依赖安全的健康检查 | 权限、依赖或运行时状态不明 |
| DevTools | 编译准确目录，检查模拟器，上传命名版本 | 版本、时间、SHA、工具版本 | 模拟器代码陈旧或目录不确定 |
| 体验与真机 | 管理员/会员、iOS/Android、弱网与关键路径验收 | 路由级设备矩阵 | 用模拟器替代真机结论 |
| 支付与审核 | 服务端核验支付事实，提交平台审核 | 支付回执与平台状态 | 只有客户端 callback 或 mock 结果 |

## 状态词汇

用精确状态代替笼统的“完成”或“上线”：

| 状态 | 能证明什么 | 不能证明什么 |
|---|---|---|
| `verified-software` | 本地测试、验证、审计通过 | CloudBase 或微信平台已生效 |
| `verified-cloud` | 指定环境的后端部署与健康检查通过 | 前端体验版已上传 |
| `verified-experience` | 指定版本可通过体验入口访问 | iOS/Android 全部通过 |
| `verified-device` | 记录中的真机矩阵通过 | 真实支付或平台审核通过 |
| `verified-payment` | 服务端验证的支付链路通过 | 平台审核或正式发布完成 |
| `verified-review` | 微信平台审核状态已读回 | 当前版本已正式发布，除非另有回执 |
| `blocked-external` | 缺少人、身份、平台或设备动作 | 不是软件失败，也不能被自动绕过 |

## 核心安全边界

### 身份与内容

- AppID、CloudBase env ID、OpenID、管理员角色、支付凭据和账号主体必须分别确认。
- 管理员必须满足 `role === 'admin' && status === 'active'`。
- 会员必须处于 active 状态且有效期晚于当前时间。
- 未知、缺失、冻结或过期状态一律拒绝访问。
- 受保护内容和图片不允许客户端直接读取；由服务端鉴权后签发短期 URL。

### 订单与支付

- 客户端支付回调不能直接开通会员。
- 服务端必须核验订单所有者、金额、支付方、交易和事件身份。
- 订单需要确定性幂等标识、原子 claim/CAS 或事务、初始化 lease 和持久化 pending 时间。
- 丢失的客户端结果应从支付服务商事实进行 reconciliation。
- 真实支付始终是独立的人类批准闸门。

### 秘密与平台动作

- 不提交 `.env.local`、运行时覆盖、AppSecret、支付密钥或私钥证书。
- 不要求人在聊天中粘贴秘密。
- QR 扫码、账号身份确认、法律条款、支付材料和审核决定由人完成。

## 最小证据包

每次准备体验版或正式发布时，至少保留：

```text
release-evidence/
├── milestone-issue.md         # Outcome、验收标准、范围和禁区
├── release-check.txt          # mock gate 的实际输出
├── release-check-cloud.txt    # configured/cloud gate 的实际输出
├── cloud-health.json          # 环境脱敏后的健康响应
├── upload-receipt.md          # version、timestamp、commit SHA、上传说明
├── device-matrix.md           # iOS / Android、账号角色、route-level 结果
└── blocked-external.md        # 尚未完成的人类或平台闸门
```

证据中不得包含 AppSecret、支付密钥、私钥证书、完整 OpenID 或其他敏感身份数据。

## 常见失败模式

| 症状 | 根因 | 应对方式 |
|---|---|---|
| 代码完成但无法上传 | 游客 AppID、正式 AppID 缺失或账号关联错误 | 分开软件与身份/平台闸门 |
| 前端“部署到 CloudBase”后用户看不到变化 | 混淆前端上传与后端部署 | 用 DevTools 上传前端，CloudBase 只部署后端/资源 |
| 把存储改为公开后图片才显示 | 把 FileID 当成授权 | 保持 server-only，鉴权后签发临时 URL |
| 云函数已上传但健康检查失败 | 依赖安装或包结构不适配运行时 | 构建准确 production package 再做启动检查 |
| 模拟器截图正确但当前代码已改变 | 截图早于 commit 或捕获陈旧 | 记录 SHA、时间、工具和设备，降级陈旧证据 |
| mock 支付通过便声称支付完成 | mock 只验证内部状态机 | 将真实支付、结算和退款单独验收 |

更多踩坑与反模式见 [`references/project-lessons.md`](./references/project-lessons.md)。

## 项目结构

```text
wechat-miniprogram-shipping/
├── SKILL.md                       # 完整工作流与操作边界
├── README.md                      # 人与 AI Agent 的能力入口
├── agents/
│   └── openai.yaml                # Codex skill 展示与默认 prompt 元数据
└── references/
    └── project-lessons.md         # 可迁移经验、失败模式和证据要求
```

## For AI Agents

本仓库提供工作流知识，不暴露 HTTP API、CLI 或 MCP server。Agent 应读取 `SKILL.md`，在项目自身的工具与权限边界内执行。

### Capability Contract

```yaml
name: wechat-miniprogram-shipping
version: 1
capability:
  summary: Plan and verify native WeChat Mini Program delivery across frontend, CloudBase, device, payment, and review gates.
  in:
    - product_intent
    - existing_project_optional
    - release_target
    - platform_constraints
  out:
    - milestone_contracts
    - release_path
    - verification_matrix
    - evidence_packet
    - external_blockers
  fail:
    - "identity or environment mismatch → blocked-external"
    - "protected data is directly readable → stop and fail closed"
    - "health or evidence is stale → do not promote status"
    - "real payment or review inferred from mock → reject claim"
entrypoint: SKILL.md
reference_files:
  - references/project-lessons.md
human_only_gates:
  - qr_scan
  - account_identity_confirmation
  - legal_terms
  - payment_credentials
  - platform_review_decision
status_vocabulary:
  - verified-software
  - verified-cloud
  - verified-experience
  - verified-device
  - verified-payment
  - verified-review
  - blocked-external
```

### Agent 调用示例

```text
1. 完整读取 SKILL.md。
2. 如果项目已有平台、上传、权限、UI 或发布失败，再读取 references/project-lessons.md。
3. 先写用户结果、首个有用时刻、V1 边界和风险地图。
4. 为每个可独立验收的 milestone 建立合同。
5. 分别验证 local、Git、DevTools、WeChat platform 与 CloudBase。
6. 只提升有新鲜证据支持的状态；外部闸门输出 blocked-external。
7. 最终只报告结论、需要负责人决策的事项和证据链接。
```

## 贡献

欢迎通过 issue 提交新的可迁移失败模式或发布经验。贡献时请：

1. 区分通用规则与特定账号、套餐、工具版本或环境事实；
2. 不提交 AppID、环境 ID、OpenID、支付资料、客户数据或业务源码；
3. 为新增规则提供可复验场景或脱敏证据；
4. 保持软件验证、目标环境证明与用户/平台验收三者分离。

## License

本仓库目前未声明开源许可证。公开可见不等于授予复制、修改或再分发权；如需复用，请先联系仓库所有者或等待许可证补充。
