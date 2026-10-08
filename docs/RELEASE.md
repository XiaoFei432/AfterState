# Release files

## Upload

The archive contains an `afterstate/` directory. Upload its contents to the GitHub source repository root, including `README.md`, `.github/` and `.gitignore`. Refresh the anonymous mapping after the source upload.

Reader URL: [AfterState-1C76](https://anonymous.4open.science/r/AfterState-1C76/).

The reader URL is separate from the Git remote. No remote repository was modified during package preparation.

## Contents

Included files: Python source, tests, specifications, schemas, aggregate transcriptions, generated figures, fixture and scripted-run records, documentation and the MIT license.

Excluded files: manuscript PDF, credentials, local environments, temporary snapshots, compiled bytecode, caches, model weights and third-party source snapshots.

## Packaging

```console
python scripts/package_release.py --output ../afterstate-artifact.zip
```

The script excludes build/cache directories, scans text files for configured path and credential patterns, writes `MANIFEST.sha256`, and creates a ZIP with fixed entry timestamps. The manifest contains hashes for all distributed files except itself.

## License and provenance

The software uses the MIT license. Aggregate values are attributed to the supplied manuscript. Example wheel modules are distributed with the fixture source. Third-party datasets, repositories and model weights are not part of this archive.
