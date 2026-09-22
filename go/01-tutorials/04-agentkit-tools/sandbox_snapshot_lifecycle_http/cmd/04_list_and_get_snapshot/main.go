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
	snapshotID, err := lifecycle.RequireString(state, "snapshot_id")
	if err != nil {
		return err
	}
	client, err := lifecycle.NewClient()
	if err != nil {
		return err
	}

	snapshots, err := lifecycle.ListAllSnapshots(client, toolID)
	if err != nil {
		return err
	}
	found := false
	for _, snapshot := range snapshots {
		if fmt.Sprint(snapshot["SnapshotId"]) == snapshotID {
			found = true
			break
		}
	}
	if !found {
		return fmt.Errorf("new snapshot %s was not returned by ListSessionSnapshots", snapshotID)
	}

	response, err := client.GetSessionSnapshot(map[string]any{
		"ToolId":     toolID,
		"SnapshotId": snapshotID,
	})
	if err != nil {
		return err
	}
	if response["Snapshot"] == nil {
		return fmt.Errorf("GetSessionSnapshot response is missing Snapshot")
	}

	state["snapshots_listed_at"] = lifecycle.UTCNow()
	state["listed_snapshot_count"] = len(snapshots)
	state["snapshot"] = response
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}
	path, err := lifecycle.StatePath()
	if err != nil {
		return err
	}
	return lifecycle.PrintJSON(map[string]any{
		"state_file":         path,
		"all_tool_snapshots": snapshots,
		"new_snapshot":       response,
	})
}
