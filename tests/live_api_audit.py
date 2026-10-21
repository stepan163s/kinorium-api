"""Opt-in integration audit. Ordinary unittest discovery never runs live writes.

Use KINORIUM_EMAIL / KINORIUM_PASSWORD, or --credentials-file get_session.local.json.
Credentials and cookies are never included in the report.
"""
import argparse
import asyncio
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kinorium import (InvalidOptionError, KinoriumClient,
                      KinoriumClientAsync, Movie, NetworkError, User, UserList)
from get_session import load_credentials


async def call(fn, *args, **kwargs):
    value = fn(*args, **kwargs)
    return await value if inspect.isawaitable(value) else value


def checked(movie):
    user = movie['data']['user']
    return {key: user.get(key) for key in
            ('status', 'rating', 'vote', 'note', 'make_date', 'status_list')}


def counts(response):
    return {x['ulist_id']: {k: v for k, v in x.items()
                           if k == 'cnt' or k.startswith('cnt_')}
            for x in response['data']['ulist']}


class Audit:
    def __init__(self, options, email, password):
        self.options, self.email, self.password = options, email, password
        self.results, self.baselines = [], {}

    def save(self):
        if self.options.report:
            self.options.report.write_text(json.dumps({
                'results': self.results, 'baselines': self.baselines,
            }, ensure_ascii=False, indent=2))

    def check(self, client, operation, ok, **detail):
        row = dict(client=client, operation=operation, ok=bool(ok), **detail)
        self.results.append(row)
        self.save()
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if not ok:
            raise AssertionError(operation)

    async def run_client(self, cls, name):
        c = cls()
        movie_id = self.options.movie_id
        key = '_' + str(movie_id)
        baseline, changed = None, False
        try:
            await call(c.authenticate, self.email, self.password)
            profile = await call(c.get_user_info)
            user = User.de_json(profile, c)
            self.check(name, 'authenticate/cookies/profile',
                       c.auth_cookie and c.phpsessid_cookie and user.id_ > 0)
            explicit = User.de_json(await call(c.get_user_info, user.id_))
            self.check(name, 'explicit_user_id', explicit.id_ == user.id_)
            movie = await call(c.get_movie, movie_id)
            baseline = checked(movie)
            film = Movie.de_json(movie, c)
            self.check(name, 'movie_model', film.title and film.genres and isinstance(film.year, int))
            lists = await call(user.get_lists)
            baseline_counts = counts(lists)
            self.check(name, 'user_active_method', counts(await call(c.get_user_lists)) == baseline_counts)
            models = UserList.de_list(lists['data']['ulist'], c)
            original_ids = {}
            for model in models:
                data = (await call(model.get_objects))['data']
                original_ids[model.ulist_id] = [x['id_'] for x in data.get('list_', [])]
                direct = (await call(c.get_user_list_objects, model.ulist_id))['data']
                self.check(name, 'list:' + model.special,
                           [x['id_'] for x in direct.get('list_', [])] == original_ids[model.ulist_id])
            self.check(name, 'websocket_signature',
                       c.sign_websocket('1437056') == 'aeee25a24d3d2ebb4128fcddda0dc956')
            self.baselines[name] = dict(movie_id=movie_id, checked=baseline,
                                        counts=baseline_counts, ids=original_ids)
            self.save()
            if not self.options.allow_write:
                return
            # A blank movie can be restored without rewriting old dates/ratings.
            if key in (baseline['status_list'] or {}) or baseline['note']:
                raise ValueError('Choose a movie without an existing status or note')

            for status in ('future', 'done', 'never'):
                changed = True
                await call(c.set_movie_status, movie_id, status)
                state = checked(await call(c.get_movie, movie_id))['status_list'][key]
                self.check(name, 'set_status:' + status, state.get('status') == status)
                await call(c.remove_movie_status, movie_id)
                self.check(name, 'remove_status:' + status,
                           checked(await call(c.get_movie, movie_id)) == baseline)
                changed = False
            changed = True
            try:
                await call(c.set_movie_status, movie_id, 'now')
            except InvalidOptionError:
                self.check(name, 'reject_unsupported_status', True)
            else:
                self.check(name, 'reject_unsupported_status', False)
            changed = False

            changed = True
            for status in ('future', 'done', 'never', 'future'):
                await call(c.set_movie_status, movie_id, status)
                state = checked(await call(c.get_movie, movie_id))['status_list'][key]
                self.check(name, 'transition_to:' + status, state.get('status') == status)
            await call(c.remove_movie_status, movie_id)
            self.check(name, 'restore_after_transitions', checked(await call(c.get_movie, movie_id)) == baseline)
            changed = False

            changed = True
            for rating in (1, 10):
                await call(c.request, 'POST', 'setMovieStatus', data={
                    'movie_id': movie_id, 'status': 'done', 'rating': rating,
                })
                state = checked(await call(c.get_movie, movie_id))['status_list'][key]
                self.check(name, 'set_rating:' + str(rating),
                           state.get('status') == 'done' and str(state.get('rating')) == str(rating))
            for repetition in (1, 2):
                await call(c.request, 'DELETE', 'removeMovieStatus', params={
                    'movie_id': movie_id, 'type': 'rating',
                })
                state = checked(await call(c.get_movie, movie_id))['status_list'][key]
                self.check(name, 'remove_rating:' + str(repetition),
                           not state.get('rating') and state.get('status') == 'done')
            await call(c.remove_movie_status, movie_id)
            self.check(name, 'restore_after_rating', checked(await call(c.get_movie, movie_id)) == baseline)
            changed = False

            for path in ('data', 'params'):
                changed = True
                await call(c.request, 'POST', 'setMovieStatus', **{
                    path: {'movie_id': movie_id, 'status': 'future'},
                })
                state = checked(await call(c.get_movie, movie_id))['status_list'][key]
                self.check(name, 'raw_POST:' + path, state.get('status') == 'future')
                watchlist = next(x for x in models if x.special == 'future')
                expected = set(original_ids[watchlist.ulist_id]) | {movie_id}
                actual = set()
                for page in range(1, len(expected) + 1):
                    data = (await call(watchlist.get_objects, page=page, perpage=1))['data']
                    films = Movie.de_list(data['list_'], c)
                    self.check(name, 'pagination:' + path + ':' + str(page),
                               len(films) == 1 and films[0].title and films[0].genres)
                    actual.update(x.id_ for x in films)
                self.check(name, 'all_pagination_ids:' + path, actual == expected)
                await call(c.request, 'DELETE', 'removeMovieStatus', **{path: {'movie_id': movie_id}})
                self.check(name, 'raw_DELETE:' + path,
                           checked(await call(c.get_movie, movie_id)) == baseline)
                await call(c.remove_movie_status, movie_id)
                self.check(name, 'repeat_delete:' + path,
                           checked(await call(c.get_movie, movie_id)) == baseline)
                changed = False

            try:
                await call(c.request, 'DELETE', 'getMovie', params={'movie_id': movie_id})
            except NetworkError as exc:
                self.check(name, 'real_HTTP_DELETE_405', '405' in str(exc))
            else:
                self.check(name, 'real_HTTP_DELETE_405', False)
            self.check(name, 'final_movie_state', checked(await call(c.get_movie, movie_id)) == baseline)
            self.check(name, 'final_all_list_counts', counts(await call(c.get_user_lists)) == baseline_counts)
            for model in models:
                data = (await call(model.get_objects))['data']
                self.check(name, 'final_list:' + model.special,
                           [x['id_'] for x in data.get('list_', [])] == original_ids[model.ulist_id])
        finally:
            try:
                if changed:
                    await call(c.request, 'POST', 'removeMovieStatus', data={'movie_id': movie_id, 'type': 'rating'})
                    await call(c.remove_movie_status, movie_id)
                    self.check(name, 'emergency_cleanup', checked(await call(c.get_movie, movie_id)) == baseline)
            finally:
                if name == 'async':
                    await c.close()
                    await c.close()
                else:
                    c._request._session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-file', type=Path)
    parser.add_argument('--movie-id', type=int, default=447299)
    parser.add_argument('--allow-write', action='store_true')
    parser.add_argument('--report', type=Path)
    options = parser.parse_args()
    email, password = load_credentials(options.credentials_file)
    if not email or not password:
        parser.error('Provide login credentials via environment or --credentials-file')
    audit = Audit(options, email, password)

    async def run():
        await audit.run_client(KinoriumClient, 'sync')
        await audit.run_client(KinoriumClientAsync, 'async')
    asyncio.run(run())
    print(json.dumps({'checks': len(audit.results), 'ok': all(r['ok'] for r in audit.results)}))


if __name__ == '__main__':
    main()
