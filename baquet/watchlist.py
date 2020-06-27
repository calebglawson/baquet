'''
From this module, we control data in the watchlist.
The watchlist houses a list of users and words of interest.
'''

import json
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, or_

from .models.watchlist import BASE, WatchlistSQL, WatchwordsSQL
from .user import hydrate_user_identifiers


def _transform_user(user):
    return WatchlistSQL(
        contributors_enabled=user.contributors_enabled,
        created_at=user.created_at,
        default_profile=user.default_profile,
        default_profile_image=user.default_profile_image,
        description=user.description,
        entities=json.dumps(user.entities),
        favorites_count=user.favourites_count,
        followers_count=user.followers_count,
        friends_count=user.friends_count,
        geo_enabled=user.geo_enabled,
        has_extended_profile=user.has_extended_profile,
        user_id=user.id,
        is_translation_enabled=user.is_translation_enabled,
        is_translator=user.is_translator,
        lang=user.lang,
        listed_count=user.listed_count,
        location=user.location,
        name=user.name,
        needs_phone_verification=user.needs_phone_verification if hasattr(
            user, "needs_phone_verification") else None,
        profile_banner_url=user.profile_banner_url if hasattr(
            user, "profile_banner_url") else None,
        profile_image_url=user.profile_image_url,
        protected=user.protected,
        screen_name=user.screen_name,
        statuses_count=user.statuses_count,
        suspended=user.suspended if hasattr(
            user, "suspended") else None,
        url=user.url,
        verified=user.verified,
        last_updated=datetime.utcnow(),
    )


class Watchlist:
    '''
    From this class, we control data in the watchlist and watchwords.
    '''

    def __init__(self, name, cache_expiry=604800):
        self._name = name
        self._cache_expiry = cache_expiry
        self._conn = self._make_conn()

    def _make_conn(self):
        database = Path(f'./watchlists/{self._name}.db')
        engine = create_engine(
            f'sqlite:///{database}', connect_args={"check_same_thread": False})
        session = sessionmaker(
            autocommit=False, autoflush=False, bind=engine)()

        if not database.exists():
            database.parent.mkdir(parents=True, exist_ok=True)
            BASE.metadata.create_all(engine)

        return session

    def add_watchlist(self, users):
        '''
        Add one or more users to the watchlist.
        '''

        if not isinstance(users, list):
            users = [users]

        for i, user in enumerate(users):
            if not isinstance(user, int):
                users[i] = user.get_user_id()

            users[i] = WatchlistSQL(user_id=users[i])
            self._conn.merge(users[i])

        self._conn.commit()

    def remove_watchlist(self, user):
        '''
        Remove a user from the watchlist.
        '''
        user = self._conn.query(WatchlistSQL).filter(
            WatchlistSQL.user_id == user.get_user_id()).first()
        self._conn.delete(user)
        self._conn.commit()

    def get_watchlist(self):
        '''
        Get the watchlist as a list.
        '''
        return [user.user_id for user in self._conn.query(WatchlistSQL).all()]

    def get_watchlist_count(self):
        '''
        Get the count of users on the watchlist.
        '''

        return self._conn.query(WatchlistSQL).count()

    def add_watchword(self, regex):
        '''
        Add a search term to the watchwords.
        '''
        regex = WatchwordsSQL(regex=regex)
        self._conn.merge(regex)
        self._conn.commit()

    def remove_watchword(self, regex):
        '''
        Remove a search term from the watchwords.
        '''
        regex = self._conn.query(WatchwordsSQL).filter(
            WatchwordsSQL.regex == regex).first()
        self._conn.delete(regex)
        self._conn.commit()

    def get_watchwords(self):
        '''
        Get the watchwords as a list.
        '''
        return [regex.regex for regex in self._conn.query(WatchwordsSQL).all()]

    def get_watchwords_count(self):
        '''
        Get the count of users on the watchwords.
        '''

        return self._conn.query(WatchwordsSQL).count()

    def refresh_watchlist_user_data(self):
        '''
        Populate user data if missing or expired.
        '''
        last_updated_expiry = datetime.utcnow() - timedelta(seconds=self._cache_expiry)

        refresh = [u.user_id for u in self._conn.query(
            WatchlistSQL).filter(
                or_(
                    WatchlistSQL.last_updated < last_updated_expiry,
                    WatchlistSQL.screen_name.is_(None)
                )).all()]
        refresh = hydrate_user_identifiers(user_ids=refresh)

        for user in refresh:
            self._conn.merge(_transform_user(user))

        self._conn.commit()
