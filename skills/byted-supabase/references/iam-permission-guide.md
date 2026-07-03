# 权限被拒（IAM 授权不足）排查

> 命令统一用 `byted-supabase-cli`（已别名为 `supabase` 亦可）。
>
> 🔴 **最高原则：如实报错，绝不臆造 IAM 细节。** 本产品子账号授权固定为 **`AIDAPFullAccess` + `ServiceRoleForAIDAP`** 两项（见下文第 2 步），照此给即可；**除此之外**不要编造别的策略名、权限项名、控制台 URL 或授权步骤。不确定的名字/路径一律以火山引擎控制台实际项与官方文档为准（对应 SKILL.md[核心原则 1]）——宁可说"需到 IAM 控制台核对对应权限项"，也不要猜。

## 何时属于本文场景

命令返回 `AccessDenied` / `Forbidden` / "无权限" / "未授权" 一类错误时（**创建 workspace 等写操作最常触发**，报错里通常带被拒的 Action 名）。

## 第 1 步：先分清「凭据」还是「授权」

| 现象 | 判断 | 处理 |
|------|------|------|
| `login` 失败 / 全部命令都报错 / 提示凭据无效 | **凭据问题** | 重新 `login` 或 `configure set` AK/SK、核对 region（见 SKILL.md「鉴权与前置条件」） |
| 能 `login`、`projects list` 等多数命令可跑通，**仅个别命令被拒** | **IAM 授权不足** | 进入第 2 步，**不要**反复重配凭据 |

> 关键：授权不足**不是** AK/SK / region 配错。反复重登录、重配凭据解决不了授权问题。

## 第 2 步：按账号类型分流

先判断当前用的是**主账号**还是**子账号（IAM 用户）**，两者处置完全不同。

### 主账号（未授权 / 首次使用）

多为**首次使用该产品、服务尚未开通或未一键授权**。用主账号进入授权页面，按引导开通 / 一键授权即可，通常一步到位：

- 授权页面：<https://console.volcengine.com/aidap/region:aidap+cn-beijing/workspaces?scene=create>（`cn-beijing` 为实例所在 region，按需替换）

完成后重跑原命令验证（对应 SKILL.md[核心原则 2] —— 没验证＝没完成）。

### 子账号（IAM 用户）—— 需主账号/管理员授权

子账号**无法自助开通**，必须由**主账号**授权。授权逻辑：

1. **用主账户登录**火山引擎。
2. 进入 **访问控制 → 用户管理**（该菜单下有【用户】【用户组】【安全设置】），点 **【用户】**；直达链接：<https://console-stable.volcanicengine.com/iam/identitymanage/user>
3. 在【用户】列表里**搜索**目标子账户，找到后给该用户点 **【添加权限】**。
4. **添加以下两个授权**：
   - **`AIDAPFullAccess`** —— 本产品（AI 原生 BaaS 平台 / AIDAP）的完整访问权限策略。
   - **`ServiceRoleForAIDAP`** —— 本产品运行所需的服务关联角色。
5. 授权生效后，让子账号重跑原命令验证（对应 SKILL.md[核心原则 2] —— 没验证＝没完成）。

> **`AIDAPFullAccess` + `ServiceRoleForAIDAP` 是本产品固定要加的两项，照此给即可，不要另猜别的策略名。** 若这两个名字在控制台面板里检索不到（版本/命名差异），再按产品名在授权面板检索或查官方[常见系统预设策略](https://www.volcengine.com/docs/6257/1253730)核对，以面板实际存在的为准。

## 官方文档

- [访问控制（IAM）· 创建用户并授权](https://www.volcengine.com/docs/6257/94013)
- [访问控制（IAM）· 常见系统预设策略](https://www.volcengine.com/docs/6257/1253730)
- [访问控制（IAM）· 基本概念（用户 / 用户组 / 策略）](https://www.volcengine.com/docs/6257/64963)
