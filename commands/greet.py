import discord
from discord.ext import commands
import os
from commands.premiumsystem import Premium


class Greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command()
    async def greet(self, ctx):
        if await Premium.is_premium(ctx) == False:
            return
        await ctx.respond(f"Hello {ctx.author.mention}!")

def setup(bot):
    bot.add_cog(Greet(bot))