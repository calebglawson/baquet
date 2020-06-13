'''
From this module, we control data in the watchlist.
The watchlist houses a list of users and words of interest.
'''

from pathlib import Path
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from .models.watchlist import BASE, WatchlistSQL, WatchwordsSQL


class Watchlist:
    '''
    From this class, we control data in the watchlist and watchwords.
    '''

    def __init__(self, name):
        self._name = name
        self._conn = self._make_conn()

    def _make_conn(self):
        database = Path(f'./watchlists/{self._name}.db')
        engine = create_engine(f'sqlite:///{database}')
        session = sessionmaker(bind=engine)()

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

        self._conn.bulk_save_objects(users)
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

    def add_watchword(self, word):
        '''
        Add a search term to the watchwords.
        '''
        word = WatchwordsSQL(word=word)
        self._conn.merge(word)
        self._conn.commit()

    def remove_watchword(self, word):
        '''
        Remove a search term from the watchwords.
        '''
        word = self._conn.query(WatchwordsSQL).filter(
            WatchwordsSQL.word == word).first()
        self._conn.delete(word)
        self._conn.commit()

    def get_watchwords(self):
        '''
        Get the watchwords as a list.
        '''
        return [word.word for word in self._conn.query(WatchwordsSQL).all()]
