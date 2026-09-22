package lifecycle

import (
	"encoding/json"
	"testing"
)

func TestRedactSensitiveValues(t *testing.T) {
	value := map[string]any{
		"endpoint": "https://example.com/?Authorization=secret-token&x=1",
		"nested": []any{
			"https://example.com/?x=1&Authorization=another-secret",
		},
	}
	redacted := RedactSensitiveValues(value).(map[string]any)

	if redacted["endpoint"] != "https://example.com/?Authorization=<redacted>&x=1" {
		t.Fatalf("endpoint = %v", redacted["endpoint"])
	}
	nested := redacted["nested"].([]any)
	if nested[0] != "https://example.com/?x=1&Authorization=<redacted>" {
		t.Fatalf("nested[0] = %v", nested[0])
	}
}

func TestResolveToolIDRejectsConflictingEnvironment(t *testing.T) {
	t.Setenv("AGENTKIT_TOOL_ID", "tool-a")
	t.Setenv("AGENTKIT_SANDBOX_TOOL_ID", "tool-b")

	if _, err := ResolveToolID(nil); err == nil {
		t.Fatal("expected conflicting tool ID error")
	}
}

func TestInvokePayloadJSONUsesEnvironment(t *testing.T) {
	t.Setenv("AGENTKIT_INVOKE_CODE", "print(123)")
	t.Setenv("AGENTKIT_INVOKE_TIMEOUT_SECONDS", "9")
	t.Setenv("AGENTKIT_INVOKE_KERNEL_NAME", "python-custom")

	payload, err := InvokePayloadJSON()
	if err != nil {
		t.Fatal(err)
	}
	var decoded map[string]any
	if err := json.Unmarshal([]byte(payload), &decoded); err != nil {
		t.Fatal(err)
	}
	if decoded["code"] != "print(123)" {
		t.Fatalf("code = %v, want print(123)", decoded["code"])
	}
	if decoded["timeout"] != float64(9) {
		t.Fatalf("timeout = %v, want 9", decoded["timeout"])
	}
	if decoded["kernel_name"] != "python-custom" {
		t.Fatalf("kernel_name = %v, want python-custom", decoded["kernel_name"])
	}
}

func TestInvokeResultFailed(t *testing.T) {
	if !InvokeResultFailed(map[string]any{"success": false}) {
		t.Fatal("success=false should fail")
	}
	if !InvokeResultFailed(map[string]any{"data": map[string]any{"status": "error"}}) {
		t.Fatal("data.status=error should fail")
	}
	if InvokeResultFailed(map[string]any{"success": true}) {
		t.Fatal("success=true should not fail")
	}
}
