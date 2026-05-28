#!/bin/bash

load_config() {
  # 检查 jq 是否安装
  if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed. Please install jq first (e.g. brew install jq or sudo apt install jq)."
    return 1
  fi

  # 解析 json，将每个 key-value 转成 export KEY="VALUE" 的格式
  local exports
  exports=$(jq -r 'to_entries | .[] | "export \(.key)=\(.value | @sh)"' ~/.bytehouse_config.json)

  # 执行生成的 export 命令
  eval "$exports"
  echo "Configuration loaded from ~/.bytehouse_config.json"
}

load_config