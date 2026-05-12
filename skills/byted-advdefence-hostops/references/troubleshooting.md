# Troubleshooting

Use this reference when interface calls return empty data, validation errors, or unexpected failures.

## Common pitfalls

### `DescHostRules` returns empty `Result`
Possible cause:
- `Demension` is missing
- `Demension` is passed as a string instead of an integer

What to do:
- pass integer `1` for host-based lookup

### `GetWafAllowList`, `GetWafBlockList`, or `DescWebDefBanRegion` returns 404
Possible cause:
- the request shape does not match the expected request method and parameters

What to do:
- retry with the request method and parameters documented in `references/api-surface.md`

### `DescribeAttackEvent` or similar four-layer interfaces fail validation because `InstanceIp` or `InstanceIps` is missing
Possible cause:
- the workflow skipped host-to-instance-IP resolution

What to do:
- resolve instance IPs first via `DescHostRules`
- if resolution fails, explain that four-layer DDoS views cannot be completed

### `InvalidActionOrVersion`
Possible cause:
- the interface name or version does not match the expected contract

What to do:
- verify the interface name and version in `references/api-surface.md`

## Reporting guidance

When an interface call fails:
- report the exact error instead of hiding it
- distinguish service errors from missing data
- include the request ID when available
- do not conclude that the host is healthy just because a call failed or returned no data
