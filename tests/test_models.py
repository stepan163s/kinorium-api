import unittest
from unittest.mock import MagicMock
from kinorium.models import User, Movie, UserList


class TestModels(unittest.TestCase):
    def test_deserialization_and_cleanup(self):
        # API response normalized (snake_case, underscores on reserved words)
        data = {
            "id_": 1437056,
            "name": "Stepan",
            "avatar": "http://avatar.url",
            "unknown_api_field": "ignore_me"
        }
        user = User.de_json(data)
        self.assertIsNotNone(user)
        self.assertEqual(user.id_, 1437056)
        self.assertEqual(user.name, "Stepan")
        self.assertEqual(user.avatar, "http://avatar.url")
        # Ensure unknown_api_field is filtered out
        self.assertFalse(hasattr(user, "unknown_api_field"))

    def test_deserialization_list(self):
        data = [
            {"id_": 1, "title": "Movie 1", "year": 2020},
            {"id_": 2, "title": "Movie 2", "year": 2021}
        ]
        movies = Movie.de_list(data)
        self.assertEqual(len(movies), 2)
        self.assertEqual(movies[0].id_, 1)
        self.assertEqual(movies[0].title, "Movie 1")
        self.assertEqual(movies[1].id_, 2)
        self.assertEqual(movies[1].title, "Movie 2")

    def test_serialization_camelcase(self):
        # We start with python dataclass model
        # Note: 'id_' field is reserved, so it should serialize back to 'id'
        user = User(id_=999, name="Test User", avatar="avatar_path")
        
        # Standard dict conversion
        d_normal = user.to_dict(for_request=False)
        self.assertEqual(d_normal["id_"], 999)
        self.assertEqual(d_normal["name"], "Test User")
        
        # For request serialization (camelCase, trailing underscores removed)
        d_req = user.to_dict(for_request=True)
        self.assertEqual(d_req["id"], 999)
        self.assertEqual(d_req["name"], "Test User")
        self.assertEqual(d_req["avatar"], "avatar_path")

    def test_comparison_and_hash(self):
        m1 = Movie(id_=10, title="Inception", year=2010)
        m2 = Movie(id_=10, title="Inception Different Title", year=2020)
        m3 = Movie(id_=11, title="Inception", year=2010)
        
        # Equal based on _id_attrs ("id_")
        self.assertEqual(m1, m2)
        self.assertNotEqual(m1, m3)
        
        # Hashing based on id_
        self.assertEqual(hash(m1), hash(m2))
        self.assertNotEqual(hash(m1), hash(m3))

    def test_active_methods(self):
        client = MagicMock()
        user = User(id_=1437056, name="Stepan")
        user.client = client
        
        user.get_lists()
        client.get_user_lists.assert_called_once_with(user_id=1437056)

        ulist = UserList(ulist_id=16975670, title="Буду смотреть")
        ulist.client = client
        ulist.get_objects(page=2, perpage=100)
        client.get_user_list_objects.assert_called_once_with(ulist_id=16975670, page=2, perpage=100)
