import discord
from discord.ext import commands
from cogs.utils.paginators import SimplePaginator
import datetime
import asyncio


class KothHandler:

    def __init__(self, bot):
        self.bot = bot
        self.db = self.bot.dbc['koth']['entries']
        self.dba = self.bot.dbc['koth']['auths']
        self.dbc = self.bot.dbc['koth']['channels']
        self.dbd = self.bot.dbc['koth']['dst']
        self.bot.loop.create_task(self.koth_loop())

        self._times = ('30', '00')
        self._dst = None

    async def koth_loop(self):
        self.bot.wait_until_ready()

        _dst = await self.dbd.find_one({'_id': '_dst'})
        if _dst is None:
            await self.dbd.update_one({'_id': '_dst'}, {'$set': {'dst': False}}, upsert=True)
        self._dst = _dst['dst']

        if not hasattr(self.bot, 'koth_start'):
            self.bot.koth_start = datetime.datetime.utcnow()

        while not self.bot.is_closed():

            if self._dst is True:
                dtime = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
            else:
                dtime = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

            if dtime.strftime('%M') in self._times:
                dtimes = []
                t30 = dtime + datetime.timedelta(minutes=30)
                t60 = dtime + datetime.timedelta(minutes=60)
                t30s = t30.strftime('%Y-%m-%d %H%M')
                t60s = t60.strftime('%Y-%m-%d %H%M')
                dtimes.extend([t30s, t60s])

                if await self.db.find({}).count() <= 0:
                    pass
                else:
                    entries = []
                    async for entry in self.db.find({}):
                        if entry['datetime'] in dtimes:
                            entries.append(entry)
                        if entry['datetime'] == dtime.strftime('%Y-%m-%d %H%M'):
                            entries.append(entry)
                            self.db.delete_many({'_id': entry['_id']})

                    if entries:
                        self.bot.loop.create_task(self.koth_announcer(t30, t60, dtime, entries))

            if int(dtime.strftime('%S')) > 30 or int(dtime.strftime('%S')) == 00:
                await asyncio.sleep(40)
            else:
                await asyncio.sleep(60)

    async def koth_announcer(self, t30, t60, dtime, entries):

        for entry in entries:
            info = await self.dbc.find_one({'_id': entry['gid']})

            if not info:
                return

            try:
                thumb = info['image']
            except:
                thumb = 'https://i.imgur.com/4Voqzou.jpg'

            embed = discord.Embed(colour=0xFF0000, title='KoTH Announcement',
                                  description='All times in **Dofus Time**\n\n')
            embed.set_thumbnail(url=thumb if thumb else 'https://i.imgur.com/4Voqzou.jpg')

            if entry['time'] == dtime.strftime('%H%M'):
                embed.add_field(name='Starting Now:', value=f'{entry["name"]} | {entry["pos"]}\n'
                                                            f'```css\n{entry["info"]}\n```')
            elif entry['time'] == t30.strftime('%H%M'):
                embed.add_field(name='Starting in 30 Minutes:', value=f'{entry["name"]} | {entry["pos"]}\n'
                                                                      f'```css\n{entry["info"]}\n```')
            elif entry['time'] == t60.strftime('%H%M'):
                embed.add_field(name='Starting in 60 Minutes:', value=f'{entry["name"]} | {entry["pos"]}\n'
                                                                      f'```css\n{entry["info"]}\n```')

            channel = self.bot.get_channel(int(info['channel']))

            try:
                await channel.send(content='@here - KoTH Announcement!', embed=embed)
            except Exception as e:
                print(e)

    @commands.group(name='koth', invoke_without_command=True)
    async def kgroup(self, ctx):
        pass

    @kgroup.command(name='login', aliases=['setlogin'])
    @commands.has_permissions(manage_guild=True)
    async def koth_password(self, ctx, username: str, password: str):

        username = username.lower()

        try:
            await ctx.message.delete()
        except:
            pass

        if len(password) < 8:
            return await ctx.send('Please enter a password that is at least **8** characters long.', delete_after=10)

        authg = await self.dba.find_one({'_id': ctx.guild.id})
        authp = await self.dba.find_one({'username': username})

        if authg:
            return await ctx.send('You already have a login set for this guild.', delete_after=10)

        if authp:
            return await ctx.send('This username is currently taken. Please try again.')

        await self.dba.insert_one({'_id': ctx.guild.id, 'password': password, 'username': username})
        await ctx.send('I have successfully set your username and password.', delete_after=10)

        try:
            await ctx.author.send(f'`Here are your KoTH Login details:`\n\n'
                                  f'**Username:**  {username}\n'
                                  f'**Password:**  {password}\n\n'
                                  f'`Please keep them safe!`')
        except:
            pass

    @kgroup.command(name='list')
    async def koth_list(self, ctx, password: str=None):

        entries = []

        pipe = [{'$sort': {'_id': 1}}]
        async for entry in self.db.aggregate(pipeline=pipe):
            if not password:
                if entry['gid'] == ctx.guild.id:
                    fmt = f'{entry["name"]} - {entry["pos"]} | `[{entry["datetime"]}]`'
                    entries.append(fmt)

        if not entries:
            return await ctx.send('You currently have no entries.')

        pages = SimplePaginator(title='KoTH List:',
                                ctx=ctx, bot=self.bot,
                                colour=0xCC3232,
                                entries=entries,
                                prepend='**•** - ',
                                append='',
                                footer=f'Valid for {ctx.guild}',
                                length=5)
        await pages.embed_creator()

    @kgroup.command(name='channels')
    @commands.has_permissions(manage_channels=True)
    async def koth_channel(self, ctx, channel: discord.TextChannel):

        try:
            await self.dbc.update_one({'_id': ctx.guild.id}, {'$set': {'channel': channel.id}}, upsert=True)
        except Exception as e:
            return print(e)

        await ctx.send(f'I have added {channel.mention} to your KoTH Announcement channels.')

    @kgroup.command(name='dst')
    @commands.has_permissions(manage_channels=True)
    async def koth_dst(self, ctx, dst: str):

        if dst.lower() == 'true':
            self._dst = True
            await self.dbd.update_one({'_id': '_dst'}, {'$set': {'dst': True}}, upsert=True)
        elif dst.lower() == 'false':
            self._dst = False
            await self.dbd.update_one({'_id': '_dst'}, {'$set': {'dst': False}}, upsert=True)
        else:
            return await ctx.send('Invalid. Enter either True or False.')

        await ctx.send(f'I have set DST to: {dst.upper()}.')

    @kgroup.command(name='image')
    @commands.has_permissions(manage_guild=True)
    async def koth_image(self, ctx, img: str):

        if not img.startswith('http'):
            return await ctx.send('This is not a valid image url.')
        else:
            await self.dbc.update_one({'_id': ctx.guild.id}, {'$set': {'image': img}}, upsert=True)

        await ctx.send('I have set your image.')


def setup(bot):
    bot.add_cog(KothHandler(bot))
