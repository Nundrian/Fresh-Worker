"""Safety checks for server-supplied worker chat identifiers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "open-webui"))

from fresh_worker import Tools  # noqa: E402


class ChatIdTests(unittest.TestCase):
    def test_normal_open_webui_ids_are_accepted(self):
        for value in ("7a9e9c10-1fd0-4f12-93fa-abcd12345678", "chat_test-23"):
            with self.subTest(value=value):
                self.assertEqual(Tools._validate_chat_id(value), value)

    def test_unsafe_chat_identifiers_are_rejected_before_path_use(self):
        for value in ("", "../outside", "x/../../outside", "path\\other", "a?x=1", "a#fragment", "white space"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                Tools._validate_chat_id(value)


if __name__ == "__main__":
    unittest.main()
