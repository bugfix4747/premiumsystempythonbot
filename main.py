import discord
from discord.ext import commands
import os
from colorama import Fore
import json

bot = commands.Bot(intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(Fore.LIGHTGREEN_EX + f"✅ㅤ| {bot.user.display_name} is successfully loaded")


def cogs():
    for file in os.listdir(r"commands"):
        if file.endswith(".py"):

            extension = file.replace(".py", "")
            try:
                bot.load_extension(f"commands.{extension}")
                print(Fore.LIGHTMAGENTA_EX + f"🟧ㅤ| Load {file[:-3]}.py")
            except Exception as error:
                print(error)


def main():
    with open(r"config.json") as fh:
        bot.config = json.load(fh)
    bot.run(bot.config["token"])


if __name__ == "__main__":
    cogs()
    main()