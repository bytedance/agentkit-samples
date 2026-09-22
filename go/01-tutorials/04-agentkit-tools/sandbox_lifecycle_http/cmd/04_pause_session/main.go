package main

import (
	"fmt"

	"sandbox_lifecycle_http/internal/lifecycle"
)

func main() {
	lifecycle.Main(run)
}

func run() error {
	state, err := lifecycle.LoadState()
	if err != nil {
		return err
	}
	toolID, err := lifecycle.ResolveToolID(state)
	if err != nil {
		return err
	}
	instanceID, err := lifecycle.RequireString(state, "instance_id")
	if err != nil {
		return err
	}
	client, err := lifecycle.NewClient()
	if err != nil {
		return err
	}

	response, err := client.PauseSession(map[string]any{
		"ToolId":    toolID,
		"SessionId": instanceID,
	})
	if err != nil {
		return err
	}
	responseSessionID := fmt.Sprint(response["SessionId"])
	if responseSessionID == "" || responseSessionID == "<nil>" {
		responseSessionID = instanceID
	}
	if responseSessionID != instanceID {
		return fmt.Errorf("PauseSession returned unexpected SessionId %s; expected %s", responseSessionID, instanceID)
	}

	state["pause_requested_at"] = lifecycle.UTCNow()
	state["pause_response"] = response
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}

	session, err := lifecycle.WaitForPausedSession(client, toolID, instanceID)
	if err != nil {
		return err
	}
	state["paused_at"] = lifecycle.UTCNow()
	state["paused_session"] = session
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}
	output, err := lifecycle.OutputWithStateFile(state)
	if err != nil {
		return err
	}
	return lifecycle.PrintJSON(output)
}
