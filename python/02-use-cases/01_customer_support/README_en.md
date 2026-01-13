# Customer Support Agent

This is a "Customer Inquiry and After-Sales Service" agent built with Volcano Engine AgentKit, supporting both shopping consultation and after-sales processing scenarios. The system integrates a knowledge base and CRM tools, combined with short-term/long-term memory and identity verification, to provide efficient, accurate, and privacy-secured services for real-world customer service workflows.

## Overview

This use case demonstrates how to build an enterprise-level customer support system with the following capabilities:

- **After-Sales Assistant**: An after-sales service assistant based on AgentKit that can answer after-sales questions, schedule on-site repairs, and more.
- **Shopping Guide Assistant**: A shopping guide assistant built with AgentKit that provides users with shopping guidance based on their needs and preferences.
- **Enterprise System Integration**: Supports rapid integration of enterprise systems into the Agent via an HTTP-to-MCP tool approach.
- **Long-Term Memory**: Supports session memory and user history storage, implemented through the Viking vector database or Mem0.
- **Observability**: Integrated with OpenTelemetry for tracing and APMPlus for monitoring.

## Core Functionality

![Customer Support Agent with AgentKit Runtime](img/archtecture_customer_support.jpg)

```text
Customer Inquiry
    ↓
AgentKit Runtime
    ↓
Customer Support Agent (Main Router)
    ├── Shopping Guide Sub-Agent
    │   ├── Product Knowledge Base
    │   └── Customer Information Tool
    └── After-Sales Support Sub-Agent
        ├── Warranty & Policy Knowledge
        ├── Troubleshooting Guides
        └── Service Ticket Management (CRUD)
```

## Agent Capabilities

| Component | Description |
| - | - |
| **Agent Service** | [`agent.py`](agent.py) - The main application, orchestrating sub-agents via `AgentkitAgentServerApp` |
| **CRM Tool** | [`tools/crm_mock.py`](tools/crm_mock.py) - A mock CRM API providing CRUD operations for customers, purchases, warranties, and tickets |
| **Knowledge Base** | [`pre_build/knowledge/`](pre_build/knowledge/) - Product guides, policy documents, and troubleshooting manuals |
| **Short-Term Memory** | Local session context to maintain conversation continuity |
| **Long-Term Memory** | Viking vector database or Mem0 for persisting user history |

## Directory Structure

```text
01_customer_support/
├── agent.py                          # Main agent, includes sub-agent orchestration
├── tools/
│   └── crm_mock.py                   # Mock CRM tool (customer, purchase, warranty, ticket)
├── pre_build/
│   └── knowledge/                    # Knowledge base files
│       ├── policies.md               # Return & warranty policies
│       ├── shopping_guide.md         # Product consultation knowledge
│       ├── troubleshooting_for_phone.md   # Phone troubleshooting guide
│       └── troubleshooting_for_tv.md      # TV troubleshooting guide
├── requirements.txt                  # Python dependencies
├── README.en.md                     # Project documentation (English)
└── .dockerignore                     # Docker build exclusions
```

## Quick Start

### Prerequisites

**Python Version:**

- Python 3.12 or higher is required.

**Volcano Engine Access Credentials:**

1. Log in to the [Volcano Engine Console](https://console.volcengine.com)
2. Go to "Access Control" → "Users" -> Create a new user or search for an existing one -> Click the username to go to "User Details" -> Go to "Keys" -> Create a new key or copy an existing AK/SK.
   - As shown below:
   ![Volcengine AK/SK Management](../../assets/images/volcengine_aksk.jpg)
3. Configure access permissions for services required by AgentKit:
   - On the "User Details" page -> Go to "Permissions" -> Click "Add Permission" and grant the following policies to the user:
     - `AgentKitFullAccess` (Full access to AgentKit)
     - `APMPlusServerFullAccess` (Full access to APMPlus)
4. Obtain a Volcano Ark model Agent API Key:
   - Log in to the [Volcano Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)
   - Go to "API Key Management" -> Create or copy an existing API Key. The `MODEL_AGENT_API_KEY` environment variable will need to be set to this value.
   - As shown below:
   ![Ark API Key Management](../../assets/images/ark_api_key_management.jpg)
5. Activate pre-built model inference endpoints:
   - Log in to the [Volcano Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)
   - Go to "Activation Management" -> "Language Models" -> Find the desired model -> Click "Activate Service".
   - Confirm activation and wait for the service to become effective (usually 1-2 minutes).
   - Activate the following models used in this case (you can also activate other models as needed and specify them in the `agent.py` code):
      - `deepseek-v3-1-terminus`
   - As shown below:
   ![Ark Model Service Management](../../assets/images/ark_model_service_management.jpg)

**Knowledge Base (auto-configured on first run):**:

- If `DATABASE_VIKING_COLLECTION` is not set, the agent will automatically:
  - Upload files from `pre_build/knowledge/` to TOS
  - Create a Viking collection
  - Import the knowledge base content
- For production environments, it is recommended to manually create the knowledge base and set the collection name.

### Install Dependencies

*It is recommended to use the `uv` tool to build the project.*

```bash
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

cd python/02-use-cases/01_customer_support

# create virtual environment
uv venv --python 3.12

# activate virtual environment
source .venv/bin/activate

# install necessary dependencies
uv pip install -r requirements.txt
```

### Configure Environment Variables

Set the following environment variables:

```bash
export VOLCENGINE_ACCESS_KEY=AK
export VOLCENGINE_SECRET_KEY=SK
export DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}

# Optional: Use an existing knowledge base
export DATABASE_VIKING_COLLECTION=<existing_knowledge_index>

# Optional: Long-term memory (choose one)
# Option 1: Viking Memory
export DATABASE_VIKINGMEM_COLLECTION=<mem_index>
export DATABASE_VIKINGMEM_MEMORY_TYPE=<memory_type>

# Option 2: Mem0
export DATABASE_MEM0_BASE_URL=<mem0_base_url>
export DATABASE_MEM0_API_KEY=<mem0_api_key>
```

**Environment Variable Explanations:**

- `DATABASE_TOS_BUCKET`: Required for automatic knowledge base initialization. If `DATABASE_VIKING_COLLECTION` is not set, on the first run, `pre_build/knowledge` will be automatically uploaded to TOS and imported into the Viking vector database.
  - Format: `DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}`
  - Example: `DATABASE_TOS_BUCKET=agentkit-platform-12345678901234567890`
  - `{{your_account_id}}` needs to be replaced with your Volcano Engine account ID.
- `DATABASE_VIKING_COLLECTION`: The name of a pre-created knowledge base collection (recommended for production).
- The default model is `deepseek-v3-1-terminus`. This can be changed in the code if needed.

## Local Execution

Use `veadk web` for local debugging:
> `veadk web` is a FastAPI-based web service for debugging Agent applications. Running this command starts a web server that loads and runs your AgentKit agent code, providing a chat interface to interact with the agent. In the sidebar or specific panels of the interface, you can view the agent's operational details, including its thought process, tool calls, and model inputs/outputs.

```bash
# 1. Go to the parent directory
cd 02-use-cases

# 2. Optional: Create a .env file (skip if environment variables are already set)
touch .env
echo "VOLCENGINE_ACCESS_KEY=AK" >> .env
echo "VOLCENGINE_SECRET_KEY=SK" >> .env
# Recommended: Manually create a knowledge base in the AgentKit console and set the collection name
echo "DATABASE_VIKING_COLLECTION=agentkit_customer_support" >> .env
# Optional: If using auto-initialization, set the TOS bucket for uploading knowledge base files
echo "DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}" >> .env

# 3. Start the Web UI
veadk web
```

The service runs on port 8000 by default. Access `http://127.0.0.1:8000`, select the `01_customer_support` agent, and start testing in the input panel.

### Example Prompts

**After-Sales Scenarios:**

- "Hello, the TV I bought before is broken."
- "My email is `zhang.ming@example.com`, and the TV serial number is SN20240001."
- "I need help troubleshooting my TV - it won't turn on."

**Shopping Consultation:**

- "I want to buy a smart TV for my living room, mainly for gaming, with a budget under 3000 yuan."
- "What is your warranty policy for smartphones?"
- "Can you recommend a phone with good battery life?"

**Expected Behavior:**

- The agent automatically identifies the intent as "shopping guide" or "after-sales" and routes to the appropriate sub-agent.
- Returns structured responses based on tools and the knowledge base.
- Guides the user through identity verification when necessary.
- Retrieves purchase history and warranty status.
- Creates/updates/deletes service tickets only with explicit user consent and complete information.

## AgentKit Deployment

1. Deploy to Volcano Engine AgentKit Runtime:

```bash
# 1. Go to the project directory
cd python/02-use-cases/01_customer_support

# 2. Configure agentkit
agentkit config \
--agent_name customer_support \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}} \
--launch_type cloud

# 3. Deploy to runtime
agentkit launch
```

2. Invoke the agent

```bash
agentkit invoke '{"prompt": "I want to buy a smart TV for my living room, mainly for gaming, with a budget under 3000 yuan."}'
```

## Key Features

### Intelligent Intent Routing

Automatically distinguishes between shopping consultation and after-sales support requests, routing them to specialized sub-agents equipped with the relevant tools and knowledge.

### Knowledge Base Integration

Combines structured documents with vector search to provide accurate, context-aware responses for product questions, policy inquiries, and troubleshooting scenarios.

### CRM Tool Connection

Demonstrates an integration pattern with a mock CRM interface for:

- Customer information retrieval
- Purchase history lookup
- Warranty status verification
- Service ticket CRUD operations

### Identity Verification

Verifies user identity via email confirmation before accessing sensitive data or performing account actions.

### Memory Management

- **Short-Term Memory**: Maintains conversational context within a session.
- **Long-Term Memory**: Persists user preferences and history across sessions via Viking or Mem0.

### Extensible Architecture

Decouples tools and knowledge, allowing for seamless replacement with a real CRM API or the addition of more business integrations.

## Demonstration

Customer Support demonstration.

## FAQ

**Error: `DATABASE_TOS_BUCKET not set`**

- Required for automatic knowledge base initialization.
- Set the name of the TOS bucket for uploading knowledge files.
- Alternative: Manually create a knowledge base and use `DATABASE_VIKING_COLLECTION`.

**Knowledge Base Not Initialized:**

- If `DATABASE_VIKING_COLLECTION` is not set, the first run will trigger an automatic import.
- Ensure TOS is configured correctly and the account has the necessary permissions.
- Check the import task status in the AgentKit console.

**Default Test User `CUST001`:**

- Demo data is tied to this customer ID.
- Production deployments should pass `user_id` in the request headers and integrate with a real identity system.

**Replacing the Mock CRM with a Real API:**

- Modify [`tools/crm_mock.py`](tools/crm_mock.py) to call your actual CRM endpoints.
- Maintain consistent interface semantics (query/create/update/delete).
- Preserve parameter names and return value structures.

**Service Ticket Operations Require User Consent:**

- Creating/updating/deleting tickets requires explicit user approval.
- Ensure all required fields (customer_id, product_sn, issue_description) are collected before performing the operation.

## Related Resources

- [AgentKit Official Documentation](https://www.volcengine.com/docs/86681/1844878?lang=en)
- [Viking Vector Database](https://www.volcengine.com/docs/84313/1860732?lang=en)
- [TOS Object Storage](https://www.volcengine.com/product/TOS)
- [Mem0 Memory Management](todo)

## Code License

This project is licensed under the Apache 2.0 License.
