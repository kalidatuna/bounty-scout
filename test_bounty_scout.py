import contextlib
import io
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import bounty_scout as scout


class BountyScoutTests(unittest.TestCase):
    @patch("bounty_scout.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_github_cli_has_clear_error(self, _run):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as result:
                scout.gh_api("repos/o/r")
        self.assertEqual(result.exception.code, 1)
        self.assertIn("not installed", errors.getvalue())

    @patch("bounty_scout.subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 20))
    def test_api_timeout_has_clear_error(self, _run):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as result:
                scout.gh_api("repos/o/r")
        self.assertEqual(result.exception.code, 1)
        self.assertIn("timed out", errors.getvalue())

    @patch("bounty_scout.subprocess.run")
    def test_invalid_api_json_has_clear_error(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "not JSON", "")
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as result:
                scout.gh_api("repos/o/r")
        self.assertEqual(result.exception.code, 1)
        self.assertIn("invalid JSON", errors.getvalue())

    @patch("bounty_scout.subprocess.run")
    def test_api_failure_reports_to_stderr(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "HTTP 403")
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as result:
                scout.gh_api("repos/o/r")
        self.assertEqual(result.exception.code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("HTTP 403", errors.getvalue())

    def test_issue_url_accepts_trailing_slash(self):
        self.assertEqual(scout.parse_issue_url("https://github.com/o/r/issues/123/"), ("o", "r", 123))

    def test_issue_url_accepts_copied_query_and_fragment(self):
        self.assertEqual(scout.parse_issue_url("https://github.com/o/r/issues/123?issue=123#issuecomment-1"), ("o", "r", 123))

    def test_invalid_issue_urls_exit(self):
        for url in ("https://example.com/o/r/issues/1", "https://github.com/o/r/pull/1", "garbage"):
            with self.subTest(url=url), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    scout.parse_issue_url(url)
                self.assertEqual(error.exception.code, 1)

    def test_inactivity_boundaries(self):
        for days, expected in ((None, 100), (90, 100), (91, 85), (365, 85), (366, 60)):
            with self.subTest(days=days):
                self.assertEqual(scout.opportunity_score("open", days, 0, 0)[0], expected)

    def test_pr_boundaries(self):
        for count, expected in ((0, 100), (1, 95), (2, 85), (4, 85), (5, 65)):
            with self.subTest(count=count):
                self.assertEqual(scout.opportunity_score("open", 0, count, 0)[0], expected)

    def test_comment_boundary(self):
        self.assertEqual(scout.opportunity_score("open", 0, 0, 20)[0], 100)
        self.assertEqual(scout.opportunity_score("open", 0, 0, 21)[0], 90)

    def test_recommendations_and_closed_issue_clamp(self):
        for args, expected in (
            (("open", 91, 1, 0), (80, "STRONG CANDIDATE")),
            (("open", 366, 0, 0), (60, "INVESTIGATE")),
            (("open", 366, 1, 21), (45, "WEAK CANDIDATE")),
            (("open", 366, 5, 21), (15, "SKIP")),
            (("closed", 366, 5, 21), (0, "SKIP")),
        ):
            with self.subTest(args=args):
                self.assertEqual(scout.opportunity_score(*args), expected)

    def test_archived_or_disabled_repo_is_not_recommended(self):
        self.assertEqual(scout.opportunity_score("open", 0, 0, 0, True), (0, "SKIP"))

    def test_locked_issue_is_not_recommended(self):
        self.assertEqual(scout.opportunity_score("open", 0, 0, 0, False, True), (0, "SKIP"))

    @patch("bounty_scout.gh_api")
    def test_linked_prs_are_deduplicated_and_missing_sources_ignored(self, api):
        pr = {"source": {"issue": {"pull_request": {"url": "api-url"}, "html_url": "pr-url"}}}
        api.return_value = [pr, pr, {}, {"source": None}, {"source": {"issue": {"html_url": "issue-url"}}}]
        self.assertEqual(scout.linked_pull_requests("o", "r", 1), {"pr-url"})
        api.assert_called_once_with("repos/o/r/issues/1/timeline?per_page=100&page=1")

    @patch("bounty_scout.gh_api")
    def test_linked_prs_include_later_timeline_pages(self, api):
        first_page = [{} for _ in range(100)]
        second_page = [{"source": {"issue": {"pull_request": {"url": "api-url"}, "html_url": "pr-url"}}}]
        api.side_effect = [first_page, second_page]
        self.assertEqual(scout.linked_pull_requests("o", "r", 1), {"pr-url"})
        self.assertEqual(api.call_count, 2)

    @patch("bounty_scout.gh_api")
    def test_report_uses_existing_score_and_labels(self, api):
        api.side_effect = [
            {"stargazers_count": 2, "open_issues_count": 3},
            {"state": "open", "title": "Example", "labels": [{"name": "help wanted"}]},
            [],
        ]
        output = io.StringIO()
        with patch("sys.argv", ["bounty_scout.py", "https://github.com/o/r/issues/1"]), contextlib.redirect_stdout(output):
            scout.main()
        self.assertIn("Opportunity score: 100/100", output.getvalue())
        self.assertIn("STRONG CANDIDATE", output.getvalue())
        self.assertIn("help wanted", output.getvalue())
        self.assertEqual(api.call_count, 3)

    @patch("bounty_scout.gh_api")
    def test_pull_request_disguised_as_issue_is_rejected(self, api):
        api.side_effect = [{}, {"pull_request": {"url": "api-pr"}}]
        with patch("sys.argv", ["bounty_scout.py", "https://github.com/o/r/issues/1"]), contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(scout.main(), 1)
        self.assertIn("pull request", errors.getvalue())
        self.assertEqual(api.call_count, 2)

    @patch("bounty_scout.gh_api")
    def test_json_report_is_machine_readable(self, api):
        api.side_effect = [
            {"stargazers_count": 2, "open_issues_count": 3},
            {"state": "open", "title": "Example", "labels": []},
            [],
        ]
        output = io.StringIO()
        with patch("sys.argv", ["bounty_scout.py", "https://github.com/o/r/issues/1", "--json"]), contextlib.redirect_stdout(output):
            self.assertEqual(scout.main(), 0)
        report = scout.json.loads(output.getvalue())
        self.assertEqual(report["repository"], "o/r")
        self.assertEqual(report["score"], 100)
        self.assertEqual(report["linked_prs"], [])

    def test_missing_timestamp(self):
        self.assertIsNone(scout.days_since(None))

    def test_future_timestamp_does_not_report_negative_age(self):
        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        self.assertEqual(scout.days_since(future), 0)


if __name__ == "__main__":
    unittest.main()
