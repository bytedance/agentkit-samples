# Bytedance TOS Audio Process Reference

This document explains the current async audio conversion path implemented by this skill.

## Authentication

Authentication is handled by the TOS Python SDK. The `tos_jobs_client.py` shared client signs requests with the TOS identity declared in `SKILL.md` metadata. No additional DP-specific configuration is needed.

## Core Operation

### `AudioConvert`

The script `scripts/audio_to_pcm.py` converts a source object in TOS by:

1. Building an `AudioConvertConfig` payload
2. Posting a JSON payload to the TOS gateway's `media_jobs` API with query `media_jobs=&job_type=AudioConvert`
3. Polling the job state via the `media_jobs` API with `job_type=AudioConvert&job_id=<job_id>`
4. The output is a WAV file (PCM container) saved to TOS

## Job Payload

The submission body follows the TOS gateway's `media_jobs` API contract:

```json
{
  "Input": {"Object": "test.wav"},
  "AudioConvertConfig": {
    "ContainerFormat": "wav",
    "SampleRate": 16000,
    "Channels": 1,
    "SampleFormat": "s16"
  },
  "Output": {
    "Region": "cn-beijing",
    "Bucket": "source-bucket",
    "Object": "skill-test/audio/test_pcm.wav"
  }
}
```

Optional `TimeInterval` can be added to `AudioConvertConfig` for trimming:

```json
{
  "Start": 30000,
  "Duration": 10000
}
```

## CLI Mapping

| CLI argument | Meaning | Notes |
| --- | --- | --- |
| `--key` | Source audio object key | Overrides `TOS_OBJECT_KEY` |
| `--sample-rate` | Target sample rate | Default `16000` |
| `--channels` | Target channel count | Default `1` |
| `--sample-format` | Target sample format | Default `s16` |
| `--format` | Output container | Currently fixed to `wav` |
| `--start-ms` | Trim start offset | Optional |
| `--duration-ms` | Trim duration | Optional |
| `--output-bucket` | Output bucket | Defaults to source bucket |
| `--output-object` | Output object key | Defaults to `<basename>.wav` |
| `--wait` | Poll until completion | Optional |

## Workflow States

The polling client currently treats these states as:

| State | Meaning |
| --- | --- |
| `Submitted` | Job accepted by workflow service |
| `Running` | Backend is processing |
| `Success` | Output object should be ready |
| `Failed` | Job finished with error |

## Notes

- The script prints the raw create-job response when `--wait` is not used.
- When `--wait` is used, the final printed object is the first job item returned by `get_job`.
- Authentication uses the TOS identity declared in `SKILL.md` metadata. No DP-specific configuration is needed.
