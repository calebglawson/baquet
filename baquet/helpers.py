'''
A place to put code common to user and watchlist.
'''

import json
import re
from pathlib import Path
from datetime import datetime
from copy import copy

import tweepy

from .constants import BaquetConstants
from .models.user import (
    UsersSQL,
    TimelineSQL,
    FavoritesSQL,
)
from .models.directory import (
    DirectorySQL,
    CacheSQL,
)
from .models.watchlist import (
    WatchlistSQL
)


def make_config():
    '''
    Load the config from a file.
    '''
    config = open(Path(BaquetConstants.PATH_CONFIG))
    return json.load(config)


def make_api(config):
    '''
    Make a Tweepy api object.
    '''
    auth = tweepy.OAuthHandler(
        config.get(BaquetConstants.CONFIG_CONSUMER_KEY),
        config.get(BaquetConstants.CONFIG_CONSUMER_SECRET)
    )

    auth.set_access_token(
        config.get(BaquetConstants.CONFIG_ACCESS_TOKEN),
        config.get(BaquetConstants.CONFIG_ACCESS_TOKEN_SECRET)
    )

    api = tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True
    )

    return api


def filter_for_watchwords(results, watchwords):
    '''
    Filter a set of results that contain one or more search terms.
    '''
    matches = []
    for result in results:
        for regex in watchwords:
            if re.search(regex, result.text):
                matches.append(result)
                break
    return matches


def get_watchlist(watchlist, kind):
    '''
    Get either a list of watchwords or watchlist members.
    '''
    kind = kind.lower()
    if not isinstance(watchlist, list):
        if kind == BaquetConstants.WATCHLIST:
            return watchlist.get_watchlist()
        elif kind == BaquetConstants.WATCHWORDS:
            return watchlist.get_watchwords()
    return watchlist


def _transform_user_id(user):
    user_id = None

    if hasattr(user, BaquetConstants.ATTR_ID_STR):
        user_id = user.id_str
    elif hasattr(user, BaquetConstants.ATTR_ID):
        user_id = user.id
    elif hasattr(user, BaquetConstants.ATTR_USER_ID):
        user_id = user.user_id

    return user_id


def transform_user(user, kind):
    '''
    Take in an object and transform it to the target SQL Alchemy class.
    '''
    kind = kind.lower()

    if kind == BaquetConstants.USER:
        target_class = UsersSQL
    elif kind == BaquetConstants.DIRECTORY:
        target_class = DirectorySQL
    elif kind == BaquetConstants.CACHE:
        target_class = CacheSQL
    elif kind == BaquetConstants.WATCHLIST:
        target_class = WatchlistSQL
    else:
        return None

    return target_class(
        contributors_enabled=user.contributors_enabled,
        created_at=user.created_at,
        default_profile=user.default_profile,
        default_profile_image=user.default_profile_image,
        description=user.description,
        entities=user.entities if isinstance(
            user.entities,
            str
        ) else json.dumps(user.entities),
        favorites_count=user.favorites_count if hasattr(
            user,
            BaquetConstants.ATTR_FAVORITES_COUNT
        ) else user.favourites_count,
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
            user,
            BaquetConstants.ATTR_NEEDS_PHONE_VERIFICATION
        ) else None,
        profile_banner_url=user.profile_banner_url if hasattr(
            user,
            BaquetConstants.ATTR_PROFILE_BANNER_URL
        ) else None,
        profile_image_url=user.profile_image_url,
        protected=user.protected,
        screen_name=user.screen_name,
        statuses_count=user.statuses_count,
        suspended=user.suspended if hasattr(
            user,
            BaquetConstants.ATTR_SUSPENDED
        ) else None,
        url=user.url,
        verified=user.verified,
        last_updated=datetime.utcnow(),
    )


def transform_tweet(tweet, kind):
    '''
    Transforms an object to a SQLAlchemy model.
    '''
    kind = kind.lower()
    is_retweet = hasattr(tweet, BaquetConstants.ATTR_RETWEETED_STATUS)

    if kind == BaquetConstants.FAVORITE:
        return FavoritesSQL(
            created_at=tweet.created_at,
            entities=json.dumps(tweet.entities),
            favorite_count=tweet.favorite_count,
            tweet_id=tweet.id_str,
            is_quote_status=tweet.is_quote_status,
            lang=tweet.lang,
            possibly_sensitive=tweet.possibly_sensitive if hasattr(
                tweet,
                BaquetConstants.ATTR_POSSIBLY_SENSITIVE
            ) else False,
            retweet_count=tweet.retweet_count,
            source=tweet.source,
            source_url=tweet.source_url,
            text=tweet.full_text,
            user_id=tweet.author.id_str,
            screen_name=tweet.author.screen_name,
            name=tweet.author.name,
            last_updated=datetime.utcnow(),
        )

    return TimelineSQL(
        created_at=tweet.created_at,
        entities=json.dumps(tweet.entities),
        favorite_count=tweet.favorite_count,
        tweet_id=tweet.id_str,
        is_quote_status=tweet.is_quote_status,
        lang=tweet.lang,
        possibly_sensitive=tweet.possibly_sensitive if hasattr(
            tweet,
            BaquetConstants.ATTR_POSSIBLY_SENSITIVE
        ) else False,
        retweet_count=tweet.retweet_count,
        source=tweet.source,
        source_url=tweet.source_url,
        text=tweet.retweeted_status.full_text if is_retweet else tweet.full_text,
        retweet_user_id=tweet.retweeted_status.author.id_str if is_retweet else None,
        retweet_screen_name=tweet.retweeted_status.author.screen_name
        if is_retweet else None,
        retweet_name=tweet.retweeted_status.author.name if is_retweet else None,
        user_id=tweet.author.id_str,
        screen_name=tweet.author.screen_name,
        name=tweet.author.name,
        last_updated=datetime.utcnow(),
    )


def serialize_entities(item):
    '''
    When going from SQLAlchemy to JSON, serialize the entities.
    '''
    # Without copying, there's some SQLAlchemy weirdness.
    item = copy(item)
    if hasattr(item, BaquetConstants.ATTR_ENTITIES) and item.entities:
        item.entities = json.loads(item.entities)
    return item


def serialize_paginated_entities(page):
    '''
    For each page in the sqlalchemy paginator, serialize the entities.
    '''
    new_items = []
    for item in page.items:
        new_items.append(serialize_entities(item))
    page.items = new_items
    return page
