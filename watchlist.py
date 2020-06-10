from pathlib import Path
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.sql import func
from datetime import datetime

from models.watchlist import BASE, WatchlistSQL, WatchwordsSQL


class Watchlist:
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

    def add_watchlist(self, user):
        user = WatchlistSQL(id=user.get_user_id())
        self._conn.merge(user)
        self._conn.commit()

    def add_watchword(self, word):
        word = WatchwordsSQL(word=word)
        self._conn.merge(word)
        self._conn.commit()

    def remove_watchlist(self, user):
        user = self._conn.query(WatchlistSQL).filter(
            WatchlistSQL.id == user.get_user_id()).first()
        self._conn.delete(user)
        self._conn.commit()

    def remove_watchword(self, word):
        word = self._conn.query(WatchwordsSQL).filter(
            WatchwordsSQL.word == word).first()
        self._conn.delete(word)
        self._conn.commit()

    def get_watchlist(self):
        return [user.id for user in self._conn.query(WatchlistSQL).all()]

    def get_watchwords(self):
        return [word.word for word in self._conn.query(WatchwordsSQL).all()]
