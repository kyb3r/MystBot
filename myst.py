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
            'cogs.apis')


class Botto(commands.Bot):

    def __init__(self):
        self.session = None
        self.blocks = {}
        self.prefix_cache = {}
        self.dbc = dbc
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
