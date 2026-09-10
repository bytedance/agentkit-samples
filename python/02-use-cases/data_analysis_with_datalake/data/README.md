# IMDb LanceDB Dataset

This directory contains the local LanceDB dataset for the
`data_analysis_with_datalake` sample.

The source CSV and generated `imdb_top_1000` table contain 1,000 movies.
Top-N analyses should select their subset at query time, for example by sorting
non-null `gross` values in descending order and applying `LIMIT 100`.

## Upload to TOS

Upload the contents of `lance_catalog/` while preserving all directory names.
For a bucket named `<bucket>`, the resulting objects must have these prefixes:

```text
lance_catalog/default/imdb_top_1000.lance/
lance_catalog/default/metadata_table.lance/
```

Do not rename or omit the `_versions`, `_transactions`, or `data` directories.
When replacing an earlier build, delete the two existing `.lance` directories
from TOS first, then upload the newly generated directories. This prevents stale
manifest and data objects from being mixed with the new build.

Configure the runtime with table names without the `.lance` suffix:

```text
LANCEDB_URI=s3://<bucket>/lance_catalog/default/imdb_top_1000
LANCEDB_METADATA_URI=s3://<bucket>/lance_catalog/default/metadata_table
TOS_REGION=cn-beijing
```

The `source/` directory and `poster_embeddings.jsonl` checkpoint are not needed
by the runtime and do not need to be uploaded.

## Rebuild

From the sample directory:

```bash
source .venv/bin/activate
python build_imdb_dataset.py
```

Use `--force-download` to download the source CSV again, or
`--force-embeddings` to regenerate all poster embeddings.
