import tweepy
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, or_
from sqlalchemy.sql import func
from datetime import datetime
from math import ceil
import json

from models.user import BASE, UsersSQL, TimelineSQL, FavoritesSQL, FriendsSQL, FollowersSQL
from watchlist import Watchlist


def _make_config():
    config = open(Path('./config.json'))
    return json.load(config)


_CONFIG = _make_config()


def _make_api():
    auth = tweepy.OAuthHandler(_CONFIG.get(
        'consumer_key'), _CONFIG.get('consumer_secret'))
    auth.set_access_token(_CONFIG.get('access_token'),
                          _CONFIG.get('access_token_secret'))

    api = tweepy.API(auth, wait_on_rate_limit=True,
                     wait_on_rate_limit_notify=True)

    return api


_API = _make_api()


def screen_names_to_user_ids(screen_names):
    iterations = ceil(len(screen_names) / 100)
    results = []
    for i in range(iterations):
        start = i * 100
        end = len(screen_names) if (i + 1) * \
            100 > len(screen_names) else (i + 1) * 100
        print(start, end)
        users = _API.lookup_users(screen_names=screen_names[start:end])
        results = results + [user.id for user in users]

    return results


class User:
    def __init__(self, user_id=None, limit=100, cache_expiry=86400):
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

    def _transform_watchlist(self, watchlist, kind):
        if isinstance(watchlist, Watchlist):
            if kind.lower() == "watchlist":
                return watchlist.get_watchlist()
            elif kind.lower() == "watchwords":
                return watchlist.get_watchwords()
        return watchlist

    def _filter_for_watchwords(self, results, watchwords):
        matches = []
        for result in results:
            for watchword in watchwords:
                if watchword.lower() in result.text.lower():
                    matches.append(result)
                    break
        return matches

    def get_user_id(self):
        return self._user_id

    def get_user(self):
        if self._cache_expired(UsersSQL):
            self._fetch_user()

        return self._conn.query(UsersSQL).filter(UsersSQL.id == self._user_id).first()

    def _fetch_user(self):
        user = _API.get_user(user_id=self._user_id)

        if user:
            user_sql = UsersSQL(
                contributors_enabled=user.contributors_enabled,
                created_at=user.created_at,
                default_profile=user.default_profile,
                default_profile_image=user.default_profile_image,
                description=user.description,
                entities=str(user.entities),
                favorites_count=user.favourites_count,
                followers_count=user.followers_count,
                friends_count=user.friends_count,
                geo_enabled=user.geo_enabled,
                has_extended_profile=user.has_extended_profile,
                id=user.id,
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

            self._conn.merge(user_sql)
            self._conn.commit()

    def get_timeline(self, watchlist=None, watchwords=None):
        if self._cache_expired(TimelineSQL):
            self._fetch_timeline()

        if watchlist:
            watchlist = self._transform_watchlist(watchlist, "watchlist")
            watchlist.remove(self._user_id)
            results = self._conn.query(TimelineSQL).filter(or_(TimelineSQL.retweet_user_id.in_(watchlist),
                                                               TimelineSQL.user_id.in_(watchlist))).all()
        else:
            results = self._conn.query(TimelineSQL).all()

        if watchwords:
            watchwords = self._transform_watchlist(watchwords, "watchwords")
            results = self._filter_for_watchwords(results, watchwords)

        return results

    def _fetch_timeline(self):
        for tweet in tweepy.Cursor(_API.user_timeline, id=self._user_id).items(self._limit):
            is_retweet = hasattr(tweet, "retweeted_status")
            tweet_sql = TimelineSQL(
                created_at=tweet.created_at,
                entities=str(tweet.entities),
                extended_entities=str(tweet.extended_entities) if hasattr(
                    tweet, "extended_entities") else None,
                favorite_count=tweet.favorite_count,
                id=tweet.id,
                is_quote_status=tweet.is_quote_status,
                lang=tweet.lang,
                possibly_sensitive=tweet.possibly_sensitive if hasattr(
                    tweet, "possibly_sensitive") else False,
                retweet_count=tweet.retweet_count,
                source=tweet.source,
                source_url=tweet.source_url,
                text=tweet.text,
                truncated=tweet.truncated,
                retweet_user_id=tweet.retweeted_status.author.id if is_retweet else None,
                retweet_screen_name=tweet.retweeted_status.author.screen_name if is_retweet else None,
                retweet_name=tweet.retweeted_status.author.name if is_retweet else None,
                user_id=tweet.author.id,
                screen_name=tweet.author.screen_name,
                name=tweet.author.name,
                last_updated=datetime.utcnow(),
            )

            self._conn.merge(tweet_sql)
        self._conn.commit()

    def get_favorites(self, watchlist=None, watchwords=None):
        if self._cache_expired(FavoritesSQL):
            self._fetch_favorites()

        if watchlist:
            watchlist = self._transform_watchlist(watchlist, "watchlist")
            results = self._conn.query(FavoritesSQL).filter(
                FavoritesSQL.user_id.in_(watchlist))
        else:
            results = self._conn.query(FavoritesSQL).all()

        if watchwords:
            watchwords = self._transform_watchlist(watchwords, "watchwords")
            results = self._filter_for_watchwords(results, watchwords)

        return results

    def _fetch_favorites(self):
        for favorite in tweepy.Cursor(_API.favorites, id=self._user_id).items(self._limit):
            favorite_sql = FavoritesSQL(
                created_at=favorite.created_at,
                entities=str(favorite.entities),
                extended_entities=str(favorite.extended_entities) if hasattr(
                    favorite, "extended_entities") else None,
                favorite_count=favorite.favorite_count,
                id=favorite.id,
                is_quote_status=favorite.is_quote_status,
                lang=favorite.lang,
                possibly_sensitive=favorite.possibly_sensitive if hasattr(
                    favorite, "possibly_sensitive") else False,
                retweet_count=favorite.retweet_count,
                source=favorite.source,
                source_url=favorite.source_url,
                text=favorite.text,
                truncated=favorite.truncated,
                user_id=favorite.author.id,
                screen_name=favorite.author.screen_name,
                name=favorite.author.name,
                last_updated=datetime.utcnow(),
            )

            self._conn.merge(favorite_sql)
        self._conn.commit()

    def get_friends(self, watchlist=None):
        if self._cache_expired(FriendsSQL):
            self._fetch_friends()

        if watchlist:
            watchlist = self._transform_watchlist(watchlist, "watchlist")
            return self._conn.query(FriendsSQL).filter(FriendsSQL.id.in_(watchlist)).all()

        return self._conn.query(FriendsSQL).all()

    def _fetch_friends(self):
        for friend_id in tweepy.Cursor(_API.friends_ids, id=self._user_id).items():
            friend_sql = FriendsSQL(
                id=friend_id, last_updated=datetime.utcnow())
            self._conn.merge(friend_sql)

    def get_followers(self, watchlist=None):
        if self._cache_expired(FollowersSQL):
            self._fetch_followers()

        if watchlist:
            watchlist = self._transform_watchlist(watchlist, "watchlist")
            return self._conn.query(FollowersSQL).filter(FollowersSQL.id.in_(watchlist)).all()

        return self._conn.query(FollowersSQL).all()

    def _fetch_followers(self):
        for follower_id in tweepy.Cursor(_API.followers_ids, id=self._user_id).items():
            follower_sql = FollowersSQL(
                id=follower_id, last_updated=datetime.utcnow())
            self._conn.merge(follower_sql)
        self._conn.commit()
