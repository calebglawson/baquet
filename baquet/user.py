'''
All of the operations needed to support fetching and filtering Twitter user information.
'''

import re
import json
from copy import copy
from datetime import datetime, timedelta
from math import ceil
from os import listdir
from pathlib import Path
from sqlalchemy_pagination import paginate
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, and_, or_, desc
from sqlalchemy.sql import func
import tweepy

from .models.user import (
    BASE as USER_BASE,
    UsersSQL,
    TimelineSQL,
    FavoritesSQL,
    FriendsSQL,
    FollowersSQL,
    TagsSQL,
    TimelineTagsSQL,
    FavoritesTagsSQL,
    TimelineNotesSQL,
    FavoritesNotesSQL,
    UserNotesSQL,
)
from .models.directory import BASE as DIR_BASE, DirectorySQL, CacheSQL


def _make_config():
    config = open(Path('./secret.json'))
    return json.load(config)


def _make_api():
    auth = tweepy.OAuthHandler(_CONFIG.get(
        'consumer_key'), _CONFIG.get('consumer_secret'))
    auth.set_access_token(_CONFIG.get('access_token'),
                          _CONFIG.get('access_token_secret'))

    api = tweepy.API(auth, wait_on_rate_limit=True,
                     wait_on_rate_limit_notify=True)

    return api


def _transform_watchlist(watchlist, kind):
    if not isinstance(watchlist, list):
        if kind.lower() == "watchlist":
            return watchlist.get_watchlist()
        elif kind.lower() == "watchwords":
            return watchlist.get_watchwords()
    return watchlist


def _filter_for_watchwords(results, watchwords):
    matches = []
    for result in results:
        for regex in watchwords:
            if re.search(regex, result.text):
                matches.append(result)
                break
    return matches


def _transform_user(user):
    return UsersSQL(
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
        user_id=user.id_str,
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


def _transform_tweet(tweet, is_favorite=False):
    is_retweet = hasattr(tweet, "retweeted_status")

    if is_favorite:
        return FavoritesSQL(
            created_at=tweet.created_at,
            entities=json.dumps(tweet.entities),
            favorite_count=tweet.favorite_count,
            tweet_id=tweet.id_str,
            is_quote_status=tweet.is_quote_status,
            lang=tweet.lang,
            possibly_sensitive=tweet.possibly_sensitive if hasattr(
                tweet, "possibly_sensitive") else False,
            retweet_count=tweet.retweet_count,
            source=tweet.source,
            source_url=tweet.source_url,
            text=tweet.full_text,
            user_id=tweet.author.id_str,
            screen_name=tweet.author.screen_name,
            name=tweet.author.name,
            last_updated=datetime.utcnow(),
        )

    return TimelineSQL(
        created_at=tweet.created_at,
        entities=json.dumps(tweet.entities),
        favorite_count=tweet.favorite_count,
        tweet_id=tweet.id_str,
        is_quote_status=tweet.is_quote_status,
        lang=tweet.lang,
        possibly_sensitive=tweet.possibly_sensitive if hasattr(
            tweet, "possibly_sensitive") else False,
        retweet_count=tweet.retweet_count,
        source=tweet.source,
        source_url=tweet.source_url,
        text=tweet.retweeted_status.full_text if is_retweet else tweet.full_text,
        retweet_user_id=tweet.retweeted_status.author.id_str if is_retweet else None,
        retweet_screen_name=tweet.retweeted_status.author.screen_name
        if is_retweet else None,
        retweet_name=tweet.retweeted_status.author.name if is_retweet else None,
        user_id=tweet.author.id_str,
        screen_name=tweet.author.screen_name,
        name=tweet.author.name,
        last_updated=datetime.utcnow(),
    )


def _serialize_entities(item):
    # Without copying, there's some SQLAlchemy weirdness.
    item = copy(item)
    if hasattr(item, "entities") and item.entities:
        item.entities = json.loads(item.entities)
    return item


def _serialize_paginated_entities(page):
    new_items = []
    for item in page.items:
        new_items.append(_serialize_entities(item))
    page.items = new_items
    return page


def hydrate_user_identifiers(user_ids=None, screen_names=None):
    '''
    Input screen names and output a list of users.
    Beyond 1500 becomes slow due to Twitter rate limiting,
    be prepared to wait 15 minutes between each 1500.
    '''
    results = []
    user_identifiers = user_ids if user_ids else [
        s_n.lower() for s_n in screen_names]
    if not user_identifiers:
        return results

    cache_results = _DIRECTORY.get_cache(user_identifiers)
    cache_results = [_serialize_entities(user) for user in cache_results]
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
        tweepy_results = [_serialize_entities(_transform_user(result))
                          for result in tweepy_results]

    results = cache_results + tweepy_results

    return results


class User:
    '''
    With a user object, you can read, filter, and store Twitter data.
    '''

    def __init__(self, user_id, limit=100, cache_expiry=86400):
        self._user_id = user_id
        self._limit = limit
        self._cache_expiry = cache_expiry
        self._conn = self._make_conn()

    def _make_conn(self):
        database = Path(f'./users/{self._user_id}.db')
        engine = create_engine(
            f'sqlite:///{database}', connect_args={"check_same_thread": False})
        session = sessionmaker(
            autocommit=False, autoflush=False, bind=engine)()

        if not database.exists():
            database.parent.mkdir(parents=True, exist_ok=True)
            USER_BASE.metadata.create_all(engine)

        return session

    def _cache_expired(self, table):
        last_updated = self._conn.query(func.max(table.last_updated)).scalar()
        elapsed = datetime.utcnow() - last_updated if last_updated else None

        return not elapsed or elapsed.seconds > self._cache_expiry

    def get_user_id(self):
        '''
        Get the user id.
        '''
        return self._user_id

    def _fetch_user(self):
        user = _API.get_user(user_id=self._user_id)

        if user:
            _DIRECTORY.add_directory(user)
            user_sql = _transform_user(user)
            self._conn.merge(user_sql)
            self._conn.commit()

    def get_user(self):
        '''
        Get the user as an ORM object.
        If cache is expired, fetch first.
        '''
        if self._cache_expired(UsersSQL):
            self._fetch_user()

        return _serialize_entities(
            self._conn.query(UsersSQL).filter(
                UsersSQL.user_id == self._user_id).first()
        )

    def get_notes(self, page, page_size=20):
        '''
        Get user notes.
        '''
        return paginate(
            self._conn.query(UserNotesSQL).order_by(
                desc(UserNotesSQL.created_at)),
            page=page,
            page_size=page_size
        )

    def add_note(self, note):
        '''
        Add a note to the user.
        '''
        note = UserNotesSQL(text=note, created_at=datetime.utcnow())
        self._conn.add(note)
        self._conn.commit()

    def remove_note(self, note_id):
        '''
        Remove note from user.
        '''
        note = self._conn.query(UserNotesSQL).filter(
            UserNotesSQL.note_id == note_id).first()

        if note:
            self._conn.delete(note)
            self._conn.commit()

    def _fetch_timeline(self):
        for tweet in tweepy.Cursor(
                _API.user_timeline, id=self._user_id, tweet_mode="extended").items(self._limit):
            self._conn.merge(_transform_tweet(tweet))

        self._conn.commit()

    def get_timeline(self, page, page_size=20, watchlist=None, watchwords=None):
        '''
            Get Tweets and Retweets from a user's timeline.
            If the cache is expired,
        '''
        if self._cache_expired(TimelineSQL):
            self._fetch_timeline()

        if watchlist:
            watchlist = _transform_watchlist(watchlist, "watchlist")
            # When filtering, we are not interested in Tweets authored by the user.
            if self._user_id in watchlist:
                watchlist.remove(self._user_id)
            results = paginate(self._conn.query(TimelineSQL).filter(or_(
                TimelineSQL.retweet_user_id.in_(watchlist),
                TimelineSQL.user_id.in_(watchlist)
            )).order_by(desc(TimelineSQL.created_at)), page=page, page_size=page_size)
        else:
            results = paginate(self._conn.query(TimelineSQL).order_by(desc(TimelineSQL.created_at)),
                               page=page, page_size=page_size)

        if watchwords:
            watchwords = _transform_watchlist(watchwords, "watchwords")
            results.items = _filter_for_watchwords(results.items, watchwords)

        return _serialize_paginated_entities(results)

    def _get_tag_id(self, text):
        text = text.strip()
        tag = self._conn.query(TagsSQL).filter(TagsSQL.text == text).first()

        if not tag:
            tag = TagsSQL(text=text)
            self._conn.add(tag)
            self._conn.commit()

        return tag.tag_id

    def get_tags_timeline(self, tweet_id):
        '''
        Get the tags on a timeline tweet.
        '''
        results = self._conn.query(TimelineTagsSQL).filter(
            TimelineTagsSQL.tweet_id == tweet_id).all()
        return [result.tag for result in results]

    def get_timelines_tag(self, tag_id, page, page_size=20):
        '''
        Get the tweets matching a particular tag.
        '''
        return paginate(
            self._conn.query(TimelineSQL).join(
                TimelineTagsSQL,
                TimelineSQL.tweet_id == TimelineTagsSQL.tweet_id
            ).filter(
                TimelineTagsSQL.tag_id == tag_id
            ).order_by(desc(TimelineSQL.created_at)),
            page=page,
            page_size=page_size
        )

    def tag_timeline(self, tweet_id, tag_text):
        '''
        Applies a tag to a given tweet.
        '''
        tag_id = self._get_tag_id(tag_text)

        timeline_tag = TimelineTagsSQL(tag_id=tag_id, tweet_id=tweet_id)
        self._conn.merge(timeline_tag)
        self._conn.commit()

    def untag_timeline(self, tweet_id, tag_id):
        '''
        Delete a tag from a tweet.
        '''
        tag_id = self._conn.query(TimelineTagsSQL).filter(
            TimelineTagsSQL.tag_id == tag_id and TimelineTagsSQL.tweet_id == tweet_id).first()
        self._conn.delete(tag_id)
        self._conn.commit()

    def get_notes_timeline(self, tweet_id):
        '''
        Get notes from a tweet.
        '''
        return self._conn.query(
            TimelineNotesSQL
        ).filter(TimelineNotesSQL.tweet_id == tweet_id).all()

    def add_note_timeline(self, tweet_id, text):
        '''
        Add a note to a tweet.
        '''
        note = TimelineNotesSQL(
            tweet_id=tweet_id, text=text, created_at=datetime.utcnow())
        self._conn.add(note)
        self._conn.commit()

    def remove_note_timeline(self, tweet_id, note_id):
        '''
        Remove note from a tweet.
        '''
        note = self._conn.query(TimelineNotesSQL).filter(
            TimelineNotesSQL.tweet_id == tweet_id and TimelineNotesSQL.note_id == note_id).first()
        self._conn.delete(note)
        self._conn.commit()

    def get_retweet_watchlist_percent(self, watchlist):
        '''
        Get percentage of retweets that are from folks on the watchlist.
        '''
        if self._cache_expired(TimelineSQL):
            self._fetch_timeline()

        watchlist = _transform_watchlist(watchlist, "watchlist")
        retweets_on_watchlist = self._conn.query(TimelineSQL).filter(
            TimelineSQL.retweet_user_id.in_(watchlist)).count()
        retweets = self._conn.query(
            TimelineSQL).filter(TimelineSQL.retweet_user_id is not None).count()

        return retweets_on_watchlist / retweets if retweets != 0 else 0

    def _fetch_favorites(self):
        for favorite in tweepy.Cursor(
                _API.favorites, id=self._user_id, tweet_mode="extended").items(self._limit):
            self._conn.merge(_transform_tweet(favorite, is_favorite=True))

        self._conn.commit()

    def get_favorites(self, page, page_size=20, watchlist=None, watchwords=None):
        '''
        Get the posts a user has liked.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FavoritesSQL):
            self._fetch_favorites()

        if watchlist:
            watchlist = _transform_watchlist(watchlist, "watchlist")
            results = paginate(self._conn.query(FavoritesSQL).filter(FavoritesSQL.user_id.in_(
                watchlist)).order_by(desc(FavoritesSQL.created_at)), page=page, page_size=page_size)
        else:
            results = paginate(self._conn.query(FavoritesSQL).order_by(
                desc(FavoritesSQL.created_at)), page=page, page_size=page_size)

        if watchwords:
            watchwords = _transform_watchlist(watchwords, "watchwords")
            results.items = _filter_for_watchwords(results.items, watchwords)

        return _serialize_paginated_entities(results)

    def get_tags_favorite(self, tweet_id):
        '''
        Get the tags on a favorited tweet.
        '''
        results = self._conn.query(FavoritesTagsSQL).filter(
            FavoritesTagsSQL.tweet_id == tweet_id).all()
        return [result.tag for result in results]

    def get_favorites_tag(self, tag_id, page, page_size=20):
        '''
        Get the tweets matching a particular tag.
        '''
        return paginate(
            self._conn.query(FavoritesSQL).join(
                FavoritesTagsSQL, FavoritesSQL.tweet_id == FavoritesTagsSQL.tweet_id
            ).filter(
                FavoritesTagsSQL.tag_id == tag_id
            ).order_by(desc(FavoritesSQL.created_at)),
            page=page,
            page_size=page_size
        )

    def tag_favorite(self, tweet_id, tag):
        '''
        Applies a tag to a given tweet.
        '''
        tag_id = self._get_tag_id(tag)

        favorite_tag = FavoritesTagsSQL(tag_id=tag_id, tweet_id=tweet_id)
        self._conn.merge(favorite_tag)
        self._conn.commit()

    def untag_favorite(self, tweet_id, tag_id):
        '''
        Delete a tag from a tweet.
        '''
        tag_id = self._conn.query(FavoritesTagsSQL).filter(
            FavoritesTagsSQL.tag_id == tag_id and FavoritesSQL.tweet_id == tweet_id).first()
        self._conn.delete(tag_id)
        self._conn.commit()

    def get_notes_favorite(self, tweet_id):
        '''
        Get notes from a tweet.
        '''
        return self._conn.query(
            FavoritesNotesSQL
        ).filter(FavoritesNotesSQL.tweet_id == tweet_id).all()

    def add_note_favorite(self, tweet_id, text):
        '''
        Add a note to a tweet.
        '''
        note = FavoritesNotesSQL(
            tweet_id=tweet_id, text=text, created_at=datetime.utcnow())
        self._conn.add(note)
        self._conn.commit()

    def remove_note_favorite(self, tweet_id, note_id):
        '''
        Remove note from a tweet.
        '''
        note = self._conn.query(FavoritesNotesSQL).filter(
            FavoritesNotesSQL.tweet_id == tweet_id and FavoritesNotesSQL.note_id == note_id).first()
        self._conn.delete(note)
        self._conn.commit()

    def get_favorite_watchlist_percent(self, watchlist):
        '''
        Get percentage of likes that are from folks on the watchlist.
        '''
        if self._cache_expired(FavoritesSQL):
            self._fetch_favorites()

        watchlist = _transform_watchlist(watchlist, "watchlist")
        favorites_on_watchlist = self._conn.query(FavoritesSQL).filter(
            FavoritesSQL.user_id.in_(watchlist)).count()
        favorites = self._conn.query(FavoritesSQL).count()

        return favorites_on_watchlist / favorites if favorites != 0 else 0

    def get_friends(self, page, page_size=10000, watchlist=None):
        '''
        Get the users this user is following.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FriendsSQL):
            self._fetch_friends()

        if watchlist:
            watchlist = _transform_watchlist(watchlist, "watchlist")
            results = paginate(
                self._conn.query(FriendsSQL).filter(
                    FriendsSQL.user_id.in_(watchlist)),
                page=page,
                page_size=page_size
            )
            if results.items:
                hydrated_results = hydrate_user_identifiers(
                    user_ids=[result.user_id for result in results.items])
            else:
                hydrated_results = []

            new_items = []
            for item in results.items:
                for result in hydrated_results:
                    if item.user_id == result.user_id:
                        setattr(item, "user", result)
                        new_items.append(item)
            results.items = new_items

            return results

        return paginate(self._conn.query(FriendsSQL), page=page, page_size=page_size)

    def get_friends_watchlist_percent(self, watchlist):
        '''
        Get percentage of friends that are on the watchlist.
        '''
        if self._cache_expired(FriendsSQL):
            self._fetch_friends()

        watchlist = _transform_watchlist(watchlist, "watchlist")
        friends_on_watchlist = self._conn.query(FriendsSQL).filter(
            FriendsSQL.user_id.in_(watchlist)).count()
        friends = self._conn.query(FriendsSQL).count()

        return friends_on_watchlist / friends if friends != 0 else 0

    def get_friends_watchlist_completion(self, watchlist):
        '''
        Get percentage completion of watchlist,
        based on friends on the watchlist.
        '''
        if self._cache_expired(FriendsSQL):
            self._fetch_friends()

        watchlist = _transform_watchlist(watchlist, "watchlist")
        friends_on_watchlist = self._conn.query(FriendsSQL).filter(
            FriendsSQL.user_id.in_(watchlist)).count()

        return (friends_on_watchlist / len(watchlist)
                if watchlist else 0)

    def _fetch_friends(self):
        # Delete to prevent stale entries.
        self._conn.query(FriendsSQL).delete()

        friends = []
        for friend_id in tweepy.Cursor(_API.friends_ids, id=self._user_id).items():
            self._conn.merge(FriendsSQL(
                user_id=friend_id, last_updated=datetime.utcnow()))

        self._conn.bulk_save_objects(friends)
        self._conn.commit()

    def get_followers(self, page, page_size=10000, watchlist=None):
        '''
        Get the users followed by this user.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FollowersSQL):
            self._fetch_followers()

        if watchlist:
            watchlist = _transform_watchlist(watchlist, "watchlist")
            results = paginate(self._conn.query(FollowersSQL).filter(
                FollowersSQL.user_id.in_(watchlist)
            ), page=page, page_size=page_size)

            if results.items:
                hydrated_results = hydrate_user_identifiers(
                    user_ids=[result.user_id for result in results.items])
            else:
                hydrated_results = []

            new_items = []
            for item in results.items:
                for result in hydrated_results:
                    if item.user_id == result.user_id:
                        setattr(item, "user", result)
                        new_items.append(item)
            results.items = new_items

            return results

        return paginate(self._conn.query(FollowersSQL), page=page, page_size=page_size)

    def get_followers_watchlist_percent(self, watchlist):
        '''
        Get percentage of followers that are on the watchlist.
        '''
        if self._cache_expired(FollowersSQL):
            self._fetch_followers()

        watchlist = _transform_watchlist(watchlist, "watchlist")
        followers_on_watchlist = self._conn.query(FollowersSQL).filter(
            FollowersSQL.user_id.in_(watchlist)).count()
        followers = self._conn.query(FollowersSQL).count()

        return followers_on_watchlist / followers if followers != 0 else 0

    def get_followers_watchlist_completion(self, watchlist):
        '''
        Get percentage completion of watchlist,
        based on followers on the watchlist.
        '''
        if self._cache_expired(FollowersSQL):
            self._fetch_followers()

        watchlist = _transform_watchlist(watchlist, "watchlist")
        followers_on_watchlist = self._conn.query(FollowersSQL).filter(
            FollowersSQL.user_id.in_(watchlist)).count()

        return (followers_on_watchlist / len(watchlist)
                if watchlist else 0)

    def _fetch_followers(self):
        # Delete to prevent stale entries.
        self._conn.query(FollowersSQL).delete()

        followers = []
        for follower_id in tweepy.Cursor(_API.followers_ids, id=self._user_id).items():
            followers.append(FollowersSQL(user_id=follower_id,
                                          last_updated=datetime.utcnow()))

        self._conn.bulk_save_objects(followers)
        self._conn.commit()


def _transform_directory(user):
    return DirectorySQL(
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
        user_id=user.id_str,
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


def _transform_cache(user):
    return CacheSQL(
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
        user_id=user.id_str,
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
        session = sessionmaker(
            autocommit=False, autoflush=False, bind=engine)()

        if not database.exists():
            database.parent.mkdir(parents=True, exist_ok=True)
            DIR_BASE.metadata.create_all(engine)

        return session

    def add_directory(self, user):
        '''
        Add or update a user in the directory.
        '''
        user = _transform_directory(user)
        self._conn.merge(user)
        self._conn.commit()

    def scan_and_update_directory(self):
        '''
        Find the difference between the folder contents and the user directory
        and update accordingly. Potential to be inefficient.
        '''
        users_in_path = set([int(fn.split('.')[0])
                             for fn in listdir(self._path) if fn.split('.')[0].isnumeric()])
        users_in_directory = set(
            [u.user_id for u in self._conn.query(DirectorySQL).filter(
                DirectorySQL.last_updated > self._expired_time
            ).all()])

        add = list(users_in_path - users_in_directory)
        add = hydrate_user_identifiers(user_ids=add)
        add = [_transform_directory(u) for u in add]

        for user in add:
            self._conn.merge(user)
        self._conn.commit()

        delete = list(users_in_directory - users_in_path)
        if delete:
            self._conn.query(DirectorySQL).filter(
                DirectorySQL.user_id.in_(delete)).delete(synchronize_session=False)

        self._conn.commit()

    def get_directory(self, page, page_size=20):
        '''
        Get users in the directory.
        '''
        return _serialize_paginated_entities(
            paginate(
                self._conn.query(DirectorySQL).order_by(
                    DirectorySQL.screen_name),
                page=page,
                page_size=page_size
            )
        )

    def add_cache(self, user):
        '''
        Add a user to the cache.
        '''
        self._conn.merge(_transform_cache(user))
        self._conn.commit()

    def get_cache(self, user_identifiers):
        '''
        Get users in the cache.
        '''
        return self._conn.query(CacheSQL).filter(
            and_(
                or_(
                    CacheSQL.user_id.in_(user_identifiers),
                    func.lower(CacheSQL.screen_name).in_(user_identifiers)
                ),
                (CacheSQL.last_updated > self._expired_time)
            )
        )


# GLOBAL - All User instances share one.
_CONFIG = _make_config()
_API = _make_api()
_DIRECTORY = Directory()
