'''
Model for the watchlist.
Used to conveniently store keys for the information that we are interested in.
'''

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

BASE = declarative_base()


class WatchlistSQL(BASE):
    '''
    Twitter user ids of interest.
    '''
    __tablename__ = 'watchlist'
    user_id = Column(Integer, primary_key=True)


class WatchwordsSQL(BASE):
    '''
    Twitter words, phrases, fragments of interest.
    '''
    __tablename__ = 'watchwords'
    regex = Column(String, primary_key=True)
