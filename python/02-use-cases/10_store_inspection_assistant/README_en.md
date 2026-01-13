# Smart Store Inspection System

An intelligent store inspection assistant based on AgentKit, specialized for store quality checks: signboard LED light status detection, sink cleanliness detection, shelf display detection, and work uniform compliance detection. The system can automatically identify anomalies to achieve standardized management of store operations.

## Overview

This project builds an AI-driven solution for store quality inspection, using computer vision and artificial intelligence to automate the inspection of various store facilities. The system intelligently identifies key indicators such as the lighting status of signboard LEDs, cleanliness of sinks, and compliance of shelf displays. It reports anomalies in a timely manner, helping store managers respond to and resolve issues quickly.

## Core Features

### 🔍 Intelligent Image Processing and Analysis

- **Accurate Object Detection**: Automatically identifies the store signboard area and intelligently frames the complete signboard.
- **Intelligent Image Cropping**: Automatically extracts the main subject of the signboard, removing irrelevant background interference.
- **Intelligent Text Recognition**: Accurately detects Chinese and English text on the signboard.
- **Multimodal Image Understanding**: Deeply understands image content through a large vision model to identify issues like abnormal LED lighting and cleanliness of shelves/sinks.

### 🤖 Multi-Agent Collaborative Architecture

- **Multi-Agent Architecture**: Adopts a collaborative work model with multiple agents to autonomously determine the optimal task execution flow.
- **Specialized Division of Labor**: Image processing and anomaly analysis agents have distinct roles, improving detection efficiency.
- **End-to-End Automation**: Fully automated processing from image acquisition to alert notification.

## Agent Capabilities

Main Volcano Engine products or Agent components:

- Doubao Large Language Model:
  - doubao-seed-1.6-vision
  - doubao-seed-1-6-251015
- Custom Tools
- Identity
- APMPlus

## Directory Structure

```bash
.
├── Dockerfile
├── README.md
├── __init__.py
├── agent.py   # Agent application entry point
├── agent.yaml # Agent configuration file (defines core features and behavior rules)
├── requirements.txt
└── tools      # Custom tools
    ├── __init__.py
    ├── image  # Image recognition and detection tools
    │   ├── __init__.py
    │   ├── attire_inspection.py # Worker attire inspection tool
    │   ├── image_cropper.py     # Image cropping tool
    │   ├── image_editor.py      # Image annotation tool
    │   ├── shelf_inspection.py  # Shelf inspection tool
    │   ├── signboard_inspection.py # Store signboard inspection tool
    │   └── sink_inspection.py      # Sink inspection tool
    ├── model_auth.py   # Ark large model API key exchange tool
    └── tos_upload.py   # Volcano TOS file upload tool
```

## Quick Start

### Prerequisites

**Python Version:**

- Python 3.12 or higher

**Volcano Engine Access Credentials:**

1. Log in to the [Volcano Engine Console](https://console.volcengine.com)
2. Go to "Access Control" → "Users" -> Create a new user or search for an existing username -> Click the username to enter "User Details" -> Go to "Keys" -> Create a new key or copy an existing AK/SK.
   - As shown below:
     ![Volcengine AK/SK Management](../../assets/images/volcengine_aksk.jpg)
3. Configure access permissions for the services AgentKit depends on for the user:
   - On the "User Details" page -> Go to "Permissions" -> Click "Add Permission" and grant the following policies to the user:
     - `AgentKitFullAccess` (Full access to AgentKit)
     - `APMPlusServerFullAccess` (Full access to APMPlus)
4. Obtain the Volcano Ark model Agent API Key for the user:
   - Log in to the [Volcano Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)
   - Go to "API Key Management" -> Create or copy an existing API Key. The `MODEL_AGENT_API_KEY` environment variable will need to be set to this value.
   - As shown below:
     ![Ark API Key Management](../../assets/images/ark_api_key_management.jpg)
5. Activate pre-built model inference endpoints:
   - Log in to the [Volcano Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)
   - Go to "Activation Management" -> "Language Models" -> Find the respective model -> Click "Activate Service".
   - Confirm activation and wait for the service to become effective (usually 1-2 minutes).
   - Activate the following models used in this case (you can also activate other models' pre-built inference endpoints as needed and specify them in the `agent.py` code):
     - `deepseek-v3-1-terminus`
     - `doubao-seed-1-6-vision-250815`
     - `doubao-seed-1-6-251015`
   - As shown below:
     ![Ark Model Service Management](../../assets/images/ark_model_service_management.jpg)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Set the following environment variables:

```bash
# Volcano Engine AK/SK
export VOLCENGINE_ACCESS_KEY=AK
export VOLCENGINE_SECRET_KEY=SK
# TOS bucket name
export DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}
# Large model API_KEY (optional)
export MODEL_AGENT_API_KEY=<your_ark_api_key>
```

## Local Execution

Use `veadk web` for local debugging:

```bash
# 1. Go to the parent directory
cd 02-use-cases

# 2. Optional: Create a .env file (skip if environment variables are already set)
touch .env
echo "VOLCENGINE_ACCESS_KEY=AK" >> .env
echo "VOLCENGINE_SECRET_KEY=SK" >> .env
# Set the TOS bucket for uploading result files from the inspection process
echo "DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}}" >> .env

# 3. Start the Web UI
veadk web
```

The service runs on port 8000 by default. Access `http://127.0.0.1:8000`, select the `10_store_inspection_assistant` agent, and start testing in the input panel.

### Example Prompts

```text
Check the LED light status of the store signboard, image url: https://agentkit-demo.tos-cn-beijing.volces.com/volc_coffe.jpeg
Check the cleanliness of the store's sink, image url: https://agentkit-demo.tos-cn-beijing.volces.com/20251111-174301.png
Check the store's shelf display, image url: https://agentkit-demo.tos-cn-beijing.volces.com/20251111-192602.jpeg
Check the worker's attire in the store, image url: https://agentkit-demo.tos-cn-beijing.volces.com/20251112-102002.jpeg
```

## AgentKit Deployment

1. Deploy to Volcano Engine AgentKit Runtime:

```bash
# 1. Go to the project directory
cd python/02-use-cases/10_store_inspection_assistant

# 2. Configure agentkit
agentkit config \
--agent_name inspection_assistant \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}} \
--launch_type cloud

# 3. Deploy to runtime
agentkit launch
```

### Test the Deployed Agent

After successful deployment:

1. Visit the [Volcano Engine AgentKit Console](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/runtime)
2. Click **Runtime** to see the deployed agent `inspection_assistant`
3. Get the public access domain (e.g., `https://xxxxx.apigateway-cn-beijing.volceapi.com`) and API Key

#### **Debugging with chatui**

The agent list page in AgentKit provides a debugging entry point. Click it to debug the agent's functionality in a visual UI.

![img](./img/agent-test-run.png)

#### **Debugging with the command line**

You can directly use `agentkit invoke` to debug the current agent. The command is as follows:

```bash
agentkit invoke '{"prompt": "Check the LED light status of the store signboard, image url: https://agentkit-demo.tos-cn-beijing.volces.com/volc_coffe.jpeg"}'
```

## Demonstration

Demonstration of the smart store inspection.

## FAQ

## Best Practices

- **Image Quality Requirements**: Ensure that the uploaded store images are clear and well-lit for the best detection results.
- **Monitoring and Maintenance**: Establish a comprehensive monitoring mechanism to ensure the stable operation of the system.

## 🔗 Related Resources

- [AgentKit Official Documentation](https://www.volcengine.com/docs/86681/1844878?lang=en)
- [TOS Object Storage](https://www.volcengine.com/product/TOS)
- [AgentKit Console](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/overview?projectName=default)
- [Volcano Ark Console](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)

## Code License

This project is licensed under the Apache 2.0 License.

## Technical Support

For technical support or any questions, please refer to the AgentKit official documentation or contact the Volcano Engine technical support team.
