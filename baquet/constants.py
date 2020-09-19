'''
Module in which constants are kept.
'''


class BaquetConstants():
    '''
    Constants are, well... constant.
    '''
    USER = "user"
    DIRECTORY = "directory"
    CACHE = "cache"
    WATCHLIST = "watchlist"
    WATCHWORDS = "watchwords"
    FAVORITE = "favorite"
    TIMELINE = "timeline"
    RETWEET = "retweet"

    # SUBLIST TYPES
    SUBLIST_TYPE_SELF = 1
    SUBLIST_TYPE_TWITTER = 2
    SUBLIST_TYPES_BLOCKBOT = 3

    # CONFIGS
    CONFIG_CONSUMER_KEY = 'consumer_key'
    CONFIG_CONSUMER_SECRET = 'consumer_secret'
    CONFIG_ACCESS_TOKEN = 'access_token'
    CONFIG_ACCESS_TOKEN_SECRET = 'access_token_secret'

    # PATHS
    PATH_CONFIG = './config.json'

    # ATTRS
    ATTR_ID_STR = 'id_str'
    ATTR_ID = 'id'
    ATTR_USER_ID = 'user_id'
    ATTR_FAVORITES_COUNT = 'favorites_count'
    ATTR_NEEDS_PHONE_VERIFICATION = 'needs_phone_verification'
    ATTR_PROFILE_BANNER_URL = 'profile_banner_url'
    ATTR_SUSPENDED = 'suspended'
    ATTR_POSSIBLY_SENSITIVE = 'possibly_sensitive'
    ATTR_ENTITIES = 'entities'
    ATTR_RETWEETED_STATUS = 'retweeted_status'
