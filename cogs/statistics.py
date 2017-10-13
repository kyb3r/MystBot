import discord
from discord.ext import commands

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

import numpy as np
import itertools
import datetime
import asyncio

from concurrent.futures import ThreadPoolExecutor
import functools


matplotlib.use('Agg')


class Plots:
    """Commands which make graphs and other pretties."""

    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.grab_pings())
        self.threadex = ThreadPoolExecutor(max_workers=2)

    async def grab_pings(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            if len(self.bot._pings) >= 60:
                self.bot._pings.pop(0)

            self.bot._pings.append(self.bot.latency * 1000)
            await asyncio.sleep(60)

    def pager(self, entries, chunk: int):
        for x in range(0, len(entries), chunk):
            yield entries[x:x + chunk]

    def hilo(self, numbers, indexm: int=1):
        highest = [index * indexm for index, val in enumerate(numbers) if val == max(numbers)]
        lowest = [index * indexm for index, val in enumerate(numbers) if val == min(numbers)]

        return highest, lowest

    def get_times(self):
        fmt = '%H%M'
        current = datetime.datetime.utcnow()
        times = []
        times2 = []
        times3 = []
        tcount = 0

        rcurrent = current - datetime.timedelta(minutes=60)
        rcurrent2 = current - datetime.timedelta(minutes=30)
        for x in range(7):
            times.append(rcurrent + datetime.timedelta(minutes=tcount))
            tcount += 10

        tcount = 0
        for x in range(7):
            times2.append(rcurrent2 + datetime.timedelta(minutes=tcount))
            tcount += 5

        tcount = 0
        for t3 in range(26):
            times3.append(rcurrent + datetime.timedelta(minutes=tcount))
            tcount += 60/25

        times = [t.strftime(fmt) for t in times]
        times2 = [t.strftime(fmt) for t in times2]
        times3 = [t.strftime(fmt) for t in times3]

        return times, times2, times3, current

    def ping_plotter(self, data: (tuple, list)=None):

        # Base Data
        if data is None:
            numbers = self.bot._pings
        else:
            numbers = data

        long_num = list(itertools.chain.from_iterable(itertools.repeat(num, 2) for num in numbers))
        chunks = tuple(self.pager(numbers, 4))

        avg = list(itertools.chain.from_iterable(itertools.repeat(np.average(x), 8) for x in chunks))
        mean = [np.mean(numbers)] * 60
        prange = int(max(numbers)) - int(min(numbers))
        plog = np.log(numbers)

        t = np.sin(np.array(numbers) * np.pi*2 / 180.)
        xnp = np.linspace(-np.pi, np.pi, 60)
        tmean = [np.mean(t)] * 60

        # Spacing/Figure/Subs
        plt.style.use('ggplot')
        fig = plt.figure(figsize=(15, 7.5))
        ax = fig.add_subplot(2, 2, 2, axisbg='aliceblue', alpha=0.3)   # Right
        ax2 = fig.add_subplot(2, 2, 1, axisbg='thistle', alpha=0.2)  # Left
        ax3 = fig.add_subplot(2, 1, 2, axisbg='aliceblue', alpha=0.3)  # Bottom
        ml = MultipleLocator(5)
        ml2 = MultipleLocator(1)

        # Times
        times, times2, times3, current = self.get_times()

        # Axis's/Labels
        plt.title(f'Latency over Time(WebSocket) | {current} UTC')
        ax.set_xlabel(' ')
        ax.set_ylabel('Network Stability')
        ax2.set_xlabel(' ')
        ax2.set_ylabel('Milliseconds(ms)')
        ax3.set_xlabel('Time(HHMM)')
        ax3.set_ylabel('Latency(ms)')

        if min(numbers) > 100:
            ax3.set_yticks(np.arange(min(int(min(numbers)), 2000) - 100,
                                     max(range(0, int(max(numbers)) + 100)) + 50, max(numbers) / 12))
        else:
            ax3.set_yticks(np.arange(min(0, 1), max(range(0, int(max(numbers)) + 100)) + 50, max(numbers) / 12))

        # Labels
        ax.yaxis.set_minor_locator(ml2)
        ax2.xaxis.set_minor_locator(ml2)
        ax3.yaxis.set_minor_locator(ml)
        ax3.xaxis.set_major_locator(ml)

        ax.set_ylim([-1, 1])
        ax.set_xlim([0, np.pi])
        ax.yaxis.set_ticks_position('right')
        ax.set_xticklabels(times2)
        ax.set_xticks(np.linspace(0, np.pi, 7))
        ax2.set_ylim([min(numbers) - prange/4, max(numbers) + prange/4])
        ax2.set_xlim([0, 60])
        ax2.set_xticklabels(times)
        ax3.set_xlim([0, 120])
        ax3.set_xticklabels(times3, rotation=45)
        plt.minorticks_on()
        ax3.tick_params()

        highest, lowest = self.hilo(numbers, 2)

        mup = []
        mdw = []
        count = 0
        p10 = mean[0] * (1 + 0.5)
        m10 = mean[0] * (1 - 0.5)

        for x in numbers:
            if x > p10:
                mup.append(count)
            elif x < m10:
                mdw.append(count)
            count += 1

        # Axis 2 - Left
        ax2.plot(range(0, 60), list(itertools.repeat(p10, 60)), '--', c='indianred',
                 linewidth=1.0,
                 markevery=highest,
                 label='+10%')
        ax2.plot(range(0, 60), list(itertools.repeat(m10, 60)), '--', c='indianred',
                 linewidth=1.0,
                 markevery=highest,
                 label='+-10%')
        ax2.plot(range(0, 60), numbers, '-', c='blue',
                 linewidth=1.0,
                 label='Mark Up',
                 alpha=.8,
                 drawstyle='steps-post')
        ax2.plot(range(0, 60), numbers, ' ', c='red',
                 linewidth=1.0,
                 markevery=mup,
                 label='Mark Up',
                 marker='^')
        """ax2.plot(range(0, 60), numbers, ' ', c='green',
                 linewidth=1.0, markevery=mdw,
                 label='Mark Down',
                 marker='v')"""
        ax2.plot(range(0, 60), mean, label='Mean', c='blue',
                linestyle='--',
                linewidth=.75)
        ax2.plot(list(range(0, 60)), plog, 'darkorchid',
                 alpha=.9,
                 linewidth=1,
                 drawstyle='default',
                 label='Ping')

        # Axis 3 - Bottom
        ax3.plot(list(range(0, 120)), long_num, 'darkorchid',
                 alpha=.9,
                 linewidth=1.25,
                 drawstyle='default',
                 label='Ping')
        ax3.fill_between(list(range(0, 120)), long_num, 0, facecolors='darkorchid', alpha=0.3)
        ax3.plot(range(0, 120), long_num, ' ', c='indianred',
                 linewidth=1.0,
                 markevery=highest,
                 marker='^',
                 markersize=12)
        ax3.text(highest[0], max(long_num) - 10, f'{round(max(numbers))}ms', fontsize=12)
        ax3.plot(range(0, 120), long_num, ' ', c='lime',
                 linewidth=1.0,
                 markevery=lowest,
                 marker='v',
                 markersize=12)
        ax3.text(lowest[0], min(long_num) - 10, f'{round(min(numbers))}ms', fontsize=12)
        ax3.plot(list(range(0, 120)), long_num, 'darkorchid',
                 alpha=.5,
                 linewidth=.75,
                 drawstyle='steps-pre',
                 label='Steps')
        ax3.plot(range(0, 120), avg, c='forestgreen',
                 linewidth=1.25,
                 markevery=.5,
                 label='Average')

        # Axis - Right
        """ax.plot(list(range(0, 60)), plog1, 'darkorchid',
                 alpha=.9,
                 linewidth=1,
                 drawstyle='default',
                 label='Ping')
        ax.plot(list(range(0, 60)), plog2, 'darkorchid',
                 alpha=.9,
                 linewidth=1,
                 drawstyle='default',
                 label='Ping')
        ax.plot(list(range(0, 60)), plog10, 'darkorchid',
                 alpha=.9,
                 linewidth=1,
                 drawstyle='default',
                 label='Ping')"""

        ax.fill_between(list(range(0, 120)), .25, 1, facecolors='lime', alpha=0.2)
        ax.fill_between(list(range(0, 120)), .25, -.25, facecolors='dodgerblue', alpha=0.2)
        ax.fill_between(list(range(0, 120)), -.25, -1, facecolors='crimson', alpha=0.2)
        ax.fill_between(xnp, t, 1, facecolors='darkred')

        """ax.plot(list(range(0, 60)), t, 'darkred',
                linewidth=1.0,
                alpha=1,
                label='Stability')
        ax.plot(list(range(0, 60)), tmean, 'purple',
                linewidth=1.0,
                alpha=1,
                linestyle=' ')
        ax.plot(list(range(0, 60)), tp10, 'limegreen',
                linewidth=1.0,
                alpha=1,
                linestyle=' ')
        ax.plot(list(range(0, 60)), tm10, 'limegreen',
                linewidth=1.0,
                alpha=1,
                linestyle=' ')"""

        # Legend
        ax.legend(bbox_to_anchor=(.905, .97), bbox_transform=plt.gcf().transFigure)
        ax3.legend(loc='best', bbox_transform=plt.gcf().transFigure)

        # Grid
        ax.grid(which='minor')
        ax2.grid(which='both')
        ax3.grid(which='both')
        plt.grid(True, alpha=0.25)

        # Inverts
        ax.invert_yaxis()

        # File
        current = datetime.datetime.utcnow()
        save = current.strftime("%Y-%m-%d%H%M")

        plt.savefig(f'/pings/{save}', bbox_inches='tight')  # !!!VPS!!!
        self.bot._latest_ping[save] = f'/pings/{save}.png'  # !!!VPS!!!

        plt.clf()
        plt.close()
        return save

    @commands.command(name='wsping')
    async def _ping(self, ctx):
        """Ping. Shown as a pretty graph."""

        current = datetime.datetime.utcnow().strftime('%Y-%m-%d%H%M')

        if len(self.bot._pings) < 60:
            return await ctx.send(f'Latency: **`{self.bot.latency * 1000}`**')

        await ctx.channel.trigger_typing()
        try:
            pfile = self.bot._latest_ping[current]
            return await ctx.send(file=discord.File(pfile))
        except:
            pass

        getfile = functools.partial(self.ping_plotter)
        pfile = await self.bot.loop.run_in_executor(self.threadex, getfile)
        await ctx.send(file=discord.File(f'/pings/{pfile}.png'))  # !!!VPS!!!


def setup(bot):
    bot.add_cog(Plots(bot))
