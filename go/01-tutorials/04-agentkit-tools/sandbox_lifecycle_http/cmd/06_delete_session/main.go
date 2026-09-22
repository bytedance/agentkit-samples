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

	response, err := client.DeleteSession(map[string]any{
		"ToolId":    toolID,
		"SessionId": instanceID,
	})
	if err != nil {
		return err
	}
	deletedID := fmt.Sprint(response["SessionId"])
	if deletedID == "" || deletedID == "<nil>" {
		deletedID = instanceID
	}
	if deletedID != instanceID {
		return fmt.Errorf("DeleteSession returned unexpected SessionId %s; expected %s", deletedID, instanceID)
	}

	state["deleted_at"] = lifecycle.UTCNow()
	state["delete_response"] = response
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}
	output, err := lifecycle.OutputWithStateFile(state)
	if err != nil {
		return err
	}
	return lifecycle.PrintJSON(output)
}
