from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

BASE = declarative_base()


class WatchlistSQL(BASE):
    __tablename__ = 'watchlist'
    id = Column(Integer, primary_key=True)


class WatchwordsSQL(BASE):
    __tablename__ = 'watchwords'
    word = Column(String, primary_key=True)
