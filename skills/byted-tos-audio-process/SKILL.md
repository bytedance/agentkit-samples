---
name: byted-tos-audio-process
description: "Converts audio objects stored in Volcengine TOS into PCM-oriented WAV output through TOS data-process async jobs. Use this skill when the user needs to convert audio to PCM or WAV, resample audio to 16k, convert to mono, change sample format, normalize audio for ASR pipelines, or prepare TOS audio files for speech recognition — even if they don't explicitly mention 'PCM' or 'audio conversion'."
metadata:
  version: "1.0.0"
  openclaw:
    identity:
      - type: apikey
        provider: tos_provider
        env:
          - TOS_ACCESS_KEY
          - TOS_SECRET_KEY
          - TOS_ENDPOINT
          - TOS_REGION
          - TOS_BUCKET
        required: true
    optional:
      env:
        - TOS_OBJECT_KEY
        - TOS_SECURITY_TOKEN
user-invocable: true
license: Apache-2.0
---

# Volcengine TOS Audio Process

Convert audio files stored in Volcengine TOS into PCM-oriented WAV output through the TOS gateway's `media_jobs` API.

## Setup (once per environment)

Install dependencies on first use:

```bash
cd {baseDir}
pip install -r {baseDir}/requirements.txt
```

Then run scripts with Python 3.7+:

```bash
python3 {baseDir}/scripts/<script>.py <args>
```

## Environment Variables

This skill relies on the TOS identity declared in the `metadata` block. Common runtime variables are:

| Environment Variable | Required | Description |
| --- | --- | --- |
| `TOS_ACCESS_KEY` | Yes | TOS access key ID |
| `TOS_SECRET_KEY` | Yes | TOS secret access key |
| `TOS_ENDPOINT` | Yes | TOS endpoint URL |
| `TOS_REGION` | Yes | TOS region |
| `TOS_BUCKET` | Yes | Source bucket that stores the audio object |
| `TOS_OBJECT_KEY` | No | Source object key of the audio file. Can be overridden with `--key` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials |

## Quick start

```bash
# Convert an audio object to 16k mono s16 WAV and wait for completion
python3 {baseDir}/scripts/audio_to_pcm.py \
  --key test.wav \
  --sample-rate 16000 \
  --channels 1 \
  --sample-format s16 \
  --output-object skill-test/audio/test_pcm.wav \
  --wait
```

## Available scripts

| Script | Purpose |
|--------|---------|
| `scripts/audio_to_pcm.py` | Submit an async `AudioConvert` job via the TOS gateway's `media_jobs` API that converts TOS audio into PCM-oriented WAV output. Supports `--wait` to poll until completion. |
| `scripts/tos_jobs_client.py` | Shared client for TOS gateway `doc_jobs`/`media_jobs` APIs using pre-signed URL auth. |

## Rules

- **TOS gateway API**: This skill uses the TOS gateway's `media_jobs` API with `job_type=AudioConvert`. Authentication is handled via `pre_signed_url` from the TOS Python SDK and the TOS identity declared in the `metadata` block above.
- **Current output format**: The output is a WAV file (PCM container), not raw headerless `.pcm` bytes.
- **Async job model**: The script creates async jobs and optionally waits for completion with the `--wait` flag.
- **Language**: Reply in the user's preferred language.

## Further reading

- Setup and environment: [README.md](README.md)
- Parameter reference: [REFERENCE.md](REFERENCE.md)
- End-to-end workflows: [WORKFLOWS.md](WORKFLOWS.md)
