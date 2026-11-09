import unittest
from web.channel.clip_order import latest_clips


class LatestClipTests(unittest.IsolatedAsyncioTestCase):
    async def test_popularity_page_is_split_before_sorting(self):
        calls = []
        async def fetch(params):
            calls.append(params)
            if len(calls) == 1:
                return {'data': [], 'pagination': {'cursor': 'more'}}
            return {'data': [{'id': 'old', 'created_at': '2026-01-01'},
                             {'id': 'new', 'created_at': '2026-01-02'}]}
        result = await latest_clips(fetch, 'channel', 0, '')
        self.assertEqual([r['id'] for r in result['data']], ['new', 'old'])
        self.assertGreater(calls[1]['started_at'], calls[0]['started_at'])
        self.assertTrue(result['pagination']['cursor'])

    async def test_empty_history_terminates_at_range_boundary(self):
        async def fetch(params):
            return {'data': []}
        result = await latest_clips(fetch, 'channel', 7, '')
        self.assertEqual(result, {'data': [], 'pagination': {'cursor': ''}})

    async def test_invalid_cursor_is_rejected(self):
        async def fetch(params):
            self.fail('Invalid cursors must not reach Twitch')
        for cursor in ('invalid', '2099-01-01T00:00:00+00:00', '2026-01-01'):
            with self.assertRaises(ValueError):
                await latest_clips(fetch, 'channel', 0, cursor)
