# Bytedance TOS Video Process Skill

This skill provides a focused video-processing toolkit for files stored in Bytedance TOS. It covers the most common TOS video workflows: reading metadata, extracting single snapshots, and capturing multiple frames across a timeline.

## When To Use

Use this skill when you need to:
- Read video metadata with `video/info`
- Generate poster images or thumbnails from videos in TOS
- Capture a frame at a specific timestamp
- Capture multiple frames for a timeline or sampling workflow
- Sample frames either by explicit timestamps or by interval
- Save snapshot results locally or back to TOS

Do not use this skill for:
- Full video transcoding pipelines
- Image-only or document-only workflows
- Generic object storage tasks unrelated to TOS video processing

## How It Works

Video processing is performed by passing a formatted `process` string to the Volcengine TOS SDK. The main patterns are:

- `video/info`
- `video/snapshot,t_<time>,f_<format>,w_<width>,h_<height>`

The scripts in this skill show how to combine those operations with local file output, TOS-to-TOS save flows, and repeated snapshot extraction across multiple timestamps.

## Directory Layout

```text
byted-tos-video-process/
├── SKILL.md
├── README.md
├── REFERENCE.md
├── WORKFLOWS.md
├── LICENSE
├── requirements.txt
├── .gitignore
└── scripts/
    ├── tos_jobs_client.py
    ├── video_info.py
    ├── video_snapshot.py
    ├── video_snapshots.py
    └── video_concat.py
```

## Requirements

- Python 3.7+
- Access to Volcengine TOS
- Valid AK/SK or STS credentials
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
| `TOS_BUCKET` | Yes | Source bucket that stores the video. | `my-video-bucket` |
| `TOS_OBJECT_KEY` | Yes | Source object key of the video. | `input/demos/wildlife.mp4` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials. | `STS...` |
| `TOS_SAVEAS_BUCKET` | No | Default target bucket for saving snapshots. | `my-snapshot-bucket` |
| `TOS_SAVEAS_OBJECT_PREFIX` | No | Default key prefix for saving snapshots. | `processed/snapshots/` |

For production usage, prefer short-lived STS credentials. The SDK automatically uses `TOS_SECURITY_TOKEN` when it is present.

## Quick Start

Export the minimum required configuration:

```bash
export TOS_ACCESS_KEY="YOUR_AK"
export TOS_SECRET_KEY="YOUR_SK"
export TOS_ENDPOINT="https://tos-cn-beijing.volces.com"
export TOS_REGION="cn-beijing"
export TOS_BUCKET="your-video-bucket"
export TOS_OBJECT_KEY="path/to/your/video.mp4"
```

Run one of the ready-to-use examples:

Read video metadata:

```bash
python3 scripts/video_info.py --key path/to/your/video.mp4 --json
```

Capture a single frame at 5 seconds:

```bash
python3 scripts/video_snapshot.py --key path/to/your/video.mp4 --time 5000 --output local_frame.jpg
```

Capture multiple frames and save to TOS:

```bash
python3 scripts/video_snapshots.py \
  --key path/to/your/video.mp4 \
  --timestamps 1000 3000 5000 \
  --saveas-bucket "your-output-bucket" \
  --saveas-object "snapshots"
```

Capture multiple frames by interval:

```bash
python3 scripts/video_snapshots.py \
  --key test.mp4 \
  --interval-ms 5000 \
  --duration-ms 60000 \
  --output snapshots
```

Create a concat job:

```bash
python3 scripts/video_concat.py \
  --key clips/part1.mp4 \
  --fragments clips/part2.mp4,clips/part3.mp4 \
  --saveas-object clips/final_concat.mp4 \
  --wait
```

## Document Roles

- `SKILL.md`: trigger-oriented instructions for agents deciding whether to load this skill
- `README.md`: setup guide and runnable entry points for humans and agents
- `REFERENCE.md`: parameter reference and result semantics
- `WORKFLOWS.md`: common snapshot and metadata workflows
- `scripts/`: executable examples for common video-processing tasks

## Usage Notes

- This skill focuses on `video/info` and `video/snapshot`, not full video transcoding.
- Validate timestamp and output size parameters before sending requests.
- Multi-frame extraction is a client-side orchestration pattern that issues repeated snapshot requests concurrently.
- `video_snapshots.py` now supports `--key` and `--bucket` overrides, which makes it consistent with the rest of the TOS skills during manual testing.
- Saving snapshots back to TOS is often preferable for downstream workflows.
- Official Volcengine TOS documentation remains the source of truth for the full parameter matrix.

## Related Files

- Parameter reference: [REFERENCE.md](REFERENCE.md)
- Workflow guide: [WORKFLOWS.md](WORKFLOWS.md)

## License

This skill is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
