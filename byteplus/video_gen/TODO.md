# TODO Items

Housekeeping tasks to carry out as part of improvements to the codebase. 

- [x] Remove the `llm_client` exclude workaround in agent.py once google-adk stops
      leaking the live client into `/dev/apps/{app}/build_graph`. Still needed as of
      google-adk 2.2.0 — it is not specific to the old 1.32.0 pin. Recheck by
      commenting the block out and loading the Dev UI; a 500 on `build_graph` means
      it is still required.
- [ ] Remove the `_parse_tool_call_arguments` json-repair workaround in agent.py
      once google-adk can tolerate malformed tool-call JSON from the model
      (unescaped quotes inside prompt strings). Still needed as of google-adk
      2.6.2 — the model error otherwise aborts the whole workflow run with a
      `json.decoder.JSONDecodeError`.
- [ ] Remove the agent.yaml prompt guardrail forbidding `sequential_image_generation`
      / `max_images` / `output_format` / `tools` in image_generate tasks once the
      BytePlus image model (`dola-seedream-5-0-pro-260628`) supports them, or once
      veadk stops forwarding `sequential_image_generation: "disabled"` to the API
      (veadk's image_generate sends the field whenever the LLM passes any non-empty
      value, and the model rejects it with a 400 InvalidParameter).
