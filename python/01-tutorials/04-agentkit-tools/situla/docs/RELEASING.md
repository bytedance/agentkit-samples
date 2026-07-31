# Releasing Situla

Official binaries are built from a version tag with the exact Node.js release
recorded in `.node-version`. Linux and macOS builds must use the same Node.js
version and `package-lock.json`.

## Prepare

1. Update the matching versions in `package.json`, `package-lock.json`,
   `src/version.ts`, and `scripts/install.sh`.
2. Run `npm ci`.
3. Run `npm run licenses` and review `THIRD_PARTY_NOTICES.txt`.
4. Run the verification suite:

   ```bash
   npm run typecheck
   npm test
   npm run build
   git diff --check
   ```

## Build

Use the Node.js version declared by the repository:

```bash
nvm install
nvm use
npm ci
npm run build:binary
```

The build fails if a different Node.js version is active or if the official
Node.js distribution's `LICENSE` file cannot be found. It generates:

- `dist/situla-vVERSION-PLATFORM-ARCH`
- `dist/situla-vVERSION-PLATFORM-ARCH.sha256`
- `THIRD_PARTY_NOTICES.txt`, also embedded for `situla licenses`

Build and test each advertised platform on its native runner.

## macOS signing

The build script applies only an ad-hoc signature so a local development binary
can run. Before public distribution, replace it with a Developer ID Application
signature, enable the hardened runtime, notarize the final artifact, and verify
it with `codesign` and `spctl`.

Calculate and publish checksums only after final signing, notarization, and
packaging.

## Publish

Publish immutable, versioned artifacts together with:

- `SHA256SUMS`;
- a signature or artifact provenance attestation;
- an SPDX or CycloneDX SBOM;
- `THIRD_PARTY_NOTICES.txt`;
- the matching source tag.

Test the installer in clean Linux and macOS environments before announcing the
release.
