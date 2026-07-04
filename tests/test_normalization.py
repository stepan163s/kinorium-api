import unittest
from kinorium.utils.request import Request

class TestNormalization(unittest.TestCase):
    def setUp(self):
        self.request = Request(None, api_salt="salt", base_url="url", user_agent="agent")

    def test_normalize_keys(self):
        d = {
            "book-uuid": "123",
            "listenerCount": 10,
            "type": "audiobook",
            "id": 9,
            "from": "user",
            "normal_field": "val"
        }
        normalized = self.request._normalize_keys(d)
        self.assertEqual(normalized["book_uuid"], "123")
        self.assertEqual(normalized["listener_count"], 10)
        self.assertEqual(normalized["type_"], "audiobook")
        self.assertEqual(normalized["id_"], 9)
        self.assertEqual(normalized["from_"], "user")
        self.assertEqual(normalized["normal_field"], "val")
