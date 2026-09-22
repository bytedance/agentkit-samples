package main

import (
	"fmt"
	"os"
	"strings"

	"sandbox_lifecycle_http/internal/lifecycle"
)

func main() {
	lifecycle.Main(run)
}

func run() error {
	state := map[string]any{}
	if path, err := lifecycle.StatePath(); err != nil {
		return err
	} else if _, err := os.Stat(path); err == nil {
		state, err = lifecycle.LoadState()
		if err != nil {
			return err
		}
	} else if !os.IsNotExist(err) {
		return err
	}

	toolID, err := lifecycle.ResolveToolID(state)
	if err != nil {
		return err
	}
	sessionID := strings.TrimSpace(os.Getenv("AGENTKIT_SESSION_ID"))
	if sessionID == "" {
		if _, ok := state["instance_id"]; ok {
			sessionID, err = lifecycle.RequireString(state, "instance_id")
			if err != nil {
				return err
			}
		}
	}

	client, err := lifecycle.NewClient()
	if err != nil {
		return err
	}
	sessions, err := lifecycle.ListAllSessions(client, toolID)
	if err != nil {
		return err
	}
	var session any
	if sessionID != "" {
		response, err := client.GetSession(map[string]any{
			"ToolId":    toolID,
			"SessionId": sessionID,
		})
		if err != nil {
			return err
		}
		responseSessionID := strings.TrimSpace(fmt.Sprint(response["SessionId"]))
		if responseSessionID != sessionID {
			return fmt.Errorf("GetSession returned unexpected SessionId %q; expected %s", responseSessionID, sessionID)
		}
		session = response
	}
	return lifecycle.PrintJSON(map[string]any{
		"tool_id":              toolID,
		"listed_session_count": len(sessions),
		"all_tool_sessions":    sessions,
		"session":              session,
	})
}
