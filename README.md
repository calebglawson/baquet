# `baquet`
A library to make analyzing associations between Twitter users easier for humans.

## Easy Start Guide
Get a Twitter API key and generate your tokens, set them in `config.json` in your project's working directory.

```
from baquet.user import User
from baquet.watchlist import Watchlist
```

A `User` is a single Twitter user. You can use many get methods to get information about a user, `baquet` will talk to Twitter for you and preserve the data in its own cache.

```
u = User(8392018391)
for tweet in u.get_timeline():
  print(tweet.text)
```

A `Watchlist` is a collection of Twitter users and words that you are interested in searching for on an individual user.

```
wl = Watchlist("look_at_all_the_people")
wl.add_watchlist(76589457843)
```

This returns all the favorited (liked) tweets of this user that were authored by users on the watchlist.

```
u.get_favorites(watchlist=wl)
```

`baquet` can do many more things for you. Happy exploring!
