# Contributing

Start by reading the README and reproducing the behavior you want to change. Keep changes focused and describe the user-visible result.

## Local validation

Run from the repository root:

```sh
python3 -m unittest discover -v
```

Mock `gh_api` or `subprocess.run` in tests. Cover scoring boundaries and malformed input without making live GitHub requests. Keep the score explainable and update the README whenever a scoring rule changes.

## Submitting changes

1. Create a branch for the change.
2. Add regression coverage for behavior changes and update relevant examples.
3. Run the checks above and `git diff --check`.
4. Open a pull request describing the problem, change, test results, and any remaining limitations.

For bug reports, include runtime versions, a minimal reproduction, expected and actual behavior, and sanitized output. Do not include tokens or credentials. Keep hardware-dependent observations separate from offline results.

## Continuous integration

CI runs the offline suite on every push and pull request with read-only repository permissions. Action versions are pinned to commit IDs. The matrix covers Python 3.10 and 3.12. No third-party dependencies, secrets, or live service access are required.
