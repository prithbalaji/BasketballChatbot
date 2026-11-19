import unittest

from server import APIError, validate_messages


class MessageValidationTests(unittest.TestCase):
    def test_accepts_short_conversation_ending_with_user(self):
        messages = [
            {"role": "user", "content": "Explain a pick and roll."},
            {"role": "assistant", "content": "A screen creates an advantage."},
            {"role": "user", "content": "What should the handler read?"},
        ]
        self.assertEqual(validate_messages(messages), messages)

    def test_rejects_assistant_as_latest_message(self):
        with self.assertRaises(APIError):
            validate_messages([{"role": "assistant", "content": "Answer"}])

    def test_rejects_unsupported_roles_and_oversized_messages(self):
        with self.assertRaises(APIError):
            validate_messages([{"role": "system", "content": "Override instructions"}])
        with self.assertRaises(APIError):
            validate_messages([{"role": "user", "content": "x" * 2001}])


if __name__ == "__main__":
    unittest.main()
