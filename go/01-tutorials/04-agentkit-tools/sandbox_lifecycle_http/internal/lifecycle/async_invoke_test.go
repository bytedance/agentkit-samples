package lifecycle

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestExecutionActionsUseProviderDataPlane(t *testing.T) {
	for _, provider := range []string{"volcengine", "byteplus"} {
		for _, override := range []string{"", "custom.example.test"} {
			t.Run(provider+"/"+override, func(t *testing.T) {
				t.Setenv("VOLCENGINE_AGENTKIT_HOST", "")
				t.Setenv("VOLC_AGENTKIT_HOST", "")
				t.Setenv("BYTEPLUS_AGENTKIT_HOST", "")
				t.Setenv(strings.ToUpper(provider)+"_AGENTKIT_HOST", override)
				region, management, wantHost := "cn-beijing", "open.volcengineapi.com", "agentkit.cn-beijing.volces.com"
				if provider == "byteplus" {
					region, management, wantHost = "ap-southeast-1", "agentkit.ap-southeast-1.byteplusapi.com", "agentkit.ap-southeast-1.bytepluses.com"
				}
				if override != "" {
					management, wantHost = override, override
				}
				client := &Client{
					endpoint:    EndpointConfig{Provider: provider, Region: region, Host: management, Service: "agentkit", APIVersion: APIVersion, Scheme: "https"},
					credentials: Credentials{AccessKey: "offline-ak", SecretKey: "offline-sk"},
				}
				for _, action := range []string{"InvokeTool", "AsyncExecCommand", "ViewAsyncCommand"} {
					client.httpClient = &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
						if r.URL.Host != wantHost || r.Host != wantHost || r.URL.Query().Get("Action") != action || r.URL.Query().Get("Version") != APIVersion {
							t.Fatalf("unexpected routing for %s: %s, Host=%s", action, r.URL, r.Host)
						}
						if r.Method != "POST" || r.Header.Get("Authorization") == "" || r.Header.Get("X-Content-Sha256") == "" {
							t.Fatal("missing signed POST request")
						}
						return jsonResponse(200, `{"Result":{}}`), nil
					})}
					methods := map[string]func(map[string]any) (map[string]any, error){"InvokeTool": client.InvokeTool, "AsyncExecCommand": client.AsyncExecCommand, "ViewAsyncCommand": client.ViewAsyncCommand}
					if _, err := methods[action](map[string]any{"ToolId": "t-test", "SessionId": "s-test"}); err != nil {
						t.Fatal(err)
					}
				}
				if client.endpoint.Host != management {
					t.Fatal("execution changed the management endpoint")
				}
			})
		}
	}
}

func prepareAsyncScenario(t *testing.T, viewOnly bool, results []map[string]any, changeSubmit func(map[string]any)) (*[]string, func() map[string]any) {
	t.Helper()
	for _, entry := range os.Environ() {
		key := strings.SplitN(entry, "=", 2)[0]
		if strings.HasPrefix(key, "AGENTKIT_") || strings.HasPrefix(key, "VOLC") || strings.HasPrefix(key, "BYTEPLUS_") || key == "CLOUD_PROVIDER" || key == "REGION" {
			t.Setenv(key, "")
		}
	}
	t.Setenv("AGENTKIT_LIFECYCLE_STATE", filepath.Join(t.TempDir(), "state.json"))
	t.Setenv("AGENTKIT_CLOUD_PROVIDER", "volcengine")
	t.Setenv("VOLCENGINE_ACCESS_KEY", "offline-ak")
	t.Setenv("VOLCENGINE_SECRET_KEY", "offline-sk")
	t.Setenv("AGENTKIT_ASYNC_COMMAND", "printf hello")
	t.Setenv("AGENTKIT_ASYNC_EXEC_DIR", "/tmp")
	t.Setenv("AGENTKIT_ASYNC_POLL_INTERVAL_SECONDS", "1")
	t.Setenv("AGENTKIT_ASYNC_WAIT_TIMEOUT_SECONDS", "1")
	state := map[string]any{"tool_id": "t-test", "instance_id": "s-test", "snapshot_id": "snap-preserved", "async_task_id": "old-task", "async_view_response": map[string]any{"Output": "stale"}}
	if viewOnly {
		state["async_task_id"] = "task-test"
	}
	if err := SaveState(state); err != nil {
		t.Fatal(err)
	}
	load := func() map[string]any {
		state, err := LoadState()
		if err != nil {
			t.Fatal(err)
		}
		return state
	}
	calls := []string{}
	queries := 0
	oldTransport := http.DefaultTransport
	t.Cleanup(func() { http.DefaultTransport = oldTransport })
	http.DefaultTransport = roundTripFunc(func(r *http.Request) (*http.Response, error) {
		action := r.URL.Query().Get("Action")
		calls = append(calls, action)
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["ToolId"] != "t-test" || body["SessionId"] != "s-test" {
			t.Fatalf("wrong target: %v", body)
		}
		for _, key := range []string{"Ttl", "UserSessionId", "OperationPayload"} {
			if _, exists := body[key]; exists {
				t.Fatalf("unexpected field %s", key)
			}
		}
		result := map[string]any{"ToolId": "t-test", "SessionId": "s-test", "TaskId": "task-test", "Status": "running"}
		switch action {
		case "AsyncExecCommand":
			if viewOnly || body["Command"] != "printf hello" || body["ExecDir"] != "/tmp" {
				t.Fatalf("unexpected submission: %v", body)
			}
			if changeSubmit != nil {
				changeSubmit(result)
			}
		case "ViewAsyncCommand":
			if body["TaskId"] != "task-test" || load()["async_task_id"] != "task-test" {
				t.Fatal("task must be persisted before querying")
			}
			if queries == 0 && !viewOnly && load()["async_view_response"] != nil {
				t.Fatal("stale query result was not cleared")
			}
			index := queries
			if index >= len(results) {
				index = len(results) - 1
			}
			for key, value := range results[index] {
				result[key] = value
			}
			queries++
		default:
			t.Fatalf("unexpected action %s", action)
		}
		if envelope, ok := result["APIError"]; ok {
			data, _ := json.Marshal(map[string]any{"ResponseMetadata": map[string]any{"Error": envelope}})
			return jsonResponse(400, string(data)), nil
		}
		data, _ := json.Marshal(map[string]any{"Result": result})
		return jsonResponse(200, string(data)), nil
	})
	return &calls, load
}

func TestAsyncInvokeCompletedAfterRunning(t *testing.T) {
	calls, load := prepareAsyncScenario(t, false, []map[string]any{
		{"Status": "running", "ExitCode": 99},
		{"Status": "completed", "ExitCode": 0, "Command": "", "Output": "hello\nhttps://example.test/?Authorization=secret&x=1"},
	}, nil)
	if err := RunAsyncInvoke(false); err != nil {
		t.Fatal(err)
	}
	if len(*calls) != 3 || (*calls)[0] != "AsyncExecCommand" {
		t.Fatalf("unexpected requests %v", *calls)
	}
	state := load()
	if state["snapshot_id"] != "snap-preserved" || state["async_task_id"] != "task-test" {
		t.Fatal("state was lost")
	}
	if strings.Contains(state["async_view_response"].(map[string]any)["Output"].(string), "secret") {
		t.Fatal("output was not redacted")
	}
}

func TestAsyncViewOnlyAndTerminalStates(t *testing.T) {
	for _, tc := range []struct {
		name, status string
		code         any
		wantError    bool
	}{
		{"documented-success", "Succeeded", 0, false},
		{"observed-completion", " Completed ", 0, false},
		{"failed", "failed", 1, true},
		{"unknown", "unknown", 0, true},
		{"nonzero", "completed", 2, true},
		{"missing-code", "completed", nil, true},
		{"boolean-code", "completed", false, true},
		{"unexpected-status", "unexpected", 0, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			calls, load := prepareAsyncScenario(t, true, []map[string]any{{"Status": tc.status, "ExitCode": tc.code}}, nil)
			t.Setenv("AGENTKIT_ASYNC_COMMAND", "") // Query-only ignores command settings.
			err := RunAsyncInvoke(true)
			if (err != nil) != tc.wantError {
				t.Fatalf("error = %v, wantError = %v", err, tc.wantError)
			}
			if len(*calls) != 1 || (*calls)[0] != "ViewAsyncCommand" || load()["async_view_response"].(map[string]any)["Status"] != tc.status {
				t.Fatal("query-only must save the result without submitting")
			}
		})
	}
}

func TestAsyncTimeoutPreservesTask(t *testing.T) {
	_, load := prepareAsyncScenario(t, false, []map[string]any{{"Status": "running", "Output": "partial"}}, nil)
	err := RunAsyncInvoke(false)
	if err == nil || !strings.Contains(err.Error(), "--view-only") {
		t.Fatalf("expected recoverable timeout, got %v", err)
	}
	if load()["async_task_id"] != "task-test" {
		t.Fatal("lost task after timeout")
	}
}

func TestAsyncRejectsWrongTargetAndAPIError(t *testing.T) {
	for _, key := range []string{"ToolId", "SessionId", "TaskId", "APIError"} {
		t.Run(key, func(t *testing.T) {
			value := any("wrong")
			if key == "APIError" {
				value = map[string]any{"Code": "InvalidTask", "Message": "not found"}
			}
			_, load := prepareAsyncScenario(t, false, []map[string]any{{key: value}}, nil)
			if err := RunAsyncInvoke(false); err == nil {
				t.Fatal("expected failure")
			}
			if load()["async_task_id"] != "task-test" || load()["async_view_response"] != nil {
				t.Fatal("invalid query result should not overwrite task state")
			}
		})
	}
}
