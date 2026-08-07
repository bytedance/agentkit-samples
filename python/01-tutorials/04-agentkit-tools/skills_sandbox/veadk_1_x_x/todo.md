3 * 3

(local_skills, remote_registry, local_skills + remote_registry) * (runtime, runtime + skills_sandbox, runtime + aio_sandbox)


[xf, todo], case3: remote_registry, skills_sandbox
runtime agent (execute_skills) -> skills sandbox (veadk agent -> runtime)
runtime agent system prompt: 你是一个技能执行小助手，但你不能直接执行技能，只能调用execute_skills工具。所以你收到请求后，你需要先调用execute_skills工具，才能完成任务。
runtime agent (skills=[ss-xxx], 不给挂bashtool) -> skills sandbox (veadk agent -> runtime, bashtool)

[xf, todo], case8: remote_registry, aio_sandbox
runtime agent (run_code) -> aio sandbox
runtime agent system prompt: 你是一个xx小助手，你有run_code工具。假设你需要执行skills来完成任务，在执行skills过程中，如果有需要跑的代码、执行一些shell命令，需要调用run_code工具来完成。


[ok], case2: local_skills, runtime
[ok], case4: remote_registry, runtime
[ok], case6: local_skills + remote_registry, runtime

[不推荐，之后看需求再搞], case9: local_skills + remote_registry, aio_sandbox
[不推荐，之后看需求再搞], case7: local_skills, aio_sandbox
[不推荐，之后看需求再搞], case5: local_skills + remote_registry, skills_sandbox
[不推荐，之后看需求再搞], case1: local_skills, skills_sandbox

