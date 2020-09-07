'''
Model for a user's info, stores information of interest.
'''

import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from .helpers.custom_types import GUID

BASE = declarative_base()


class FavoritesSQL(BASE):
    '''
    Tweets this user has liked.
    '''
    __tablename__ = 'favorites'
    created_at = Column(DateTime)
    entities = Column(String)
    favorite_count = Column(Integer)
    tweet_id = Column(String, primary_key=True)
    is_quote_status = Column(Boolean)
    lang = Column(String)
    possibly_sensitive = Column(Boolean)
    retweet_count = Column(Integer)
    source = Column(String)
    source_url = Column(String)
    text = Column(String)
    user_id = Column(String)
    screen_name = Column(String)
    name = Column(String)
    last_updated = Column(DateTime)


class TimelineSQL(BASE):
    '''
    Tweets authored by this user and retweets.
    '''
    __tablename__ = 'timeline'
    created_at = Column(DateTime)
    entities = Column(String)
    favorite_count = Column(Integer)
    tweet_id = Column(String, primary_key=True)
    is_quote_status = Column(Boolean)
    lang = Column(String)
    possibly_sensitive = Column(Boolean)
    retweet_count = Column(Integer)
    source = Column(String)
    source_url = Column(String)
    text = Column(String)
    retweet_user_id = Column(String)
    retweet_screen_name = Column(String)
    retweet_name = Column(String)
    user_id = Column(String)
    screen_name = Column(String)
    name = Column(String)
    last_updated = Column(DateTime)


class UsersSQL(BASE):
    '''
    Stores the top level info for a user.
    '''
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


class FollowersSQL(BASE):
    '''
    Account user ids that follow this user.
    '''
    __tablename__ = 'followers'
    user_id = Column(String, primary_key=True)
    last_updated = Column(DateTime)


class FriendsSQL(BASE):
    '''
    Account user ids that the subject user follows.
    '''
    __tablename__ = 'friends'
    user_id = Column(String, primary_key=True)
    last_updated = Column(DateTime)


class TagsSQL(BASE):
    '''
    Store all unique tags.
    '''
    __tablename__ = 'tags'
    tag_id = Column(Integer, primary_key=True)
    text = Column(String)


class TimelineTagsSQL(BASE):
    '''
    Link timeline tweets to tags.
    '''
    __tablename__ = 'timeline_tags'
    tweet_id = Column(String, ForeignKey(
        'timeline.tweet_id'), primary_key=True)
    tag_id = Column(Integer, ForeignKey('tags.tag_id'), primary_key=True)

    # Relationships
    tag = relationship("TagsSQL")


class TimelineNotesSQL(BASE):
    '''
    Store notes about particular tweets.
    '''
    __tablename__ = 'timeline_notes'
    tweet_id = Column(String, ForeignKey(
        'timeline.tweet_id'), primary_key=True)
    note_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    text = Column(String)
    created_at = Column(DateTime)


class FavoritesTagsSQL(BASE):
    '''
    Association
    Link tweets to tags.
    '''
    __tablename__ = 'favorite_tags'
    tweet_id = Column(String, ForeignKey(
        'favorites.tweet_id'), primary_key=True)
    tag_id = Column(Integer, ForeignKey('tags.tag_id'), primary_key=True)

    # Relationships
    tag = relationship("TagsSQL")


class FavoritesNotesSQL(BASE):
    '''
    Store notes about particular tweets.
    '''
    __tablename__ = 'favorite_notes'
    tweet_id = Column(String, ForeignKey(
        'favorites.tweet_id'), primary_key=True)
    note_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    text = Column(String)
    created_at = Column(DateTime)


class UserNotesSQL(BASE):
    '''
    Store notes about the user.
    '''
    __tablename__ = 'user_notes'
    note_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    text = Column(String)
    created_at = Column(DateTime)


class ListMembershipsSQL(BASE):
    '''
    Twitter lists this user belongs to.
    '''
    __tablename__ = 'list_memberships'
    list_id = Column(String, primary_key=True)
    name = Column(String)
    last_updated = Column(DateTime)
