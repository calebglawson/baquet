'''
Directory of users in the users folder, used for quick lookups.
'''

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base

BASE = declarative_base()


class DirectorySQL(BASE):
    '''
    Stores the top level info for a user in the user folder.
    '''
    __tablename__ = 'directory'
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
    user_id = Column(String, primary_key=True)
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


class CacheSQL(BASE):
    '''
    Ephemeral store of every user ever encountered.
    '''
    __tablename__ = 'cache'
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
    user_id = Column(String, primary_key=True)
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
