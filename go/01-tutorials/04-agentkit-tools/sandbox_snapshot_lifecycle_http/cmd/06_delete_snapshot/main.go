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

	response, err := client.DeleteSessionSnapshot(map[string]any{
		"ToolId":     toolID,
		"SnapshotId": snapshotID,
	})
	if err != nil {
		return err
	}
	deletedID := fmt.Sprint(response["SnapshotId"])
	if deletedID == "" || deletedID == "<nil>" {
		deletedID = snapshotID
	}
	if deletedID != snapshotID {
		return fmt.Errorf("DeleteSessionSnapshot returned unexpected SnapshotId %s; expected %s", deletedID, snapshotID)
	}

	state["snapshot_deleted_at"] = lifecycle.UTCNow()
	state["delete_snapshot_response"] = response
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}

	remaining, err := lifecycle.WaitUntil(
		fmt.Sprintf("snapshot %s to disappear from the tool", snapshotID),
		func() ([]map[string]any, error) {
			return lifecycle.ListAllSnapshots(client, toolID)
		},
		func(snapshots []map[string]any) bool {
			for _, snapshot := range snapshots {
				if fmt.Sprint(snapshot["SnapshotId"]) == snapshotID {
					return false
				}
			}
			return true
		},
		func(_ []map[string]any) bool { return false },
	)
	if err != nil {
		return err
	}
	state["snapshot_delete_verified_at"] = lifecycle.UTCNow()
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}
	path, err := lifecycle.StatePath()
	if err != nil {
		return err
	}
	return lifecycle.PrintJSON(map[string]any{
		"state_file":               path,
		"deleted_snapshot_id":      snapshotID,
		"remaining_tool_snapshots": remaining,
	})
}
