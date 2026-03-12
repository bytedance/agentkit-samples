# Volcano Engine Milvus Skill

## Introduction
The Volcano Engine Milvus skill is a custom extension for OpenClaw that enables the agent to operate and manage Milvus instances on the Volcano Engine cloud platform.

This skill provides comprehensive capabilities across two main areas:
- **Control Plane (Cluster Management)**: Provision new clusters, scale existing instances, delete clusters, and inspect details such as connection endpoints and hardware specifications. It also allows the agent to discover available VPCs and subnets automatically.
- **Data Plane (Collection & Data Operations)**: Manage collections (create, drop, list, describe), insert or upsert data with automated text embeddings (via OpenAI or Volcengine Doubao models), and perform semantic vector searches.

## How to Add this Skill to OpenClaw

To add and use this skill in your OpenClaw environment, follow these steps:

### 1. Installation
Install the skill into your `.openclaw/skills` directory:
This `volcengine-milvus` directory should be placed at `.openclaw/skills/openclaw-skill-volcengine-milvus`.

The OpenClaw agent is designed to automatically set up the Python virtual environment (`venv`) and install the necessary dependencies from `requirements.txt` upon its first invocation of this skill. There is no manual installation step required unless you want to pre-install them.

### 2. Configuration
You must configure the skill in your `.openclaw/openclaw.json` file. Add the following configuration to the `skills` section, providing your Volcano Engine credentials (and an API key if you plan to use automatic embeddings via Volcengine Doubao):

```json
  "skills": {
    "entries": {
      "volcengine-milvus": {
        "enabled": true,
        "env": {
          "VOLCENGINE_AK": "...",
          "VOLCENGINE_SK": "...",
          "VOLCENGINE_REGION": "cn-beijing",
          "MS_EMBEDDING_API_KEY": "...",
          "MS_EMBEDDING_PROVIDER": "volcengine",
          "MS_EMBEDDING_BASE_URL": "...",
          "MS_EMBEDDING_MODEL": "...",
          "MS_EMBEDDING_DIMENSION": "2048"
        }
      }
    }
  }
```

**Notes:**

* `MS_EMBEDDING_PROVIDER` can be `volcengine` or `openai`.
* `MS_EMBEDDING_BASE_URL` is optional, if not set, it will use the default base url.

### 4. Usage
Once configured, you can directly instruct OpenClaw using natural language to interact with your Milvus infrastructure and data. The agent will read `SKILL.md` to understand the available commands and workflows.

**Example Prompts:**
- *Control Plane:* "Create a Milvus instance on Volcengine named my-vector-db."
- *Control Plane:* "List all my Milvus clusters."
- *Control Plane:* "Scale up the proxy nodes for my Milvus instance."
- *Data Plane:* "Create a collection named 'documents' in my Milvus database."
- *Data Plane:* "Insert this text data into Milvus and use OpenAI to generate embeddings."
- *Data Plane:* "Search for documents about artificial intelligence in my Milvus collection."
