from scripts.discover_a2a_card import card_url, extract_card_summary


def test_card_url_accepts_service_and_rpc_urls():
    assert (
        card_url("https://agent.example/runtime/")
        == "https://agent.example/runtime/.well-known/agent-card.json"
    )
    assert (
        card_url("https://agent.example/runtime/a2a")
        == "https://agent.example/runtime/.well-known/agent-card.json"
    )


def test_extract_card_summary_uses_agentcard_capabilities():
    assert extract_card_summary(
        {
            "name": "hybrid-cloud-complaint-data-agent",
            "skills": [{"id": "complaint-trend-analysis", "name": "投诉趋势分析"}],
        }
    ) == {
        "name": "hybrid-cloud-complaint-data-agent",
        "capability_ids": ["complaint-trend-analysis"],
    }
