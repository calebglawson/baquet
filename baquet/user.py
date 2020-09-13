'''
All of the operations needed to support fetching and filtering Twitter user information.
'''

from contextlib import contextmanager
from datetime import datetime, timedelta
from math import ceil
from os import listdir
from pathlib import Path

from sqlalchemy_pagination import paginate
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine, and_, or_, desc
from sqlalchemy.sql import func
import tweepy

from .constants import BaquetConstants
from .helpers import(
    make_api,
    make_config,
    filter_for_watchwords,
    get_watchlist,
    transform_user,
    transform_tweet,
    serialize_entities,
    serialize_paginated_entities
)
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
    ListMembershipsSQL,
)
from .models.directory import BASE as DIR_BASE, DirectorySQL, CacheSQL


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


class User:
    '''
    With a user object, you can read, filter, and store Twitter data.
    '''

    def __init__(self, user_id, limit=100, cache_expiry=86400):
        self._user_id = user_id
        self._limit = limit
        self._cache_expiry = cache_expiry
        self._conn = self._make_conn()

    def _cache_expired(self, table):
        connection = self._conn()
        last_updated = connection.query(func.max(table.last_updated)).scalar()
        elapsed = datetime.utcnow() - last_updated if last_updated else None
        connection.close()
        return not elapsed or elapsed.seconds > self._cache_expiry

    def _make_conn(self):
        database = Path(f'./users/{self._user_id}.db')
        engine = create_engine(
            f'sqlite:///{database}',
            connect_args={"check_same_thread": False}
        )
        session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
        session = scoped_session(
            session_factory
        )

        if not database.exists():
            database.parent.mkdir(parents=True, exist_ok=True)
            USER_BASE.metadata.create_all(engine)

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

    # USER

    def _fetch_user(self):
        user = _API.get_user(user_id=self._user_id)

        if user:
            _DIRECTORY.add_directory(user)
            user_sql = transform_user(user, kind=BaquetConstants.USER)

            with self._session() as session:
                session.merge(user_sql)
                session.commit()

    def add_note_user(self, text):
        '''
        Add a note to the user.
        '''
        note = UserNotesSQL(text=text, created_at=datetime.utcnow())

        with self._session() as session:
            session.add(note)
            session.commit()

    def _fetch_list_memberships(self):
        with self._session() as session:
            # Clear all to remove deletions
            session.query(ListMembershipsSQL).delete()

            list_memberships = _API.lists_memberships(user_id=self._user_id)

            for membership in list_memberships:
                list_membership = ListMembershipsSQL(
                    list_id=membership.id_str,
                    name=membership.full_name,
                    last_updated=datetime.utcnow()
                )
                session.merge(list_membership)
            session.commit()

    def get_list_memberships(self):
        '''
        Get the lists the twitter user is a member of.
        '''
        if self._cache_expired(ListMembershipsSQL):
            self._fetch_list_memberships()

        with self._session() as session:
            return session.query(ListMembershipsSQL).all()

    def get_notes_user(self, page, page_size=20):
        '''
        Get user notes.
        '''
        with self._session() as session:
            return paginate(
                session.query(UserNotesSQL).order_by(
                    desc(UserNotesSQL.created_at)),
                page=page,
                page_size=page_size
            )

    def get_user(self):
        '''
        Get the user as an ORM object.
        If cache is expired, fetch first.
        '''
        if self._cache_expired(UsersSQL):
            self._fetch_user()

        with self._session() as session:
            return serialize_entities(
                session.query(UsersSQL).filter(
                    UsersSQL.user_id == self._user_id
                ).first()
            )

    def get_user_id(self):
        '''
        Get the user id.
        '''
        return self._user_id

    def remove_note_user(self, note_id):
        '''
        Remove note from user.
        '''
        with self._session() as session:
            note = session.query(UserNotesSQL).filter(
                UserNotesSQL.note_id == note_id
            ).first()

            if note:
                session.delete(note)
                session.commit()

    # TIMELINE

    def _fetch_timeline(self):
        with self._session() as session:
            for tweet in tweepy.Cursor(
                    _API.user_timeline,
                    id=self._user_id,
                    tweet_mode="extended"
            ).items(self._limit):
                session.merge(
                    transform_tweet(tweet, kind=BaquetConstants.TIMELINE)
                )
                session.commit()

    def add_note_timeline(self, tweet_id, text):
        '''
        Add a note to a tweet.
        '''
        note = TimelineNotesSQL(
            tweet_id=tweet_id,
            text=text,
            created_at=datetime.utcnow()
        )
        with self._session() as session:
            session.add(note)
            session.commit()

    def add_tag_timeline(self, tweet_id, tag_text):
        '''
        Applies a tag to a given tweet.
        '''
        tag_id = self._get_tag_id(tag_text)

        timeline_tag = TimelineTagsSQL(tag_id=tag_id, tweet_id=tweet_id)

        with self._session() as session:
            session.merge(timeline_tag)
            session.commit()

    def get_notes_timeline(self, tweet_id):
        '''
        Get notes from a tweet.
        '''
        with self._session() as session:
            return session.query(
                TimelineNotesSQL
            ).filter(TimelineNotesSQL.tweet_id == tweet_id).all()

    def get_retweet_watchlist_percent(self, watchlist):
        '''
        Get percentage of retweets that are from folks on the watchlist.
        '''
        if self._cache_expired(TimelineSQL):
            self._fetch_timeline()

        watchlist = get_watchlist(watchlist, kind=BaquetConstants.WATCHLIST)
        with self._session() as session:
            retweets_on_watchlist = session.query(TimelineSQL).filter(
                TimelineSQL.retweet_user_id.in_(watchlist)
            ).count()
            retweets = session.query(TimelineSQL).filter(
                TimelineSQL.retweet_user_id is not None
            ).count()

        return retweets_on_watchlist / retweets if retweets != 0 else 0

    def get_tags_timeline(self, tweet_id):
        '''
        Get the tags on a timeline tweet.
        '''
        with self._session() as session:
            return session.query(TagsSQL).join(TimelineTagsSQL).filter(
                TimelineTagsSQL.tweet_id == tweet_id
            ).all()

    def get_timeline(self, page, page_size=20, watchlist=None, watchwords=None):
        '''
            Get Tweets and Retweets from a user's timeline.
            If the cache is expired,
        '''
        if self._cache_expired(TimelineSQL):
            self._fetch_timeline()

        with self._session() as session:
            if watchlist:
                watchlist = get_watchlist(
                    watchlist, kind=BaquetConstants.WATCHLIST)
                # When filtering, we are not interested in Tweets authored by the user.
                if self._user_id in watchlist:
                    watchlist.remove(self._user_id)
                results = paginate(session.query(TimelineSQL).filter(or_(
                    TimelineSQL.retweet_user_id.in_(watchlist),
                    TimelineSQL.user_id.in_(watchlist)
                )).order_by(desc(TimelineSQL.created_at)), page=page, page_size=page_size)
            else:
                results = paginate(
                    session.query(TimelineSQL).order_by(
                        desc(TimelineSQL.created_at)
                    ),
                    page=page,
                    page_size=page_size
                )

        if watchwords:
            watchwords = get_watchlist(
                watchwords, kind=BaquetConstants.WATCHWORDS)
            results.items = filter_for_watchwords(results.items, watchwords)

        return serialize_paginated_entities(results)

    def get_timeline_tagged(self, tag_id, page, page_size=20):
        '''
        Get the tweets matching a particular tag.
        '''
        with self._session() as session:
            results = paginate(
                session.query(TimelineSQL).join(
                    TimelineTagsSQL,
                    TimelineSQL.tweet_id == TimelineTagsSQL.tweet_id
                ).filter(
                    TimelineTagsSQL.tag_id == tag_id
                ).order_by(desc(TimelineSQL.created_at)),
                page=page,
                page_size=page_size
            )

        return serialize_paginated_entities(results)

    def remove_note_timeline(self, tweet_id, note_id):
        '''
        Remove note from a tweet.
        '''
        with self._session() as session:
            note = session.query(TimelineNotesSQL).filter(
                TimelineNotesSQL.tweet_id == tweet_id and TimelineNotesSQL.note_id == note_id
            ).first()
            session.delete(note)
            session.commit()

    def remove_tag_timeline(self, tweet_id, tag_id):
        '''
        Delete a tag from a tweet.
        '''
        with self._session() as session:
            tag_id = session.query(TimelineTagsSQL).filter(
                TimelineTagsSQL.tag_id == tag_id and TimelineTagsSQL.tweet_id == tweet_id
            ).first()
            session.delete(tag_id)
            session.commit()

    # FAVORITES

    def _fetch_favorites(self):
        with self._session() as session:
            for favorite in tweepy.Cursor(
                    _API.favorites, id=self._user_id, tweet_mode="extended").items(self._limit):
                session.merge(
                    transform_tweet(
                        favorite,
                        kind=BaquetConstants.FAVORITE
                    )
                )
            session.commit()

    def add_note_favorite(self, tweet_id, text):
        '''
        Add a note to a tweet.
        '''
        note = FavoritesNotesSQL(
            tweet_id=tweet_id, text=text, created_at=datetime.utcnow())
        with self._session() as session:
            session.add(note)
            session.commit()

    def add_tag_favorite(self, tweet_id, tag_text):
        '''
        Applies a tag to a given tweet.
        '''
        tag_id = self._get_tag_id(tag_text)

        favorite_tag = FavoritesTagsSQL(tag_id=tag_id, tweet_id=tweet_id)
        with self._session() as session:
            session.merge(favorite_tag)
            session.commit()

    def get_favorite_watchlist_percent(self, watchlist):
        '''
        Get percentage of likes that are from folks on the watchlist.
        '''
        if self._cache_expired(FavoritesSQL):
            self._fetch_favorites()

        watchlist = get_watchlist(watchlist, kind=BaquetConstants.WATCHLIST)
        with self._session() as session:
            favorites_on_watchlist = session.query(FavoritesSQL).filter(
                FavoritesSQL.user_id.in_(watchlist)
            ).count()
            favorites = session.query(FavoritesSQL).count()

        return favorites_on_watchlist / favorites if favorites != 0 else 0

    def get_favorites(self, page, page_size=20, watchlist=None, watchwords=None):
        '''
        Get the posts a user has liked.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FavoritesSQL):
            self._fetch_favorites()

        with self._session() as session:
            if watchlist:
                watchlist = get_watchlist(
                    watchlist,
                    kind=BaquetConstants.WATCHLIST
                )
                results = paginate(
                    session.query(FavoritesSQL).filter(
                        FavoritesSQL.user_id.in_(watchlist)
                    ).order_by(desc(FavoritesSQL.created_at)),
                    page=page,
                    page_size=page_size
                )
            else:
                results = paginate(
                    session.query(FavoritesSQL).order_by(
                        desc(FavoritesSQL.created_at)
                    ),
                    page=page,
                    page_size=page_size
                )

        if watchwords:
            watchwords = get_watchlist(
                watchwords, kind=BaquetConstants.WATCHWORDS)
            results.items = filter_for_watchwords(
                results.items, watchwords)

        return serialize_paginated_entities(results)

    def get_favorites_tagged(self, tag_id, page, page_size=20):
        '''
        Get the tweets matching a particular tag.
        '''
        with self._session() as session:
            results = paginate(
                session.query(FavoritesSQL).join(
                    FavoritesTagsSQL, FavoritesSQL.tweet_id == FavoritesTagsSQL.tweet_id
                ).filter(
                    FavoritesTagsSQL.tag_id == tag_id
                ).order_by(desc(FavoritesSQL.created_at)),
                page=page,
                page_size=page_size
            )

        return serialize_paginated_entities(results)

    def get_notes_favorite(self, tweet_id):
        '''
        Get notes from a tweet.
        '''
        with self._session() as session:
            return session.query(
                FavoritesNotesSQL
            ).filter(FavoritesNotesSQL.tweet_id == tweet_id).all()

    def get_tags_favorite(self, tweet_id):
        '''
        Get the tags on a favorited tweet.
        '''
        with self._session() as session:
            return session.query(TagsSQL).join(FavoritesTagsSQL).filter(
                FavoritesTagsSQL.tweet_id == tweet_id
            ).all()

    def remove_note_favorite(self, tweet_id, note_id):
        '''
        Remove note from a tweet.
        '''
        with self._session() as session:
            session.query(FavoritesNotesSQL).filter(
                and_(
                    FavoritesNotesSQL.tweet_id == tweet_id,
                    FavoritesNotesSQL.note_id == note_id
                )
            ).delete(synchronize_session='fetch')
            session.commit()

    def remove_tag_favorite(self, tweet_id, tag_id):
        '''
        Delete a tag from a tweet.
        '''
        with self._session() as session:
            tag_id = session.query(FavoritesTagsSQL).filter(
                and_(
                    FavoritesTagsSQL.tag_id == tag_id,
                    FavoritesTagsSQL.tweet_id == tweet_id
                )
            ).delete(synchronize_session='fetch')
            session.commit()

    # FRIENDS

    def _fetch_friends(self):
        # Delete to prevent stale entries.
        with self._session() as session:
            session.query(FriendsSQL).delete()

            friends = []
            for friend_id in tweepy.Cursor(_API.friends_ids, id=self._user_id).items():
                session.merge(
                    FriendsSQL(
                        user_id=friend_id,
                        last_updated=datetime.utcnow()
                    )
                )

            session.bulk_save_objects(friends)
            session.commit()

    def get_friends(self, page, page_size=10000, watchlist=None):
        '''
        Get the users this user is following.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FriendsSQL):
            self._fetch_friends()

        if watchlist:
            watchlist = get_watchlist(
                watchlist, kind=BaquetConstants.WATCHLIST)
            with self._session() as session:
                results = paginate(
                    session.query(FriendsSQL).filter(
                        FriendsSQL.user_id.in_(watchlist)
                    ),
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

        with self._session() as session:
            return paginate(session.query(FriendsSQL), page=page, page_size=page_size)

    def get_friends_watchlist_completion(self, watchlist):
        '''
        Get percentage completion of watchlist,
        based on friends on the watchlist.
        '''
        if self._cache_expired(FriendsSQL):
            self._fetch_friends()

        watchlist = get_watchlist(watchlist, kind=BaquetConstants.WATCHLIST)
        with self._session() as session:
            friends_on_watchlist = session.query(FriendsSQL).filter(
                FriendsSQL.user_id.in_(watchlist)
            ).count()

        return (friends_on_watchlist / len(watchlist)
                if watchlist else 0)

    def get_friends_watchlist_percent(self, watchlist):
        '''
        Get percentage of friends that are on the watchlist.
        '''
        if self._cache_expired(FriendsSQL):
            self._fetch_friends()

        watchlist = get_watchlist(watchlist, kind=BaquetConstants.WATCHLIST)
        with self._session() as session:
            friends_on_watchlist = session.query(FriendsSQL).filter(
                FriendsSQL.user_id.in_(watchlist)
            ).count()
            friends = session.query(FriendsSQL).count()

        return friends_on_watchlist / friends if friends != 0 else 0

    # FOLLOWERS

    def _fetch_followers(self):
        with self._session() as session:
            # Delete to prevent stale entries.
            session.query(FollowersSQL).delete()

            followers = []
            for follower_id in tweepy.Cursor(_API.followers_ids, id=self._user_id).items():
                followers.append(
                    FollowersSQL(
                        user_id=follower_id,
                        last_updated=datetime.utcnow()
                    )
                )

            session.bulk_save_objects(followers)
            session.commit()

    def get_followers(self, page, page_size=10000, watchlist=None):
        '''
        Get the users followed by this user.
        If cache is expired, fetch them.
        '''
        if self._cache_expired(FollowersSQL):
            self._fetch_followers()

        if watchlist:
            watchlist = get_watchlist(
                watchlist, kind=BaquetConstants.WATCHLIST)
            with self._session() as session:
                results = paginate(
                    session.query(FollowersSQL).filter(
                        FollowersSQL.user_id.in_(watchlist)
                    ),
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
        with self._session() as session:
            return paginate(session.query(FollowersSQL), page=page, page_size=page_size)

    def get_followers_watchlist_completion(self, watchlist):
        '''
        Get percentage completion of watchlist,
        based on followers on the watchlist.
        '''
        if self._cache_expired(FollowersSQL):
            self._fetch_followers()

        watchlist = get_watchlist(watchlist, kind=BaquetConstants.WATCHLIST)
        with self._session() as session:
            followers_on_watchlist = session.query(FollowersSQL).filter(
                FollowersSQL.user_id.in_(watchlist)
            ).count()

        return (followers_on_watchlist / len(watchlist)
                if watchlist else 0)

    def get_followers_watchlist_percent(self, watchlist):
        '''
        Get percentage of followers that are on the watchlist.
        '''
        if self._cache_expired(FollowersSQL):
            self._fetch_followers()

        watchlist = get_watchlist(watchlist, kind=BaquetConstants.WATCHLIST)
        with self._session() as session:
            followers_on_watchlist = session.query(FollowersSQL).filter(
                FollowersSQL.user_id.in_(watchlist)
            ).count()
            followers = session.query(FollowersSQL).count()

        return followers_on_watchlist / followers if followers != 0 else 0

    # TAGS

    def _get_tag_id(self, text):
        text = text.strip()
        with self._session() as session:
            tag = session.query(TagsSQL).filter(TagsSQL.text == text).first()

            if not tag:
                tag = TagsSQL(text=text)
                session.add(tag)
                session.commit()

            return tag.tag_id

    def get_tags(self, kind):
        '''
        Get the tags that apply to a given concept.
        '''
        if kind == BaquetConstants.FAVORITE:
            query_class = FavoritesTagsSQL
        elif kind == BaquetConstants.TIMELINE:
            query_class = TimelineTagsSQL
        else:
            return None
        with self._session() as session:
            return session.query(TagsSQL).join(
                query_class,
                query_class.tag_id == TagsSQL.tag_id
            ).all()


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
            autocommit=False, autoflush=False, bind=engine)()

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
                int(fn.split('.')[0]) for fn in listdir(self._path) if fn.split('.')[0].isnumeric()
            ]
        )
        with self._session() as session:
            users_in_directory = set(
                [u.user_id for u in session.query(DirectorySQL).filter(
                    DirectorySQL.last_updated > self._expired_time
                ).all()])

            add = list(users_in_path - users_in_directory)
            add = hydrate_user_identifiers(user_ids=add)
            add = [transform_user(u, kind=BaquetConstants.DIRECTORY)
                   for u in add]

            for user in add:
                session.merge(user)
            session.commit()

            delete = list(users_in_directory - users_in_path)
            if delete:
                session.query(DirectorySQL).filter(
                    DirectorySQL.user_id.in_(delete)).delete(synchronize_session=False)
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

        shard_size = BaquetConstants.SQLITE_SHARD_SIZE
        result = []
        iterations = ceil(len(user_ids) / shard_size)
        for iteration in range(iterations):
            primary_clause = CacheSQL.user_id.in_(
                user_ids[
                    iteration * shard_size:iteration * (shard_size + 1)
                ]
            ) if user_ids else CacheSQL.user_id.in_(
                screen_names[
                    iteration * shard_size:iteration * (shard_size + 1)
                ]
            )

            with self._session() as session:
                result = result + session.query(CacheSQL).filter(
                    and_(
                        primary_clause,
                        (CacheSQL.last_updated > self._expired_time)
                    )
                ).all()
        return result


# GLOBALS
_CONFIG = make_config()
_API = make_api(_CONFIG)
_DIRECTORY = Directory()
