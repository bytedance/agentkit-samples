
# 常见问题（FAQ）

本文档收集了使用火山引擎 CDN 域名创建时的常见问题和解答。

---

## Q1: 提示未找到 've' 命令怎么办？

A: 需要先安装火山引擎 CLI，请参考 [CLI 安装指南进行安装。

---

## Q2: 提示 CLI 版本过低怎么办？

A: 需要升级 CLI 到 v1.0.39 或以上版本，请参考 CLI 安装指南重新安装最新版本。

---

## Q3: 提示签名错误（SignatureDoesNotMatch）怎么办？

A: 检查 AK/SK 是否配置正确，可以使用以下命令重新配置：
```bash
ve configure set --access-key &lt;您的AK&gt; --secret-key &lt;您的SK&gt; --region cn-guangzhou --profile default
```

---

## Q4: 如何查看已添加的域名？

A: 可以使用以下命令查看：
```bash
ve cdn ListCdnDomains
```

---

## Q5: 如何查询域名配置详情？

A: 可以使用以下命令查看：
```bash
ve cdn DescribeCdnConfig --Domain "www.example.com"
```

---

## Q6: 如何自定义缓存规则？

A: 本脚本已支持智能推荐配置，会根据业务类型自动应用对应的配置规则。如需进一步自定义，可以：
1. 使用交互式脚本创建域名后，登录火山引擎控制台修改
2. 或者使用 `UpdateCdnConfig` API 进行修改
3. 或者参考 [参数说明](parameters.md) 中的推荐配置示例进行自定义

推荐配置包含：
- 缓存规则配置
- 智能压缩
- 分片回源
- 视频拖拽
- 缓存键优化等

---

## Q7: 可以添加多个源站吗？

A: 可以。交互式脚本已支持添加多个主源站和备源站。您可以按提示逐步添加源站，每个源站可以配置：
- 源站类型（IP/域名）
- 回源协议（http/https/followclient）
- 权重（1-100）

如果需要使用命令行方式，您可以在 OriginLines 数组中添加多个源站配置。

---

## Q8: 如何删除已添加的域名？

A: 可以使用以下命令删除：
```bash
ve cdn DeleteCdnDomain --Domain "www.example.com"
```

---

## Q9: 域名添加成功后，如何获取 CNAME？

A: 可以通过以下方式获取：
1. 登录火山引擎 CDN 控制台查看
2. 使用 CLI 查询：
```bash
ve cdn DescribeCdnConfig --Domain "www.example.com"
```

---

## Q10: 域名添加后多久生效？

A: 通常需要 1-5 分钟让域名配置生效。状态会从「配置中」变为「正常运行」。

