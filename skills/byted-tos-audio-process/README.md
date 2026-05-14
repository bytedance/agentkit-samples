# Bytedance TOS Audio Process Skill

This skill provides an async audio-processing toolkit for files stored in Bytedance TOS. It currently focuses on the agent-relevant preprocessing case of converting source audio into PCM-oriented WAV output for ASR, speech analytics, or downstream media pipelines.

## When To Use

Use this skill when you need to:
- Convert a TOS audio object into 16k/8k PCM-style WAV
- Downmix stereo audio to mono
- Normalize sample rate and sample format before ASR
- Trim and convert a specific time range of an audio object
- Submit an async `AudioConvert` job via the TOS gateway's `media_jobs` API and optionally wait for completion

Do not use this skill for:
- Local-only ffmpeg workflows that do not involve TOS
- Video transcoding or frame extraction
- Document preview or image transformation

## Why This Skill Exists

The audio-to-PCM path is exposed as an async job via the TOS gateway's `media_jobs` API. This skill wraps that API into a runnable Python script so agents can:

1. Submit an `AudioConvert` job via the `media_jobs` API
2. Poll the job state until success or failure
3. The output is a WAV file (PCM container) saved to TOS

## Directory Layout

```text
byted-tos-audio-process/
├── SKILL.md
├── README.md
├── REFERENCE.md
├── WORKFLOWS.md
├── LICENSE
├── requirements.txt
└── scripts/
    ├── audio_to_pcm.py
    └── tos_jobs_client.py
```

## Requirements

- Python 3.7+
- Access to Volcengine TOS
- Valid TOS AK/SK or STS credentials
- Network access to the target TOS endpoint

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

| Variable | Required | Description | Example |
| --- | --- | --- | --- |
| `TOS_ACCESS_KEY` | Yes | TOS access key ID. | `AK...` |
| `TOS_SECRET_KEY` | Yes | TOS secret access key. | `your-secret-key` |
| `TOS_ENDPOINT` | Yes | TOS endpoint URL. | `https://tos-cn-beijing.volces.com` |
| `TOS_REGION` | Yes | TOS region. | `cn-beijing` |
| `TOS_BUCKET` | Yes | Source bucket that stores the audio object. | `my-audio-bucket` |
| `TOS_OBJECT_KEY` | No | Source object key of the audio file. Can be overridden with `--key`. | `audio/test.wav` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials. | `STS...` |

## Quick Start

Export the minimum required configuration:

```bash
export TOS_ACCESS_KEY="YOUR_AK"
export TOS_SECRET_KEY="YOUR_SK"
export TOS_ENDPOINT="https://tos-cn-beijing.volces.com"
export TOS_REGION="cn-beijing"
export TOS_BUCKET="your-audio-bucket"
export TOS_OBJECT_KEY="skill-test/input/test.wav"
```

Submit an async conversion job:

```bash
python3 scripts/audio_to_pcm.py \
  --sample-rate 16000 \
  --channels 1 \
  --sample-format s16 \
  --output-object skill-test/audio/test_pcm.wav
```

Wait for completion and download locally:

```bash
python3 scripts/audio_to_pcm.py \
  --key test.wav \
  --sample-rate 16000 \
  --channels 1 \
  --sample-format s16 \
  --output-object skill-test/audio/test_pcm.wav \
  --wait \
  --download /tmp/skill-test/audio/test_pcm.wav
```

Trim a clip before conversion:

```bash
python3 scripts/audio_to_pcm.py \
  --key test.wav \
  --start-ms 30000 \
  --duration-ms 10000 \
  --output-object skill-test/audio/test_clip_pcm.wav \
  --wait
```

## Usage Notes

- The script outputs a WAV file (PCM container) because that format cleanly carries PCM sample format, sample rate, and channel settings.
- `--sample-format s16 --sample-rate 16000 --channels 1` is the most common speech-preprocessing combination.
- The script uses the TOS gateway's `media_jobs` API with `job_type=AudioConvert`, authenticated via `pre_signed_url` from the TOS Python SDK. No extra environment variables beyond the standard TOS credentials are needed.
- Successful submission returns a `JobId`; `--wait` then polls the job `State` until `Success` or `Failed`.

## Related Files

- Trigger-oriented usage: [SKILL.md](SKILL.md)
- Parameter reference: [REFERENCE.md](REFERENCE.md)
- Workflow guide: [WORKFLOWS.md](WORKFLOWS.md)

## License

This skill is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
