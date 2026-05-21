# 支持的云产品

- 来源页面：[支持的云产品](https://www.volcengine.com/docs/6408/1115078?lang=zh)
- 页面主题：云监控已接入的云产品、对应 `Namespace` 与监控数据保存时长
- 页面更新时间：`2026.03.09 11:24:59`

## 页面说明

支持的云产品如下。云产品已接入云监控服务，当您使用该云产品后，系统会自动开启该产品的监控，并上报监控指标。

## 云产品列表

| 产品分类 | 产品名称 | Namespace | 数据保存时长（天） |
| --- | --- | --- | --- |
| 弹性计算 | 云服务器 | `VCM_ECS` | 60 |
| 弹性计算 | 专有宿主机 | `VCM_DDH` | 60 |
| 弹性计算 | AgentKit-MCP服务 | `VCM_AgentKitMcp` | 30 |
| 弹性计算 | AgentKit-智能体运行时 | `VCM_AgentKitRuntime` | 30 |
| 弹性计算 | AgentKit-工具 | `VCM_AgentKitSandboxTool` | 30 |
| 弹性计算 | AgentKit-MCP工具集 | `VCM_AgentKitMcpToolset` | 30 |
| 容器 | 容器服务 | `VCM_VKE` | 30 |
| CDN 与加速 | 内容分发网络 | `VCM_CDN` | 30 |
| CDN 与加速 | 全站加速 | `VCM_DCDN` | 30 |
| CDN 与加速 | 全球加速 | `VCM_GA` | 30 |
| CDN 与加速 | 边缘联网 SD-WAN | `VCM_SDWAN` | 30 |
| CDN 与加速 | 边缘计算-边缘智能 | `VCM_VEI` | 30 |
| 视频云 | 视频点播 | `VCM_VOD` | 30 |
| 视频云 | 视频点播-CDN | `VCM_VODCDN` | 30 |
| 视频云 | veImageX | `VCM_veImageX` | 30 |
| 视频云 | 视频直播 | `VCM_LIVE` | 60 |
| Serverless | 函数服务 | `VCM_veFaaS` | 30 |
| 数据库 | 数据库传输服务 DTS | `VCM_DTS` | 30 |
| 数据库 | 表格数据库 HBase 版 | `VCM_HBase` | 30 |
| 数据库 | 表格数据库 HBase 版-多可用区 | `VCM_MultiazHBase` | 30 |
| 数据库 | 文档数据库 MongoDB 版-副本集 | `VCM_MongoDB_Replica` | 30 |
| 数据库 | 文档数据库 MongoDB 版-分片集 | `VCM_MongoDB_Sharded_Cluster` | 30 |
| 数据库 | 云数据库 MySQL Sharding 版 | `VCM_MySQL_Sharding` | 30 |
| 数据库 | 云数据库 MySQL 版 | `VCM_RDS_MySQL` | 30 |
| 数据库 | 云数据库 PostgreSQL 版 | `VCM_RDS_PostgreSQL` | 30 |
| 数据库 | 云数据库 RDS SQL Server 版 | `VCM_RDS_SQLServer` | 30 |
| 数据库 | 云数据库 veDB MySQL 版 | `VCM_veDB_MySQL` | 30 |
| 数据库 | 缓存数据库 Redis 版-社区版 | `VCM_Redis` | 30 |
| 数据库 | 缓存数据库 Redis 版-企业版 | `VCM_Redis_Enterprise` | 30 |
| 数据库 | 图数据库 veGraph | `VCM_veGraph_db` | 30 |
| 存储 | 大数据文件存储 | `VCM_CFS` | 30 |
| 存储 | 弹性块存储 | `VCM_EBS` | 60 |
| 存储 | 半托管文件缓存 SFCS | `VCM_SFCS` | 30 |
| 存储 | 文件存储 NAS 极速型 | `VCM_FileNAS` | 30 |
| 存储 | 文件存储 NAS 容量型 | `VCM_veFileNAS` | 30 |
| 存储 | 文件存储 NAS 缓存型 | `VCM_veFileNAS_Cache` | 30 |
| 存储 | 文件存储 vePFS | `VCM_vePFS` | 90 |
| 存储 | 对象存储 | `VCM_TOS` | 60 |
| 存储 | 日志服务 | `VCM_TLS` | 30 |
| 中间件 | 云原生消息引擎 | `VCM_BMQ` | 30 |
| 中间件 | 云搜索服务 | `VCM_ESCloud` | 30 |
| 中间件 | 云搜索服务 Serverless 版 | `VCM_ESCloud_Serverless` | 30 |
| 中间件 | 配置中心-Etcd | `VCM_ConfigCenter_Etcd` | 30 |
| 中间件 | 配置中心-Zookeeper | `VCM_ConfigCenter_ZooKeeper` | 30 |
| 中间件 | 托管 Prometheus | `VCM_Prometheus` | 30 |
| 中间件 | 消息队列 Kafka 版 | `VCM_Kafka` | 30 |
| 中间件 | 消息队列 RabbitMQ 版 | `VCM_RabbitMQ` | 30 |
| 中间件 | 消息队列 RocketMQ 版 | `VCM_RocketMQ` | 30 |
| 网络 | 应用型负载均衡 | `VCM_ALB` | 60 |
| 网络 | Anycast 公网IP | `VCM_AnycastEIP` | 30 |
| 网络 | 共享带宽包 | `VCM_BandwidthPackage` | 60 |
| 网络 | 云企业网 | `VCM_CEN` | 30 |
| 网络 | 负载均衡 | `VCM_CLB` | 60 |
| 网络 | 负载均衡独占集群 | `VCM_CLB_EC` | 30 |
| 网络 | 云连接器 | `VCM_CloudConnector` | 30 |
| 网络 | 专线连接-物理专线 | `VCM_DirectConnectConnection` | 30 |
| 网络 | 专线连接-专线网关 | `VCM_DirectConnectGateway` | 30 |
| 网络 | 专线连接-虚拟接口 | `VCM_DirectConnectVIF` | 30 |
| 网络 | 公网 IP | `VCM_EIP` | 60 |
| 网络 | 网际快车 | `VCM_Fasttrack` | 30 |
| 网络 | IPsec 连接 | `VCM_IPsec` | 30 |
| 网络 | 互联网通道-公网带宽 | `VCM_InternetTunnelBandwidth` | 30 |
| 网络 | 互联网通道虚拟接口 | `VCM_InternetTunnelVirtualInterface` | 30 |
| 网络 | Vortex IP | `VCM_Vortex_IP` | 30 |
| 网络 | 字节互联服务-网络 | `VCM_BIS` | 30 |
| 网络 | IPV6 公网带宽 | `VCM_Ipv6AddressBandwidth` | 30 |
| 网络 | IPV6 网关 | `VCM_Ipv6Gateway` | 30 |
| 网络 | NAT 网关 | `VCM_NAT` | 30 |
| 网络 | NAT64 网关 | `VCM_NAT64` | 30 |
| 网络 | 私网连接-终端节点 | `VCM_PrivateLinkEndpoint` | 30 |
| 网络 | 私网连接-终端节点服务 | `VCM_PrivateLinkEndpointService` | 30 |
| 网络 | 私网连接-私网连接网关 | `VCM_PrivateLinkGateway` | 30 |
| 网络 | 私网 NAT 网关 | `VCM_PrivateNAT` | 30 |
| 网络 | 中转路由器 | `VCM_TransitRouter` | 30 |
| 网络 | 中转路由器带宽包 | `VCM_TransitRouterBandwidthPackage` | 30 |
| 网络 | VPN 连接 | `VCM_VPN` | 30 |
| 数据中台 | ByteHouse 云数仓版 | `VCM_ByteHouse` | 30 |
| 数据中台 | ByteHouse 企业版 | `VCM_ByteHouse_Ce` | 30 |
| 数据中台 | ByteHouse 云数仓版 - 数据导入 | `VCM_ByteHouse_DataLoading` | 30 |
| 数据中台 | 大数据研发治理套件 | `VCM_DataLeap` | 30 |
| 数据中台 | 全域数据集成 | `VCM_DataSail` | 30 |
| 数据中台 | 全域数据集成-资源组 | `VCM_DataSail_ResourceGroup` | 30 |
| 数据中台 | 全域数据集成-采集Topic | `VCM_DataSail_Topic` | 30 |
| 数据中台 | E-MapReduce | `VCM_EMR` | 30 |
| 数据中台 | E-MapReduce on VKE | `VCM_EMR_ON_VKE` | 30 |
| 数据中台 | E-MapReduce StarRocks | `VCM_EMR_StarRocks` | 30 |
| 数据中台 | 流式计算 Flink 版 | `VCM_Flink` | 30 |
| 数据中台 | 批式计算 Spark 版 | `VCM_Spark` | 30 |
| 数据中台 | 湖仓一体分析服务 | `VCM_LAS` | 30 |
| 安全 | DDoS 高防 | `VCM_Adv_DDoS_Protection` | 30 |
| 安全 | DDoS 高防-域名 | `VCM_Adv_DDoS_Protection_Domain` | 30 |
| 研发中台 | 物联网平台 | `VCM_IoT` | 30 |
| 人工智能与算法 | 向量数据库 | `VCM_VikingDB` | 30 |
| 域名与网站 | TrafficRoute-移动解析HTTPDNS | `VCM_TrafficRoute_HTTPDNS` | 30 |

## 备注

- 本文件用于在仓库内保留页面内容的 Markdown 版本，便于离线查阅和引用。
- 若后续官方页面更新，请以来源页面为准，并按需重新同步本文件。
