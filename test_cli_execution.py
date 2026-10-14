import contextlib
import io
import unittest
from unittest.mock import patch

import bounty_scout as scout


class CliExecutionTests(unittest.TestCase):
    def test_execution_errors_exit_cleanly_without_polluting_stdout(self):
        for error in (PermissionError("Permission denied"),
                      OSError("Exec format error")):
            with self.subTest(error=type(error).__name__):
                output, errors = io.StringIO(), io.StringIO()
                with patch("bounty_scout.subprocess.run", side_effect=error), \
                        contextlib.redirect_stdout(output), \
                        contextlib.redirect_stderr(errors):
                    with self.assertRaises(SystemExit) as result:
                        scout.gh_api("repos/o/r")
                self.assertEqual(result.exception.code, 1)
                self.assertEqual(output.getvalue(), "")
                self.assertIn("Could not run GitHub CLI", errors.getvalue())
                self.assertIn(str(error), errors.getvalue())
                self.assertNotIn("Traceback", errors.getvalue())
