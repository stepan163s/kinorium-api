import unittest
from unittest.mock import AsyncMock, MagicMock
from kinorium import KinoriumClientAsync


class TestKinoriumClientAsync(unittest.IsolatedAsyncioTestCase):
    async def test_async_client_requests(self):
        mock_transport = MagicMock()
        mock_transport.get = AsyncMock(return_value={"result_code": 0, "data": {"user_id": 1437056}})
        
        client = KinoriumClientAsync(_request_instance=mock_transport)
        res = await client.get_user_info(user_id=1437056)
        
        mock_transport.get.assert_awaited_once_with("getUserInfo", params={"user_id": 1437056})
        self.assertEqual(res["data"]["user_id"], 1437056)
