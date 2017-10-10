import discord
from discord.ext import commands

import asyncio
import async_timeout
from concurrent.futures import ThreadPoolExecutor
import functools
import subprocess

import json
import datetime
import humanize
import math
import random
import logging
import uuid

import youtube_dl

from cogs.utils.paginators import SimplePaginator
from cogs.utils.handler import PlayerGarbageError

log = logging.getLogger('myst')


class SongsProcessor:
    def __init__(self, ctx, player, search: str):
        self.ctx = ctx
        self.player = player
        self.search = search
        self.mproc = None
        self.failed = 0
        self.opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{ctx.guild.id}/{self.outtmpl_seed()}%(extractor)s_%(id)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'playlistend': 50,
            'progress_hooks': [self.ytdl_hook]
        }
        self.ytdl = youtube_dl.YoutubeDL(self.opts)
        self.ytdl_ef = youtube_dl.YoutubeDL(self.opts)

        self.threadex = ThreadPoolExecutor(max_workers=4)
        self.bg_ext = self.ctx.bot.loop.create_task(self.extractor())

    def outtmpl_seed(self):
        ytid = str(uuid.uuid4()).replace('-', '')
        return str(int(ytid, 16))

    def get_duration(self, url):

        cmd = f'ffprobe -v error -show_format -of json {url}'
        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        data = json.loads(output)
        duration = data['format']['duration']

        return math.ceil(float(duration))

    def ytdl_hook(self, x):
        if x['status'] == 'error':
            log.info(f'SongProcessor:: YTDL: Error while downloading song with: ({self.search} - [{self.ctx.guild.id}]')

    async def extractor(self):
        await self.ctx.bot.wait_until_ready()

        self.ytdl_ef.params['extract_flat'] = True
        dlf = functools.partial(self.ytdl_ef.extract_info, download=False, url=self.search)
        info = await self.ctx.bot.loop.run_in_executor(self.threadex, dlf)

        if 'entries' in info:
            return await self.downloader(length=len(info['entries']))
        else:
            return await self.downloader(length=1)

    async def downloader(self, length: int):

        await self.ctx.channel.trigger_typing()

        if length > 1:
            self.mproc = \
                await self.ctx.send(f'```ini\n[Processing your songs. Playlists may take some time | 0/{length}]\n```')

        for v in range(1, length + 1):

            if self.ctx.guild.voice_client is None:
                return self.bg_ext.cancel()

            try:
                self.ytdl.params.update({'playlistend': v, 'playliststart': v})
                dlt = functools.partial(self.ytdl.extract_info, download=True, url=self.search)
                info = await self.ctx.bot.loop.run_in_executor(self.threadex, dlt)
            except Exception as e:
                if length <= 1:
                    return await self.ctx.send(f'**There was an error downloading your song.**\n```css\n[{e}]\n```')
                else:
                    self.failed += 1
                    continue

            if 'entries' in info:
                info = info['entries'][0]

            duration = info.get('duration') or self.get_duration(info.get('url'))
            song_info = {'title': info.get('title'),
                         'weburl': info.get('webpage_url'),
                         'duration': duration,
                         'views': info.get('view_count'),
                         'thumb': info.get('thumbnail'),
                         'requester': self.ctx.author,
                         'upload_date': info.get('upload_date', '\uFEFF')}
            file = self.ytdl.prepare_filename(info)

            while self.player.shuffling:
                await asyncio.sleep(1)

            await self.player.queue.put({'source': file, 'info': song_info, 'channel': self.ctx.channel})

            try:
                await self.mproc.edit(
                    content=f'```ini\n[Processing your songs. Playlists may take some time | {v}/{length}]\n```')
            except:
                pass

        if self.failed == 0 and length > 1:
            await self.ctx.send(f'```ini\n[Added your songs to the Queue]\n```', delete_after=30)
        elif self.failed != 0 and length > 1:
            await self.ctx.send(f'```ini\n[Added your songs to the Queue]\n```\n```css\n'
                                f'[{self.failed} songs failed to download.]\n```', delete_after=30)
        else:
            await self.ctx.send(f'```ini\n[Added: {song_info["title"]} to the playlist.]\n```', delete_after=30)

        if self.mproc:
            try:
                await self.mproc.delete()
            except:
                pass


class Player:
    def __init__(self, bot, guild, channel, mcls):
        self.bot = bot
        self.guild = guild
        self.channel = channel
        self.mcls = mcls

        self.player_task = self.bot.loop.create_task(self.player_loop())
        self.queue = asyncio.Queue()
        self._next = asyncio.Event()
        self.held_entry = []

        self._volume = 0.5
        self.playing = None
        self.playing_info = None
        self.requester = None
        self.paused = None
        self.downloading = None
        self.shuffling = None
        self.controls = {'▶': 'resume',
                         '⏸': 'pause',
                         '⏹': 'stop',
                         '⏭': 'skip',
                         '🔀': 'shuffle',
                         '🔂': 'repeat',
                         '➕': 'vol_up',
                         '➖': 'vol_down',
                         'ℹ': 'queue'}
        self.controller = None
        self.skips = set()
        self.pauses = set()
        self.resumes = set()
        self.shuffles = set()

    @property
    def volume(self):
        return self._volume

    async def player_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self._next.clear()

            try:
                with async_timeout.timeout(300):
                    entry = await self.queue.get()
                    del self.held_entry[:]
                    self.held_entry.append(entry)
            except asyncio.TimeoutError:
                if self.downloading:
                    continue
                await self.channel.send('I have been inactive for **5** minutes. Goodbye.', delete_after=30)
                return await self.mcls.cleanup(self.guild, self.player_task, self)

            self.playing_info = entry['info']
            self.requester = entry['info']['requester']
            self.channel = entry['channel']

            self.guild.voice_client.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(entry['source']),
                                                                      volume=self._volume),
                                         after=lambda s: self.bot.loop.call_soon_threadsafe(self._next.set()))

            await self.now_playing(entry['info'], entry['channel'])
            await self._next.wait()

            self.playing_info = None
            self.requester = None
            self.skips.clear()
            self.pauses.clear()
            self.resumes.clear()
            self.shuffles.clear()

    async def now_playing(self, info, channel):

        try:
            info['title']
        except:
            return

        embed = discord.Embed(title='Now Playing:', description=info['title'], colour=0xDB7093)
        embed.set_thumbnail(url=info['thumb'] if info['thumb'] is not None else 'http://i.imgur.com/EILyJR6.png')
        embed.add_field(name='Requested by', value=info['requester'].mention)
        embed.add_field(name='Video URL', value=f"[Click Here!]({info['weburl']})")
        embed.add_field(name='Duration', value=str(datetime.timedelta(seconds=int(info['duration']))))
        embed.add_field(name='Queue Length', value=f'{self.queue.qsize()}')
        if self.queue.qsize() > 0:
            upnext = self.queue._queue[0]['info']
            embed.add_field(name='Up Next', value=upnext['title'], inline=False)
        embed.set_footer(text=f'🎶 | Views: {humanize.intcomma(info["views"])} |'
                              f' {info["upload_date"] if not None else ""}')

        async for message in channel.history(limit=1):
            if self.playing is None or message.id != self.playing.id and message.author.id != self.bot.user.id:

                try:
                    await self.playing.delete()
                except:
                    pass
                finally:
                    self.playing = None

                self.playing = await self.channel.send(content=None, embed=embed)

                for r in self.controls:
                    try:
                        await self.playing.add_reaction(r)
                    except:
                        return

                if self.controller is not None:
                    garbage = self.controller
                    try:
                        garbage.cancel()
                    except Exception as e:
                        await channel.send(
                            f'**Error in Player Garbage Collection:: Please terminate and restart the player.**'
                            f'```css\n[{type(e)}] - [{e}]\n```')

                        return await self.mcls.cleanup(self.guild, self.player_task, self, failed=(type(e), e))
                self.controller = self.bot.loop.create_task(self.react_controller())
            else:
                try:
                    await self.playing.edit(content=None, embed=embed)
                except:
                    pass

    async def react_controller(self):
        vc = self.guild.voice_client

        def check(r, u):

            if not self.playing:
                return False

            if str(r) not in self.controls.keys():
                return False

            if u.id == self.bot.user.id or r.message.id != self.playing.id:
                return False

            if u not in vc.channel.members:
                return False

            return True

        while self.playing:

            if vc is None:
                self.controller.cancel()
                return

            react, user = await self.bot.wait_for('reaction_add', check=check)
            control = self.controls.get(str(react))

            try:
                await self.playing.remove_reaction(react, user)
            except:
                pass

            try:
                cmd = self.bot.get_command(control)
                ctx = await self.bot.get_context(react.message)
                ctx.author = user
            except Exception as e:
                log.warning(f'PLAYER:: React Controller: {e} - [{self.guild.id}]')
            else:
                try:
                    if cmd.is_on_cooldown(ctx):
                        continue
                    if not await self.invoke_react(cmd, ctx):
                        continue
                    else:
                        self.bot.loop.create_task(ctx.invoke(cmd))
                except Exception as e:
                    ctx.command = self.bot.get_command('reactcontrol')
                    await cmd.dispatch_error(ctx=ctx, error=e)
                    continue

    async def invoke_react(self, cmd, ctx):

        if not cmd._buckets.valid:
            return True

        if not (await cmd.can_run(ctx)):
            return False

        bucket = cmd._buckets.get_bucket(ctx)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return False
        return True


class Music:
    """Music related commands for Mysterial.

    For music to work properly, the bot must be able to Embed.
    It is advisable to allow the bot remove reactions and manage messages."""

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.threadex = ThreadPoolExecutor(max_workers=4)

    async def cleanup(self, guild, task, player, failed: tuple = None):

        vc = guild.voice_client

        try:
            await player.playing.delete()
        except:
            pass

        try:
            vc._connected.clear()
            try:
                if vc.ws:
                    await vc.ws.close()

                await vc.terminate_handshake(remove=True)
            finally:
                if vc.socket:
                    vc.socket.close()
        except:
            pass

        try:
            task.cancel()
        except Exception as e:
            log.error(f'PLAYERCLEANUP:: CancelError: - [{type(e): {e}}]')

        del self.players[guild.id]

        if failed:
            raise PlayerGarbageError(failed[0], failed[1], guild)

    def get_player(self, ctx):

        player = self.players.get(ctx.guild.id)

        if player is None:
            player = Player(self.bot, ctx.guild, ctx.channel, self)
            self.players[ctx.guild.id] = player
        return player

    @commands.command(name='reactcontrol', hidden=True)
    @commands.guild_only()
    async def falsy_controller(self, ctx):
        pass

    @commands.command(name='nowplaying', aliases=['playing', 'current', 'currentsong', 'np'])
    @commands.cooldown(2, 30, commands.BucketType.guild)
    @commands.guild_only()
    async def now_playing(self, ctx):
        """Display the current song, and the reaction controller."""

        player = self.get_player(ctx)
        await player.now_playing(player.playing_info, ctx.channel)

    @commands.command(name='play', aliases=['sing'])
    @commands.guild_only()
    async def search_song(self, ctx, *, search: str):
        """Play a song. If no link is provided, Myst will search YouTube for the song."""

        vc = ctx.guild.voice_client

        if vc is not None:
            if ctx.author not in vc.channel.members:
                return await ctx.send(f'You must be in **{vc.channel}** to request songs.')

        if vc is None:
            await ctx.invoke(self.voice_connect)
            vc = ctx.guild.voice_client

        player = self.get_player(ctx)
        process = SongsProcessor

        try:
            await ctx.message.delete()
        except:
            pass

        process(ctx=ctx, player=player, search=search)

    @commands.command(name='join', aliases=['summon', 'move', 'connect'])
    @commands.cooldown(2, 60, commands.BucketType.user)
    @commands.has_permissions(move_members=True)
    @commands.guild_only()
    async def voice_connect(self, ctx, *, channel: discord.VoiceChannel = None):
        """Summon Myst to a channel. If she is another channel she will be moved."""

        vc = ctx.guild.voice_client

        if vc is not None:
            if channel is None:
                try:
                    await vc.move_to(ctx.author.voice.channel)
                    return await ctx.send(f'Moved to: **{ctx.author.voice.channel}**', delete_after=10)
                except Exception as e:
                    msg = await ctx.send(f'There was an error switching channels.\n'
                                         f'{type(e)}: {e}')
                    return
            else:
                try:
                    await vc.move_to(channel)
                    return await ctx.send(f'Moved to: **{channel}**', delete_after=10)
                except Exception as e:
                    msg = await ctx.send(f'There was an error switching channels.\n'
                                         f'{type(e)}: {e}')
                    return

        if channel is None and ctx.author.voice is None:
            msg = await ctx.send('You did not specify a Voice Channel, and you are not connected to one.',
                                 delete_after=30)
            return

        if channel is None:
            try:
                vc = await ctx.author.voice.channel.connect(timeout=30, reconnect=True)
                return await ctx.send(f'Connected to: **{vc.channel}**', delete_after=30)
            except asyncio.TimeoutError:
                msg = await ctx.send('There was an error connecting to voice. Please try again later.')
                return

        else:
            try:
                vc = await channel.connect(timeout=30, reconnect=True)
                return await ctx.send(f'Connected to: **{vc.channel}**')
            except asyncio.TimeoutError:
                msg = await ctx.send(f'There was an error connecting to: {channel}\n'
                                     f'Please try again later')
                return

    @commands.command(name='resume')
    @commands.guild_only()
    async def resume_song(self, ctx):
        """Resume the paused song."""

        player = self.get_player(ctx)
        vc = ctx.guild.voice_client
        requester = player.requester

        if ctx.message.id != player.playing.id:
            try:
                await ctx.message.delete()
            except:
                pass

        if not vc.is_paused():
            return

        elif vc is None:
            return await ctx.send('**I am not currently playing anything.**', delete_after=15)

        elif requester.id == ctx.author.id and len(vc.channel.members) <= 4:
            vc.resume()
            try:
                return await player.paused.edit(content=f'**{requester.mention} has resumed the song.**',
                                                delete_after=15)
            except:
                return

        elif ctx.author.guild_permissions.manage_guild:
            vc.resume()
            try:
                return await player.paused.edit(content=f'**{ctx.author.mention} has resumed the song as an admin.**',
                                                delete_after=15)
            except:
                return

        elif len(vc.channel.members) <= 3:
            vc.resume()
            try:
                return await player.paused.edit(content=f'**{ctx.author.mention} has resumed the song.**',
                                                delete_after=15)
            except:
                return

        elif ctx.author.id in player.resumes:
            return await ctx.send(f'**{ctx.author.mention} you have already voted to resume. 1 more votes needed.**',
                                  delete_after=15)

        player.resumes.add(ctx.author.id)

        if len(player.resumes) > 1:
            vc.resume()
            await ctx.send('**Vote to resume the song passed. Resuming...**', delete_after=15)
            player.resumes.clear()
            try:
                await player.paused.delete()
            except:
                pass
            finally:
                return

        await ctx.send(f'**{ctx.author.mention} has started a resume request. 1 more votes need to pass.**',
                       delete_after=20)

    @commands.command(name='pause')
    @commands.cooldown(2, 90, commands.BucketType.user)
    @commands.guild_only()
    async def pause_song(self, ctx):
        """Pause the current song."""

        player = self.get_player(ctx)
        vc = ctx.guild.voice_client
        requester = player.requester

        if ctx.message.id != player.playing.id:

            try:
                await ctx.message.delete()
            except:
                pass

        if vc.is_paused():
            return

        elif vc is None or not vc.is_playing():
            return await ctx.send('**I am not currently playing anything.**', delete_after=10)

        elif requester.id == ctx.author.id and len(vc.channel.members) <= 4:
            vc.pause()
            player.paused = await ctx.send(f'**{requester.mention} has paused the song.**')
            return

        elif ctx.author.guild_permissions.manage_guild:
            vc.pause()
            player.paused = await ctx.send(f'**{ctx.author.mention} has paused the song as an admin.**')
            return

        elif len(vc.channel.members) <= 3:
            vc.pause()
            player.paused = await ctx.send(f'**{ctx.author.mention} has paused the song.**')
            return

        elif ctx.author.id in player.pauses:
            return await ctx.send(f'**{ctx.author.mention} you have already voted to pause. 1 more votes needed.**',
                                  delete_after=15)

        player.pauses.add(ctx.author.id)

        if len(player.pauses) > 1:
            vc.pause()
            player.paused = await ctx.send('**Pause vote passed: Pausing the song.**')
            player.pauses.clear()
            return

        await ctx.send(f'**{ctx.author.mention} has started a pause request. 1 more votes need to pass.**',
                       delete_after=15)

    @commands.command(name='stop')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def stop_player(self, ctx):
        """Terminate the player and clear the Queue."""

        vc = ctx.guild.voice_client
        player = self.get_player(ctx)

        if vc is None:
            return await ctx.send('**I am not currently playing anything.**', delete_after=10)

        try:
            await player.playing.delete()
        except:
            pass

        await self.cleanup(ctx.guild, player.player_task, player)
        await ctx.send(f'Player has been terminated by {ctx.author.mention}. **Goodbye.**', delete_after=30)

    @stop_player.error
    async def stop_error(self, ctx, error):

        if isinstance(error, commands.CheckFailure):
            await ctx.send('You need **`[Manage Server]`** permissions to stop the player.', delete_after=20)

    @commands.command(name='shuffle', aliases=['mix'])
    @commands.cooldown(1, 180, commands.BucketType.user)
    @commands.guild_only()
    async def shuffle_songs(self, ctx):
        """Shuffle all songs in your Queue."""

        vc = ctx.guild.voice_client
        player = self.get_player(ctx)

        if vc is None:
            return await ctx.send('**I am not currently playing anything.**', delete_after=20)

        elif player.downloading:
            return await ctx.send('**Please wait for your songs to finish downloading**', delete_after=15)

        elif player.queue.qsize() <= 2:
            return await ctx.send('**Please add more songs to the Queue before shuffling.**', delete_after=15)

        elif ctx.author.guild_permissions.manage_guild:
            await self.do_shuffle(ctx, player)
            return await ctx.send(f'**{ctx.author.mention} has shuffled the playlist as an admin.**', delete_after=20)

        elif len(vc.channel.members) <= 3:
            await self.do_shuffle(ctx, player)
            return await ctx.send(f'**{ctx.author.mention} has shuffled the playlist.**', delete_after=20)

        elif ctx.author.id in player.shuffles:
            return await ctx.send(f'**{ctx.author.mention} you have already voted to shuffle. 1 more votes needed.**',
                                  delete_after=15)

        player.shuffles.add(ctx.author.id)

        if len(player.shuffles) > 1:
            await ctx.send('**Shuffle vote passed: Shuffling the playlist.**', delete_after=20)
            await self.do_shuffle(ctx, player)
            player.shuffles.clear()
            return

        await ctx.send(f'**{ctx.author.mention} has started a shuffle request. 1 more votes need to pass.**',
                       delete_after=20)

    async def do_shuffle(self, ctx, player):

        shuf = []

        while not player.queue.empty():
            shuf.append(await player.queue.get())

        random.shuffle(shuf)

        for x in shuf:
            await player.queue.put(x)

        await ctx.invoke(self.now_playing)

    @commands.command(name='vol_up', hidden=True)
    @commands.cooldown(9, 60, commands.BucketType.user)
    @commands.guild_only()
    async def vol_up(self, ctx):
        """Turn the Volume Up!"""

        player = self.get_player(ctx)
        vc = ctx.guild.voice_client

        orig = int(player._volume * 100)
        vol_in = int(math.ceil((orig + 10) / 10.0)) * 10
        vol = float(vol_in) / 100

        if vol > 1.0:
            return await ctx.send('**Max volume reached.**', delete_after=5)

        try:
            vc.source.volume = vol
            player._volume = vol
        except AttributeError:
            await ctx.send('**I am not currently playing anything.**')

    @commands.command(name='vol_down', hidden=True)
    @commands.cooldown(9, 60, commands.BucketType.user)
    @commands.guild_only()
    async def vol_down(self, ctx):
        """Turn the Volume down."""

        player = self.get_player(ctx)
        vc = ctx.guild.voice_client

        orig = int(player._volume * 100)
        vol_in = int(math.ceil((orig - 10) / 10.0)) * 10
        vol = float(vol_in) / 100

        if vol < 0.1:
            return await ctx.send('**Minimum volume reached.**', delete_after=5)

        try:
            vc.source.volume = vol
            player._volume = vol
        except AttributeError:
            await ctx.send('**I am not currently playing anything.**')

    @commands.command(name='skip')
    @commands.cooldown(2, 60, commands.BucketType.user)
    @commands.guild_only()
    async def skip_song(self, ctx):
        """Skips the current song."""

        player = self.get_player(ctx)
        vc = ctx.guild.voice_client
        requester = player.requester

        if not player.playing:
            return

        if ctx.message.id != player.playing.id:

            try:
                await ctx.message.delete()
            except:
                pass

        if vc is None:
            return await ctx.send('**I am not currently playing anything.**', delete_after=10)

        elif requester.id == ctx.author.id and len(vc.channel.members) <= 4:
            vc.stop()
            return await ctx.send(f'**{requester.mention} has skipped the song.**', delete_after=10)

        elif ctx.author.guild_permissions.manage_guild:
            vc.stop()
            return await ctx.send(f'**{ctx.author.mention} has skipped the song as an admin.**', delete_after=10)

        elif len(vc.channel.members) <= 3:
            vc.stop()
            return await ctx.send(f'**{ctx.author.mention} has skipped the song.**', delete_after=10)

        req_skips = 1 if vc.channel.members == 1 \
            else 2 if 2 <= vc.channel.members <= 4 \
            else int(round(vc.channel.members / 5)) + 3

        need = req_skips - len(player.skips)

        if ctx.author.id in player.pauses:
            return await ctx.send(f'**{ctx.author.mention} you have already voted to skip. {need} more votes needed.**',
                                  delete_after=15)

        player.skips.add(ctx.author.id)

        if len(player.skips) >= req_skips:
            vc.stop()
            return await ctx.send('**Skip vote passed: Skipping the song.**', delete_after=10)

        await ctx.send(f'**{ctx.author.mention} has started a skip request. {need} more votes needed to pass.**',
                       delete_after=15)

    @commands.command(name='repeat', hidden=True)
    @commands.cooldown(3, 60, commands.BucketType.guild)
    @commands.guild_only()
    async def repeat_song(self, ctx):
        """Repeat the current song 1 time."""

        vc = ctx.guild.voice_client
        player = self.get_player(ctx)

        if not player.held_entry:
            return await ctx.send('**This song is already queued to repeat.**', delete_after=10)

        elif vc is None:
            return await ctx.send('**I am not currently playing anything.**', delete_after=10)

        await ctx.send(f'**{ctx.author.mention}: The current song will replay.**', delete_after=15)
        await self.do_repeat(ctx, player)

    async def do_repeat(self, ctx, player):

        player.shuffling = True

        while not player.queue.empty():
            player.held_entry.append(await player.queue.get())

        for x in player.held_entry:
            await player.queue.put(x)

        player.shuffling = False
        del player.held_entry[:]

        await ctx.invoke(self.now_playing)

    @commands.command(name='queue', aliases=['q', 'que', 'playlist'])
    @commands.cooldown(2, 90, commands.BucketType.user)
    @commands.guild_only()
    async def queue_info(self, ctx):
        """Display the Queue of songs."""

        player = self.get_player(ctx)
        vc = ctx.guild.voice_client

        if vc is None:
            return await ctx.send('**I am not currently playing anything.**', delete_after=10)

        elif player.queue.qsize() <= 0:
            return await ctx.send(f'```css\n[No other songs in the Queue.]\n```', delete_after=10)

        entries = [x["info"]["title"] for x in player.queue._queue]
        page = SimplePaginator(title='Playlist',
                               ctx=ctx,
                               bot=self.bot,
                               colour=0xDB7093,
                               entries=entries,
                               prepend=' - `',
                               append='`',
                               inner='**+**')
        await page.embed_creator()


def setup(bot):
    bot.add_cog(Music(bot))
