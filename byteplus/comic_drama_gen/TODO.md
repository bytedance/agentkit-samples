# TODO Items

Housekeeping tasks to carry out as part of improvements to the codebase.

- [ ] Remove the `llm_client` exclude workaround in agent.py once google-adk stops
      leaking the live client into `/dev/apps/{app}/build_graph`. Still needed as of
      google-adk 2.2.0. Recheck by commenting the block out and loading the Dev UI;
      a 500 on `build_graph` means it is still required.
- [ ] Remove the `_parse_tool_call_arguments` json-repair workaround in agent.py
      once google-adk can tolerate malformed tool-call JSON from the model
      (unescaped quotes inside prompt strings). Still needed as of google-adk
      2.2.0 — the model error otherwise aborts the whole workflow run with a
      `json.decoder.JSONDecodeError`.
- [ ] agent.py still uses the deprecated `Agent(skills=..., skills_mode="local")`
      loading path (veadk 1.0.9 logs a deprecation warning suggesting
      `google.adk.skills.load_skill_from_dir` / `SkillToolset`). Migrate when the
      legacy path is removed.
- [ ] The skill's `web_search.py` signs requests against the Volcano Engine
      torchlight endpoint (`mercury.volcengineapi.com`), which currently accepts
      BytePlus credentials too. Switch to a BytePlus-native search API (e.g.
      Searchinfinity, as veadk's builtin web_search does when
      CLOUD_PROVIDER=byteplus) for correctness.
