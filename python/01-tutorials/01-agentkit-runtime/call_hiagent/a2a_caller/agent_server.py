from veadk.integrations.agentkit import create_agentkit_app, run_agentkit_app

from veadk_agent import root_agent


app = create_agentkit_app(root_agent)


if __name__ == "__main__":
    run_agentkit_app(app, host="0.0.0.0")
