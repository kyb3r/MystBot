import discord
from discord.ext import commands


class Colour:

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='colour', aliases=['color', 'col'])
    async def show_colour(self, ctx, colour: str):

        if ctx.message.mentions:
            colour = ctx.message.mentions[0].colour
        else:
            colour = colour.strip('#').strip('0x').replace(' ', ',')

        base = 'http://www.thecolorapi.com/id?format=json&hex={}'
        basep = 'http://www.colourlovers.com/api/palettes?hex={}&format=json'

        if ',' in colour:
            rgb = tuple(map(int, colour.split(',')))
            for x in rgb:
                if x < 0 or x > 255:
                    return await ctx.send('You have entered an invalid colour. Try entering a Hex-Code or R,G,B')
            colour = '%02x%02x%02x' % rgb

        url = base.format(colour)
        urlp = basep.format(colour)

        try:
            resp, data = await self.bot.fetch(url, return_type='json')
        except:
            return await ctx.send('There was a problem with the request. Please try again.')
        else:
            if resp.status > 300:
                return await ctx.send('There was a problem with the request. Please try again.')

        try:
            data['code']
        except KeyError:
            pass
        else:
            return await ctx.send('You have entered an invalid colour. Try entering a Hex-Code or R,G,B')

        try:
            resp, datap = await self.bot.fetch(urlp, return_type='json')
        except:
            image = f'https://dummyimage.com/300/{data["hex"]["clean"]}.png'
            colours = None
        else:
            image = datap[0]['imageUrl']
            colours = datap[0]['colors']

        emcol = f"0x{data['hex']['clean']}"
        embed = discord.Embed(title=f'Colour - {data["name"]["value"]}', colour=int(emcol, 0))
        embed.set_thumbnail(url=f'https://dummyimage.com/150/{data["hex"]["clean"]}.png')
        embed.set_image(url=image)
        embed.add_field(name='HEX', value=f'{data["hex"]["value"]}')
        embed.add_field(name='RBG', value=f'{data["rgb"]["value"]}')
        embed.add_field(name='HSL', value=f'{data["hsl"]["value"]}')
        embed.add_field(name='HSV', value=f'{data["hsv"]["value"]}')
        embed.add_field(name='CMYK', value=f'{data["cmyk"]["value"]}')
        embed.add_field(name='XYZ', value=f'{data["XYZ"]["value"]}')
        if colours:
            embed.add_field(name='Scheme:', value=' | '.join(colours), inline=False)

        await ctx.send(content=None, embed=embed)


def setup(bot):
    bot.add_cog(Colour(bot))
