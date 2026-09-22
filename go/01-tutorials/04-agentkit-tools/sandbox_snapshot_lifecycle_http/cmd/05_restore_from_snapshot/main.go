package main

import (
	"fmt"
	"strings"

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
	originalInstanceID, err := lifecycle.RequireString(state, "instance_id")
	if err != nil {
		return err
	}
	if state["deleted_at"] != nil || state["snapshot_deleted_at"] != nil {
		return fmt.Errorf("the session or snapshot has already been deleted; start a new lifecycle from 01_create_session")
	}
	ttl, err := lifecycle.TTLSeconds()
	if err != nil {
		return err
	}
	client, err := lifecycle.NewClient()
	if err != nil {
		return err
	}

	request := map[string]any{
		"ToolId":            toolID,
		"SnapshotId":        snapshotID,
		"Ttl":               ttl,
		"CreateNewInstance": false,
	}
	response, err := lifecycle.RetryOnException(
		fmt.Sprintf("session %s to expire and finish terminating", originalInstanceID),
		func() (map[string]any, error) {
			return client.ResumeSessionFromSnapshot(request)
		},
		func(err error) bool {
			return strings.Contains(err.Error(), "InvalidSnapshot.InstanceAlreadyExists") ||
				strings.Contains(err.Error(), "InvalidSnapshot.InstanceStatus") ||
				strings.Contains(err.Error(), "InvalidSnapshot.InstanceTerminating")
		},
	)
	if err != nil {
		return err
	}
	restoredInstanceID := fmt.Sprint(response["SessionId"])
	if restoredInstanceID == "" || restoredInstanceID == "<nil>" {
		return fmt.Errorf("ResumeSessionFromSnapshot response is missing SessionId")
	}
	if restoredInstanceID != originalInstanceID {
		return fmt.Errorf("backend did not preserve the sandbox instance ID: expected %s, got %s", originalInstanceID, restoredInstanceID)
	}

	state["restored_at"] = lifecycle.UTCNow()
	state["restored_instance_id"] = restoredInstanceID
	state["restored_ttl_seconds"] = ttl
	state["resume_response"] = response
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}

	session, err := lifecycle.WaitForSession(client, toolID, restoredInstanceID)
	if err != nil {
		return err
	}
	state["restored_session"] = session
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}
	output, err := lifecycle.OutputWithStateFile(state)
	if err != nil {
		return err
	}
	return lifecycle.PrintJSON(output)
}
