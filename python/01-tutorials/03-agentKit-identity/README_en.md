# Agent Identity Getting Started Tutorial

> Providing enterprise-level identity and permission management capabilities for intelligent agents.

## Overview

With the explosion of LLM applications, we've noticed a clear trend: it's very easy for developers to build a demo locally (in VS Code/Cursor) using frameworks like veADK/LangChain. However, when pushing agents to an **enterprise-level production environment**, they often hit a "security wall."

Unlike traditional microservices, a true enterprise-level Agent must have **agency**. Due to model limitations, the Agent's behavior is unpredictable. This brings three core challenges:

1. **Inbound Security - Who can call the Agent?**
    * Common API Key-based access methods have low security due to the lack of anti-replay mechanisms.
    * Enterprises often want to reuse existing IdPs. The Agent needs to support user identity verification through SSO (such as Feishu) to ensure that only authorized users can initiate conversations.

2. **Outbound Security - Who is the Agent operating on behalf of?**
    * **Credential leakage risk**: Developers are used to hard-coding API Keys in the Agent's code, which is a huge security risk.
    * **Permission overstepping**: When an Agent accesses Feishu documents or databases, should it have a "God's eye view" or only the permissions of the "current user"?
    * **Identity propagation**: How to let the backend resources know that this call was initiated by "User A" authorizing "Agent B"?

3. **Fine-grained Permission Control (Governance) - How to control the "black box"?**
    * Agents need fine-grained policy control, not a one-size-fits-all `Admin` permission.
    * Enterprise CISOs and security teams need to know what resources the Agent has accessed.

## Agent Identity Solution

Agent Identity is specifically designed to solve the above problems. It is not a simple OAuth wrapper, but a complete **identity governance infrastructure** built for intelligent agents.
![alt text](image.png)
Agent Identity governs the "user → application → Agent → resource" link separately and provides a set of reusable security components:

**Inbound Authentication**: Integrates with existing enterprise IdPs (user pools / OAuth / SSO, etc.), making "who can call the Agent" configurable and auditable.
**Agent Authoritative Identity**: Provides a unique and verifiable identity principal for the Agent, which is convenient for policy binding and audit attribution.
**Outbound Credential Hosting (Token Vault)**: Separates the storage, refresh, and minimization of authorization of OAuth / API Keys from the business code; by default, "credentials do not land on the ground."
**Fine-grained Permission Control**: Combines and verifies "user permissions" and "Agent permissions" based on the delegation chain, denying by default and opening up as needed.
**Observability and Auditing**: Precipitates "who, on behalf of whom, called which tool/resource at what time" into audit events, which is convenient for troubleshooting, compliance, and internal control.

## Experiment List

| Experiment | Description | Directory |
| --- | --- | --- |
| **Experiment 1: User Pool Authentication** | Use a user pool to control agent access (Inbound authentication) | [01_userpool_inbound](./01_userpool_inbound/) |
| **Experiment 2: Feishu Federated Login** | Use a Feishu account as the enterprise identity source (IdP integration) | [02_feishu_idp](./02_feishu_idp/) |
| **Experiment 3: Feishu Document Access** | Configure the Agent to access Feishu documents on behalf of the user | [03_feishu_outbound](./03_feishu_outbound/) |

## Core Features

**Identity Authentication (Inbound)**: Verify user identity, only authorized users can access the Agent
**Credential Hosting (Outbound)**: The Agent securely accesses external services such as Feishu, and the credentials are managed by the platform
**Permission Control**: Fine-grained permissions based on the delegation chain to control the resources that the Agent can access

## Directory Structure Description

```bash
03-agentkit-identity/
├── README.md                           # This file
├── 01_userpool_inbound/        # Experiment 1: Inbound Authentication
│   ├── README.md                       # Tutorial documentation
│   ├── main.py                         # Sample code
│   ├── pyproject.toml                  # Dependency configuration
│   ├── .env.template                   # Environment variable template
│   └── assets/                         # Screenshots and flowcharts
└── 02_feishu_idp/              # Experiment 2: Feishu IdP Federated Login
    ├── README.md
    ├── main.py
    ├── pyproject.toml
    ├── .env.template
    └── assets/
└── 03_feishu_outbound/              # Experiment 3: Feishu Document Access
    ├── README.md
    ├── main.py
    ├── pyproject.toml
    ├── .env.template
    └── assets/
```

## Running Locally

### Prerequisites

| Item | Description |
| --- | --- |
| **Volcengine Console Account** | A sub-account with `IDFullAccess` and `STSAssumeRoleAccess` permissions is required |
| **Python Environment** | Python 3.12+ and [uv](https://docs.astral.sh/uv/) |
| **Feishu Account** (Experiments 2/3) | Used to test Feishu login and document access |

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/volcengine/agentkit-samples.git
cd python/01-tutorials/03-agentkit-identity

# 2. Select the experiment directory
cd 01_userpool_inbound  # or other experiments

# 3. Configure environment variables
cp .env.example .env
# Edit .env to fill in the configuration

# 4. Install dependencies
uv sync

# 5. Start the service
uv run veadk web
```

## AgentKit Deployment

All examples in this tutorial can be run locally with `uv run veadk web`.

To deploy to AgentKit Runtime, please refer to the [AgentKit Runtime documentation](https://volcengine.github.io/agentkit-sdk-python/content/4.runtime/1.runtime_quickstart.html).
