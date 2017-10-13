import discord
from discord.ext import commands

import io
import traceback
import textwrap
from contextlib import redirect_stdout

from .utils.paginators import SimplePaginator, HelpPaginator


class Admin:

    def __init__(self, bot):
        self.bot = bot
        self.db = self.bot.dbc['owner']

    @commands.command(name='load', hidden=True)
    @commands.is_owner()
    async def cog_load(self, ctx, *, cog: str):
        """Command which Loads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='unload', hidden=True)
    @commands.is_owner()
    async def cog_unload(self, ctx, *, cog: str):
        """Command which Unloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    async def cog_reload(self, ctx, *, cog: str):
        """Command which Reloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.unload_extension(cog)
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.group(name='block')
    @commands.is_owner()
    async def bot_blocks(self, ctx):
        pass

    @bot_blocks.command(name='add')
    @commands.is_owner()
    async def block_add(self, ctx, member: discord.Member):

        if member.id in self.bot.blocks:
            return await ctx.send(f'**{member}** has already been blocked.')

        await self.db['blocks'].insert_one({'_id': member.id,
                                            'name': str(member)})
        self.bot.blocks[member.id] = str(member)

        await ctx.send(f'I have added **{member}** to my block list.')

    @bot_blocks.command(name='remove', aliases=['delete'])
    @commands.is_owner()
    async def block_remove(self, ctx, member: discord.Member):

        if member.id not in self.bot.blocks:
            return await ctx.send(f'**{member}** is not currently blocked.')

        await self.db['blocks'].delete_one({'_id': member.id})
        del self.bot.blocks[member.id]

        await ctx.send(f'I have removed **{member}** from my block list')

    @bot_blocks.command(name='list', aliases=['show'])
    async def block_list(self, ctx):

        if len(self.bot.blocks) <= 0:
            return await ctx.send('No users are currently blocked.')

        pages = SimplePaginator(title='Blocked List:',
                                colour=0xe52b2b,
                                prepend='**`',
                                append='`**',
                                bot=self.bot,
                                ctx=ctx,
                                entries=tuple(self.bot.blocks.values()))
        await pages.embed_creator()

    @commands.command(name='help', hidden=True)
    async def help_paginator(self, ctx):
        # todo
        helpy = HelpPaginator(bot=self.bot, ctx=ctx)

        await helpy.help_generator()


class Eval:

    def __init__(self, bot):
        self.bot = bot

    def cleanup_code(self, content):
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])
        return content.strip('` \n')

    def get_syntax_error(self, e):
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}: {e}```'

    @commands.command(name='eval', hidden=True)
    @commands.is_owner()
    async def _eval(self, ctx, *, body: str):

        env = {
            'bot': ctx.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': ctx.bot._last_result,
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        code = textwrap.indent(body, '  ')
        to_compile = f'async def func():\n{code}'

        try:
            exec(to_compile, env)
        except SyntaxError as e:
            return await ctx.send(self.get_syntax_error(e))

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('🔘')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                ctx.bot._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')


def setup(bot):
    bot._last_result = None
    bot.add_cog(Eval(bot))
    bot.add_cog(Admin(bot))
