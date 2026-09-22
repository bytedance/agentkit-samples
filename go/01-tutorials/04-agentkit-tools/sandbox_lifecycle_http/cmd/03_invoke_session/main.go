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
	payload, err := lifecycle.InvokePayloadJSON()
	if err != nil {
		return err
	}
	client, err := lifecycle.NewClient()
	if err != nil {
		return err
	}

	response, err := client.InvokeTool(map[string]any{
		"ToolId":           toolID,
		"SessionId":        instanceID,
		"OperationType":    "RunCode",
		"OperationPayload": payload,
	})
	if err != nil {
		return err
	}
	responseSessionID := fmt.Sprint(response["SessionId"])
	if responseSessionID != instanceID {
		return fmt.Errorf("InvokeTool returned unexpected SessionId %q; expected %s", responseSessionID, instanceID)
	}

	result := lifecycle.ParseInvokeResult(response["Result"])
	state["invoked_at"] = lifecycle.UTCNow()
	state["invoke_response"] = response
	state["invoke_result"] = result
	if err := lifecycle.SaveState(state); err != nil {
		return err
	}
	output, err := lifecycle.OutputWithStateFile(state)
	if err != nil {
		return err
	}
	if err := lifecycle.PrintJSON(output); err != nil {
		return err
	}
	if lifecycle.InvokeResultFailed(result) {
		return fmt.Errorf("RunCode failed; see invoke_result in the output")
	}
	return nil
}
