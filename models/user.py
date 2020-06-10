from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

BASE = declarative_base()


class FavoritesSQL(BASE):
    '''These are tweets. I hope you know that.'''
    __tablename__ = 'favorites'
    created_at = Column(DateTime)
    entities = Column(String)
    extended_entities = Column(String)
    favorite_count = Column(Integer)
    id = Column(Integer, primary_key=True)
    is_quote_status = Column(Boolean)
    lang = Column(String)
    possibly_sensitive = Column(Boolean)
    retweet_count = Column(Integer)
    source = Column(String)
    source_url = Column(String)
    text = Column(String)
    truncated = Column(Boolean)
    user_id = Column(Integer)
    screen_name = Column(String)
    name = Column(String)
    last_updated = Column(DateTime)


class TimelineSQL(BASE):
    '''These are tweets. I hope you know that.'''
    __tablename__ = 'timeline'
    created_at = Column(DateTime)
    entities = Column(String)
    extended_entities = Column(String)
    favorite_count = Column(Integer)
    id = Column(Integer, primary_key=True)
    is_quote_status = Column(Boolean)
    lang = Column(String)
    possibly_sensitive = Column(Boolean)
    retweet_count = Column(Integer)
    source = Column(String)
    source_url = Column(String)
    text = Column(String)
    truncated = Column(Boolean)
    retweet_user_id = Column(Integer)
    retweet_screen_name = Column(String)
    retweet_name = Column(String)
    user_id = Column(Integer)
    screen_name = Column(String)
    name = Column(String)
    last_updated = Column(DateTime)


class UsersSQL(BASE):
    '''These are users. I hope you know that.'''
    __tablename__ = 'users'
    contributors_enabled = Column(Boolean)
    created_at = Column(DateTime)
    default_profile = Column(Boolean)
    default_profile_image = Column(Boolean)
    description = Column(String)
    entities = Column(String)
    favorites_count = Column(Integer)
    followers_count = Column(Integer)
    friends_count = Column(Integer)
    geo_enabled = Column(Boolean)
    has_extended_profile = Column(Boolean)
    id = Column(Integer, primary_key=True)
    is_translation_enabled = Column(Boolean)
    is_translator = Column(Boolean)
    lang = Column(String)
    listed_count = Column(Integer)
    location = Column(String)
    name = Column(String)
    needs_phone_verification = Column(Boolean)
    profile_banner_url = Column(String)
    profile_image_url = Column(String)
    protected = Column(Boolean)
    screen_name = Column(String)
    statuses_count = Column(Integer)
    suspended = Column(Boolean)
    url = Column(String)
    verified = Column(Boolean)
    last_updated = Column(DateTime)


class FollowersSQL(BASE):
    __tablename__ = 'followers'
    id = Column(Integer, primary_key=True)
    last_updated = Column(DateTime)


class FriendsSQL(BASE):
    __tablename__ = 'friends'
    id = Column(Integer, primary_key=True)
    last_updated = Column(DateTime)
