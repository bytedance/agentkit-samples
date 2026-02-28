import subprocess
import os
import sys
import time
import signal
import re

# 配置：定义本地调试时各 Agent 的端口
AGENTS = [
    {"name": "screenwriter", "port": 8001},
    {"name": "director",     "port": 8002},
    {"name": "critic",       "port": 8003},
    {"name": "producer",     "port": 8000}, # Producer 作为入口，监听 8000
]

def parse_env_file(env_path):
    """
    解析 .env 文件 (KEY=VALUE)
    """
    envs = {}
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip()
                    # 去除可能的引号
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    envs[key] = val
    except Exception as e:
        print(f"⚠️  Failed to parse {env_path}: {e}")
    return envs

def main():
    processes = []
    # 1. 复制当前环境变量 (包括 .env 中的配置)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    # 2. 为 Producer 注入子 Agent 的本地地址
    for agent in AGENTS:
        if agent["name"] != "producer":
            name_upper = agent["name"].upper()
            endpoint = f"http://127.0.0.1:{agent['port']}"
            env[f"SUB_AGENT_{name_upper}_AGENT_ENDPOINT"] = endpoint
            env[f"SUB_AGENT_{name_upper}_AGENT_TOKEN"] = "debug_token" 
            print(f"🔗 Configured {agent['name']} at {endpoint}")

    print("\n🚀 Launching AI Movie Studio Cluster...")
    
    try:
        for agent in AGENTS:
            print(f"   ▶ Starting {agent['name']} on port {agent['port']}...")
            
            # 1. 基础环境
            agent_env = env.copy()
            agent_env["PORT"] = str(agent['port'])
            
            # 2. 加载 .env 或 .env.example
            env_files = [f"sub_agents/{agent['name']}/.env", f"sub_agents/{agent['name']}/.env.example"]
            loaded = False
            for env_path in env_files:
                if os.path.exists(env_path):
                    file_envs = parse_env_file(env_path)
                    count = 0
                    for k, v in file_envs.items():
                        if k not in agent_env:
                            agent_env[k] = v
                            count += 1
                    if count > 0:
                        print(f"      + Loaded {count} envs from {env_path}")
                        loaded = True
                    break # 优先加载 .env，如果加载了就不读 example
            
            if not loaded:
                print(f"      ⚠️  No .env config found for {agent['name']}")

            # 构造启动命令
            script_path = f"sub_agents/{agent['name']}/simple_agent.py"
            if not os.path.exists(script_path):
                print(f"❌ Error: Script not found at {script_path}")
                continue

            cmd = [sys.executable, script_path]
            
            # 启动子进程 (非阻塞)
            p = subprocess.Popen(cmd, env=agent_env)
            processes.append(p)
            
            # 稍微错峰启动
            time.sleep(1)

        print("\n✅ All agents started successfully!")
        print("🎬 AI Movie Studio is ready at: http://127.0.0.1:8000")
        print("   (Press Ctrl+C to stop the cluster)")
        
        # 阻塞主进程
        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down cluster...")
        for p in processes:
            if p.poll() is None: 
                p.terminate()
        print("👋 Bye!")

if __name__ == "__main__":
    main()
