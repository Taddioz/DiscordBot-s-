"""
Todd Pieper
Created on Mon-Jul-17-2024
Last edited: Sun-Jul-23-2024
Implemented using discord.py API - https://discordpy.readthedocs.io/en/latest/index.html
All work done here is my own, I do not give permission for one to copy and use it.
Uploading all work to my GitHub ---
"""

"""
OVERVIEW
Discord bot written in Python to be able to play the game "SecretHitler" with friends.
Does not have a dedicated server to run so it is only run locally on my machine.
Rules and inspirations taken from --- https://www.secrethitler.com/assets/Secret_Hitler_Rules.pdf
Uses lots of imagery consisting of several different screenshots taken from a table top simulator version of this
game created by steam user "LostGod" link to game here  https://steamcommunity.com/sharedfiles/filedetails/?id=681382159
"""
import discord
import generalVariables as GameInformation
from generalFunctions import getname as getname
import asyncNonCommands as Game
from discord.ext import commands



intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')


# Call $start when ready to begin a game, calling $start does not automatically make you join the game
@bot.command()
async def start(ctx):
    if Game.gameActive:

        if Game.gameStarted:
            await ctx.send("Game has already started")
        else:
            await ctx.send("Game hasn't started, check if there is still room to join using \"$join\" ")
    else:

        worked = await Game.JoinSequence(ctx)
        if not worked:  # true if enough people joined, false if not
            return

        else:
            await ctx.send("Yippee! We have enough players, let's get started")
            await Game.TheGameSequence(ctx)


# available for a small-time period once $start has been invoked, will put you on the game list and the game will begin
# if enough players join
@bot.command()
async def join(ctx):

    cur_author = ctx.author
    person = getname(cur_author)

    if not Game.gameActive:
        await ctx.send("You can't use $join without creating a game first " + person + ", stupid baka")
        return

    if cur_author in GameInformation.playerList:
        await ctx.send(person + ", you are already in the game!")
        return

    if Game.gameStarted:
        await ctx.send('Sorry, the game already started')
        await ctx.send("Better luck next time " + person)
        return

    if GameInformation.playerCount == 10:
        await ctx.send("Sorry, game is full!")
        return

    GameInformation.playerList.append(ctx.author)
    GameInformation.playerCount += 1
    await ctx.send(person + " has joined the game [" + str(GameInformation.playerCount) + "/" + str(10) + "]")


# embedded link to a rule page this bot based its features on
@bot.command()
async def rules(ctx):
    embed = discord.Embed()
    embed.description = "[Rules page](https://www.secrethitler.com/assets/Secret_Hitler_Rules.pdf)"
    await ctx.send(embed=embed)


# display seating order, does not work if game has not started
@bot.command()
async def seating(ctx):
    await Game.SeatingChart(ctx)


# display board state
@bot.command()
async def board(ctx):
    await Game.BoardState(ctx)


# shutdown only I can use
@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.bot.close()


# view what you ChancellorProfile would look like if you were to be voted on
@bot.command()
async def ViewChanceCard(ctx):
    ChosenCandidate = ctx.author
    pfp = ChosenCandidate.avatar
    if pfp is None:  # default
        pfp = ("https://images-ext-1.discordapp.net/external/ajAF5AMiCpYHipGTTPkcu0Xw4ScWQnS9XEkZ7BKcEXE/%3Fsize%3D1024"
               "/https/cdn.discordapp.com/avatars/928812928000462868/f01e69f0d4b3776c36afdc9c96b218b7.png?format=webp&q"
               "uality=lossless&width=426&height=426")
    CandidateEmbed = discord.Embed(title="Chancellor Candidate, {}".format(getname(ChosenCandidate)),
                                   description="React with \'✅\' to vote JA, or react with \'❌\' to vote NEIN",
                                   color=0x003333FF)
    CandidateEmbed.set_image(url=pfp)
    await ctx.send(embed=CandidateEmbed)



token = 'BLAHBLAHBLAH' # Not sharing my bot's token on github sorry
bot.run(GameInformation.token)
