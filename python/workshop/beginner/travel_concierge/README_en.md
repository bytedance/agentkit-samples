# Travel Concierge - Travel Itinerary Planning Agent

An intelligent travel planning assistant built with Volcano Engine VeADK and AgentKit, demonstrating how to combine web search tools and professional domain knowledge to automatically plan a complete travel itinerary.

## Overview

This example builds a professional travel itinerary planner Agent.

## Core Features

- **Intelligent Planning**: Automatically plans travel itineraries based on user needs.
- **Comprehensive Coverage**: Includes natural attractions, cultural sites, and local cuisine.
- **Tool Enhancement**: Uses web search to get the latest travel information.
- **Professional Guidance**: Follows a professional travel planning process and constraints.

## Agent Capabilities

```text
User's Travel Request
    ↓
AgentKit Runtime
    ↓
Travel Agent (Travel Planner)
    ├── VeADK Agent (Dialogue Engine)
    ├── web_search (Web Search Tool)
    │   └── Searches for attractions, food, transportation, etc.
    ├── Professional Instruction System
    │   ├── Needs Analysis
    │   ├── Information Gathering
    │   ├── Itinerary Planning
    │   ├── Evaluation and Adjustment
    │   └── Presentation and Feedback
    └── ShortTermMemory (Session Memory)
```

### Core Components

| Component | Description |
| - | - |
| **Agent Service** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py) - The travel planning Agent application. |
| **Professional Instructions** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py#L21-L94) - Detailed role definition and workflow. |
| **Test Client** | [client.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/client.py) - SSE streaming invocation client. |
| **Project Configuration** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/pyproject.toml) - Dependency management (uv tool). |
| **Web Search** | `web_search` - Built-in web search tool. |
| **Short-term Memory** | Local backend for storing session context. |

### Code Features

**Agent Definition** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py#L100-L105)):

```python
root_agent = Agent(
    name="travel_agent",
    description="Simple travel Agent",
    instruction=instruction,  # Detailed professional instructions
    tools=[web_search],       # Web search tool
)
```

**Professional Instruction System** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py#L21-L44)):

Contains a complete role definition:

- **Role**: Professional travel itinerary planner.
- **Goal**: Plan a complete itinerary, combining attractions and cuisine.
- **Skills**: Rich travel knowledge, proficient in using tools.
- **Workflow**: Communicate → Gather → Plan → Evaluate → Present.
- **Constraints**: Must include three aspects, be realistic, and use tools.
- **Output Format**: Clear and organized itinerary.

## Directory Structure

```bash
travel_concierge/
├── agent.py           # Agent application entry point (with professional instruction system)
├── client.py          # Test client (SSE streaming invocation)
├── requirements.txt   # Python dependency list (required for agentkit deployment)
├── pyproject.toml     # Project configuration (uv dependency management)
└── README.md          # Project documentation
```

## Local Execution

### Prerequisites

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service.

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get your AK/SK.

### Dependency Installation

#### 1. Install uv Package Manager

```bash
# macOS / Linux (official installation script)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use Homebrew (macOS)
brew install uv
```

#### 2. Initialize Project Dependencies

```bash
# Enter the project directory
cd 02-use-cases/beginner/travel_concierge
```

Use the `uv` tool to install project dependencies:

```bash
# If you don't have a `uv` virtual environment, create one first
uv venv --python 3.12

# Use `pyproject.toml` to manage dependencies
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Activate the virtual environment
source .venv/bin/activate
```

### Environment Setup

```bash
# Volcano Ark model name
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# Volcano Engine access credentials (required)
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### Debugging Methods

#### Method 1: Command-line Testing (Recommended for beginners)

```bash
# Start the Agent service
uv run agent.py
# The service will listen on http://0.0.0.0:8000

# Open a new terminal and run the test client
uv run client.py
```

**Execution Effect**:

```bash
[create session] Response from server: {"session_id": "agentkit_session"}
[run agent] Event from server:
data: {"event":"on_agent_start",...}
data: {"event":"on_tool_start","tool":"web_search","input":"Hangzhou three-day tour attractions recommendation"}
data: {"event":"on_tool_end","tool":"web_search","output":"..."}
data: {"event":"on_llm_chunk","data":{"content":"Planning a three-day tour of Hangzhou for you..."}}
```

#### Method 2: Use VeADK Web Debugging Interface

```bash
# Go to the parent directory
cd ..

# Start the VeADK Web interface
veadk web

# Visit in your browser: http://127.0.0.1:8000
```

The web interface allows real-time viewing of web search calls and results.

## AgentKit Deployment

### Prerequisites

**Important Note**: Before running this example, please visit the [AgentKit Console Authorization Page](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) to authorize all dependent services to ensure the case can be executed normally.

**1. Activate Volcano Ark Model Service:**

- Visit the [Volcano Ark Console](https://exp.volcengine.com/ark?mode=chat)
- Activate the model service.

**2. Obtain Volcano Engine Access Credentials:**

- Refer to the [User Guide](https://www.volcengine.com/docs/6291/65568?lang=zh) to get your AK/SK.

### AgentKit Cloud Deployment

```bash
cd travel_concierge

# Configure deployment parameters
agentkit config

# Start the cloud service
agentkit launch

# Test the deployed Agent
agentkit invoke 'I want to take a 3-day trip to Hangzhou. I like natural scenery and history, and have a medium budget.'

# Or use client.py to connect to the cloud service
uv run client.py
```

## Example Prompts

### Example 1: Three-Day Tour of Hangzhou

```text
User: I want to take a 3-day trip to Hangzhou. I like natural scenery and history, and have a medium budget.

Agent Execution Flow:
1. [Needs Analysis] Extract key information:
   - Destination: Hangzhou
   - Duration: 3 days
   - Preferences: Natural scenery, history and culture
   - Budget: Medium

2. [Information Gathering] Use web_search to search for:
   - "Hangzhou natural attractions recommendation"
   - "Hangzhou historical and cultural sites"
   - "Hangzhou specialty food"
   - "Hangzhou transportation and accommodation"

3. [Itinerary Planning] Plan the itinerary based on search results.

4. [Evaluation and Adjustment] Check for reasonableness and feasibility.

Agent Reply:

Here is a planned three-day itinerary for your trip to Hangzhou:

**Day 1: West Lake and Surroundings**

Morning:
- Arrive in Hangzhou, head to West Lake.
- Visit natural beauties like Su Causeway and Bai Causeway.
- Stroll along the lake and enjoy the "Ten Scenes of West Lake."

Noon:
- Enjoy local delicacies like West Lake Vinegar Fish and Longjing Shrimp at a lakeside restaurant.
- Per person: 80-120 RMB.

Afternoon:
- Visit Yue Fei Temple to learn about Yue Fei's story and Southern Song history.
- Ticket: 25 RMB.

Evening:
- West Lake Musical Fountain show (free).
- Enjoy late-night snacks on Hubin Road.

**Day 2: Lingyin Temple and Jiuxi**

Morning:
- Go to Lingyin Temple (Feilai Peak Scenic Area).
- Experience the Buddhist culture of the ancient temple.
- Ticket: 75 RMB (including Feilai Peak).

Noon:
- Enjoy a vegetarian meal near Lingyin Temple.
- Per person: 60-80 RMB.

Afternoon:
- Visit Jiuxi (Nine Creeks in Misty Forest) and enjoy the natural scenery.
- Walk along the creek, breathing in the fresh air.
- Free attraction.

Evening:
- Return to the city and try Hangzhou cuisine.
- Recommendations: Lou Wai Lou, Zhi Wei Guan.
- Per person: 100-150 RMB.

**Day 3: Museums and Specialty Streets**

Morning:
- Visit Zhejiang Provincial Museum or Hangzhou Museum.
- Learn about the history and culture of Hangzhou.
- Free admission.

Noon:
- Try specialty snacks on Hefang Street.
- Recommendations: Dingsheng Cake, Congbao Hui, Crispy Oil Pancake.
- Per person: 40-60 RMB.

Afternoon:
- Stroll through Hefang Street and Southern Song Imperial Street.
- Shop for local products like Longjing tea and silk.
- Prepare for departure.

**Budget (per person)**:
- Accommodation: 300 RMB/night × 2 nights = 600 RMB
- Food: ~500 RMB
- Tickets: ~100 RMB
- Transportation (city): ~100 RMB
- Total: ~1300-1500 RMB

**Transportation Tips**:
- Hangzhou has a well-developed subway system; buying a Hangzhou Pass is recommended.
- Shared bikes are a good way to explore the West Lake area.
- Some attractions are directly accessible by bus.

**Accommodation Recommendations**:
- Budget hotels near West Lake: 300-400 RMB/night.
- Or choose a location near Hefang Street for convenient transportation.

Please let me know if you have any other needs. Enjoy your trip!
```

### Example 2: Four-Day Tour of Chengdu

```text
User: I plan to visit Chengdu for 4 days. I love food and a relaxed atmosphere, and have a sufficient budget.

Agent Execution Flow:
1. [Needs Analysis] Destination: Chengdu, Duration: 4 days, Preferences: Food, leisure, Budget: Sufficient.

2. [Information Gathering] Search for:
   - "Chengdu food guide"
   - "Chengdu leisure attractions"
   - "Chengdu one-day trips"

3. [Itinerary Planning] Plan a 4-day itinerary.

Agent Reply:

Here is a planned four-day itinerary for your trip to Chengdu:

**Day 1: Leisurely City Tour**

Morning:
- Arrive in Chengdu, head to Jinli Ancient Street.
- Experience the relaxed atmosphere of Chengdu.
- Free admission.

Noon:
- Try Chengdu snacks in Jinli.
- Recommendations: San Da Pao, Tang You Guo Zi, Zhong Dumplings.
- Per person: 60-80 RMB.

Afternoon:
- Visit Wuhou Shrine to learn about the Three Kingdoms culture.
- Ticket: 50 RMB.

Evening:
- Enjoy authentic Sichuan hot pot.
- Recommendations: Shu Da Xia, Xiao Long Kan.
- Per person: 120-180 RMB.

**Day 2: Day Trip to Mount Qingcheng**

Morning:
- Head to Mount Qingcheng (about 1 hour drive).
- Enjoy the natural scenery of "the most secluded mountain under heaven."
- Ticket: 80 RMB, round-trip cable car 60 RMB.

Noon:
- Enjoy a farmhouse meal on the mountain.
- Per person: 60-80 RMB.

Afternoon:
- Relax on Mount Qingcheng and enjoy the tranquility.
- Optional: Hot springs (extra cost).

Evening:
- Return to Chengdu.
- Experience the nightlife at Jiuyanqiao Bar Street.

**Day 3: Culture and Food**

Morning:
- Visit Du Fu Thatched Cottage to experience the poetic culture.
- Ticket: 50 RMB.

Noon:
- Try Sichuan cuisine at a nearby restaurant.
- Recommendation: Chen Mapo Tofu.
- Per person: 80-120 RMB.

Afternoon:
- Shop at Kuanzhai Alley.
- Try specialty snacks and tea.
- Free admission.

Evening:
- Watch a Sichuan Opera face-changing show.
- Recommendation: Shu Feng Ya Yun.
- Ticket price: 180-280 RMB.

**Day 4: Panda Base**

Morning:
- Go to the Chengdu Research Base of Giant Panda Breeding.
- See the adorable giant pandas.
- Ticket: 55 RMB.
- Recommended to arrive before 9 AM (when pandas are most active).

Noon:
- Dine at a restaurant near the base.
- Per person: 80-100 RMB.

Afternoon:
- Return to the city, shop at Chunxi Road.
- Or drink tea and play mahjong in a teahouse (experience Chengdu's slow life).

Evening:
- Prepare for departure.

**Budget (per person)**:
- Accommodation: 500 RMB/night × 3 nights = 1500 RMB
- Food: ~800 RMB
- Tickets and transportation: ~500 RMB
- Entertainment (face-changing show, etc.): ~300 RMB
- Total: ~3000-3500 RMB

**Food List**:
- Must-eats: Hot pot, Chuan Chuan, Malatang, Dan Dan Noodles, Longchaoshou.
- Desserts: San Da Pao, Brown Sugar Rice Cake.
- Snacks: Fuqi Feipian, Zhong Dumplings, Han Baozi.

**Accommodation Recommendations**:
- Chunxi Road/Taikoo Li area: Convenient transportation, good for shopping.
- Near Kuanzhai Alley: Good atmosphere, experience Chengdu life.

Enjoy your trip to Chengdu! Let me know if you need any adjustments.
```

### Example 3: Weekend Short Trip

```text
User: I want to take a one-day trip around Beijing this weekend. I like historical sites. Any recommendations?

Agent: Based on your needs, here are some recommendations for a one-day trip around Beijing:

**Recommendation 1: Badaling Great Wall**

Itinerary:
- 7:30 AM: Depart (to avoid crowds).
- 9:00 AM: Arrive at Badaling Great Wall.
- 9:00 AM - 12:00 PM: Climb the Great Wall and experience the saying "He who has not been to the Great Wall is not a true man."
- 12:00 PM - 1:00 PM: Lunch nearby.
- 1:30 PM - 3:00 PM: Visit the Great Wall Museum.
- 3:30 PM: Return.

Cost: Ticket 40 RMB, round-trip transportation ~50 RMB.

**Recommendation 2: Mutianyu Great Wall (less crowded, more beautiful scenery)**

Suitable for tourists who want to avoid crowds. The scenery is more pristine and the experience is better.

**Recommendation 3: Gubei Water Town**

Has both historical sites and a unique town feel. You can enjoy hot springs and local food.

Which one do you prefer? I can plan a detailed itinerary for you!
```

## Effect Demonstration

## Technical Points

### Professional Instruction System

The core of this example is the detailed professional instruction system ([agent.py](agent.py:21-94)), which includes:

**1. Role Definition**:

```text
You are a professional travel itinerary planner, skilled at creating travel plans that include natural attractions, cultural sites, and local cuisine based on user needs and local conditions.
```

**2. Goal Setting**:

- Plan a complete itinerary according to user needs.
- Combine natural attractions, cultural sites, and local cuisine.
- Use appropriate tools to meet requirements.

**3. Workflow**:

1. Communicate with the user to clarify needs (time, budget, preferences, etc.).
2. Use tools to gather information.
3. Plan a preliminary itinerary based on the information.
4. Evaluate and adjust to ensure reasonableness.
5. Present the itinerary and modify based on feedback.

**4. Constraints**:

- Must combine natural attractions, cultural sites, and cuisine.
- Content must be consistent with local conditions.
- Must use tools for information gathering.
- Prohibit planning unreasonable or infeasible itineraries.

**5. Output Format**:

- Clear and organized text.
- Daily itinerary.
- Attraction introductions, food recommendations.
- Professional and practical writing style.

### Web Search Tool Usage

**Tool Integration** ([agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py#L104)):

```python
from veadk.tools.builtin_tools.web_search import web_search

root_agent = Agent(
    tools=[web_search],
)
```

**Search Strategy**:

The Agent automatically organizes search keywords based on user needs:

- Destination + "tourist attractions recommendation"
- Destination + "specialty food"
- Destination + "accommodation and transportation"
- Destination + "travel guide"

**Result Processing**:

The Agent will:

1. Extract key information from multiple search results.
2. Verify the authenticity and timeliness of the information.
3. Synthesize information from multiple sources to plan.
4. Filter out ads and irrelevant content.

### 🎯 Extension Directions

### 1. Enhance Information Sources

- **Integrate Map API**: Get real-time distances and routes.
- **Weather API**: Adjust itinerary based on weather conditions.
- **Review Data**: Incorporate ratings from Dianping, Ctrip, etc.

### 2. Personalized Recommendations

- **User Profile**: Record user's historical preferences.
- **Intelligent Recommendations**: Recommend attractions based on historical data.
- **Dynamic Adjustments**: Adjust itinerary based on real-time feedback.

### 3. Automated Services

- **Booking Integration**: Automatically book hotels and tickets.
- **Itinerary Reminders**: Send itinerary reminders and notes.
- **Tour Guide Service**: Provide real-time tours and explanations.

## Related Examples

After completing Travel Concierge, you can explore:

1. **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world/README.md)** - Learn about basic Agents.
2. **[MCP Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple/README.md)** - Integrate more professional tools.
3. **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents/README.md)** - Build multi-agent collaboration.
4. **[Video Generator](../../video_gen/README.md)** - Complex toolchain orchestration.

## FAQ

None.

## References

- [VeADK Official Documentation](https://volcengine.github.io/veadk-python/)
- [AgentKit Development Guide](https://volcengine.github.io/agentkit-sdk-python/)
- [Volcano Ark Model Service](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## Code License

This project is licensed under the Apache 2.0 License.
