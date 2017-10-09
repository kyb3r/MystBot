import discord
from discord.ext import commands

import inspect
import textwrap
import datetime

from cogs.utils.paginators import SimplePaginator
from cogs.utils.enums import Perms


class Moderation:

    def __init__(self, bot):
        self.bot = bot
        self.dbp = self.bot.dbc['prefix']

    @commands.group(name='prefix', invoke_without_command=True)
    async def prefix(self, ctx):
        pass

    @prefix.command(name='add', aliases=['set'])
    @commands.has_permissions(manage_guild=True)
    async def add_prefix(self, ctx, *, pre: str):
        """Add a Prefix to Mysterial specific to your Server.

        Wrap your prefix in quotes if you would like to allow for spaces, as Discord
        Strips any whitespace at the end of the message."""

        prefix = pre.strip('"').strip("'")

        if await self.dbp[str(ctx.guild.id)].find_one({'_id': prefix}):
            return await ctx.send(f'You already have the prefix **{prefix}** assigned.')

        await self.dbp[str(ctx.guild.id)].insert_one({'_id': prefix})

        try:
            self.bot.prefix_cache[ctx.guild.id].append(prefix)
        except:
            self.bot.prefix_cache[ctx.guild.id] = [prefix]

        await ctx.send(f'I have added **{prefix}** to my assigned prefixes.')

    @add_prefix.error
    async def prefix_add_handle(self, ctx, error):

        if isinstance(error, commands.CheckFailure):
            await ctx.send('`You need [Manage Server] permissions to use this command.`', delete_after=15)

    @prefix.command(name='delete', aliases=['remove', 'del', 'rem'])
    @commands.has_permissions(manage_guild=True)
    async def del_prefix(self, ctx, *, pre: str):
        """Remove a prefix assigned to me specific to your Server."""

        prefix = pre.strip("'").strip('"')

        opre = await self.dbp[str(ctx.guild.id)].find_one({'_id': prefix})

        if opre is None:
            return await ctx.send(f'I have not been assigned the prefix: {prefix}\nPlease try again.')

        await self.dbp[str(ctx.guild.id)].delete_many({'_id': prefix})
        self.bot.prefix_cache[ctx.guild.id].remove(prefix)

        await ctx.send(f'I have removed **{prefix}** from my assigned prefixes.')

    @prefix.command(name='list', aliases=['all'])
    @commands.guild_only()
    async def list_prefix(self, ctx):
        """Lists the prefixes assigned to me, specific to your Server."""

        _prefix = '\n'.join(['myst pls ', 'myst '])

        if await self.dbp[str(ctx.guild.id)].find().count() <= 0:
            return await ctx.send(f'**My assigned prefixes for your server:**\n\n{_prefix}')

        prefixes = [x['_id'] async for x in self.dbp[str(ctx.guild.id)].find()]

        pages = SimplePaginator(title='Prefixes',
                                ctx=ctx, bot=self.bot,
                                colour=0x886aff,
                                entries=prefixes,
                                prepend='**•** - ',
                                append='',
                                footer='You may also mention me.')
        await pages.embed_creator()

    @commands.command(name='prefixes')
    @commands.guild_only()
    async def get_prefixes(self, ctx):
        """Lists the prefixes assigned to me, specific to your Server."""

        await ctx.invoke(self.list_prefix)

    @prefix.command(name='reset', aliases=['drop', 'bomb', 'purge'])
    @commands.has_permissions(manage_guild=True)
    async def reset_prefix(self, ctx):
        """Removes all but the default prefixes assigned to me for your Server."""

        if await self.dbp[str(ctx.guild.id)].find().count() <= 0:
            return await ctx.send('Your server has no custom prefixes to purge.')

        try:
            await self.dbp[str(ctx.guild.id)].drop()
            await self.dbp[str(ctx.guild.id)].insert_many([{'_id': 'myst pls '}, {'_id': 'myst '}])
        except:
            return await ctx.send('There was an error purging. Please try again later.')

        self.bot.prefix_cache[ctx.guild.id] = ['myst ', 'myst pls ']
        await ctx.send('I have purged all my assigned prefixes. You can now use the defaults.')

    @commands.command(name='source', aliases=['sauce'])
    @commands.is_owner()
    async def get_source(self, ctx, *, command: str):
        """Posts the source code of a command or cod."""

        cmd = self.bot.get_command(command)
        if cmd is not None:
            code = inspect.getsource(cmd.callback)
            code = textwrap.dedent(code).replace('`', '\uFEFF`')
        else:
            cog = self.bot.get_cog(command)
            if cog is None:
                return await ctx.send(f'I could not find the command or cog: **{command}**')
            code = inspect.getsource(cog.__class__)
            code = textwrap.dedent(code).replace('`', '\uFEFF')

        if len(code) > 1990:
            gist = await self.bot.create_gist(self.bot.session, f'Source for {command}', [(f'{command}.py', code)])
            return await ctx.send(f'**Your requested source was too large... So I have uploaded it to Gist.**\n{gist}')

        await ctx.send(f'```py\n{code}\n```')

    @commands.command(name='perms', aliases=['perms_for', 'permissions'])
    @commands.guild_only()
    async def check_permissions(self, ctx, *, member: discord.Member=None):
        """A simple command which checks a members Guild Permissions."""

        if not member:
            member = ctx.author

        perms = '\n'.join(p.name for p in sorted(Perms[str(perm)]
                                                 for perm, value in member.guild_permissions if value))
        permsf = '\n'.join(p.name for p in sorted(Perms[str(perm)]
                                                  for perm, value in member.guild_permissions if not value))
        embed = discord.Embed(title='Permissions for:', description=ctx.guild.name, colour=member.colour)
        embed.set_author(icon_url=member.avatar_url, name=str(member))
        embed.add_field(name='Allowed', value=perms)
        embed.add_field(name='Denied', value=permsf if permsf else 'None')

        await ctx.send(content=None, embed=embed)

    @commands.command(name='purge', aliases=['clear'])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def purge_messages(self, ctx, limit: int=10, member: discord.Member=None):
        """Purge all messages within the provided limit.
         limit : The number of messages to check.
         member : The member whos messages should be removed."""

        def check(message):
            return member.id == message.author.id

        purged = await ctx.channel.purge(limit=limit, check=check if member else None)
        if member:
            await ctx.send(f'Purged **{len(purged)}** messages belonging to **{member.display_name}**', delete_after=10)
        else:
            await ctx.send(f'Purged **{len(purged)}** messages.', delete_after=10)

    @commands.command(name='botclear', aliases=['bclear'])
    @commands.has_permissions(manage_permissions=True)
    @commands.guild_only()
    async def botpurge_messages(self, ctx, limit: int=100, ago: int=None):

        if limit > 101:
            return await ctx.send('Limit can not be more than **101**.')

        def check(message):
            return self.bot.user.id == message.author.id

        if ago:
            around = datetime.datetime.utcnow() - datetime.timedelta(hours=ago)
        else:
            around = datetime.datetime.utcnow()

        htime = around.strftime('%d/%m/%Y - %H:%M')

        purged = await ctx.channel.purge(limit=limit, check=check, around=around)
        await ctx.send(f'Purged **{len(purged)}** messages from myself around `{htime} UTC`.')


def setup(bot):
    bot.add_cog(Moderation(bot))
