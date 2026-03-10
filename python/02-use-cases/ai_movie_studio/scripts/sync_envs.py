import yaml
import os
import sys

# 排除列表：不希望同步到云端的本地变量
EXCLUDE_KEYS = {
    "PORT", "PYTHONPATH", "debug", 
    # AK/SK 通常在云端通过 IAM Role 自动获取，不需要显式配置？
    # 或者云端也需要？如果云端 Runtime 也是 veadk，那通常需要。
    # 除非 AgentKit 平台有专门的 Secret 管理。
    # 这里先不做过多假设，全量同步。
}

def load_env_file(path):
    """读取 .env 文件"""
    envs = {}
    if not os.path.exists(path):
        return envs
    
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                # 去除引号
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                envs[key] = val
    return envs

def sync_agent(agent_dir):
    # 优先读取 .env，其次 .env.example
    config_path = os.path.join(agent_dir, ".env")
    if not os.path.exists(config_path):
        config_path = os.path.join(agent_dir, ".env.example")
        
    agentkit_path = os.path.join(agent_dir, "agentkit.yaml")
    
    if not os.path.exists(config_path) or not os.path.exists(agentkit_path):
        print(f"⚠️  Skipping {agent_dir}: .env/example or agentkit.yaml missing")
        return

    print(f"🔄 Syncing {os.path.basename(agent_dir)}...")
    print(f"   Source: {config_path}")
    print(f"   Target: {agentkit_path}")

    # 1. Load Source Envs
    source_envs = load_env_file(config_path)
    
    # 2. Load Target YAML
    try:
        with open(agentkit_path, 'r', encoding='utf-8') as f:
            agentkit_data = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to parse agentkit.yaml: {e}")
        return
        
    if 'common' not in agentkit_data:
        agentkit_data['common'] = {}
    
    target_envs = agentkit_data['common'].get('runtime_envs', {})
    
    # 3. Merge
    updates = 0
    for k, v in source_envs.items():
        if k in EXCLUDE_KEYS:
            continue
        # 即使值一样，也覆盖以确保一致性
        if target_envs.get(k) != v:
            target_envs[k] = v
            updates += 1
            print(f"   + Updated {k}")
            
    agentkit_data['common']['runtime_envs'] = target_envs
    
    # 4. Write Back
    if updates > 0:
        try:
            with open(agentkit_path, 'w', encoding='utf-8') as f:
                # 保持 YAML 格式整洁
                yaml.dump(agentkit_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            print(f"✅ Synced {updates} variables.")
        except Exception as e:
            print(f"❌ Failed to write agentkit.yaml: {e}")
    else:
        print("✨ No changes needed.")

def main():
    base_dir = "sub_agents"
    if len(sys.argv) > 1:
        agents = [sys.argv[1]]
    else:
        if os.path.exists(base_dir):
            agents = os.listdir(base_dir)
        else:
            print(f"❌ Directory {base_dir} not found.")
            return
        
    for agent in agents:
        agent_path = os.path.join(base_dir, agent)
        if os.path.isdir(agent_path):
            sync_agent(agent_path)

if __name__ == "__main__":
    main()
