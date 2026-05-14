# Bytedance TOS Audio Process Workflows

This document shows common end-to-end workflows for the async audio conversion script.

## Workflow 1: Convert Full Audio to 16k Mono PCM-WAV

**Goal**: Convert a full audio file into a speech-friendly WAV output.

**Script**: `scripts/audio_to_pcm.py`

```bash
python3 scripts/audio_to_pcm.py \
  --key test.wav \
  --sample-rate 16000 \
  --channels 1 \
  --sample-format s16 \
  --output-object skill-test/audio/test_pcm.wav \
  --wait
```

**Expected Result**:
- Prints `JobId`
- Polls until `Success`
- Writes the converted object to `skill-test/audio/test_pcm.wav`

## Workflow 2: Convert and Download Locally

**Goal**: Keep the TOS output and also fetch a local copy for inspection.

```bash
mkdir -p /tmp/skill-test/audio

python3 scripts/audio_to_pcm.py \
  --key test.wav \
  --sample-rate 16000 \
  --channels 1 \
  --sample-format s16 \
  --output-object skill-test/audio/test_pcm.wav \
  --wait \
  --download /tmp/skill-test/audio/test_pcm.wav
```

## Workflow 3: Convert Only a Time Slice

**Goal**: Extract and convert a shorter segment of the source audio.

```bash
python3 scripts/audio_to_pcm.py \
  --key test.wav \
  --start-ms 15000 \
  --duration-ms 5000 \
  --output-object skill-test/audio/test_clip_pcm.wav \
  --wait
```

## Workflow 4: Submit Without Waiting

**Goal**: Hand off the job quickly and let another system query later.

```bash
python3 scripts/audio_to_pcm.py \
  --key test.wav \
  --output-object skill-test/audio/test_async.wav
```

**Expected Result**:
- Prints the create-job response
- Does not poll workflow state

## Troubleshooting

- If the script exits with missing environment-variable errors, verify that the TOS runtime configuration declared by the skill has been provided correctly.
- If submission succeeds but polling fails, confirm the TOS credentials have permission to access the `media_jobs` API.
- If the job fails after submission, check the `Code` and `Message` fields in the job result for details.
