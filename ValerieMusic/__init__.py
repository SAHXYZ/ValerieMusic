from ValerieMusic.core.bot import Valerie
from ValerieMusic.core.dir import dirr
from ValerieMusic.core.git import git
from ValerieMusic.core.userbot import Userbot
from ValerieMusic.misc import dbb, heroku

from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = Valerie()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
