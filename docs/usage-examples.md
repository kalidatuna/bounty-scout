# Usage examples

Authenticate with `gh auth login`, then pass an issue URL. A copied URL with a
query string or comment fragment works too.

```sh
python3 bounty_scout.py https://github.com/OWNER/REPOSITORY/issues/123
```

The report shows the issue's state, lock status, repository activity, labels,
all linked pull requests, and a score. Only open or unknown-state linked PRs
lower the score. Review the linked PRs yourself: a cross-reference can be
unrelated to the proposed fix.

## Use the result in a script

`--json` writes a single JSON object to stdout; errors go to stderr and exit
nonzero. For example, with `jq` installed:

```sh
python3 bounty_scout.py https://github.com/OWNER/REPOSITORY/issues/123 --json \
  | jq '{issue_url, recommendation, score, open_linked_prs}'
```

To review several issues, run the command once per URL. Each invocation reads
the repository, issue, and every page of its timeline, so a large batch can
use substantial API quota.

## Decide whether to contribute

A strong score is a prompt to investigate, not a bounty guarantee. Before
starting, read the issue and contribution instructions, check whether an open
PR already addresses it, and verify any payment terms with the project owner.
Closed or locked issues and archived or disabled repositories score zero.
