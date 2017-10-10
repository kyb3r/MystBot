import discord
from discord.ext import commands
import asyncio


class SimplePaginator:

    def __init__(self, bot, ctx, title: str, colour, length: int=10, entries: list or tuple=None, pairs: dict=None,
                 prepend='', append='', desc: str=None, footer: str='\uFEFF', inner: str=''):
        self.bot = bot
        self.ctx = ctx
        self.title = title
        self.colour = colour
        self.length = length
        self.entries = entries
        if pairs:
            self.pairs = tuple(pairs.items())
            self.desc = desc
        else:
            self.pairs = None
            self.desc = None
        self.prepend = prepend
        self.append = append
        self.footer = footer
        self.inner = inner

        self.formatted = []
        self.pages = []

        self.current = 0
        self.controls = {'⏮': 'reset',
                         '◀': -1,
                         '⏹': 'stop',
                         '▶': +1,
                         '⏭': 'end'}
        self.controller = None

    @staticmethod
    def pager(entries, chunk: int):
        for x in range(0, len(entries), chunk):
            yield entries[x:x + chunk]

    async def stop_controller(self, message):

        try:
            await message.delete()
        except:
            pass

        del self.pages
        del self.formatted

        try:
            return self.controller.cancel()
        except:
            return

    async def react_controller(self, length: int, message, author):

        def check(r, u):

            if str(r) not in self.controls.keys():
                return False

            if u.id == self.bot.user.id or r.message.id != message.id:
                return False

            if u.id != author.id:
                return False

            return True

        while True:

            try:
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=60)
            except asyncio.TimeoutError:
                return await self.stop_controller(message)

            control = self.controls.get(str(react))

            try:
                await message.remove_reaction(react, user)
            except:
                pass

            if control == 'reset':
                self.current = 0
            elif control == 'end':
                self.current = length - 1
            elif control == 'stop':
                return await self.stop_controller(message)
            elif control == -1:
                if self.current <= 0:
                    continue
                else:
                    self.current += control
            elif control == +1:
                if self.current >= length - 1:
                    continue
                else:
                    self.current += control

            try:
                await message.edit(embed=self.pages[self.current])
            except KeyError:
                continue

    async def embed_creator(self):

        entries = self.entries or self.pairs

        chunks = list(self.pager(entries, self.length))
        count = 0
        ine_count = 0

        if self.inner:
            splat = self.inner.split('+')

        if self.entries:
            for c in chunks:
                count += 1
                embed = discord.Embed(title=f'{self.title} - Page {count}/{len(chunks)}', colour=self.colour)
                for entry in c:
                    ine_count += 1
                    if self.inner:
                        self.inner = f'{splat[0]}{ine_count}{splat[1]}'
                    self.formatted.append('{0}{1}{2}{3}'.format(self.inner, self.prepend, entry, self.append))
                entries = '\n'.join(self.formatted)
                embed.description = entries
                embed.set_footer(text=self.footer)
                self.pages.append(embed)
                del self.formatted[:]
        else:
            for c in chunks:
                count += 1
                embed = discord.Embed(title=f'{self.title} - Page {count}/{len(chunks)}', colour=self.colour)
                for entry in c:
                    embed.add_field(name=entry[0], value='{0}{1}{2}'.format(self.prepend, entry[1], self.append),
                                    inline=False)
                    embed.set_footer(text=self.footer)
                self.pages.append(embed)

        message = await self.ctx.send(embed=self.pages[0])

        if len(self.pages) <= 1:
            await message.add_reaction('⏹')
        else:
            message = await self.ctx.send(embed=self.pages[0])
            for r in self.controls:
                try:
                    await message.add_reaction(r)
                except:
                    return

        self.controller = self.bot.loop.create_task(self.react_controller(length=len(self.pages),
                                                                          message=message,
                                                                          author=self.ctx.author))
        return


class HelpPaginator:
    """This is bad but I just want something done for now. Will fix up later."""

    def __init__(self, bot, ctx):
        self.bot = bot
        self.ctx = ctx
        self.colours = {'Music': 0xd02525, 'Moderation': 0xff8003, 'Colour': 0xdeadbf,
                        'Admin': 0xffffff, 'Eval': 0xffffff, 'KothHandler': 0xffffff}
        self.ignored = ('Eval', 'Admin', 'KothHandler', 'ErrorHandler',)

        self.current = 0
        self.controls = {'⏮': 'reset',
                         '◀': -1,
                         '⏹': 'stop',
                         '▶': +1,
                         '⏭': 'end'}
        self.controller = None
        self.pages = []

    async def help_generator(self):

        about = discord.Embed(title='Mysterial - Help',
                              description='For additional help and resources:\n\n'
                                          'Discord Server: [Here](http://discord.gg/Hw7RTtr)\n'
                                          'Mysterial Web:  [Here](http://mysterialbot.com/)\n\n'
                                          'To use the help command, simply with click on the reactions below.',
                              colour=0x8599ff)
        self.pages.append(about)

        coms = sorted((cog, self.bot.get_cog_commands(cog)) for cog in self.bot.cogs if self.bot.get_cog_commands(cog))
        for x in coms:
            if x[0] in self.ignored:
                continue
            cog = self.bot.get_cog(x[0])

            embed = discord.Embed(title=x[0], description=f'```ini\n{cog.__doc__}\n```', colour=self.colours[x[0]])
            embed.set_thumbnail(url='http://pngimages.net/sites/default/files/help-png-image-34233.png')
            for c in x[1]:
                if c.hidden:
                    continue
                try:
                    await c.can_run(self.ctx)
                except:
                    continue
                if isinstance(c, commands.Group):
                    grouped = '  \n'.join(com.name for com in c.commands)
                    embed.add_field(name=f'{c.name} - <Group>', value=f'{c.short_doc if c.short_doc else "Nothing"}'
                                                                      f'\n\n`{grouped}`')
                else:
                    embed.add_field(name=c.name, value=c.short_doc if c.short_doc else 'Nothing', inline=False)

            self.pages.append(embed)

        message = await self.ctx.send(embed=self.pages[0])
        for r in self.controls:
            try:
                await message.add_reaction(r)
            except:
                return

        self.controller = self.bot.loop.create_task(self.react_controller(length=len(self.pages),
                                                                          message=message,
                                                                          author=self.ctx.author))

    async def stop_controller(self, message):

        try:
            await message.delete()
        except:
            pass

        try:
            return self.controller.cancel()
        except:
            return

    async def react_controller(self, length: int, message, author):

        def check(r, u):

            if str(r) not in self.controls.keys():
                return False

            if u.id == self.bot.user.id or r.message.id != message.id:
                return False

            if u.id != author.id:
                return False

            return True

        while True:

            try:
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=90)
            except asyncio.TimeoutError:
                return await self.stop_controller(message)

            control = self.controls.get(str(react))

            try:
                await message.remove_reaction(react, user)
            except:
                pass

            if control == 'reset':
                self.current = 0
            elif control == 'end':
                self.current = length - 1
            elif control == 'stop':
                return await self.stop_controller(message)
            elif control == -1:
                if self.current <= 0:
                    continue
                else:
                    self.current += control
            elif control == +1:
                if self.current >= length - 1:
                    continue
                else:
                    self.current += control

            try:
                await message.edit(embed=self.pages[self.current])
            except KeyError:
                continue










