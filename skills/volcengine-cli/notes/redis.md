# Redis Service Notes

## Allow-list deletion requires the instance to be fully released

Calling `DeleteAllowList` immediately after `DeleteDBInstance` fails with `AllowListBindInstanceCannotDelete` because the instance has not been fully removed yet.

**Correct approach:** wait for the Redis instance to be fully deleted (~30 seconds) before deleting the associated allow list.

```bash
# Poll until the instance no longer exists
ve redis DescribeDBInstanceDetail --body '{"InstanceId":"redis-xxx"}'
# Once the instance is gone, delete the allow list
ve redis DeleteAllowList --body '{"AllowListId":"acl-xxx"}'
```
