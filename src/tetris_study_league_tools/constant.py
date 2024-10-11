from re import compile

from yarl import URL

BASE_URL = URL('https://ch.tetr.io/api/')

USER_ID = compile(r'^[a-f0-9]{24}$')
USER_NAME = compile(r'^[a-zA-Z0-9_-]{3,16}$')
