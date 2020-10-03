
from contextlib import contextmanager
from datetime import datetime, timedelta
from math import ceil
from os import listdir
from pathlib import Path
import uuid

from sqlalchemy_pagination import paginate
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine, and_

from .constants import BaquetConstants
from .models.directory import (
    BASE as DIR_BASE,
    DirectorySQL,
    CacheSQL,
    TempJoinSQL as DirTempJoinSQL
)
from .helpers import(
    make_api,
    make_config,
    transform_user,
    serialize_entities,
    serialize_paginated_entities
)


def hydrate_user_identifiers(user_ids=None, screen_names=None):
    '''
    Input screen names and output a list of users.
    Beyond 1500 becomes slow due to Twitter rate limiting,
    be prepared to wait 15 minutes between each 1500.
    '''
    results = []
    user_identifiers = user_ids if user_ids else [
        s_n.lower() for s_n in screen_names
    ]

    if not user_ids:
        screen_names = user_identifiers  # Refresh for cache lookup

    if not user_identifiers:
        return results

    cache_results = _DIRECTORY.get_cache(
        user_ids=user_ids, screen_names=screen_names)
    cache_results = [serialize_entities(user) for user in cache_results]
    cache_results_ids = [user.user_id for user in cache_results]
    cache_results_screen_names = [
        user.screen_name.lower() for user in cache_results
    ]

    tweepy_results = []
    # Remove cached users from the users to look up.
    user_identifiers = [
        user_id for user_id in user_identifiers if (
            user_id not in cache_results_ids and user_id not in cache_results_screen_names
        )
    ]

    if user_identifiers:
        iterations = ceil(len(user_identifiers) / 100)
        for i in range(iterations):
            start = i * 100
            end = len(user_identifiers) if (i + 1) * \
                100 > len(user_identifiers) else (i + 1) * 100
            if user_ids:
                users = _API.lookup_users(user_ids=user_identifiers[start:end])
            else:
                users = _API.lookup_users(
                    screen_names=user_identifiers[start:end])

            for user in users:
                _DIRECTORY.add_cache(user)

            tweepy_results.extend(users)
        tweepy_results = [serialize_entities(transform_user(result, kind=BaquetConstants.USER))
                          for result in tweepy_results]

    results = cache_results + tweepy_results

    return results


class Directory:
    '''
    Maintain a list of all the users in the directory and maintain a global user cache.
    '''

    def __init__(self, cache_expiry=7776000):
        self._path = Path('./users/')
        self._conn = self._make_conn()
        self._expired_time = datetime.utcnow() - timedelta(seconds=cache_expiry)

    def _make_conn(self):
        database = self._path.joinpath(Path('./directory.db'))
        engine = create_engine(
            f'sqlite:///{database}', connect_args={"check_same_thread": False})
        session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=engine)

        session = scoped_session(
            session_factory
        )

        if not database.exists():
            database.parent.mkdir(parents=True, exist_ok=True)
            DIR_BASE.metadata.create_all(engine)

        return session

    @contextmanager
    def _session(self):
        session = self._conn()
        try:
            yield session
        except:
            session.rollback()
            raise
        finally:
            session.close()

    # DIRECTORY

    def _add_temp_join(self, join_data):
        join_id = uuid.uuid4().hex
        join = [DirTempJoinSQL(join_id=join_id, join_on=j) for j in join_data]

        with self._session() as session:
            session.bulk_save_objects(join)
            session.commit()

        return join_id

    def _remove_temp_join(self, join_id):
        with self._session() as session:
            session.query(DirTempJoinSQL).filter(
                DirTempJoinSQL.join_id == join_id
            ).delete(synchronize_session='fetch')
            session.commit()

    def add_directory(self, user):
        '''
        Add or update a user in the directory.
        '''
        user = transform_user(user, kind=BaquetConstants.DIRECTORY)
        with self._session() as session:
            session.merge(user)
            session.commit()

    def get_directory(self, page, page_size=20):
        '''
        Get users in the directory.
        '''
        with self._session() as session:
            return serialize_paginated_entities(
                paginate(
                    session.query(DirectorySQL).order_by(
                        DirectorySQL.screen_name
                    ),
                    page=page,
                    page_size=page_size
                )
            )

    def scan_and_update_directory(self):
        '''
        Find the difference between the folder contents and the user directory
        and update accordingly. Potential to be inefficient.
        '''
        users_in_path = set(
            [
                fn.split('.')[0] for fn in listdir(self._path) if fn.split('.')[0].isnumeric()
            ]
        )
        with self._session() as session:
            users_in_directory = set(
                [u.user_id for u in session.query(DirectorySQL).filter(
                    DirectorySQL.last_updated > self._expired_time
                ).all()])

            add = list(users_in_path - users_in_directory)
            if add:
                add = hydrate_user_identifiers(user_ids=add)
                add = [transform_user(u, kind=BaquetConstants.DIRECTORY)
                       for u in add]

            for user in add:
                session.merge(user)
            session.commit()

            delete = list(users_in_directory - users_in_path)
            with self._session() as session:
                for user in delete:
                    session.query(DirectorySQL).filter(
                        DirectorySQL.user_id == user).delete(synchronize_session='fetch')
                session.commit()

    # CACHE

    def add_cache(self, user):
        '''
        Add a user to the cache.
        '''
        with self._session() as session:
            session.merge(transform_user(user, kind=BaquetConstants.CACHE))
            session.commit()

    def get_cache(self, user_ids, screen_names):
        '''
        Get users in the cache.
        '''

        if user_ids:
            user_id_join = self._add_temp_join(user_ids)

            with self._session() as session:
                results = session.query(CacheSQL).join(
                    DirTempJoinSQL,
                    and_(
                        CacheSQL.user_id == DirTempJoinSQL.join_on,
                        DirTempJoinSQL.join_id == user_id_join
                    )
                ).all()

            self._remove_temp_join(user_id_join)
        else:
            screen_name_join = self._add_temp_join(screen_names)

            with self._session() as session:
                results = session.query(CacheSQL).join(
                    DirTempJoinSQL,
                    and_(
                        CacheSQL.screen_name == DirTempJoinSQL.join_on,
                        DirTempJoinSQL.join_id == screen_name_join
                    )
                ).all()

            self._remove_temp_join(screen_name_join)

        return results


# GLOBALS
_CONFIG = make_config()
_API = make_api(_CONFIG)
_DIRECTORY = Directory()
