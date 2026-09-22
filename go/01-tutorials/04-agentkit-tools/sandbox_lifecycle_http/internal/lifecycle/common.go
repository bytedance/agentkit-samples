package lifecycle

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

const (
	defaultTTLSeconds          = 8 * 60 * 60
	defaultWaitTimeoutSeconds  = 10 * 60
	defaultPollIntervalSeconds = 5
	defaultInvokeTimeout       = 30
	stateFileEnv               = "AGENTKIT_LIFECYCLE_STATE"
)

var authorizationQueryRE = regexp.MustCompile(`(?i)(Authorization=)[^&\s]+`)

func Main(run func() error) {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}

func UTCNow() string {
	return time.Now().UTC().Format(time.RFC3339Nano)
}

func StatePath() (string, error) {
	if configured := env(stateFileEnv); configured != "" {
		if strings.HasPrefix(configured, "~") {
			home, err := os.UserHomeDir()
			if err != nil {
				return "", err
			}
			if configured == "~" {
				configured = home
			} else if strings.HasPrefix(configured, "~/") {
				configured = filepath.Join(home, configured[2:])
			}
		}
		return filepath.Abs(configured)
	}
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		return "", fmt.Errorf("cannot resolve default state path")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", ".sandbox_state.json")), nil
}

func LoadState() (map[string]any, error) {
	path, err := StatePath()
	if err != nil {
		return nil, err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("state file does not exist: %s; run 01_create_session first", path)
		}
		return nil, err
	}
	var state map[string]any
	if err := json.Unmarshal(data, &state); err != nil {
		return nil, fmt.Errorf("state file must contain a JSON object: %s", path)
	}
	return RedactSensitiveValues(state).(map[string]any), nil
}

func SaveState(state map[string]any) error {
	path, err := StatePath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(RedactSensitiveValues(state), "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func PrintJSON(value any) error {
	data, err := json.MarshalIndent(RedactSensitiveValues(value), "", "  ")
	if err != nil {
		return err
	}
	fmt.Println(string(data))
	return nil
}

func RedactSensitiveValues(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		redacted := make(map[string]any, len(typed))
		for key, item := range typed {
			redacted[key] = RedactSensitiveValues(item)
		}
		return redacted
	case []any:
		redacted := make([]any, len(typed))
		for index, item := range typed {
			redacted[index] = RedactSensitiveValues(item)
		}
		return redacted
	case []map[string]any:
		redacted := make([]map[string]any, len(typed))
		for index, item := range typed {
			redacted[index] = RedactSensitiveValues(item).(map[string]any)
		}
		return redacted
	case string:
		return authorizationQueryRE.ReplaceAllString(typed, "${1}<redacted>")
	default:
		return typed
	}
}

func RequireString(state map[string]any, key string) (string, error) {
	value := stringValue(state[key])
	if value == "" {
		return "", fmt.Errorf("state is missing required field %q", key)
	}
	return value, nil
}

func ResolveToolID(state map[string]any) (string, error) {
	configured := map[string]string{}
	for _, name := range []string{"AGENTKIT_TOOL_ID", "AGENTKIT_SANDBOX_TOOL_ID"} {
		if value := env(name); value != "" {
			configured[name] = value
		}
	}
	distinct := map[string]bool{}
	for _, value := range configured {
		distinct[value] = true
	}
	if len(distinct) > 1 {
		parts := make([]string, 0, len(configured))
		for name, value := range configured {
			parts = append(parts, fmt.Sprintf("%s=%s", name, value))
		}
		return "", fmt.Errorf("conflicting tool ID environment variables: %s", strings.Join(parts, ", "))
	}

	envToolID := ""
	for _, value := range configured {
		envToolID = value
		break
	}
	stateToolID := ""
	if state != nil {
		stateToolID = stringValue(state["tool_id"])
	}
	if envToolID != "" && stateToolID != "" && envToolID != stateToolID {
		return "", fmt.Errorf("tool ID from environment (%s) does not match state (%s)", envToolID, stateToolID)
	}
	toolID := envToolID
	if toolID == "" {
		toolID = stateToolID
	}
	if toolID == "" {
		return "", fmt.Errorf("set AGENTKIT_TOOL_ID or AGENTKIT_SANDBOX_TOOL_ID to the sandbox tool ID")
	}
	return toolID, nil
}

func TTLSeconds() (int, error) {
	return positiveIntEnv("AGENTKIT_SESSION_TTL_SECONDS", defaultTTLSeconds)
}

func InvokePayloadJSON() (string, error) {
	timeout, err := positiveIntEnv("AGENTKIT_INVOKE_TIMEOUT_SECONDS", defaultInvokeTimeout)
	if err != nil {
		return "", err
	}
	code := env("AGENTKIT_INVOKE_CODE")
	if code == "" {
		code = "print('Hello from AgentKit sandbox!')"
	}
	kernelName := env("AGENTKIT_INVOKE_KERNEL_NAME")
	if kernelName == "" {
		kernelName = "python3"
	}
	payload := map[string]any{
		"code":        code,
		"timeout":     timeout,
		"kernel_name": kernelName,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

func ParseInvokeResult(value any) any {
	raw := stringValue(value)
	if raw == "" {
		return value
	}
	var parsed any
	if err := json.Unmarshal([]byte(raw), &parsed); err != nil {
		return raw
	}
	return parsed
}

func InvokeResultFailed(result any) bool {
	resultMap, ok := result.(map[string]any)
	if !ok {
		return false
	}
	if success, ok := resultMap["success"].(bool); ok && !success {
		return true
	}
	data, ok := resultMap["data"].(map[string]any)
	return ok && stringValue(data["status"]) == "error"
}

func WaitUntil[T any](description string, fetch func() (T, error), done func(T) bool, failed func(T) bool) (T, error) {
	timeout, err := positiveIntEnv("AGENTKIT_WAIT_TIMEOUT_SECONDS", defaultWaitTimeoutSeconds)
	if err != nil {
		var zero T
		return zero, err
	}
	interval, err := positiveIntEnv("AGENTKIT_POLL_INTERVAL_SECONDS", defaultPollIntervalSeconds)
	if err != nil {
		var zero T
		return zero, err
	}
	deadline := time.Now().Add(time.Duration(timeout) * time.Second)
	for {
		value, err := fetch()
		if err != nil {
			var zero T
			return zero, err
		}
		if done(value) {
			return value, nil
		}
		if failed(value) {
			return value, fmt.Errorf("%s entered a failure state", description)
		}
		if time.Now().After(deadline) {
			return value, fmt.Errorf("timed out after %ds waiting for %s", timeout, description)
		}
		time.Sleep(time.Duration(interval) * time.Second)
	}
}

func WaitForSession(client *Client, toolID string, sessionID string) (map[string]any, error) {
	ready := map[string]bool{"ready": true, "running": true, "available": true, "active": true, "succeeded": true, "success": true}
	failed := map[string]bool{"failed": true, "error": true, "deleted": true, "terminated": true}
	return WaitUntil(
		fmt.Sprintf("session %s to become ready", sessionID),
		func() (map[string]any, error) {
			return client.GetSession(map[string]any{"ToolId": toolID, "SessionId": sessionID})
		},
		func(value map[string]any) bool { return ready[NormalizedStatus(value)] },
		func(value map[string]any) bool { return failed[NormalizedStatus(value)] },
	)
}

func WaitForPausedSession(client *Client, toolID string, sessionID string) (map[string]any, error) {
	failed := map[string]bool{"failed": true, "error": true, "deleted": true, "terminated": true}
	return WaitUntil(
		fmt.Sprintf("session %s to become paused", sessionID),
		func() (map[string]any, error) {
			return client.GetSession(map[string]any{"ToolId": toolID, "SessionId": sessionID})
		},
		func(value map[string]any) bool { return NormalizedStatus(value) == "paused" },
		func(value map[string]any) bool { return failed[NormalizedStatus(value)] },
	)
}

func ListAllSessions(client *Client, toolID string) ([]map[string]any, error) {
	sessions := []map[string]any{}
	nextToken := ""
	seenTokens := map[string]bool{}
	for {
		request := map[string]any{"ToolId": toolID, "MaxResults": 100}
		if nextToken != "" {
			request["NextToken"] = nextToken
		}
		response, err := client.ListSessions(request)
		if err != nil {
			return nil, err
		}
		if rawSessions, ok := response["SessionInfos"].([]any); ok {
			for _, item := range rawSessions {
				if session, ok := item.(map[string]any); ok {
					sessions = append(sessions, session)
				}
			}
		}
		nextToken = stringValue(response["NextToken"])
		if nextToken == "" {
			return RedactSensitiveValues(sessions).([]map[string]any), nil
		}
		if seenTokens[nextToken] {
			return nil, fmt.Errorf("ListSessions repeated NextToken %q", nextToken)
		}
		seenTokens[nextToken] = true
	}
}

func NormalizedStatus(value map[string]any) string {
	if value == nil {
		return ""
	}
	return strings.ToLower(stringValue(value["Status"]))
}

func OutputWithStateFile(state map[string]any) (map[string]any, error) {
	path, err := StatePath()
	if err != nil {
		return nil, err
	}
	output := make(map[string]any, len(state)+1)
	output["state_file"] = path
	for key, value := range state {
		output[key] = value
	}
	return output, nil
}

func RandomUserSessionID() (string, error) {
	buffer := make([]byte, 8)
	if _, err := rand.Read(buffer); err != nil {
		return "", err
	}
	return "session-demo-" + hex.EncodeToString(buffer), nil
}
