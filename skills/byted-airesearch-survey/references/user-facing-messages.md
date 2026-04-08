# User-Facing Messages

Use these wording patterns to keep the production skill stable and product-like.

## API key required

Tell the user:

- first-time use requires binding an API key
- the API key can be obtained from the fixed console URL
- after sending the key, the skill will continue the previous request without requiring the user to repeat the research need

## API key invalid or expired

Tell the user:

- the current API key is invalid or expired
- they should get a new key from the same URL
- after sending the new key, the skill can continue the previous request directly

## No plan in current session

Tell the user:

- there is no research plan in the current session yet
- they should first describe the research need

## Service temporarily unavailable

Tell the user:

- the request did not start successfully this time
- they can retry later
- they can also check progress later with an explicit follow-up query

## Unsupported industry

Tell the user:

- the current industry is not directly supported
- supported industries are limited to the known executable set
- they can revise the request and continue in the same conversation

## Execution failed

Tell the user:

- the research execution failed
- they can revise the request, retry, or restart
- do not imply that a valid result exists
