package main

import (
	"fmt"

	"sandbox_snapshot_lifecycle_http/internal/lifecycle"
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

	response, err := client.CreateSessionSnapshot(map[string]any{
		"ToolId":    toolID,
		"SessionId": instanceID,
	})
	if err != nil {
		return err
	}
	snapshotID := fmt.Sprint(response["SnapshotId"])
	if snapshotID == "" || snapshotID == "<nil>" {
		return fmt.Errorf("CreateSessionSnapshot response is missing SnapshotId")
	}

	state["snapshot_id"] = snapshotID
	state["snapshot_requested_at"] = lifecycle.UTCNow()
	state["create_snapshot_response"] = response
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}

	snapshot, err := lifecycle.WaitForSnapshot(client, toolID, snapshotID)
	if err != nil {
		return err
	}
	state["snapshot"] = snapshot
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}
	output, err := lifecycle.OutputWithStateFile(state)
	if err != nil {
		return err
	}
	return lifecycle.PrintJSON(output)
}
