package lifecycle

import (
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

func TestResolveEndpointSupportsBytePlusDefaults(t *testing.T) {
	t.Setenv("AGENTKIT_CLOUD_PROVIDER", "byteplus")

	endpoint, err := ResolveEndpoint("")
	if err != nil {
		t.Fatal(err)
	}
	if endpoint.Provider != "byteplus" {
		t.Fatalf("Provider = %q, want byteplus", endpoint.Provider)
	}
	if endpoint.Region != "ap-southeast-1" {
		t.Fatalf("Region = %q, want ap-southeast-1", endpoint.Region)
	}
	if endpoint.Host != "agentkit.ap-southeast-1.byteplusapi.com" {
		t.Fatalf("Host = %q, want default BytePlus host", endpoint.Host)
	}
}

func TestClientCallSendsSignedOpenAPIRequest(t *testing.T) {
	var gotBody map[string]any
	var gotAuth string
	var gotPayloadHash string

	client := &Client{
		endpoint: EndpointConfig{
			Provider:   "volcengine",
			Region:     "cn-beijing",
			Host:       "example.com",
			Service:    "agentkit",
			APIVersion: APIVersion,
			Scheme:     "https",
		},
		credentials: Credentials{AccessKey: "ak", SecretKey: "sk"},
		httpClient: &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if r.URL.Query().Get("Action") != "CreateSession" {
				t.Fatalf("Action = %q, want CreateSession", r.URL.Query().Get("Action"))
			}
			if r.URL.Query().Get("Version") != APIVersion {
				t.Fatalf("Version = %q, want %s", r.URL.Query().Get("Version"), APIVersion)
			}
			if r.Method != http.MethodPost {
				t.Fatalf("Method = %q, want POST", r.Method)
			}
			if err := json.NewDecoder(r.Body).Decode(&gotBody); err != nil {
				t.Errorf("decode body: %v", err)
			}
			gotAuth = r.Header.Get("Authorization")
			gotPayloadHash = r.Header.Get("X-Content-Sha256")
			return jsonResponse(200, `{"ResponseMetadata":{"RequestId":"r1"},"Result":{"SessionId":"s1"}}`), nil
		})},
		retries: 0,
	}

	result, err := client.CreateSession(map[string]any{"ToolId": "tool-1"})
	if err != nil {
		t.Fatal(err)
	}
	if result["SessionId"] != "s1" {
		t.Fatalf("SessionId = %v, want s1", result["SessionId"])
	}
	if gotBody["ToolId"] != "tool-1" {
		t.Fatalf("ToolId body = %v, want tool-1", gotBody["ToolId"])
	}
	if !strings.HasPrefix(gotAuth, "HMAC-SHA256 Credential=ak/") {
		t.Fatalf("Authorization header = %q", gotAuth)
	}
	if gotPayloadHash == "" {
		t.Fatal("missing X-Content-Sha256 header")
	}
}

func TestClientCallReturnsOpenAPIError(t *testing.T) {
	client := &Client{
		endpoint: EndpointConfig{
			Provider:   "volcengine",
			Region:     "cn-beijing",
			Host:       "example.com",
			Service:    "agentkit",
			APIVersion: APIVersion,
			Scheme:     "https",
		},
		credentials: Credentials{AccessKey: "ak", SecretKey: "sk"},
		httpClient: &http.Client{Transport: roundTripFunc(func(_ *http.Request) (*http.Response, error) {
			return jsonResponse(200, `{"ResponseMetadata":{"Error":{"Code":"InvalidParameter","Message":"bad request"}},"Result":{}}`), nil
		})},
		retries: 0,
	}

	_, err := client.GetTool(map[string]any{"ToolId": "tool-1"})
	if err == nil {
		t.Fatal("expected error")
	}
	apiErr, ok := err.(*AgentKitHTTPError)
	if !ok {
		t.Fatalf("error type = %T, want *AgentKitHTTPError", err)
	}
	if apiErr.Code != "InvalidParameter" || apiErr.Message != "bad request" {
		t.Fatalf("api error = %#v", apiErr)
	}
}

func TestInvokeToolUsesVolcengineDataPlaneEndpoint(t *testing.T) {
	t.Setenv("VOLCENGINE_AGENTKIT_HOST", "")
	t.Setenv("VOLC_AGENTKIT_HOST", "")
	t.Setenv("VOLCENGINE_AGENTKIT_SCHEME", "")
	t.Setenv("VOLC_AGENTKIT_SCHEME", "")

	client := &Client{
		endpoint: EndpointConfig{
			Provider:   "volcengine",
			Region:     "cn-beijing",
			Host:       "open.volcengineapi.com",
			Service:    "agentkit",
			APIVersion: APIVersion,
			Scheme:     "https",
		},
		credentials: Credentials{AccessKey: "ak", SecretKey: "sk"},
		httpClient: &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if r.URL.Query().Get("Action") != "InvokeTool" {
				t.Fatalf("Action = %q, want InvokeTool", r.URL.Query().Get("Action"))
			}
			if r.URL.Host != "agentkit.cn-beijing.volces.com" {
				t.Fatalf("URL host = %q, want data-plane host", r.URL.Host)
			}
			if r.Host != "agentkit.cn-beijing.volces.com" {
				t.Fatalf("request host = %q, want data-plane host", r.Host)
			}
			return jsonResponse(200, `{"ResponseMetadata":{"RequestId":"r1"},"Result":{"SessionId":"s1","Result":"{\"success\":true}"}}`), nil
		})},
		retries: 0,
	}

	result, err := client.InvokeTool(map[string]any{"ToolId": "tool-1", "SessionId": "s1"})
	if err != nil {
		t.Fatal(err)
	}
	if result["SessionId"] != "s1" {
		t.Fatalf("SessionId = %v, want s1", result["SessionId"])
	}
}

func TestRetryAfterOrBackoff(t *testing.T) {
	headers := http.Header{"Retry-After": []string{"1.5"}}

	if got := retryAfterOrBackoff(headers, 0); got != 1500*time.Millisecond {
		t.Fatalf("retryAfterOrBackoff = %s, want 1.5s", got)
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) {
	return f(r)
}

func jsonResponse(statusCode int, body string) *http.Response {
	return &http.Response{
		StatusCode: statusCode,
		Header:     http.Header{"Content-Type": []string{"application/json"}},
		Body:       io.NopCloser(strings.NewReader(body)),
	}
}
