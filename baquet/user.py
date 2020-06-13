'''
All of the operations needed to support fetching and filtering Twitter user information.
'''

import re
import json
from datetime import datetime
from math import ceil
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, or_
from sqlalchemy.sql import func
import tweepy

from .models.user import BASE, UsersSQL, TimelineSQL, FavoritesSQL, FriendsSQL, FollowersSQL


def _make_config():
    config = open(Path('./config.json'))
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


def _transform_tweet(tweet, is_favorite=False):
    is_retweet = hasattr(tweet, "retweeted_status")

    if is_favorite:
        return FavoritesSQL(
            created_at=tweet.created_at,
            entities=json.dumps(tweet.entities),
            favorite_count=tweet.favorite_count,
            tweet_id=tweet.id,
            is_quote_status=tweet.is_quote_status,
            lang=tweet.lang,
            possibly_sensitive=tweet.possibly_sensitive if hasattr(
                tweet, "possibly_sensitive") else False,
            retweet_count=tweet.retweet_count,
            source=tweet.source,
            source_url=tweet.source_url,
            text=tweet.full_text,
            user_id=tweet.author.id,
            screen_name=tweet.author.screen_name,
            name=tweet.author.name,
            last_updated=datetime.utcnow(),
        )

    return TimelineSQL(
        created_at=tweet.created_at,
        entities=json.dumps(tweet.entities),
        favorite_count=tweet.favorite_count,
        tweet_id=tweet.id,
        is_quote_status=tweet.is_quote_status,
        lang=tweet.lang,
        possibly_sensitive=tweet.possibly_sensitive if hasattr(
            tweet, "possibly_sensitive") else False,
        retweet_count=tweet.retweet_count,
        source=tweet.source,
        source_url=tweet.source_url,
        text=tweet.retweeted_status.full_text if is_retweet else tweet.full_text,
        retweet_user_id=tweet.retweeted_status.author.id if is_retweet else None,
        retweet_screen_name=tweet.retweeted_status.author.screen_name
        if is_retweet else None,
        retweet_name=tweet.retweeted_status.author.name if is_retweet else None,
        user_id=tweet.author.id,
        screen_name=tweet.author.screen_name,
        name=tweet.author.name,
        last_updated=datetime.utcnow(),
    )


def screen_names_to_user_ids(screen_names):
    '''
    Input screen names and output a list of user ids.
    Beyond 1500 becomes slow due to Twitter rate limiting,
    be prepared to wait 15 minutes between each 1500.
    '''
    iterations = ceil(len(screen_names) / 100)
    results = []
    for i in range(iterations):
        start = i * 100
        end = len(screen_names) if (i + 1) * \
            100 > len(screen_names) else (i + 1) * 100
        users = _API.lookup_users(screen_names=screen_names[start:end])
        results.extend([user.id for user in users])

    return results


# All User instances share one.
_CONFIG = _make_config()
_API = _make_api()


class User:
    '''
    With a user object, you can read, filter, and store Twitter data.
    '''

    def __init__(self, user_id, limit=100, cache_expiry=86400):

        if not isinstance(user_id, int):
            raise TypeError('User id must be an integer.')

        self._user_id = user_id
        self._limit = limit
        self._cache_expiry = cache_expiry
        self._conn = self._make_conn()

    def _make_conn(self):
        database = Path(f'./users/{self._user_id}.db')
        engine = create_engine(f'sqlite:///{database}')
        session = sessionmaker(bind=engine)()

        if not database.exists():
            database.parent.mkdir(parents=True, exist_ok=True)
            BASE.metadata.create_all(engine)

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

    def get_user(self):
        '''
        Get the user as an ORM object.
        If cache is expired, fetch first.
        '''
        if self._cache_expired(UsersSQL):
            self._fetch_user()

        return self._conn.query(UsersSQL).filter(UsersSQL.user_id == self._user_id).first()

    def _fetch_user(self):
        user = _API.get_user(user_id=self._user_id)

        if user:
            user_sql = _transform_user(user)
            self._conn.merge(user_sql)
            self._conn.commit()

    def get_timeline(self, watchlist=None, watchwords=None):
        '''
            Get Tweets and Retweets from a user's timeline.
            If the cache is expired,
        '''
        if self._cache_expired(TimelineSQL):
            self._fetch_timeline()

        if watchlist:
            watchlist = _transform_watchlist(watchlist, "watchlist")
            # When filtering, we are not interested in Tweets authored by the user.
            watchlist.remove(self._user_id)
            results = self._conn.query(TimelineSQL).filter(or_(
                TimelineSQL.retweet_user_id.in_(watchlist),
                TimelineSQL.user_id.in_(watchlist)
            )).all()
        else:
            results = self._conn.query(TimelineSQL).all()

        if watchwords:
            watchwords = _transform_watchlist(watchwords, "watchwords")
            results = _filter_for_watchwords(results, watchwords)

        return results

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

    def _fetch_timeline(self):
        for tweet in tweepy.Cursor(
                _API.user_timeline, id=self._user_id, tweet_mode="extended").items(self._limit):
            self._conn.merge(_transform_tweet(tweet))

        self._conn.commit()

    def get_favorites(self, watchlist=None, watchwords=None):
        '''
        Get the posts a user has liked.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FavoritesSQL):
            self._fetch_favorites()

        if watchlist:
            watchlist = _transform_watchlist(watchlist, "watchlist")
            results = self._conn.query(FavoritesSQL).filter(
                FavoritesSQL.user_id.in_(watchlist))
        else:
            results = self._conn.query(FavoritesSQL).all()

        if watchwords:
            watchwords = _transform_watchlist(watchwords, "watchwords")
            results = _filter_for_watchwords(results, watchwords)

        return results

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

    def _fetch_favorites(self):
        for favorite in tweepy.Cursor(
                _API.favorites, id=self._user_id, tweet_mode="extended").items(self._limit):
            self._conn.merge(_transform_tweet(favorite, is_favorite=True))

        self._conn.commit()

    def get_friends(self, watchlist=None):
        '''
        Get the users this user is following.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FriendsSQL):
            self._fetch_friends()

        if watchlist:
            watchlist = _transform_watchlist(watchlist, "watchlist")
            return self._conn.query(FriendsSQL).filter(FriendsSQL.user_id.in_(watchlist)).all()

        return self._conn.query(FriendsSQL).all()

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

    def get_followers(self, watchlist=None):
        '''
        Get the users followed by this user.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FollowersSQL):
            self._fetch_followers()

        if watchlist:
            watchlist = _transform_watchlist(watchlist, "watchlist")
            return self._conn.query(FollowersSQL).filter(FollowersSQL.user_id.in_(watchlist)).all()

        return self._conn.query(FollowersSQL).all()

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
