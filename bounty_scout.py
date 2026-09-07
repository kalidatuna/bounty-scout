#!/usr/bin/env python3

import json
import re
import subprocess
import sys
from datetime import datetime, timezone


def gh_api(endpoint):
    result = subprocess.run(
        [
            "gh", "api",
            "-H", "Accept: application/vnd.github+json",
            endpoint,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("GitHub API error:")
        print(result.stderr.strip())
        sys.exit(1)

    return json.loads(result.stdout)


def parse_issue_url(url):
    match = re.fullmatch(
        r"https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)/?",
        url,
    )

    if not match:
        print("Expected a GitHub issue URL like:")
        print("https://github.com/owner/repository/issues/123")
        sys.exit(1)

    return match.group(1), match.group(2), int(match.group(3))


def days_since(timestamp):
    if not timestamp:
        return None

    then = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return (now - then).days


def linked_pull_requests(owner, repo, number):
    timeline = gh_api(
        f"repos/{owner}/{repo}/issues/{number}/timeline?per_page=100"
    )

    prs = set()

    for event in timeline:
        source = event.get("source") or {}
        source_issue = source.get("issue") or {}

        if source_issue.get("pull_request"):
            url = source_issue.get("html_url")
            if url:
                prs.add(url)

    return prs


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("python3 bounty_scout.py <github-issue-url>")
        sys.exit(1)

    owner, repo, number = parse_issue_url(sys.argv[1])

    repository = gh_api(f"repos/{owner}/{repo}")
    issue = gh_api(f"repos/{owner}/{repo}/issues/{number}")

    prs = linked_pull_requests(owner, repo, number)

    repo_inactive_days = days_since(repository.get("pushed_at"))
    issue_age = days_since(issue.get("created_at"))
    competing_prs = len(prs)

    labels = [
        label["name"]
        for label in issue.get("labels", [])
    ]

    score = 100

    if issue.get("state") != "open":
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

    if issue.get("comments", 0) > 20:
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

    print()
    print("=" * 60)
    print("BOUNTY SCOUT")
    print("=" * 60)

    print(f"Repository:        {owner}/{repo}")
    print(f"Issue:             #{number} — {issue.get('title')}")
    print(f"State:             {issue.get('state')}")
    print(f"Stars:             {repository.get('stargazers_count')}")
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


if __name__ == "__main__":
    main()
