## Description: <br>
Searches configured Viking knowledge collections through an APIG gateway and returns relevant chunks, scores, and document metadata. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[volcengine-skills](https://clawhub.ai/user/volcengine-skills) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
Agents use this skill to answer user questions with content from authorized Viking knowledge collections. It supports collection metadata checks, single-collection search, and parallel multi-collection search. <br>

### Deployment Geography for Use: <br>
Global, subject to the configured Volcengine/Viking APIG service region. <br>

## Known Risks and Mitigations: <br>
Risk: Search queries and API credentials are sent to the configured APIG service. <br>
Mitigation: Treat queries and credentials as sensitive, use the configured gateway, and never expose environment variables or API keys in responses. <br>
Risk: Long task descriptions can dilute semantic retrieval and return low-quality chunks. <br>
Mitigation: Split the task into 2-4 independent keyword queries and run them separately, as required by the skill instructions. <br>
Risk: The skill can access only authorized collections. <br>
Mitigation: Restrict searches to `DATABASE_VIKING_COLLECTION`; if access is denied, use the allowed list or report the permission issue instead of guessing collection names or IDs. <br>


## Reference(s): <br>
- [Byted Viking Search Knowledgebase on ClawHub](https://clawhub.ai/volcengine-skills/byted-viking-search-knowledgebase) <br>


## Skill Output: <br>
**Output Type(s):** [text, JSON, shell commands, configuration guidance] <br>
**Output Format:** [JSON search results and command guidance] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Requires APIG credentials and an authorized collection allowlist before execution.] <br>

## Skill Version(s): <br>
1.0.2 (source: server release metadata) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review retrieved content before relying on it, and apply their organization's safety, security, and compliance requirements before deployment. <br>
