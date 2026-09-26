#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit


def gh_api(endpoint):
    try:
        result = subprocess.run(
            ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except FileNotFoundError:
        print("GitHub CLI (gh) is not installed or not on PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("GitHub API request timed out after 20 seconds.", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print("GitHub API error:", file=sys.stderr)
        print(result.stderr.strip() or "The GitHub CLI returned an error without details.", file=sys.stderr)
        sys.exit(1)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print("GitHub API returned invalid JSON.", file=sys.stderr)
        sys.exit(1)


def parse_issue_url(url):
    parsed = urlsplit(url)
    match = re.fullmatch(
        r"/([^/]+)/([^/]+)/issues/(\d+)/?",
        parsed.path,
    )

    if parsed.scheme not in ("http", "https") or parsed.netloc != "github.com" or not match:
        print("Expected a GitHub issue URL like:")
        print("https://github.com/owner/repository/issues/123")
        sys.exit(1)

    return match.group(1), match.group(2), int(match.group(3))


def days_since(timestamp):
    if not timestamp:
        return None

    then = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return max(0, (now - then).days)


def linked_pull_requests(owner, repo, number):
    prs = set()
    page = 1
    while True:
        timeline = gh_api(
            f"repos/{owner}/{repo}/issues/{number}/timeline?per_page=100&page={page}"
        )
        for event in timeline:
            source = event.get("source") or {}
            source_issue = source.get("issue") or {}
            if source_issue.get("pull_request"):
                url = source_issue.get("html_url")
                if url:
                    prs.add(url)
        if len(timeline) < 100:
            break
        page += 1

    return prs


def opportunity_score(issue_state, repo_inactive_days, competing_prs, comments, repo_unavailable=False, issue_locked=False):
    """Return the heuristic score and label without making API requests."""
    score = 100

    if issue_state != "open" or repo_unavailable or issue_locked:
        score -= 100

    if repo_inactive_days is not None:
        if repo_inactive_days > 365:
            score -= 40
        elif repo_inactive_days > 90:
            score -= 15

    if competing_prs >= 5:
        score -= 35
    elif competing_prs >= 2:
        score -= 15
    elif competing_prs == 1:
        score -= 5

    if comments > 20:
        score -= 10

    score = max(0, min(100, score))

    if score >= 80:
        recommendation = "STRONG CANDIDATE"
    elif score >= 60:
        recommendation = "INVESTIGATE"
    elif score >= 40:
        recommendation = "WEAK CANDIDATE"
    else:
        recommendation = "SKIP"

    return score, recommendation


def main():
    parser = argparse.ArgumentParser(description="Review a GitHub issue as a development opportunity")
    parser.add_argument("issue_url", help="GitHub issue URL")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report")
    args = parser.parse_args()
    owner, repo, number = parse_issue_url(args.issue_url)

    repository = gh_api(f"repos/{owner}/{repo}")
    issue = gh_api(f"repos/{owner}/{repo}/issues/{number}")
    if issue.get("pull_request"):
        print("The URL points to a pull request, not an issue.", file=sys.stderr)
        return 1

    prs = linked_pull_requests(owner, repo, number)

    repo_inactive_days = days_since(repository.get("pushed_at"))
    issue_age = days_since(issue.get("created_at"))
    competing_prs = len(prs)

    labels = [
        label["name"]
        for label in issue.get("labels", [])
    ]

    score, recommendation = opportunity_score(
        issue.get("state"), repo_inactive_days, competing_prs, issue.get("comments", 0),
        repository.get("archived", False) or repository.get("disabled", False),
        issue.get("locked", False),
    )
    report = {
        "issue_url": issue.get("html_url") or f"https://github.com/{owner}/{repo}/issues/{number}",
        "repository": f"{owner}/{repo}", "issue_number": number,
        "title": issue.get("title"), "state": issue.get("state"),
        "locked": issue.get("locked", False),
        "stars": repository.get("stargazers_count"),
        "archived": repository.get("archived", False),
        "disabled": repository.get("disabled", False),
        "open_issues": repository.get("open_issues_count"),
        "repo_inactive_days": repo_inactive_days, "issue_age_days": issue_age,
        "comments": issue.get("comments", 0), "linked_prs": sorted(prs),
        "labels": labels, "score": score, "recommendation": recommendation,
    }
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print()
    print("=" * 60)
    print("BOUNTY SCOUT")
    print("=" * 60)

    print(f"Repository:        {owner}/{repo}")
    print(f"URL:               {report['issue_url']}")
    print(f"Issue:             #{number} — {issue.get('title')}")
    print(f"State:             {issue.get('state')}")
    print(f"Locked:            {issue.get('locked', False)}")
    print(f"Stars:             {repository.get('stargazers_count')}")
    print(f"Archived/disabled: {repository.get('archived', False)}/{repository.get('disabled', False)}")
    print(f"Open issues:       {repository.get('open_issues_count')}")
    print(f"Repo last push:    {repo_inactive_days} days ago")
    print(f"Issue age:         {issue_age} days")
    print(f"Comments:          {issue.get('comments', 0)}")
    print(f"Linked PRs:        {competing_prs}")
    print(f"Labels:            {', '.join(labels) if labels else 'None'}")

    print()
    print(f"Opportunity score: {score}/100")
    print(f"Recommendation:    {recommendation}")

    if prs:
        print()
        print("Linked pull requests:")
        for url in sorted(prs):
            print(f"  - {url}")

    print()
    print("Important:")
    print("This score does NOT verify that a bounty is funded or payable.")
    print("Always verify bounty terms and contribution rules manually.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
