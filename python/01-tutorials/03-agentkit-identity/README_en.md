# Agent Identity Getting Started Tutorial

> Provide enterprise-level identity and permission management capabilities for intelligent agents.

## Overview

With the explosion of LLM applications, we've noticed a clear trend: it's very easy for developers to build a demo locally (in VS Code/Cursor) using frameworks like veADK/LangChain. However, when pushing agents to an **enterprise production environment**, they often hit a "security wall."

Unlike traditional microservices, a true enterprise-grade agent must have **agency**. Due to model limitations, the agent's behavior is unpredictable. This brings three core challenges:

1. **Inbound Security - Who can call the agent?**
    * Common API Key-based access methods have low security due to the lack of anti-replay mechanisms.
    * Enterprises often want to reuse existing IdPs. Agents need to support SSO (such as Feishu) to verify user identity and ensure that only authorized users can initiate conversations.

2. **Outbound Security - Who does the agent operate on behalf of?**
    * **Credential leakage risk**: Developers are used to hard-coding API Keys in agent code, which is a huge security risk.
    * **Permission escalation**: When an agent accesses Feishu documents or databases, should it have a "God's eye view" or only the permissions of the "current user"?
    * **Identity propagation**: How to let backend resources know that this call was initiated by "User A" authorizing "Agent B"?

3. **Fine-grained permission control (Governance) - How to control the "black box"?**
    * Agents need fine-grained policy control, not a one-size-fits-all `Admin` permission.
    * Enterprise CISOs and security teams need to know what resources the agent has accessed.

## Agent Identity Solution

Agent Identity is designed to solve the above problems. It is not a simple OAuth wrapper, but a complete **identity governance infrastructure** built for intelligent agents.

![alt text](docs/images/img_overview.png)
Agent Identity separates the "user → application → agent → resource" link for governance and provides a set of reusable security components:

**Inbound authentication**: Connect to the enterprise's existing IdP (user pool / OAuth / SSO, etc.) to make "who can call the agent" configurable and auditable.
**Agent authoritative identity**: Provide a unique and verifiable identity subject for the agent, which is convenient for policy binding and audit attribution.
**Outbound credential hosting (Token Vault)**: Separate the storage, refresh, and minimization of authorization of OAuth / API Keys from business code; by default, "credentials do not land on the ground."
**Fine-grained permission control**: Based on the delegation chain, the "user permission" and "agent permission" are combined for verification, which is denied by default and released on demand.
**Observability and audit**: Precipitate "who, when, on behalf of whom, called which tool/resource" into audit events to facilitate troubleshooting, compliance, and internal control.

## Experiment List

| Experiment | Description | Directory |
| --- | --- | --- |
| **Experiment 1: User Pool Authentication** | Use user pools to control agent access (Inbound authentication) | [tutorial-1-userpool-inbound](./tutorial-1-userpool-inbound/) |
| **Experiment 2: Feishu Federated Login** | Use Feishu account as the enterprise identity source (IdP integration) | [tutorial-2-feishu-idp](./tutorial-2-feishu-idp/) |
| **Experiment 3: Feishu Document Access** | Configure the agent to access Feishu documents on behalf of the user | [tutorial-3-feishu-outbound](./tutorial-3-feishu-outbound/) |

## Core Functions

**Identity Authentication (Inbound)**: Verify user identity, only authorized users can access the agent.
**Credential Hosting (Outbound)**: The agent securely accesses external services such as Feishu, and the credentials are managed by the platform.
**Permission Control**: Fine-grained permissions based on the delegation chain to control the resources that the agent can access.

## Directory Structure Description

```bash
./
├── README.md                           # This file
├── docs/                               # Documentation and image resources
│   └── images/
├── tutorial-1-userpool-inbound/        # Experiment 1: Inbound Authentication
│   ├── README.md                       # Tutorial documentation
│   ├── app.py                          # Sample code
│   ├── oauth2_testapp.py               # OAuth2 test application
│   ├── requirements.txt                # Dependency configuration
│   ├── .env.template                   # Environment variable template
│   ├── templates/                      # HTML template
│   │   └── index.html
│   └── test_agent/                     # Agent under test
│       ├── agent.py                    # Agent code
│       └── agentkit.yaml.template      # AgentKit configuration template
├── tutorial-2-feishu-idp/              # Experiment 2: Feishu IdP Federated Login
│   ├── README.md                       # Tutorial documentation
│   ├── app.py                          # Sample code
│   ├── requirements.txt                # Dependency configuration
│   ├── .env.template                   # Environment variable template
│   └── templates/                      # HTML template
│       └── index.html
└── tutorial-3-feishu-outbound/         # Experiment 3: Feishu Document Access
    ├── README.md                       # Tutorial documentation
    ├── app.py                          # Sample code
    ├── requirements.txt                # Dependency configuration
    ├── .env.template                   # Environment variable template
    ├── templates/                      # HTML template
    │   └── index.html
    └── test_agent/                     # Agent under test
        ├── agent.py                    # Agent code
        ├── agentkit.yaml.template      # AgentKit configuration template
        └── requirements.txt            # Agent dependency configuration
```

## Prerequisites

| Item | Description |
| --- | --- |
| **Volcano Engine Console Account** | AgentKit and Agent Identity products need to be activated |
| **Volcano Engine Account AK/SK** | Requires AgentKit Administrator permission for AgentKit CLI to deploy Runtime |
| **Python Environment** | Python 3.12+ and [uv](https://docs.astral.sh/uv/) |
| **AgentKit CLI** | Refer to [AgentKit CLI Security Guide](https://volcengine.github.io/agentkit-sdk-python/content/1.introduction/2.installation.html) |
| **Feishu Account** (Experiment 2/3) | Used to test Feishu login and document access |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/bytedance/agentkit-samples.git
```

## Overview

## Core Functions

## Agent Capabilities

## Directory Structure Description

## Local Running

## AgentKit Deployment

## Sample Prompts

## Effect Display

## Common Problems

## Code License

This project follows the Apache 2.0 License.
