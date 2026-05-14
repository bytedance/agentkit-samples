# Bytedance TOS File Process Workflows

This document shows common end-to-end workflows for the async file compression and uncompression scripts.

## Workflow 1: Compress Multiple Files into a Zip Archive

**Goal**: Archive multiple TOS objects into a single zip file.

**Script**: `scripts/file_compress.py`

```bash
python3 scripts/file_compress.py \
  --keys file1.jpg,file2.txt,file3.pdf \
  --format zip \
  --saveas-object output/archive.zip \
  --wait
```

**Expected Result**:
- Prints job creation payload
- Polls until `Success`
- Writes the archive to `output/archive.zip`

## Workflow 2: Compress Files with Flattened Structure

**Goal**: Compress files without preserving their directory structure.

```bash
python3 scripts/file_compress.py \
  --keys dir1/file1.jpg,dir2/file2.txt \
  --format zip \
  --flatten 1 \
  --saveas-object output/flat_archive.zip \
  --wait
```

## Workflow 3: Create a Tar or Zst Archive

**Goal**: Use an alternative archive format.

```bash
# Tar archive
python3 scripts/file_compress.py \
  --keys file1.jpg,file2.txt \
  --format tar \
  --saveas-object output/archive.tar \
  --wait

# Zstd archive
python3 scripts/file_compress.py \
  --keys file1.jpg,file2.txt \
  --format zst \
  --saveas-object output/archive.zst \
  --wait
```

## Workflow 4: Uncompress an Archive with Original Directory Structure

**Goal**: Extract a zip archive while preserving the original directory layout.

```bash
python3 scripts/file_uncompress.py \
  --key output/archive.zip \
  --prefix output/extracted/ \
  --prefix-replaced 0 \
  --wait
```

**Expected Result**:
- Prints `JobId`
- Polls until `Success`
- Extracts files to `output/extracted/` with original directory structure preserved

## Workflow 5: Uncompress and Replace Directory with Prefix

**Goal**: Extract an archive and replace the original directory structure with the specified prefix.

```bash
python3 scripts/file_uncompress.py \
  --key output/archive.zip \
  --prefix output/flat/ \
  --prefix-replaced 1 \
  --wait
```

## Workflow 6: Submit Without Waiting

**Goal**: Hand off the job quickly and let another system query later.

```bash
python3 scripts/file_compress.py \
  --keys file1.jpg,file2.txt \
  --format zip \
  --saveas-object output/async_archive.zip \
  --json
```

**Expected Result**:
- Prints the create-job response
- Does not poll workflow state
- Suitable for agent orchestration that records `job_id` and queries later with `--job-id`

## Workflow 7: Compress Then Uncompress (Round Trip)

**Goal**: Archive files and then extract them to a different location.

```bash
# Step 1: Compress
python3 scripts/file_compress.py \
  --keys file1.jpg,file2.txt \
  --format zip \
  --output-key output/archive.zip \
  --wait

# Step 2: Uncompress to a new prefix
python3 scripts/file_uncompress.py \
  --key output/archive.zip \
  --prefix output/restored/ \
  --wait
```

## Workflow 8: Validate or Query a Job

**Goal**: Let an agent inspect the resolved request before submission or resume from an existing job id.

```bash
# Preview the resolved payload without submitting
python3 scripts/file_compress.py \
  --keys file1.jpg,file2.txt \
  --format zip \
  --saveas-object output/archive.zip \
  --validate

# Query an existing compression job
python3 scripts/file_compress.py --job-id <job_id> --json

# Query an existing uncompression job
python3 scripts/file_uncompress.py --job-id <job_id> --json
```

**Behavior Notes**:
- `--validate` and `--dry-run` return the resolved payload without creating a job.
- `--job-id` switches the script into query mode.
- `--json` is recommended when the next step is agent orchestration.

## Troubleshooting

- If the script exits with missing environment-variable errors, verify that the TOS runtime configuration declared by the skill has been provided correctly.
- If submission succeeds but polling fails, confirm the TOS credentials have permission to access the `file_jobs` API.
- If the job fails after submission, check the `Code` and `Message` fields in the job result for details.
- If the output key suffix does not match the format, the script will exit with an error before submission.

---

## Workflow 9: Compress Then Uncompress (Round Trip)

**Goal**: Archive multiple TOS objects into a zip, then extract them to a new directory — verifying the full async job lifecycle (submit → poll → result).

**Pipeline**: `file_compress` → `file_uncompress`

### Step 1: Compress files into an archive

```bash
python3 scripts/file_compress.py \
  --keys file1.jpg,file2.mp3 \
  --format zip \
  --saveas-bucket my-bucket \
  --saveas-object output/archive.zip \
  --wait --json
```

On success, the archive is written to `output/archive.zip`.

### Step 2: Uncompress to a new directory

```bash
python3 scripts/file_uncompress.py \
  --key output/archive.zip \
  --prefix output/extracted/ \
  --prefix-replaced 0 \
  --wait --json
```

- `--prefix-replaced 0` preserves the original directory structure inside the archive.
- `--prefix-replaced 1` replaces the original directory structure with the specified prefix.

The extracted files appear under `output/extracted/`.

### Agent orchestration notes

- Both steps are async jobs; use `--wait` for blocking or `--json` to capture `job_id` and query later with `--job-id`.
- Step 2 depends on Step 1 — the archive must exist in TOS before uncompressing.
- This workflow is the simplest end-to-end demo of the async job pattern and can serve as a smoke test for the `file_jobs` API.
