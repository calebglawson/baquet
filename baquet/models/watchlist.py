'''
Model for the watchlist.
Used to conveniently store keys for the information that we are interested in.
'''

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

BASE = declarative_base()


class WatchlistSQL(BASE):
    '''
    Twitter user ids of interest.
    '''
    __tablename__ = 'watchlist'
    contributors_enabled = Column(Boolean, nullable=True)
    created_at = Column(DateTime, nullable=True)
    default_profile = Column(Boolean, nullable=True)
    default_profile_image = Column(Boolean, nullable=True)
    description = Column(String, nullable=True)
    entities = Column(String, nullable=True)
    favorites_count = Column(Integer, nullable=True)
    followers_count = Column(Integer, nullable=True)
    friends_count = Column(Integer, nullable=True)
    geo_enabled = Column(Boolean, nullable=True)
    has_extended_profile = Column(Boolean, nullable=True)
    user_id = Column(String, primary_key=True)
    is_translation_enabled = Column(Boolean, nullable=True)
    is_translator = Column(Boolean, nullable=True)
    lang = Column(String, nullable=True)
    listed_count = Column(Integer, nullable=True)
    location = Column(String, nullable=True)
    name = Column(String, nullable=True)
    needs_phone_verification = Column(Boolean, nullable=True)
    profile_banner_url = Column(String, nullable=True)
    profile_image_url = Column(String, nullable=True)
    protected = Column(Boolean, nullable=True)
    screen_name = Column(String, nullable=True)
    statuses_count = Column(Integer, nullable=True)
    suspended = Column(Boolean, nullable=True)
    url = Column(String, nullable=True)
    verified = Column(Boolean, nullable=True)
    last_updated = Column(DateTime, nullable=True)

    sublists = relationship("UserSubListSQL")


class WatchwordsSQL(BASE):
    '''
    Twitter words, phrases, fragments of interest.
    '''
    __tablename__ = 'watchwords'
    regex = Column(String, primary_key=True)


class UserSubListSQL(BASE):
    '''
    User and sublist join.
    '''
    __tablename__ = 'user_sublists'
    user_id = Column(String, ForeignKey('watchlist.user_id'), primary_key=True)
    sublist_id = Column(Integer, ForeignKey(
        'sublists.sublist_id'), primary_key=True)
    locally_excluded = Column(Boolean, default=False)

    sublist = relationship("SubListSQL")
    user = relationship("WatchlistSQL")


class SubListSQL(BASE):
    '''
    Store external lists.
    '''
    __tablename__ = 'sublists'
    sublist_id = Column(Integer, primary_key=True)
    sublist_type_id = Column(
        Integer,
        ForeignKey('sublist_types.sublist_type_id')
    )
    name = Column(String)
    external_id = Column(String, nullable=True)

    sublist_type = relationship("SubListTypeSQL", lazy='joined')
    users = relationship("UserSubListSQL")


class SubListTypeSQL(BASE):
    '''
    The type of list.
    '''
    __tablename__ = 'sublist_types'
    sublist_type_id = Column(String, primary_key=True)
    name = Column(String)

    sublists = relationship("SubListSQL")
