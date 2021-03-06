# `baquet`
A library to make analyzing associations between Twitter users easier for humans.

## Easy Start Guide
Get a Twitter API key and copy your tokens to `config.json` in your project's working directory.

```python
from baquet.user import User
from baquet.watchlist import Watchlist
```

A `User` is a single Twitter user. You can use many get methods to get information about a user, `baquet` will talk to Twitter for you and preserve the data in its own cache. You can specify the `cache_expiry` and the fetch `limit` when instantiating a user. Users are instantiated with their unique Twitter id. If you don't have any handy, `baquet` provides the `hydrate_user_identifiers()` helper method for you. Results are paginated with [sqlalchemy-pagination](https://github.com/wizeline/sqlalchemy-pagination).

```python
u = User(8392018391)

has_items = True
page = 1
while(has_next)
  result = u.get_timeline(page)
  for tweet in result.items:
    print(tweet.text)
  has_next = result.has_next
  page = result.next_page
```

A `Watchlist` is a collection of Twitter users and words that you are interested in searching for within individual user's data.

```python
wl = Watchlist("look_at_all_the_people")
wl.add_watchlist(76589457843)
wl.add_watchword("the")
```

The first statement returns all the favorited (liked) tweets of this user that were authored by users on the watchlist. The second statement returns all tweets and retweets from this user's timeline containing "the". The third statement calculates the percentage of their friends that are on the watchlist.

```python
u.get_favorites(watchlist=wl)
u.get_timeline(watchwords=wl)
u.get_friends_watchlist_percent(wl)
```

`baquet` can do many more things for you. Have fun, and happy exploring!
