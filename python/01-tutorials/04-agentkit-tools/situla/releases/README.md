# Prebuilt releases

This directory contains a compressed, versioned Linux x64 Situla binary that
can be checked into the sample repository without exceeding common Git hosting
single-file limits.

Verify a package before extracting it:

```bash
sha256sum -c situla-v0.1.0-linux-x64.gz.sha256
```

Extract and verify the executable:

```bash
gzip -dk situla-v0.1.0-linux-x64.gz
chmod 755 situla-v0.1.0-linux-x64
sha256sum -c situla-v0.1.0-linux-x64.sha256
./situla-v0.1.0-linux-x64 --version
```

The first checksum covers the compressed package; the second covers the
extracted executable.

The one-line installer documented in the project README downloads the native,
uncompressed artifact from the release host and verifies it independently.
