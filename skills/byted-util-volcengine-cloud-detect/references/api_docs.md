# Volcengine Cloud Detect API Reference

## API Overview

- **Base URL**: `https://cloud-detect.volcengineapi.com`
- **API Version**: `2025-10-31`
- **Service**: `cloud_detect`
- **Region**: `cn-north-1` (or any region for non-region services)
- **Signature Method**: HMAC-SHA256 (Volcengine Signature v4)

## Authentication

Requires Volcengine AccessKeyId and SecretKey. The request must be signed using HMAC-SHA256.

### Required Headers
| Header | Description | Example |
|--------|-------------|---------|
| X-Date | UTC timestamp in ISO 8601 format | 20201103T104027Z |
| Authorization | HMAC-SHA256 signature | See signature method docs |

### Query Parameters (Always Required)
| Parameter | Description | Example |
|-----------|-------------|---------|
| Action | API action name | CreateTask |
| Version | API version | 2025-10-31 |

---

## 1. CreateTask - Create Periodic Detection Task

Create a scheduled detection task to monitor network performance and stability.

### Request
```
POST https://cloud-detect.volcengineapi.com?Action=CreateTask&Version=2025-10-31
```

### Key Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| ProjectName | string | No | "default" | Resource project name |
| Type | integer | **Yes** | 1 (HTTPS) | Task type: 1=HTTP(S), 2=DNS, 3=PING, 5=UDP, 6=TCP, 8=Upload, 9=Download, 11=PageElement |
| Name | string | **Yes** | - | Task name |
| Address | string | **Yes** | - | Target address to detect |
| NodeCount | integer | **Yes** | 5 | Number of samples per line |
| IntervalSeconds | long | **Yes** | 60 | Detection frequency in seconds. Options: 60, 120, 180, 300, 600, 900, 1200, 1800, 3600, 7200, 10800, 21600, 43200, 86400 |
| FinishTime | long | **Yes** | 0 | End time (Unix timestamp in seconds), 0 = unlimited |
| LineIdList | long[] | **Yes** | - | List of node IDs to use for detection |

### HTTP Type Specific Config (HttpConfig)
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| HttpMethod | integer | No | 1 | HTTP method: 1=GET, 2=POST, 3=PUT, 4=DELETE, 5=PATCH, 6=HEAD, 7=OPTIONS |
| Timeout | integer | No | 30 | Timeout in seconds [1-120] |
| Redirect | boolean | No | false | Enable redirect |
| HttpVersion | string | No | "auto" | HTTP version: "auto", "http/1.1", "h2", "h3" |
| DnsType | string | No | "system" | DNS type: "system", "custom", "doh", "isp" |

### Response
```json
{
  "ResponseMetadata": {
    "RequestId": "...",
    "Action": "CreateTask",
    "Version": "2025-10-31",
    "Service": "cloud_detect",
    "Region": "cn-north-1"
  },
  "Result": {
    "TaskId": 23275831,
    "LocationInfo": { ... }
  }
}
```

---

## 2. GetTaskResult - Get Task Results

Query detection task execution results. Time range must be within 1 hour.

### Request
```
POST https://cloud-detect.volcengineapi.com?Action=GetTaskResult&Version=2025-10-31
```

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| TaskId | long | **Yes** | Task ID |
| StartTime | long | **Yes** | Query start time (Unix timestamp in seconds) |
| EndTime | long | **Yes** | Query end time (Unix timestamp in seconds), range <= 1 hour |
| PageNum | long | **Yes** | Page number |
| PageSize | long | **Yes** | Results per page (max 500) |
| ProjectName | string | No | Project name |

### Response Data Structure

Each result item in `Data` array contains:

#### Basic Information
| Field | Type | Description |
|-------|------|-------------|
| TaskId | long | Task ID |
| Timestamp | long | Data timestamp |
| Success | boolean | Whether task executed successfully |
| ErrorMsg | string | Error message if failed |
| ClientInfo | object | Node information |
| TargetInfo | object | Target information |

#### ClientInfo (Node)
| Field | Type | Description |
|-------|------|-------------|
| Ip | string | Node IPv4 address |
| Isp | string | Node ISP |
| City | string | Node city |
| Region | string | Node region |
| Type | string | Node type: 1=LastMile, 2=IDC, 4=Private |

#### HttpDetail (for HTTP tasks)
| Field | Type | Description |
|-------|------|-------------|
| StatusCode | integer | HTTP status code |
| DnsCost | long | DNS resolution time (ms) |
| Ttfb | long | Time to first byte (ms) |
| Ttlb | long | Time to last byte (ms) |
| RedirectCost | long | Redirect latency (ms) |
| RedirectNums | long | Number of redirects |
| DownloadSpeed | long | Download speed |
| TimeDNS | double | DNS time (ms) |
| TimeTCP | double | TCP connect time (ms) |
| TimeSsl | double | SSL handshake time (ms) |
| TimeWait | double | Wait time (ms) |
| TimeReceive | double | Receive time (ms) |
| TimeTotal | double | Total time (ms) |
| HttpResponseBody | string | Response body |
| ErrorCode | string | Error code if failed |

#### PingDetail (for PING tasks)
| Field | Type | Description |
|-------|------|-------------|
| PacketsSent | integer | Packets sent |
| PacketsReceived | integer | Packets received |
| PacketLoss | double | Packet loss percentage |
| AvgLatency | double | Average latency (ms) |
| MinLatency | double | Minimum latency (ms) |
| MaxLatency | double | Maximum latency (ms) |

#### Assertions
| Field | Type | Description |
|-------|------|-------------|
| Success | boolean | Assertion passed |
| ResultValue | string | Actual value |
| ConditionMessage | string | Condition info |

---

## 3. ListNodes - Get Detection Node List

Query available detection nodes.

### Request
```
POST https://cloud-detect.volcengineapi.com?Action=ListNodes&Version=2025-10-31
```

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| IsMainland | boolean | No | Filter mainland China nodes |
| LineType | integer[] | No | Node types: 1=LastMile, 2=IDC |
| ProjectName | string | No | Project name |

### Response
```json
{
  "ResponseMetadata": { ... },
  "Result": {
    "LineList": [
      {
        "Id": 228,
        "Name": "中国-北京-北京市-中国电信（IDC）"
      }
    ]
  }
}
```

**Node Name Format**: `国家-省份-城市-运营商（类型）`

---

## 4. ListTask - Get Task List

Query detection task list with filtering.

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| PageSize | long | **Yes** | Items per page |
| PageNum | long | **Yes** | Page number |
| Name | string | No | Filter by task name (substring match) |
| Address | string | No | Filter by target address |
| Owner | string | No | Filter by creator |
| Id | string | No | Filter by task ID |
| ProjectName | string | No | Project name |

### Response
Task list with fields:
| Field | Type | Description |
|-------|------|-------------|
| Id | long | Task ID |
| Name | string | Task name |
| Address | string | Target address |
| Type | integer | Task type |
| Status | integer | Status: 2=Running, 4=Paused, 6=Ended |
| Interval | long | Detection interval |
| CreateTime | string | Creation time |

---

## 5. StopTask - Pause Task

Pause a running periodic task.

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| Id | long | **Yes** | Task ID |
| ProjectName | string | No | Project name |

---

## 6. RestartTask - Restart Task

Restart a paused periodic task.

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| Id | long | **Yes** | Task ID |
| ProjectName | string | No | Project name |

---

## 7. DeleteTask - Delete Task

Delete a periodic detection task.

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| Id | long | **Yes** | Task ID |
| ProjectName | string | No | Project name |

---

## 8. GetTask - Get Task Details

Get detailed information about a periodic task.

### Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| Id | long | **Yes** | Task ID |
| ProjectName | string | No | Project name |

### Response includes full task configuration including LineIdList, NodeCount, IntervalSeconds, etc.

---

## Error Codes

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 200 | AccessDenied | User not authorized |
| 400 | InvalidParameter | Invalid parameter value |
| 404 | TaskNotFound | Task does not exist |

## Node Types
| Type | Description |
|------|-------------|
| 1 | LastMile - Last mile node |
| 2 | IDC - IDC node |
| 4 | Private - Private node |

## Task Types
| Type | Description |
|------|-------------|
| 1 | HTTP(S) |
| 2 | DNS |
| 3 | PING |
| 5 | UDP |
| 6 | TCP |
| 8 | Upload |
| 9 | Download |
| 11 | Page Element |

## Task Status
| Status | Description |
|--------|-------------|
| 2 | Running |
| 4 | Paused |
| 6 | Ended |
