import base64
import sys
import urllib.request

def generate_mermaid_url(mermaid_code):
    graphbytes = mermaid_code.encode("utf8")
    base64_bytes = base64.urlsafe_b64encode(graphbytes)
    base64_string = base64_bytes.decode("ascii")
    return "https://mermaid.ink/img/" + base64_string

scenario_mermaid = """
graph LR
    %% Styles
    classDef purple fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c,rx:10,ry:10;
    classDef user fill:#e1bee7,stroke:#4a148c,stroke-width:2px,color:#4a148c,rx:10,ry:10;
    classDef plain fill:#ffffff,stroke:#7b1fa2,stroke-width:1px,color:#000000,rx:5,ry:5;

    %% Nodes
    User("👤 User"):::user
    
    subgraph "AI Movie Studio Agents"
        Producer("🎬 Producer<br/>(Manager)"):::purple
        Screenwriter("✍️ Screenwriter<br/>(Creative)"):::plain
        Director("🎥 Director<br/>(Action)"):::plain
        Critic("🧐 Critic<br/>(Review)"):::plain
    end
    
    GenVideo("🎞️ Video Gen"):::plain

    %% Flow
    User -->|1. Request| Producer
    Producer -->|2. Brief| Screenwriter
    Screenwriter <-->|3. Refine Script| User
    Screenwriter -->|4. Final Script| Producer
    Producer -->|5. Execute| Director
    Director -->|6. I2V| GenVideo
    GenVideo --> Director
    Director -->|7. Audit| Critic
    Critic -->|8. Feedback| Director
    Critic -->|9. Pass| Producer
    Producer -->|10. Deliver| User

    linkStyle default stroke:#7b1fa2,stroke-width:2px;
    style Producer fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
"""

technical_mermaid = """
graph LR
    %% Styles
    classDef client fill:#e1bee7,stroke:#4a148c,stroke-width:2px,color:#4a148c,rx:10,ry:10;
    classDef app fill:#f3e5f5,stroke:#ba68c8,stroke-width:2px,color:#4a148c,rx:5,ry:5;
    classDef volc fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1,rx:5,ry:5;
    classDef coze fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#e65100,rx:5,ry:5;

    subgraph "Clients"
        U1("User (Feishu)"):::client
        U2("Developer (CLI)"):::client
    end

    subgraph "AgentKit Application"
        Runtime("⚡ Runtime"):::app
        
        subgraph "Virtual Team"
            Agents("👥 Agents<br/>(Producer, Screenwriter,<br/>Director, Critic)"):::app
        end
        
        Skills("🛠️ Skills<br/>(dice-roller, evaluate-shots)"):::app
    end

    subgraph "VolcEngine Cloud Ecosystem"
        subgraph "MaaS (Models)"
            Doubao("🧠 Doubao LLM"):::volc
            Seedance("🎬 Seedance Video"):::volc
        end

        subgraph "Data & Storage"
            PG("🐘 RDS PostgreSQL<br/>(Short-term Memory)"):::volc
            Viking("🗄️ VikingDB<br/>(Long-term Memory & KB)"):::volc
            TOS("☁️ TOS Object Storage"):::volc
        end

        subgraph "Observability"
            TLS("📊 TLS<br/>(Log Service)"):::volc
            APM("📈 APMPlus<br/>(Performance)"):::volc
        end
    end

    subgraph "Cozeloop SaaS"
        PromptMgr("📝 Prompt Manager"):::coze
        CozeTrace("🔍 Agent Trace"):::coze
    end

    %% Main Flow
    U1 --> Runtime
    U2 --> Runtime
    Runtime --> Agents
    Agents --> Skills

    %% Data Connections
    Agents -.-> PG
    Agents -.-> Viking
    Runtime -.-> TOS

    %% Model Connections
    Agents -.-> Doubao
    Agents -.-> Seedance

    %% Ops Connections
    Runtime -.-> TLS
    Runtime -.-> APM
    Runtime <--> PromptMgr
    Runtime -.-> CozeTrace

    linkStyle default stroke:#7b1fa2,stroke-width:1px;
"""

def download_image(url, filename):
    try:
        print(f"Downloading to {filename}...")
        req = urllib.request.Request(
            url, 
            data=None, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req) as response, open(filename, 'wb') as out_file:
            out_file.write(response.read())
        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Error downloading {filename}: {e}")

if __name__ == "__main__":
    print("Generating Scenario Diagram...")
    scenario_url = generate_mermaid_url(scenario_mermaid)
    download_image(scenario_url, "/Users/bytedance/agentkit/ai_movie_studio/assets/architecture_scenario.png")

    print("Generating Technical Diagram...")
    tech_url = generate_mermaid_url(technical_mermaid)
    download_image(tech_url, "/Users/bytedance/agentkit/ai_movie_studio/assets/architecture_technical.png")
