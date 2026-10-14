import contextlib
import io
import unittest
from unittest.mock import patch

import bounty_scout as scout


class ApiShapeTests(unittest.TestCase):
    def assert_clean_failure(self, operation, context):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as result:
                operation()
        self.assertEqual(result.exception.code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn(f"unexpected {context} response", errors.getvalue())

    def test_repository_and_issue_must_be_objects(self):
        for responses, context in (([[]], "repository"), ([{}, None], "issue")):
            with self.subTest(context=context), \
                    patch("bounty_scout.gh_api", side_effect=responses), \
                    patch("sys.argv", ["scout", "https://github.com/o/r/issues/1", "--json"]):
                self.assert_clean_failure(scout.main, context)

    def test_timeline_must_be_an_array(self):
        with patch("bounty_scout.gh_api", return_value={"message": "unexpected"}):
            self.assert_clean_failure(lambda: scout.linked_pull_requests("o", "r", 1),
                                      "timeline")

    def test_nested_timeline_containers_are_validated(self):
        for event, context in (("invalid", "timeline event"),
                               ({"source": []}, "timeline source"),
                               ({"source": {"issue": []}}, "source issue"),
                               ({"source": {"issue": {"pull_request": {"url": "api"},
                                                       "html_url": ["url"]}}},
                                "pull request URL")):
            with self.subTest(context=context), \
                    patch("bounty_scout.gh_api", return_value=[event]):
                self.assert_clean_failure(lambda: scout.linked_pull_requests("o", "r", 1),
                                          context)

    def test_report_labels_and_comments_are_validated_before_json_output(self):
        for fields, context in (({"labels": None}, "issue labels"),
                                ({"labels": ["invalid"]}, "issue label"),
                                ({"labels": [{}]}, "label name"),
                                ({"comments": None}, "issue comments")):
            with self.subTest(context=context), \
                    patch("bounty_scout.gh_api", side_effect=[{}, {"state": "open", **fields}, []]), \
                    patch("sys.argv", ["scout", "https://github.com/o/r/issues/1", "--json"]):
                self.assert_clean_failure(scout.main, context)

    def test_later_malformed_page_does_not_return_partial_findings(self):
        with patch("bounty_scout.gh_api", side_effect=[[{}] * 100, None]):
            self.assert_clean_failure(lambda: scout.linked_pull_requests("o", "r", 1),
                                      "timeline")
