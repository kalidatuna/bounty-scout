import contextlib
import io
import unittest
from unittest.mock import patch

import bounty_scout as scout


class BountyScoutTests(unittest.TestCase):
    def test_issue_url_accepts_trailing_slash(self):
        self.assertEqual(scout.parse_issue_url("https://github.com/o/r/issues/123/"), ("o", "r", 123))

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

    @patch("bounty_scout.gh_api")
    def test_linked_prs_are_deduplicated_and_missing_sources_ignored(self, api):
        pr = {"source": {"issue": {"pull_request": {"url": "api-url"}, "html_url": "pr-url"}}}
        api.return_value = [pr, pr, {}, {"source": None}, {"source": {"issue": {"html_url": "issue-url"}}}]
        self.assertEqual(scout.linked_pull_requests("o", "r", 1), {"pr-url"})
        api.assert_called_once_with("repos/o/r/issues/1/timeline?per_page=100")

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

    def test_missing_timestamp(self):
        self.assertIsNone(scout.days_since(None))


if __name__ == "__main__":
    unittest.main()
