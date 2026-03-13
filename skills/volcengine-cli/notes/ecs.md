# ECS Service Notes

## DescribeInstanceTypes returns only 10 results by default

Calling `DescribeInstanceTypes` without filters returns at most 10 entries, making it impossible to find the smallest available instance type.

**Correct approach (two steps):**

```bash
# 1. Query available instance types in a specific zone
ve ecs DescribeAvailableResource \
  --ZoneId "cn-beijing-a" \
  --DestinationResource "InstanceType"

# 2. Filter by type name and query CPU/memory details
# Naming convention: .large < .xlarge < .2xlarge (higher = larger)
# The smallest general-purpose type typically ends with .large
ve ecs DescribeInstanceTypes --InstanceTypes.1 "ecs.c3i.large"
```

---

## veLinux image search requires an exact name

A fuzzy keyword like `"velinux"` matches GPU, Docker, ARM, and other variant images, producing too many results.

**Correct approach:** use an exact name prefix.

```bash
# Search for veLinux 2.0 64-bit
ve ecs DescribeImages \
  --ImageName "veLinux 2.0 64" \
  --ImageOwnerAlias "system"
```

Common image names:
- `veLinux 2.0 64` — standard x86_64
- `veLinux 2.0 ARM 64` — ARM

---

## Full ECS instance creation workflow

```bash
# 1. List availability zones
ve ecs DescribeZones --Region cn-beijing

# 2. Query available instance types (do NOT use DescribeInstanceTypes directly)
ve ecs DescribeAvailableResource \
  --ZoneId "cn-beijing-a" \
  --DestinationResource InstanceType

# 3. Get the veLinux image ID
ve ecs DescribeImages \
  --ImageName "veLinux 2.0 64" \
  --ImageOwnerAlias "system"

# 4. Get VPC and subnet IDs
ve vpc DescribeVpcs
ve vpc DescribeSubnets --VpcId "vpc-xxxx"

# 5. Get or create a security group and open port 22
ve ecs DescribeSecurityGroups --VpcId "vpc-xxxx"
ve ecs AuthorizeSecurityGroupIngress \
  --SecurityGroupId "sg-xxxx" \
  --Protocol "tcp" \
  --PortStart 22 \
  --PortEnd 22 \
  --CidrIp "0.0.0.0/0"

# 6. DryRun validation
output=$(ve ecs RunInstances \
  --Placement.ZoneId "cn-beijing-a" \
  --InstanceTypeId "ecs.c3i.large" \
  --ImageId "image-xxxx" \
  --NetworkInterfaces.1.SubnetId "subnet-xxxx" \
  --NetworkInterfaces.1.SecurityGroupIds.1 "sg-xxxx" \
  --SystemVolume.Size 40 \
  --SystemVolume.VolumeType "ESSD_PL0" \
  --InstanceName "my-instance" \
  --DryRun true 2>&1)
echo "$output" | grep -q "DryRunOperation" && echo "DryRun passed"

# 7. Create the instance
ve ecs RunInstances \
  --Placement.ZoneId "cn-beijing-a" \
  --InstanceTypeId "ecs.c3i.large" \
  --ImageId "image-xxxx" \
  --NetworkInterfaces.1.SubnetId "subnet-xxxx" \
  --NetworkInterfaces.1.SecurityGroupIds.1 "sg-xxxx" \
  --SystemVolume.Size 40 \
  --SystemVolume.VolumeType "ESSD_PL0" \
  --InstanceName "my-instance" \
  --Count 1
```

---

## ZoneId notes

- Beijing zones: `cn-beijing-a` / `cn-beijing-b` / `cn-beijing-c`, etc.
- `--Placement.ZoneId` is a nested parameter (dot-separated), not `--ZoneId`.
- ZoneId is required when creating instances.

---

## Instance type existence does not guarantee zone availability

`DescribeInstanceTypes` returns a global list of instance types regardless of actual zone inventory. Creating an instance may fail with `InvalidInstanceType.NotFound`.

**Correct approach:** use `DescribeAvailableResource` to query available types in the target zone. If creation fails, try an alternative type within the same family (e.g., `ecs.hfc4i.large` -> `ecs.hfc3il.large`).

---

## Cloud Assistant Agent requires a reboot after installation

After calling `InstallCloudAssistant`, the agent status is `ReadyReboot` and `RunCommand` will keep timing out.

**Correct approach:**
1. Call `InstallCloudAssistant`.
2. Call `RebootInstance` to restart the instance.
3. Poll `DescribeCloudAssistantStatus` until status becomes `Running`.
4. Then execute `RunCommand`.

> Tip: pass `--InstallRunCommandAgent true` during instance creation to avoid manual installation later.

---

## RunCommand Timeout minimum is 60

Setting `--Timeout` below 60 seconds triggers `LimitExceeded.MaximumTimeout`. Valid range: 60–86400 seconds.
