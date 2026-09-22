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
	toolID, err := lifecycle.ResolveToolID(nil)
	if err != nil {
		return err
	}
	ttl, err := lifecycle.TTLSeconds()
	if err != nil {
		return err
	}
	userSessionID := strings.TrimSpace(os.Getenv("AGENTKIT_USER_SESSION_ID"))
	if userSessionID == "" {
		userSessionID, err = lifecycle.RandomUserSessionID()
		if err != nil {
			return err
		}
	}

	client, err := lifecycle.NewClient()
	if err != nil {
		return err
	}
	response, err := client.CreateSession(map[string]any{
		"ToolId":        toolID,
		"Ttl":           ttl,
		"TtlUnit":       "second",
		"UserSessionId": userSessionID,
	})
	if err != nil {
		return err
	}
	instanceID := fmt.Sprint(response["SessionId"])
	if instanceID == "" || instanceID == "<nil>" {
		return fmt.Errorf("CreateSession response is missing SessionId")
	}

	state := map[string]any{
		"tool_id":         toolID,
		"user_session_id": response["UserSessionId"],
		"instance_id":     instanceID,
		"ttl_seconds":     ttl,
		"created_at":      lifecycle.UTCNow(),
		"create_response": response,
	}
	if state["user_session_id"] == nil || state["user_session_id"] == "" {
		state["user_session_id"] = userSessionID
	}
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}

	session, err := lifecycle.WaitForSession(client, toolID, instanceID)
	if err != nil {
		return err
	}
	state["session"] = session
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}
	output, err := lifecycle.OutputWithStateFile(state)
	if err != nil {
		return err
	}
	return lifecycle.PrintJSON(output)
}
