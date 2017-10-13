import discord
from discord.ext import commands
from motor import motor_asyncio

import asyncio
import aiohttp
import sys, traceback
import logging
from configparser import ConfigParser
import contextlib
import datetime
import json
import pprint

try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop(uvloop)


loop = asyncio.get_event_loop()
dbc = motor_asyncio.AsyncIOMotorClient(minPoolSize=5)

token = ConfigParser()
token.read('mystconfig.ini')


async def get_prefix(b, msg):
    await b._cache_ready.wait()

    defaults = commands.when_mentioned_or(*['myst pls ', 'myst '])(b, msg)

    if msg is None:
        return 'myst '

    if msg.guild.id is None:
        return defaults

    dbp = dbc['prefix'][str(msg.guild.id)]

    if await dbp.find().count() <= 0:
        await dbp.insert_many([{'_id': 'myst '}, {'_id': 'myst pls '}])
        bot.prefix_cache[msg.guild.id] = ['myst ', 'myst pls ']
        return defaults
    else:
        prefixes = sorted(bot.prefix_cache[msg.guild.id], reverse=True)
        return commands.when_mentioned_or(*prefixes)(b, msg)

init_ext = ('cogs.admin',
            'cogs.utils.handler',
            'cogs.moderation',
            'cogs.music',
            'cogs.apis',
            'cogs.koth',
            'cogs.statistics')


class Botto(commands.Bot):

    def __init__(self):
        self.blocks = {}
        self.prefix_cache = {}
        self._help_pages = None
        self._pings = [50.01774800257408, 29.89222800169955, 44.42498899879865, 36.84222200172371, 35.571497999626445, 45.443006998539204, 33.487879001768306, 66.57888499830733, 33.36994900018908, 35.29522700046073, 31.773856997460825, 43.34650400051032, 32.8031569988525, 32.66923999763094, 31.82078100144281, 68.20176600012928, 43.63060799732921, 57.990918001451064, 34.25730600065435, 36.24774100171635, 30.210675999114756, 39.007198000035714, 185.20092499966267, 30.310000998724718, 39.73802900145529, 38.2035469992843, 47.90030300137005, 40.1160549990891, 31.471319998672698, 38.705088998540305, 80.91746300124214, 29.92860799713526, 97.90236299886601, 35.569780000514584, 49.79855500278063, 33.62358199956361, 35.23018300256808, 34.91269799997099, 32.99110500302049, 43.31034099959652, 43.047053997725016, 35.320733000844484, 83.20077000098536, 63.837006000539986, 32.88700099801645, 29.838228001608513, 43.34826899867039, 66.76578100086772, 49.23401300038677, 29.752033999102423, 59.08430500130635, 37.58925900183385, 37.52192400133936, 36.28490299888654, 179.8786100007419, 42.656910001824144, 35.60600100172451, 30.034190000151284, 31.02272000251105, 37.1993789995031]
        self._latest_ping = {}

        self.dbc = dbc
        self.session = None
        self.uptime = datetime.datetime.utcnow()
        self.appinfo = None

        self._cache_ready = asyncio.Event()

        super().__init__(command_prefix=get_prefix, description=None)

    async def _load_cache(self):
        self._cache_ready.clear()
        self.session = aiohttp.ClientSession(loop=loop)

        for guild in self.guilds:
            if await self.dbc['prefix'][str(guild.id)].find({}).count() <= 0:
                await self.dbc['prefix'][str(guild.id)].insert_many([{'_id': 'myst '}, {'_id': 'myst pls '}])
            self.prefix_cache[guild.id] = [p['_id'] async for p in self.dbc['prefix'][str(guild.id)].find({})]

        async for mem in dbc['owner']['blocks'].find({}):
            self.blocks[mem['_id']] = mem['name']

        self._cache_ready.set()

    async def fetch(self, url: str, headers: dict = None, timeout: float = None,
                    return_type: str = None, **kwargs):

        async with self.session.get(url, headers=headers, timeout=timeout, **kwargs) as resp:
            if return_type:
                cont = getattr(resp, return_type)
                return resp, await cont()
            else:
                return resp, None

    async def poster(self, url: str, headers: dict = None, timeout: float = None,
                     return_type: str = None, **kwargs):

        async with self.session.post(url, headers=headers, timeout=timeout, **kwargs) as resp:
            if return_type:
                cont = getattr(resp, return_type)
                return resp, await cont()
            else:
                return resp, None

    async def msg_reactor(self, message, *react):

        for r in react:
            try:
                await message.add_reaction(r)
            except:
                pass

    async def create_gist(self, description, files, pretty=False):

        if pretty:
            file_dict = {f[0]: {"content": pprint.pformat(f[1])} for f in files}
        else:
            file_dict = {f[0]: {"content": f[1]} for f in files}
        payload = {"description": description, "public": True, "files": file_dict}
        resp, respj = await self.poster('https://api.github.com/gists', data=json.dumps(payload), return_type='json')
        return respj['html_url']

bot = Botto()
bot.remove_command('help')


@contextlib.contextmanager
def setup_logging():
    try:
        logging.getLogger('discord').setLevel(logging.INFO)
        logging.getLogger('discord.http').setLevel(logging.INFO)
        logging.getLogger('myst').setLevel(logging.INFO)

        log = logging.getLogger()
        log.setLevel(logging.INFO)
        handler = logging.FileHandler(filename='myst.log', encoding='utf-8', mode='w')
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        fmt = logging.Formatter('[{asctime}] [{levelname:<7}] {name}: {message}', dt_fmt, style='{')
        handler.setFormatter(fmt)
        log.addHandler(handler)

        yield
    finally:
        handlers = log.handlers[:]
        for hdlr in handlers:
            hdlr.close()
            log.removeHandler(hdlr)


@bot.event
async def on_ready():

    await bot._load_cache()
    bot.appinfo = await bot.application_info()

    print(f'\n\nLogging in as: {bot.user.name} - {bot.user.id}\n')
    print(f'Version: {discord.__version__}\n')

    await bot.change_presence(game=discord.Game(name='💩', type=1, url='https://twitch.tv/evieerushu'))

    if __name__ == '__main__':
        for extension in init_ext:
            try:
                bot.load_extension(extension)
            except Exception as e:
                print(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()
    print(f'Successfully logged in and booted...!')

async def shutdown():

    log = logging.getLogger('myst')
    print('\n\nAttempting to logout and shutdown...\n')

    await dbc.fsync(lock=True)

    try:
        await bot.logout()
    except Exception as e:
        await dbc.unlock()
        msg = f'Attempt to Logout failed:: {type(e)}: {e}'
        log.critical(msg)
        return print(msg)

    await dbc.unlock()

    for x in asyncio.Task.all_tasks():
        try:
            x.cancel()
        except:
            pass

    print('Logged out... Closing down.')
    log.info(f'Clean Log-Out:: {datetime.datetime.utcnow()}')

    sys.exit(0)

with setup_logging():

    try:
        loop.run_until_complete(bot.start(token.get('TOKENALPHA', '_id'), bot=True, reconnect=True))
    except KeyboardInterrupt:
        loop.run_until_complete(shutdown())
