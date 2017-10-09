import discord
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







