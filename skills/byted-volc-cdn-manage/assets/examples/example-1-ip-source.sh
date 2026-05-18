
#!/bin/bash

# 示例 1: 下载加速 + IP 源站
# 运行方式: bash example-1-ip-source.sh

echo "示例 1: 下载加速 + IP 源站"
echo ""

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

echo "请求 Body:"
echo "$BODY"
echo ""
echo "执行命令:"
echo "ve cdn AddCdnDomain --body \"\$BODY\""
echo ""
echo "注意: 请将域名和源站地址替换为您实际的地址后再运行"

