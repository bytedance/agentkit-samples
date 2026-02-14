# 🎬 AI Movie Studio

**Enterprise-grade Multi-Agent Video Production System powered by AgentKit**

> *Empowering everyone to be a producer, with AI handling the Screenwriter, Director, and Critic roles.*

## 📖 Background

With the release of next-gen video generation models like **Seedance 2.0**, creating movie-quality videos is becoming a reality. However, users still face challenges in creativity, technical prompting, and quality control. **AI Movie Studio** solves these by building a virtual production team of expert Agents.

## ✨ Key Features

- **Hub-and-Spoke Architecture**: A Producer agent coordinates specialized experts (Screenwriter, Director, Critic) for a streamlined workflow.
- **Skill Sandbox & Skill Center**: Seamlessly integrates with **AgentKit Skill Center**, dynamically invoking cloud-hosted Skills via `execute_skills` in a secure sandbox.
    - **Hot Reload**: Whether adding new capabilities (like "Dice of Destiny") or fixing logic, simply publish a new version in the Skill Center, and the Agent updates **instantly without redeployment or restart**.
    - **Ecosystem Reuse**: Leverage community or enterprise-grade Skills (e.g., document processing, data analysis) to rapidly extend Agent capabilities.

## 🏗️ Architecture

**Scenario Architecture**
![Scenario Architecture](assets/architecture_scenario.png)

**Technical Architecture**
![Technical Architecture](assets/architecture_technical.png)

### 👥 Virtual Team Roles

| Role | ID | Responsibility | Key Tools |
| :--- | :--- | :--- | :--- |
| **Producer** | `producer_agent` | **Router**: Task decomposition, progress management, user intent confirmation. | `execute_skills` |
| **Screenwriter** | `screenwriter_agent` | **Creative**: Guided brainstorming, script generation. | `web_search`, `execute_skills` |
| **Director** | `director_agent` | **Action**: I2V generation, camera control. | `image_generate`, `video_generate` |
| **Critic** | `critic_agent` | **Review**: Visual audit, consistency check. | `execute_skills` (evaluate-shots) |

## 🚀 Quick Start

### 1. Installation
```bash
uv pip install -r sub_agents/producer/requirements.txt
```

### 2. Configuration
Copy `.env.example` to `.env` and fill in your API keys.

### 3. Run Locally
```bash
cd sub_agents/producer
python -m simple_agent
```

## 📂 Directory Structure

```bash
ai_movie_studio/
├── LICENSE               # Apache 2.0 License
├── README.md             # Chinese Documentation
├── README_en.md          # English Documentation
├── project.toml          # Project Metadata
├── requirements.txt      # Dependencies
├── pyproject.toml        # Build System Dependencies
├── sub_agents/           # Sub-agents Code
├── skills/               # Custom Skills
├── knowledge/            # Knowledge Base Data
├── assets/               # Static Assets
└── scripts/              # Utility Scripts
```
