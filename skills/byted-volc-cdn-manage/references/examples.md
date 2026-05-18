
# 使用场景示例

本文档提供火山引擎 CDN 域名创建的常见使用场景示例。

---

## 场景 1：下载加速 + IP 源站

```bash
BODY='{
  "Domain": "download.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "203.0.113.10",
            "InstanceType": "ip",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "download"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 2：网页加速 + 域名源站

```bash
BODY='{
  "Domain": "www.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "origin.example.com",
            "InstanceType": "domain",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "web"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 3：全球加速

```bash
BODY='{
  "Domain": "global.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "1.1.1.1",
            "InstanceType": "ip",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "global",
  "ServiceType": "web"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 4：自定义回源端口

```bash
BODY='{
  "Domain": "custom-port.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "origin.example.com",
            "InstanceType": "domain",
            "OriginType": "primary",
            "HttpPort": "8080",
            "HttpsPort": "8443"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "web"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 5：HTTPS 回源

```bash
BODY='{
  "Domain": "https-origin.example.com",
  "OriginProtocol": "https",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "origin.example.com",
            "InstanceType": "domain",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "web"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 6：自定义回源 Host

```bash
BODY='{
  "Domain": "custom-host.example.com",
  "OriginHost": "img.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "origin.example.com",
            "InstanceType": "domain",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "web"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 7：多源站（主备源站）

```bash
BODY='{
  "Domain": "multi-origin.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "primary.example.com",
            "InstanceType": "domain",
            "OriginType": "primary",
            "Weight": "100"
          },
          {
            "Address": "backup.example.com",
            "InstanceType": "domain",
            "OriginType": "backup",
            "Weight": "100"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "web"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 8：对象存储源站（TOS）

```bash
BODY='{
  "Domain": "tos-origin.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "my-bucket.tos-cn-guangzhou.volces.com",
            "InstanceType": "tos",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "download"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 9：私有对象存储源站（带鉴权）

```bash
BODY='{
  "Domain": "private-tos.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "my-private-bucket.tos-cn-guangzhou.volces.com",
            "InstanceType": "tos",
            "OriginType": "primary",
            "PrivateBucketAccess": true,
            "PrivateBucketAuth": {
              "Switch": true,
              "TosAuthInformation": {
                "AccessKeyId": "your-access-key-id",
                "AccessKeySecret": "your-access-key-secret"
              },
              "AuthType": "tos"
            }
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "download"
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 10：视频点播 + 推荐配置

```bash
BODY='{
  "Domain": "video.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "1.1.1.1",
            "InstanceType": "ip",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "video",
  "Cache": [
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 2592000,
        "DefaultPolicy": "default"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    },
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 0,
        "DefaultPolicy": "no_cache"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "filetype",
            "Operator": "match",
            "Type": "url",
            "Value": "php;jsp;asp;aspx"
          }
        ]
      }
    }
  ],
  "Range": {
    "Switch": true,
    "RangeSize": 1,
    "Unit": "MB"
  },
  "MultiRange": {
    "Switch": true
  },
  "CacheKey": [
    {
      "CacheKeyAction": {
        "CacheKeyComponents": [
          {
            "Action": "exclude",
            "IgnoreCase": false,
            "Object": "queryString",
            "Subobject": "*"
          }
        ]
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    },
    {
      "CacheKeyAction": {
        "CacheKeyComponents": [
          {
            "Action": "include",
            "IgnoreCase": true,
            "Object": "queryString",
            "Subobject": "*"
          }
        ]
      },
      "Condition": {
        "ConditionRule": [
          {
            "Name": "",
            "Object": "directory",
            "Operator": "match",
            "Type": "url",
            "Value": "/"
          }
        ]
      }
    }
  ],
  "FollowRedirect": true,
  "VideoDrag": {
    "Switch": true
  }
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 11：网页加速 + 推荐配置

```bash
BODY='{
  "Domain": "www.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "origin.example.com",
            "InstanceType": "domain",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "web",
  "Cache": [
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 2592000,
        "DefaultPolicy": "default"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    },
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 0,
        "DefaultPolicy": "no_cache"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "filetype",
            "Operator": "match",
            "Type": "url",
            "Value": "php;jsp;asp;aspx"
          }
        ]
      }
    }
  ],
  "Compression": {
    "Switch": true,
    "CompressionRules": [
      {
        "CompressionAction": {
          "CompressionType": ["gzip", "br"],
          "CompressionFormat": "default",
          "CompressionTarget": "*",
          "MinFileSizeKB": 0
        }
      }
    ]
  },
  "PageOptimization": {
    "PageOptimizationAction": "on"
  }
}'

ve cdn AddCdnDomain --body "$BODY"
```

---

## 场景 12：下载加速 + 推荐配置

```bash
BODY='{
  "Domain": "download.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "203.0.113.10",
            "InstanceType": "ip",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "download",
  "Cache": [
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 2592000,
        "DefaultPolicy": "default"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    },
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 0,
        "DefaultPolicy": "no_cache"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "filetype",
            "Operator": "match",
            "Type": "url",
            "Value": "php;jsp;asp;aspx"
          }
        ]
      }
    }
  ],
  "Range": {
    "Switch": true,
    "RangeSize": 1,
    "Unit": "MB"
  },
  "MultiRange": {
    "Switch": true
  },
  "CacheKey": [
    {
      "CacheKeyAction": {
        "CacheKeyComponents": [
          {
            "Action": "exclude",
            "IgnoreCase": false,
            "Object": "queryString",
            "Subobject": "*"
          }
        ]
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    },
    {
      "CacheKeyAction": {
        "CacheKeyComponents": [
          {
            "Action": "include",
            "IgnoreCase": true,
            "Object": "queryString",
            "Subobject": "*"
          }
        ]
      },
      "Condition": {
        "ConditionRule": [
          {
            "Name": "",
            "Object": "directory",
            "Operator": "match",
            "Type": "url",
            "Value": "/"
          }
        ]
      }
    }
  ],
  "FollowRedirect": true
}'

ve cdn AddCdnDomain --body "$BODY"
```

