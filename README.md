# `baquet`
A library to make analyzing associations between Twitter users easier for humans.

## Easy Start Guide
Get a Twitter API key and copy your tokens to `config.json` in your project's working directory.

```
from baquet.user import User
from baquet.watchlist import Watchlist
```

A `User` is a single Twitter user. You can use many get methods to get information about a user, `baquet` will talk to Twitter for you and preserve the data in its own cache. Users are instantiated with their unique Twitter id. If you don't have them handy, `baquet` provides the `screen_names_to_user_ids()` helper method for you.

```
u = User(8392018391)
for tweet in u.get_timeline():
  print(tweet.text)
```

A `Watchlist` is a collection of Twitter users and words that you are interested in searching for within individual user's data.

```
wl = Watchlist("look_at_all_the_people")
wl.add_watchlist(76589457843)
```

This returns all the favorited (liked) tweets of this user that were authored by users on the watchlist.

```
u.get_favorites(watchlist=wl)
```

`baquet` can do many more things for you. Have fun, and happy exploring!
