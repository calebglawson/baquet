'''
Output models to which we convert, so that SQLAlchemy models are not exposed.
'''


def load_model(data, model_class, many=False):
    '''
    Any object goes in, object specified comes out.
    '''
    return (
        [model_class(
            **{attr: getattr(child, attr) for attr in dir(child) if "__" not in attr}
        ) for child in data]
        if many else
        model_class(**{attr: getattr(data, attr)
                       for attr in dir(data) if "__" not in attr})
    )


class UserModel:
    '''
    Model representation of a User.
    '''

    def __init__(
            self,
            **kwargs,
    ):
        self.contributors_enabled = kwargs.get("contributors_enabled")
        self.created_at = kwargs.get("created_at")
        self.default_profile = kwargs.get("default_profile")
        self.default_profile_image = kwargs.get("default_profile_image")
        self.description = kwargs.get("description")
        self.entities = kwargs.get("entities")
        self.favorites_count = kwargs.get("favorites_count")
        self.followers_count = kwargs.get("followers_count")
        self.friends_count = kwargs.get("friends_count")
        self.geo_enabled = kwargs.get("geo_enabled")
        self.has_extended_profile = kwargs.get("has_extended_profile")
        self.user_id = kwargs.get("user_id")
        self.is_translation_enabled = kwargs.get("is_translation_enabled")
        self.is_translator = kwargs.get("is_translator")
        self.lang = kwargs.get("lang")
        self.listed_count = kwargs.get("listed_count")
        self.location = kwargs.get("location")
        self.name = kwargs.get("name")
        self.needs_phone_verification = kwargs.get("needs_phone_verification")
        self.profile_banner_url = kwargs.get("profile_banner_url")
        self.profile_image_url = kwargs.get("profile_image_url")
        self.protected = kwargs.get("protected")
        self.screen_name = kwargs.get("screen_name")
        self.statuses_count = kwargs.get("statuses_count")
        self.suspended = kwargs.get("suspended")
        self.url = kwargs.get("url")
        self.verified = kwargs.get("verified")
        self.last_updated = kwargs.get("last_updated")


class ListMembershipsModel:
    '''
    Model representation of a Twitter list membership.
    '''

    def __init__(
            self,
            **kwargs,
    ):
        self.list_id = kwargs.get("list_id")
        self.name = kwargs.get("name")
        self.last_updated = kwargs.get("last_updated")


class BasePaginatorModel:
    '''
    The base representation of a paginator.
    '''

    def __init__(
            self,
            **kwargs,
    ):
        self.has_next = kwargs.get("has_next")
        self.has_previous = kwargs.get("has_previous")
        self.next_page = kwargs.get("next_page")
        self.pages = kwargs.get("pages")
        self.previous_page = kwargs.get("previous_page")
        self.total = kwargs.get("total")


class UserPaginatorModel(BasePaginatorModel):
    '''
    User Paginator.
    '''

    def __init__(
            self,
            items,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.items = load_model(items, UserModel, many=True)


class NoteModel:
    '''
    Note representation.
    '''

    def __init__(
            self,
            **kwargs,
    ):
        self.tweet_id = kwargs.get("tweet_id")
        self.note_id = kwargs.get("note_id")
        self.text = kwargs.get("text")
        self.created_at = kwargs.get("created_at")


class NotePaginatorModel(BasePaginatorModel):
    '''
    Note paginator.
    '''

    def __init__(
            self,
            items,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.items = load_model(items, NoteModel, many=True)


class TagModel:
    '''
    Tag model.
    '''

    def __init__(
            self,
            **kwargs,
    ):
        self.tag_id = kwargs.get("tag_id")
        self.text = kwargs.get("text")


class TweetModel:
    '''
    Tweet model.
    '''

    def __init__(
            self,
            **kwargs,
    ):
        self.created_at = kwargs.get("created_at")
        self.entities = kwargs.get("entities")
        self.favorite_count = kwargs.get("favorite_count")
        self.tweet_id = kwargs.get("tweet_id")
        self.is_quote_status = kwargs.get("is_quote_status")
        self.lang = kwargs.get("lang")
        self.possibly_sensitive = kwargs.get("possibly_sensitive")
        self.retweet_count = kwargs.get("retweet_count")
        self.source = kwargs.get("source")
        self.source_url = kwargs.get("source_url")
        self.text = kwargs.get("text")
        self.retweet_user_id = kwargs.get("retweet_user_id")
        self.retweet_screen_name = kwargs.get("retweet_screen_name")
        self.retweet_name = kwargs.get("retweet_name")
        self.user_id = kwargs.get("user_id")
        self.screen_name = kwargs.get("screen_name")
        self.name = kwargs.get("name")
        self.last_updated = kwargs.get("last_updated")


class TweetPaginatorModel(BasePaginatorModel):
    '''
    Tweet paginator model.
    '''

    def __init__(
            self,
            items,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.items = load_model(items, TweetModel, many=True)


class BaseRelationshipModel:
    '''
    Either following or follower, base.
    '''

    def __init__(
            self,
            user=None,
            **kwargs,
    ):
        self.user = load_model(user, UserModel) if user else None
        self.user_id = kwargs.get("user_id")
        self.last_updated = kwargs.get("last_updated")


class RelationshipPaginatorModel(BasePaginatorModel):
    '''
    Relationship paginator.
    '''

    def __init__(
            self,
            items,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.items = load_model(items, BaseRelationshipModel, many=True)


class SublistTypeModel:
    '''
    Sublist type model.
    '''

    def __init__(
            self,
            **kwargs,
    ):
        self.sublist_type_id = kwargs.get("sublist_type_id")
        self.name = kwargs.get("name")


class SublistModel:
    '''
    Sublist model.
    '''

    def __init__(
            self,
            sublist_type,
            **kwargs,
    ):
        self.sublist_id = kwargs.get("sublist_id")
        self.sublist_type = load_model(sublist_type, SublistTypeModel)
        self.name = kwargs.get("name")
        self.external_id = kwargs.get("external_id")
