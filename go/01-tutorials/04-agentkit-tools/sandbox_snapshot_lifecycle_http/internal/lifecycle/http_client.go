package lifecycle

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"
)

const (
	APIVersion         = "2025-10-30"
	defaultHTTPTimeout = 30
	defaultHTTPRetries = 2
)

var retryableStatusCodes = map[int]bool{
	http.StatusTooManyRequests:    true,
	http.StatusServiceUnavailable: true,
}

type EndpointConfig struct {
	Provider   string
	Region     string
	Host       string
	Service    string
	APIVersion string
	Scheme     string
}

type Credentials struct {
	AccessKey    string
	SecretKey    string
	SessionToken string
}

type AgentKitHTTPError struct {
	Action  string
	Code    string
	Message string
}

func (e *AgentKitHTTPError) Error() string {
	return fmt.Sprintf("failed to %s: %s: %s", e.Action, e.Code, e.Message)
}

type Client struct {
	endpoint    EndpointConfig
	credentials Credentials
	httpClient  *http.Client
	retries     int
}

func NewClient() (*Client, error) {
	endpoint, err := ResolveEndpoint("")
	if err != nil {
		return nil, err
	}
	credentials, err := ResolveCredentials(endpoint.Provider)
	if err != nil {
		return nil, err
	}
	timeout, err := positiveIntEnv("AGENTKIT_HTTP_TIMEOUT_SECONDS", defaultHTTPTimeout)
	if err != nil {
		return nil, err
	}
	retries, err := nonNegativeIntEnv("AGENTKIT_HTTP_RETRIES", defaultHTTPRetries)
	if err != nil {
		return nil, err
	}
	return &Client{
		endpoint:    endpoint,
		credentials: credentials,
		httpClient:  &http.Client{Timeout: time.Duration(timeout) * time.Second},
		retries:     retries,
	}, nil
}

func ResolveProvider() (string, error) {
	provider := strings.ToLower(env("AGENTKIT_CLOUD_PROVIDER"))
	if provider == "" {
		provider = strings.ToLower(env("CLOUD_PROVIDER"))
	}
	if provider == "" {
		provider = "volcengine"
	}
	switch provider {
	case "volcengine", "byteplus":
		return provider, nil
	default:
		return "", fmt.Errorf("AGENTKIT_CLOUD_PROVIDER must be one of: byteplus, volcengine")
	}
}

func ResolveEndpoint(provider string) (EndpointConfig, error) {
	var err error
	if provider == "" {
		provider, err = ResolveProvider()
		if err != nil {
			return EndpointConfig{}, err
		}
	}
	if provider == "byteplus" {
		region := firstEnv(
			"BYTEPLUS_AGENTKIT_REGION",
			"AGENTKIT_REGION",
			"BYTEPLUS_REGION",
		)
		if region == "" {
			region = "ap-southeast-1"
		}
		host := env("BYTEPLUS_AGENTKIT_HOST")
		if host == "" {
			host = fmt.Sprintf("agentkit.%s.byteplusapi.com", region)
		}
		service := env("BYTEPLUS_AGENTKIT_SERVICE")
		if service == "" {
			service = "agentkit"
		}
		version := env("BYTEPLUS_AGENTKIT_API_VERSION")
		if version == "" {
			version = APIVersion
		}
		scheme := env("BYTEPLUS_AGENTKIT_SCHEME")
		if scheme == "" {
			scheme = "https"
		}
		return EndpointConfig{
			Provider:   provider,
			Region:     region,
			Host:       host,
			Service:    service,
			APIVersion: version,
			Scheme:     scheme,
		}, nil
	}

	if provider != "volcengine" {
		return EndpointConfig{}, fmt.Errorf("unsupported provider %q", provider)
	}
	region := firstEnv(
		"VOLCENGINE_AGENTKIT_REGION",
		"AGENTKIT_REGION",
		"VOLCENGINE_REGION",
		"VOLC_REGION",
		"REGION",
	)
	if region == "" {
		region = "cn-beijing"
	}
	host := firstEnv("VOLCENGINE_AGENTKIT_HOST", "VOLC_AGENTKIT_HOST")
	if host == "" {
		host = "open.volcengineapi.com"
	}
	service := firstEnv("VOLCENGINE_AGENTKIT_SERVICE", "VOLC_AGENTKIT_SERVICE")
	if service == "" {
		service = "agentkit"
	}
	version := firstEnv("VOLCENGINE_AGENTKIT_API_VERSION", "VOLC_AGENTKIT_API_VERSION")
	if version == "" {
		version = APIVersion
	}
	scheme := firstEnv("VOLCENGINE_AGENTKIT_SCHEME", "VOLC_AGENTKIT_SCHEME")
	if scheme == "" {
		scheme = "https"
	}
	return EndpointConfig{
		Provider:   provider,
		Region:     region,
		Host:       host,
		Service:    service,
		APIVersion: version,
		Scheme:     scheme,
	}, nil
}

func ResolveCredentials(provider string) (Credentials, error) {
	var err error
	if provider == "" {
		provider, err = ResolveProvider()
		if err != nil {
			return Credentials{}, err
		}
	}
	if provider == "byteplus" {
		ak := firstEnv("BYTEPLUS_AGENTKIT_ACCESS_KEY", "BYTEPLUS_ACCESS_KEY")
		sk := firstEnv("BYTEPLUS_AGENTKIT_SECRET_KEY", "BYTEPLUS_SECRET_KEY")
		token := firstEnv("BYTEPLUS_AGENTKIT_SESSION_TOKEN", "BYTEPLUS_SESSION_TOKEN")
		if ak == "" || sk == "" {
			return Credentials{}, errors.New("BytePlus credentials not found; set BYTEPLUS_ACCESS_KEY and BYTEPLUS_SECRET_KEY")
		}
		return Credentials{AccessKey: ak, SecretKey: sk, SessionToken: token}, nil
	}

	ak := firstEnv(
		"VOLCENGINE_AGENTKIT_ACCESS_KEY",
		"VOLC_AGENTKIT_ACCESSKEY",
		"VOLCENGINE_ACCESS_KEY",
		"VOLC_ACCESSKEY",
	)
	sk := firstEnv(
		"VOLCENGINE_AGENTKIT_SECRET_KEY",
		"VOLC_AGENTKIT_SECRETKEY",
		"VOLCENGINE_SECRET_KEY",
		"VOLC_SECRETKEY",
	)
	token := firstEnv(
		"VOLCENGINE_AGENTKIT_SESSION_TOKEN",
		"VOLC_AGENTKIT_SESSIONTOKEN",
		"VOLCENGINE_SESSION_TOKEN",
		"VOLC_SESSIONTOKEN",
	)
	if ak == "" || sk == "" {
		return Credentials{}, errors.New("Volcengine credentials not found; set VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY")
	}
	return Credentials{AccessKey: ak, SecretKey: sk, SessionToken: token}, nil
}

func (c *Client) Call(action string, body map[string]any) (map[string]any, error) {
	return c.call(action, body, c.endpoint)
}

func (c *Client) invokeEndpoint() EndpointConfig {
	if c.endpoint.Provider != "volcengine" {
		return c.endpoint
	}
	endpoint := c.endpoint
	host := firstEnv("VOLCENGINE_AGENTKIT_HOST", "VOLC_AGENTKIT_HOST")
	if host == "" {
		host = fmt.Sprintf("agentkit.%s.volces.com", endpoint.Region)
	}
	endpoint.Host = host
	endpoint.Scheme = firstEnv("VOLCENGINE_AGENTKIT_SCHEME", "VOLC_AGENTKIT_SCHEME")
	if endpoint.Scheme == "" {
		endpoint.Scheme = c.endpoint.Scheme
	}
	return endpoint
}

func (c *Client) call(action string, body map[string]any, endpoint EndpointConfig) (map[string]any, error) {
	if body == nil {
		body = map[string]any{}
	}
	payload, err := marshalCompactJSON(body)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal %s request body: %w", action, err)
	}
	query := map[string]string{
		"Action":  action,
		"Version": endpoint.APIVersion,
	}
	headers := signHeaders(
		"POST",
		endpoint.Host,
		query,
		payload,
		c.credentials,
		endpoint.Service,
		endpoint.Region,
		time.Now().UTC(),
	)
	requestURL := fmt.Sprintf(
		"%s://%s/?Action=%s&Version=%s",
		endpoint.Scheme,
		endpoint.Host,
		url.QueryEscape(action),
		url.QueryEscape(endpoint.APIVersion),
	)

	var response *http.Response
	var responseBody []byte
	for attempt := 0; attempt <= c.retries; attempt++ {
		req, err := http.NewRequest(http.MethodPost, requestURL, bytes.NewReader(payload))
		if err != nil {
			return nil, fmt.Errorf("failed to create %s request: %w", action, err)
		}
		for key, value := range headers {
			req.Header.Set(key, value)
		}

		response, err = c.httpClient.Do(req)
		if err != nil {
			if isConnectionError(err) && attempt < c.retries {
				time.Sleep(backoffSeconds(attempt))
				continue
			}
			if isConnectionError(err) {
				return nil, fmt.Errorf("failed to %s: connection error after %d attempt(s): %w", action, c.retries+1, err)
			}
			return nil, fmt.Errorf("failed to %s: network error: %w", action, err)
		}
		responseBody, err = io.ReadAll(response.Body)
		closeErr := response.Body.Close()
		if err != nil {
			return nil, fmt.Errorf("failed to %s: read response body: %w", action, err)
		}
		if closeErr != nil {
			return nil, fmt.Errorf("failed to %s: close response body: %w", action, closeErr)
		}
		if retryableStatusCodes[response.StatusCode] && attempt < c.retries {
			time.Sleep(retryAfterOrBackoff(response.Header, attempt))
			continue
		}
		break
	}
	if response == nil {
		return nil, fmt.Errorf("failed to %s: no HTTP response", action)
	}

	var envelope map[string]any
	if err := json.Unmarshal(responseBody, &envelope); err != nil {
		return nil, fmt.Errorf("failed to %s: non-JSON HTTP %d response", action, response.StatusCode)
	}
	if metadata, ok := envelope["ResponseMetadata"].(map[string]any); ok {
		if apiError, ok := metadata["Error"].(map[string]any); ok {
			code := stringValue(apiError["Code"])
			message := stringValue(apiError["Message"])
			if message == "" {
				message = "Unknown error"
			}
			return nil, &AgentKitHTTPError{Action: action, Code: code, Message: message}
		}
	}
	if response.StatusCode >= http.StatusBadRequest {
		return nil, fmt.Errorf("failed to %s: HTTP %d: %s", action, response.StatusCode, string(responseBody))
	}
	result, ok := envelope["Result"].(map[string]any)
	if !ok {
		return nil, fmt.Errorf("failed to %s: Result is not a JSON object", action)
	}
	return result, nil
}

func (c *Client) GetTool(body map[string]any) (map[string]any, error) {
	return c.Call("GetTool", body)
}

func (c *Client) CreateSession(body map[string]any) (map[string]any, error) {
	return c.Call("CreateSession", body)
}

func (c *Client) GetSession(body map[string]any) (map[string]any, error) {
	return c.Call("GetSession", body)
}

func (c *Client) InvokeTool(body map[string]any) (map[string]any, error) {
	return c.call("InvokeTool", body, c.invokeEndpoint())
}

func (c *Client) CreateSessionSnapshot(body map[string]any) (map[string]any, error) {
	return c.Call("CreateSessionSnapshot", body)
}

func (c *Client) GetSessionSnapshot(body map[string]any) (map[string]any, error) {
	return c.Call("GetSessionSnapshot", body)
}

func (c *Client) ListSessionSnapshots(body map[string]any) (map[string]any, error) {
	return c.Call("ListSessionSnapshots", body)
}

func (c *Client) DeleteSession(body map[string]any) (map[string]any, error) {
	return c.Call("DeleteSession", body)
}

func (c *Client) DeleteSessionSnapshot(body map[string]any) (map[string]any, error) {
	return c.Call("DeleteSessionSnapshot", body)
}

func (c *Client) ResumeSessionFromSnapshot(body map[string]any) (map[string]any, error) {
	return c.Call("ResumeSessionFromSnapshot", body)
}

func (c *Client) PauseSession(body map[string]any) (map[string]any, error) {
	return c.Call("PauseSession", body)
}

func (c *Client) ResumeSession(body map[string]any) (map[string]any, error) {
	return c.Call("ResumeSession", body)
}

func signHeaders(method, host string, query map[string]string, body []byte, credentials Credentials, service, region string, now time.Time) map[string]string {
	xDate := now.UTC().Format("20060102T150405Z")
	shortDate := xDate[:8]
	payloadHash := sha256Hex(body)

	signed := map[string]string{
		"content-type":     "application/json",
		"host":             host,
		"x-content-sha256": payloadHash,
		"x-date":           xDate,
	}
	if credentials.SessionToken != "" {
		signed["x-security-token"] = credentials.SessionToken
	}

	keys := make([]string, 0, len(signed))
	for key := range signed {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	var canonicalHeaders strings.Builder
	for _, key := range keys {
		canonicalHeaders.WriteString(key)
		canonicalHeaders.WriteString(":")
		canonicalHeaders.WriteString(signed[key])
		canonicalHeaders.WriteString("\n")
	}
	signedHeaders := strings.Join(keys, ";")
	canonicalRequest := strings.Join([]string{
		strings.ToUpper(method),
		"/",
		canonicalQuery(query),
		canonicalHeaders.String(),
		signedHeaders,
		payloadHash,
	}, "\n")

	credentialScope := fmt.Sprintf("%s/%s/%s/request", shortDate, region, service)
	stringToSign := strings.Join([]string{
		"HMAC-SHA256",
		xDate,
		credentialScope,
		sha256Hex([]byte(canonicalRequest)),
	}, "\n")
	signingKey := hmacSHA256(
		hmacSHA256(
			hmacSHA256(
				hmacSHA256([]byte(credentials.SecretKey), shortDate),
				region,
			),
			service,
		),
		"request",
	)
	signature := hex.EncodeToString(hmacSHA256(signingKey, stringToSign))

	headers := map[string]string{
		"Accept":           "application/json",
		"Content-Type":     "application/json",
		"Host":             host,
		"X-Date":           xDate,
		"X-Content-Sha256": payloadHash,
		"Authorization": fmt.Sprintf(
			"HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s",
			credentials.AccessKey,
			credentialScope,
			signedHeaders,
			signature,
		),
	}
	if credentials.SessionToken != "" {
		headers["X-Security-Token"] = credentials.SessionToken
	}
	return headers
}

func canonicalQuery(query map[string]string) string {
	keys := make([]string, 0, len(query))
	for key := range query {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, uriEncode(key)+"="+uriEncode(query[key]))
	}
	return strings.Join(parts, "&")
}

func uriEncode(value string) string {
	encoded := url.QueryEscape(value)
	encoded = strings.ReplaceAll(encoded, "+", "%20")
	encoded = strings.ReplaceAll(encoded, "%7E", "~")
	return encoded
}

func hmacSHA256(key []byte, message string) []byte {
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(message))
	return mac.Sum(nil)
}

func sha256Hex(value []byte) string {
	sum := sha256.Sum256(value)
	return hex.EncodeToString(sum[:])
}

func marshalCompactJSON(value any) ([]byte, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buffer.Bytes(), "\n"), nil
}

func backoffSeconds(attempt int) time.Duration {
	scale := 1 << attempt
	seconds := 0.5 * float64(scale)
	if seconds > 8 {
		seconds = 8
	}
	return time.Duration(seconds * float64(time.Second))
}

func retryAfterOrBackoff(headers http.Header, attempt int) time.Duration {
	raw := strings.TrimSpace(headers.Get("Retry-After"))
	if raw == "" {
		return backoffSeconds(attempt)
	}
	value, err := strconv.ParseFloat(raw, 64)
	if err != nil || value < 0 {
		return backoffSeconds(attempt)
	}
	return time.Duration(value * float64(time.Second))
}

func isConnectionError(err error) bool {
	var netErr net.Error
	if errors.As(err, &netErr) {
		return true
	}
	return strings.Contains(strings.ToLower(err.Error()), "connection")
}

func env(name string) string {
	return strings.TrimSpace(os.Getenv(name))
}

func firstEnv(names ...string) string {
	for _, name := range names {
		if value := env(name); value != "" {
			return value
		}
	}
	return ""
}

func intEnv(name string, defaultValue int) (int, error) {
	raw := env(name)
	if raw == "" {
		return defaultValue, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("%s must be an integer", name)
	}
	return value, nil
}

func positiveIntEnv(name string, defaultValue int) (int, error) {
	value, err := intEnv(name, defaultValue)
	if err != nil {
		return 0, err
	}
	if value <= 0 {
		return 0, fmt.Errorf("%s must be greater than zero", name)
	}
	return value, nil
}

func nonNegativeIntEnv(name string, defaultValue int) (int, error) {
	value, err := intEnv(name, defaultValue)
	if err != nil {
		return 0, err
	}
	if value < 0 {
		return 0, fmt.Errorf("%s must be greater than or equal to zero", name)
	}
	return value, nil
}

func stringValue(value any) string {
	if raw, ok := value.(string); ok {
		return strings.TrimSpace(raw)
	}
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}
