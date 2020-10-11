'''
From this module, we control data in the watchlist.
The watchlist houses a list of users and words of interest.
'''

from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta

import requests
from sqlalchemy_pagination import paginate
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine, or_, and_, not_
from .constants import BaquetConstants
from .sql.watchlist import (
    BASE,
    WatchlistSQL,
    WatchwordsSQL,
    SubListSQL,
    SubListTypeSQL,
    UserSubListSQL,
)
from .helpers import (
    serialize_paginated_entities,
    transform_user,
)
from .models import (
    load_model,
    UserPaginatorModel,
    SublistModel,
    UserModel
)
from .directory import hydrate_user_identifiers, _API


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
        session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )

        session = scoped_session(session_factory)

        if not database.exists():
            database.parent.mkdir(parents=True, exist_ok=True)
            BASE.metadata.create_all(engine)

            self._db_init(session)

        return session

    def _db_init(self, session):
        try:
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
        except:
            session.rollback()
            raise
        finally:
            session.close()

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

    # WATCHLIST

    def add_watchlist(self, users, sublist_id=BaquetConstants.SUBLIST_TYPE_SELF):
        '''
        Add one or more users to the watchlist.
        '''

        if not isinstance(users, list):
            users = [users]

        with self._session() as session:
            for i, user in enumerate(users):
                if not isinstance(user, str):
                    users[i] = user.get_user_id()

                wl_sql = WatchlistSQL(user_id=users[i])
                session.merge(wl_sql)

                # Get the previous sublist if exists, to preserve local exclusions.
                prev_user_sublist = session.query(UserSubListSQL).filter(
                    UserSubListSQL.user_id == users[i] and UserSubListSQL.sublist_id == sublist_id
                ).first()
                locally_excluded = (
                    prev_user_sublist.locally_excluded if prev_user_sublist else False
                )

                user_sublist = UserSubListSQL(
                    user_id=users[i], sublist_id=sublist_id, locally_excluded=locally_excluded
                )
                session.merge(user_sublist)
            session.commit()

    def clear_watchlist(self):
        '''
        Remove all users from the watchlist.
        '''
        with self._session() as session:
            session.query(WatchlistSQL).delete()
            session.commit()

    def get_watchlist(self):
        '''
        Get the watchlist as a list of user ids.
        '''
        with self._session() as session:
            return [user.user_id for user in session.query(WatchlistSQL).all()]

    def get_watchlist_count(self):
        '''
        Get the count of users on the watchlist.
        '''
        with self._session() as session:
            return session.query(WatchlistSQL).count()

    def get_watchlist_users(self, page, page_size=20):
        '''
        Get the watchlist as a list of Users with details.
        '''
        with self._session() as session:
            results = paginate(
                session.query(WatchlistSQL),
                page=page,
                page_size=page_size,
            )

            results = serialize_paginated_entities(results)
            return load_model(results, UserPaginatorModel)

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
        with self._session() as session:
            # See if list exists already.
            current_sublist = session.query(SubListSQL).filter(
                SubListSQL.external_id == external_id
            ).first()

            if not current_sublist:
                # Create new list if not exists.
                current_sublist = SubListSQL(
                    sublist_type_id=sublist_type_id, name=name, external_id=external_id
                )
                session.add(current_sublist)
                session.commit()
                current_sublist = session.query(SubListSQL).filter(
                    SubListSQL.external_id == external_id
                ).first()
            else:
                # If list exists, delete all UserSubList links that are not locally excluded.
                session.query(UserSubListSQL).filter(
                    and_(
                        UserSubListSQL.sublist_id == current_sublist.sublist_id,
                        not_(UserSubListSQL.locally_excluded)
                    )
                ).delete(synchronize_session='fetch')
                # Delete any users that no longer belong to any sublists.
                orphans = session.query(
                    WatchlistSQL.user_id
                ).outerjoin(
                    WatchlistSQL.sublists
                ).filter(
                    WatchlistSQL.sublists == None  # pylint: disable=singleton-comparison
                )

                for orphan in orphans:
                    session.query(WatchlistSQL).filter(
                        WatchlistSQL.user_id == orphan.user_id).delete(synchronize_session='fetch')

            # Add users from the refreshe'd list.
            self.add_watchlist(
                users,
                sublist_id=current_sublist.sublist_id
            )
            session.commit()

    def get_sublists(self):
        '''
        Get a list of all sublists.
        '''
        with self._session() as session:
            results = session.query(SubListSQL).all()
            return load_model(results, SublistModel, many=True)

    def get_sublist_users(self, sublist_id, page, page_size=20):
        '''
        List the users that belong to a sublist.
        '''
        with self._session() as session:
            results = paginate(
                session.query(WatchlistSQL).join(
                    UserSubListSQL
                ).filter(UserSubListSQL.sublist_id == sublist_id),
                page=page,
                page_size=page_size,
            )

            results = serialize_paginated_entities(results)
            return load_model(results, UserPaginatorModel)

    def get_sublist_user_exclusions(self, sublist_id):
        '''
        List the users that are
        '''
        with self._session() as session:
            results = session.query(WatchlistSQL).join(UserSubListSQL).filter(
                and_(
                    UserSubListSQL.sublist_id == sublist_id,
                    UserSubListSQL.locally_excluded
                )
            ).all()
            return load_model(results, UserModel, many=True)

    def set_user_sublist_exclusion_status(self, user_id, sublist_id, excluded):
        '''
        Set the user's exclusion status.
        '''
        with self._session() as session:
            user_sublist = session.query(UserSubListSQL).filter(
                UserSubListSQL.user_id == user_id and UserSubListSQL.sublist_id == sublist_id
            ).first()
            user_sublist.locally_excluded = excluded
            session.commit()

    def refresh_sublist(self, sublist_id):
        '''
        Refresh a sublist's data. Locally excluded users are kept.
        '''
        with self._session() as session:
            sublist = session.query(SubListSQL).filter(
                SubListSQL.sublist_id == sublist_id
            ).first()
        if sublist.sublist_type_id == BaquetConstants.SUBLIST_TYPE_TWITTER:
            self.import_twitter_list(twitter_id=sublist.external_id)
        elif sublist.sublist_type_id == BaquetConstants.SUBLIST_TYPES_BLOCKBOT:
            self.import_blockbot_list(
                blockbot_id=sublist.external_id,
                name=sublist.name
            )
        else:
            pass

    def refresh_sublists(self):
        '''
        Refresh all sublist data.
        '''
        with self._session() as session:
            sublists = session.query(SubListSQL.sublist_id).all()
        for sublist in sublists:
            self.refresh_sublist(sublist.sublist_id)

    def remove_sublist(self, sublist_id):
        '''
        Remove a sublist from the watchlist.
        Removes the sublist and users that belong exclusively to this list.
        '''
        with self._session() as session:
            if not sublist_id == BaquetConstants.SUBLIST_TYPE_SELF:
                # Cannot delete self.
                session.query(SubListSQL).filter(
                    SubListSQL.sublist_id == sublist_id
                ).delete(synchronize_session='fetch')

            session.query(UserSubListSQL).filter(
                UserSubListSQL.sublist_id == sublist_id
            ).delete(synchronize_session='fetch')

            # Delete any users that no longer belong to any sublists.
            orphans = session.query(
                WatchlistSQL.user_id
            ).outerjoin(
                WatchlistSQL.sublists
            ).filter(
                WatchlistSQL.sublists == None  # pylint: disable=singleton-comparison
            )

            for orphan in orphans:
                session.query(WatchlistSQL).filter(
                    WatchlistSQL.user_id == orphan.user_id
                ).delete(synchronize_session='fetch')

            session.commit()

    def refresh_watchlist_user_data(self):
        '''
        Populate user data if missing or expired.
        '''
        last_updated_expiry = datetime.utcnow() - timedelta(seconds=self._cache_expiry)

        with self._session() as session:
            refresh = [u.user_id for u in session.query(
                WatchlistSQL).filter(
                    or_(
                        WatchlistSQL.last_updated < last_updated_expiry,
                        WatchlistSQL.screen_name.is_(None)
                    )).all()]
            if refresh:
                refresh = hydrate_user_identifiers(user_ids=refresh)

            for user in refresh:
                session.merge(transform_user(user, BaquetConstants.WATCHLIST))

            session.commit()

    def remove_watchlist(self, user):
        '''
        Remove a user from the watchlist.
        '''
        with self._session() as session:
            session.query(WatchlistSQL).filter(
                WatchlistSQL.user_id == user.get_user_id()
            ).delete(synchronize_session='fetch')
            session.query(UserSubListSQL).filter(
                UserSubListSQL.user_id == user.get_user_id()
            ).delete(synchronize_session='fetch')
            session.commit()

    # WATCHWORDS

    def add_watchword(self, regex):
        '''
        Add a search term to the watchwords.
        '''
        regex = WatchwordsSQL(regex=regex)
        with self._session() as session:
            session.merge(regex)
            session.commit()

    def get_watchwords(self):
        '''
        Get the watchwords as a list.
        '''
        with self._session() as session:
            return [ww.regex for ww in session.query(WatchwordsSQL.regex).all()]

    def get_watchwords_count(self):
        '''
        Get the count of users on the watchwords.
        '''
        with self._session() as session:
            return session.query(WatchwordsSQL).count()

    def remove_watchword(self, regex):
        '''
        Remove a search term from the watchwords.
        '''
        with self._session() as session:
            regex = session.query(WatchwordsSQL).filter(
                WatchwordsSQL.regex == regex).first()
            session.delete(regex)
            session.commit()
