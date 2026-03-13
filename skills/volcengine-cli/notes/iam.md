# IAM Service Notes

## UpdateUser does not support Tags

`UpdateUser` can only modify basic attributes such as Description and DisplayName. It cannot manage tags.

**Correct approach:** use `TagResources` to tag users separately:

```bash
ve iam TagResources --ResourceType "User" --ResourceNames.1 "<UserName>" --Tags.1.Key "key" --Tags.1.Value "value"
```

The same applies to roles — use `TagResources` with `ResourceType` set to `Role`.
