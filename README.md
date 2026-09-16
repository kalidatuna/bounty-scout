# Bounty Scout

[![CI](https://github.com/kalidatuna/bounty-scout/actions/workflows/ci.yml/badge.svg)](https://github.com/kalidatuna/bounty-scout/actions/workflows/ci.yml)

A Python command-line tool for reviewing GitHub issues as potential development opportunities. It reads repository metadata, issue details, and linked pull requests using the GitHub CLI, then prints a heuristic opportunity score.

## Quick start

Requires Python 3.10+ and an installed, authenticated [GitHub CLI](https://cli.github.com/). There are no third-party Python dependencies.

```sh
git clone https://github.com/kalidatuna/bounty-scout.git
cd bounty-scout
gh auth login
python3 bounty_scout.py https://github.com/OWNER/REPOSITORY/issues/123
```

Replace the uppercase placeholders and issue number with a real issue. The tool performs read-only API requests using your existing GitHub CLI authentication. Access to private issues depends on that account's permissions.

The report includes issue state, labels, age, comments, repository activity, linked PR URLs, a score from 0 to 100, and a recommendation.

## How the score works

Start at 100, subtract the penalties below, then clamp to 0–100:

| Signal | Penalty |
| --- | --- |
| Issue is not open | 100 |
| Repository last push over 365 days ago | 40 |
| Repository last push over 90 days ago (up to 365) | 15 |
| Five or more linked PRs | 35 |
| Two to four linked PRs | 15 |
| One linked PR | 5 |
| More than 20 comments | 10 |

Recommendations: **80–100** strong candidate, **60–79** investigate, **40–59** weak candidate, **0–39** skip. Missing repository timestamps incur no inactivity penalty.

## Limitations

- The score does not verify bounty funding, payment eligibility, implementation difficulty, specification quality, or contribution rules.
- Only the first 100 timeline events are inspected. Linked PRs are deduplicated, but may be closed, unrelated, or otherwise not competing solutions.
- Push recency and comment count are rough signals, not a judgment of project quality. GitHub's `open_issues_count` also includes pull requests.
- API failures can result from authentication, permissions, rate limits, or missing resources. Check `gh auth status` and the reported API error.

Contribution-policy detection, reward tracking, and deeper PR analysis remain planned work.

## Development

```sh
python3 -m unittest discover -v
```

Tests use mocks and require neither GitHub credentials nor network access. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.
