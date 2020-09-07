'''
From this module, we control data in the watchlist.
The watchlist houses a list of users and words of interest.
'''

import json
from copy import copy
from pathlib import Path
from datetime import datetime, timedelta

import requests
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, or_, and_, not_
from .constants import BaquetConstants
from .models.watchlist import (
    BASE,
    WatchlistSQL,
    WatchwordsSQL,
    SubListSQL,
    SubListTypeSQL,
    UserSubListSQL,
)
from .user import hydrate_user_identifiers, _API


def _serialize_entities(item):
    # Without copying, there's some SQLAlchemy weirdness.
    item = copy(item)
    if hasattr(item, "entities") and item.entities:
        item.entities = json.loads(item.entities)
    return item


def _transform_user_id(user):
    user_id = None

    if hasattr(user, "id_str"):
        user_id = user.id_str
    elif hasattr(user, "id"):
        user_id = user.id
    elif hasattr(user, "user_id"):
        user_id = user.user_id

    return user_id


def _transform_user(user):
    return WatchlistSQL(
        contributors_enabled=user.contributors_enabled,
        created_at=user.created_at,
        default_profile=user.default_profile,
        default_profile_image=user.default_profile_image,
        description=user.description,
        entities=user.entities if isinstance(user.entities,
                                             str) else json.dumps(user.entities),
        favorites_count=user.favorites_count if hasattr(
            user, "favorites_count") else user.favourites_count,
        followers_count=user.followers_count,
        friends_count=user.friends_count,
        geo_enabled=user.geo_enabled,
        has_extended_profile=user.has_extended_profile,
        user_id=_transform_user_id(user),
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
            type_self = SubListTypeSQL(
                sublist_type_id=BaquetConstants.SUBLIST_TYPE_SELF,
                name="self",
            )
            session.add(type_self)
            type_twitter = SubListTypeSQL(
                sublist_type_id=BaquetConstants.SUBLIST_TYPE_TWITTER,
                name="twitter",
            )
            session.add(type_twitter)
            type_blockbot = SubListTypeSQL(
                sublist_type_id=BaquetConstants.SUBLIST_TYPES_BLOCKBOT,
                name="blockbot",
            )
            session.add(type_blockbot)

            sub_list_self = SubListSQL(
                sublist_id=BaquetConstants.SUBLIST_TYPE_SELF,
                sublist_type_id=BaquetConstants.SUBLIST_TYPE_SELF,
                name="self"
            )
            session.add(sub_list_self)

            session.commit()

        return session

    # WATCHLIST
    def add_watchlist(self, users, sublist_id=BaquetConstants.SUBLIST_TYPE_SELF):
        '''
        Add one or more users to the watchlist.
        '''

        if not isinstance(users, list):
            users = [users]

        for i, user in enumerate(users):
            if not isinstance(user, str):
                users[i] = user.get_user_id()

            wl_sql = WatchlistSQL(user_id=users[i])
            self._conn.merge(wl_sql)

            # Get the previous sublist if exists, to preserve local exclusions.
            prev_user_sublist = self._conn.query(UserSubListSQL).filter(
                UserSubListSQL.user_id == users[i] and UserSubListSQL.sublist_id == sublist_id
            ).first()
            locally_excluded = prev_user_sublist.locally_excluded if prev_user_sublist else False

            user_sublist = UserSubListSQL(
                user_id=users[i], sublist_id=sublist_id, locally_excluded=locally_excluded
            )
            self._conn.merge(user_sublist)

        self._conn.commit()

    def clear_watchlist(self):
        '''
        Remove all users from the watchlist.
        '''
        self._conn.query(WatchlistSQL).delete()
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

    def get_watchlist_users(self):
        '''
        Get watchlist users.
        '''
        return [_serialize_entities(result) for result in self._conn.query(WatchlistSQL).all()]

    def import_blockbot_list(self, blockbot_id, name):
        '''
        Import a theblockbot.com list.
        '''

        url = f'https://www.theblockbot.com/show-blocks/{blockbot_id}.csv'
        blockbot_list = requests.get(
            url
        ).content.decode("utf-8").split("\n")[:-1]
        self._import_list(
            blockbot_id,
            name,
            BaquetConstants.SUBLIST_TYPES_BLOCKBOT,
            blockbot_list,
        )

    def import_twitter_list(self, twitter_id=None, slug=None, owner_screen_name=None):
        '''
        Import a list of users from twitter.
        '''

        assert (
            not (twitter_id and (slug and owner_screen_name))
        ), "Must supply twitter_id or both slug and owner_screen_name."

        # Get the twitter list data.
        twitter_list = _API.get_list(
            list_id=twitter_id,
            slug=slug,
            owner_screen_name=owner_screen_name
        )
        stripped_twitter_list = [
            member.id_str for member in twitter_list.members()
        ]
        self._import_list(
            twitter_list.id_str,
            twitter_list.full_name,
            BaquetConstants.SUBLIST_TYPE_TWITTER,
            stripped_twitter_list
        )

    def _import_list(self, external_id, name, sublist_type_id, users):
        # See if list exists already.
        current_sublist = self._conn.query(SubListSQL).filter(
            SubListSQL.external_id == external_id
        ).first()

        if not current_sublist:
            # Create new list if not exists.
            current_sublist = SubListSQL(
                sublist_type_id=sublist_type_id, name=name, external_id=external_id
            )
            self._conn.add(current_sublist)
            self._conn.commit()
            current_sublist = self._conn.query(SubListSQL).filter(
                SubListSQL.external_id == external_id
            ).first()
        else:
            # If list exists, delete all UserSubList links that are not locally excluded.
            self._conn.query(UserSubListSQL).filter(
                and_(
                    UserSubListSQL.sublist_id == current_sublist.sublist_id,
                    not_(UserSubListSQL.locally_excluded)
                )
            ).delete(synchronize_session='fetch')
            # Delete any users that no longer belong to any sublists.
            orphans = self._conn.query(
                WatchlistSQL.user_id
            ).outerjoin(
                WatchlistSQL.sublists
            ).filter(
                WatchlistSQL.sublists == None  # pylint: disable=singleton-comparison
            )

            self._conn.query(WatchlistSQL).filter(
                WatchlistSQL.user_id.in_(orphans.subquery())
            ).delete(synchronize_session='fetch')

        # Add users from the refreshe'd list.
        self.add_watchlist(
            users,
            sublist_id=current_sublist.sublist_id
        )
        self._conn.commit()

    def get_sublists(self):
        '''
        Get a list of all sublists.
        '''
        return self._conn.query(SubListSQL).all()

    def get_sublist_users(self, sublist_id):
        '''
        List the users that belong to a sublist.
        '''
        return self._conn.query(WatchlistSQL).join(UserSubListSQL).filter(
            UserSubListSQL.sublist_id == sublist_id
        ).all()

    def get_sublist_user_exclusions(self, sublist_id):
        '''
        List the users that are
        '''
        return self._conn.query(WatchlistSQL).join(UserSubListSQL).filter(
            and_(
                UserSubListSQL.sublist_id == sublist_id,
                UserSubListSQL.locally_excluded
            )
        ).all()

    def set_user_sublist_exclusion_status(self, user_id, sublist_id, excluded):
        '''
        Set the user's exclusion status.
        '''
        user_sublist = self._conn.query(UserSubListSQL).filter(
            UserSubListSQL.user_id == user_id and UserSubListSQL.sublist_id == sublist_id
        ).first()
        user_sublist.locally_excluded = excluded
        self._conn.commit()

    def refresh_sublist(self, sublist_id):
        '''
        Refresh a sublist's data. Locally excluded users are kept.
        '''
        sublist = self._conn.query(SubListSQL).filter(
            SubListSQL.sublist_id == sublist_id
        ).first()
        if sublist.sublist_type_id == BaquetConstants.SUBLIST_TYPE_TWITTER:
            self.import_twitter_list(twitter_id=sublist.external_id)
        elif sublist.sublist_type_id == BaquetConstants.SUBLIST_TYPES_BLOCKBOT:
            self.import_blockbot_list(
                blockbot_id=sublist.external_id, name=sublist.name)
        else:
            pass

    def refresh_sublists(self):
        '''
        Refresh all sublist data.
        '''
        sublists = self._conn.query(UserSubListSQL.sublist_id).all()
        for sublist in sublists:
            self.refresh_sublist(sublist.sublist_id)

    def remove_sublist(self, sublist_id):
        '''
        Remove a sublist from the watchlist.
        Removes the sublist and users that belong exclusively to this list.
        '''
        if not sublist_id == BaquetConstants.SUBLIST_TYPE_SELF:
            # Cannot delete self.
            self._conn.query(SubListSQL).filter(
                SubListSQL.sublist_id == sublist_id
            ).delete(synchronize_session='fetch')

        self._conn.query(UserSubListSQL).filter(
            UserSubListSQL.sublist_id == sublist_id
        ).delete(synchronize_session='fetch')

        # Delete any users that no longer belong to any sublists.
        orphans = self._conn.query(
            WatchlistSQL.user_id
        ).outerjoin(
            WatchlistSQL.sublists
        ).filter(
            WatchlistSQL.sublists == None  # pylint: disable=singleton-comparison
        )

        self._conn.query(WatchlistSQL).filter(
            WatchlistSQL.user_id.in_(orphans.subquery())
        ).delete(synchronize_session='fetch')

        self._conn.commit()

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
        if refresh:
            refresh = hydrate_user_identifiers(user_ids=refresh)

        for user in refresh:
            self._conn.merge(_transform_user(user))

        self._conn.commit()

    def remove_watchlist(self, user):
        '''
        Remove a user from the watchlist.
        '''
        user = self._conn.query(WatchlistSQL).filter(
            WatchlistSQL.user_id == user.get_user_id()).first()
        self._conn.delete(user)
        self._conn.commit()

    # WATCHWORDS

    def add_watchword(self, regex):
        '''
        Add a search term to the watchwords.
        '''
        regex = WatchwordsSQL(regex=regex)
        self._conn.merge(regex)
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

    def remove_watchword(self, regex):
        '''
        Remove a search term from the watchwords.
        '''
        regex = self._conn.query(WatchwordsSQL).filter(
            WatchwordsSQL.regex == regex).first()
        self._conn.delete(regex)
        self._conn.commit()
