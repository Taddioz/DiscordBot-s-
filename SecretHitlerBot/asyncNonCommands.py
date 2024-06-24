"""
Todd Pieper
Created on Mon-Jul-17-2024
Last edited: Sun-Jul-23-2024
Implemented using discord.py API - https://discordpy.readthedocs.io/en/latest/index.html
All work done here is my own, I do not give permission for one to copy and use it.
Uploading all work to my GitHub ---
"""

import asyncio

import generalVariables as GameInformation
import random
import discord
import generalFunctions as Helper


# Role card file name strings
FCARD = 'FascistRoleCard.png'
LCARD = 'LiberalRoleCard.png'
HCARD = 'HitlerRoleCard.png'

# Game State Booleans for join sequence to determine if one can join
gameActive = False
gameStarted = False

# Constants for Join sequence
MIN_PLAYERS = 5
TIME_LIMIT_TO_JOIN = 30  # seconds

# Lists for vote tracking
VotedJa = []
VotedNein = []
DidNotVote = []

# Emojis to react to messages with and wait for to interpret results
EmojisOneToTen = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
EmojisCheckAndX = ["✅", "❌"]

# Dictionary for role distribution, key is number of players, first element in tuple is number of liberals,
# second is fascists, there is always only one hitler
roleDistribution = {
    5: (3, 1),
    6: (4, 1),
    7: (4, 2),
    8: (5, 2),
    9: (5, 3),
    10: (6, 4)
}

# Voting is simultaneous and done through asyncio tasks which work like threads, so when updating the global lists
# the tasks must acquire a lock to prevent losing information
VoteLock = asyncio.Lock()

# 'powerUsedToPickPresident' Used to inject the President chosen by special election power once,
# variable will be reverted back within election() call
powerUsedToPickPresident = "Used"
investigated = "Investigated"


# Initialized as Strings but will be eventually overwritten with a player. Used to display Previous President/Chancellor
# during election cycles, they are set after a successful election. Any function calls that are only called after a
# successful election will use these variables to refer to the current President/Chancellor duo
PrevPresident = "None"
PrevChancellor = "None"

# Generator function to retrieve the next player in the seating order when it is time for their chance to be President
# this function pulls from a player list that can change if a player is assassinated but this generator function will
# still work.
presidentGenerator = Helper.getNextPresident()



# JoinSequence
# Called with bot command "$start" Join Sequence starts a countdown timer displaying messages when the timer reaches
# intervals of 10 seconds and the last 5. It activates the game which opens up the "$join" command for players. The
# $join command handles counting the unique layers that join the game and upon time running out this function will
# determine if enough players have joined. If not, it will resset all variables and return false, if enough joined
# it will initialize the variables that depended on enough players and return true
async def JoinSequence(ctx):
    global gameActive
    gameActive = True
    await ctx.send("Game has started!!!! You have " + str(TIME_LIMIT_TO_JOIN) + " seconds to join up using \"$join\"")

    for num in range(TIME_LIMIT_TO_JOIN, 0, -1):
        if num % 10 == 0:
            await ctx.send(str(num) + " seconds left, hurry and join!")
        if num <= 5:
            await ctx.send(str(num))
        if num == 0:
            await ctx.send("Time is up!")
        await asyncio.sleep(1)

    if GameInformation.playerCount < MIN_PLAYERS:
        await ctx.send("Sorry, not enough players joined, you need at least " + str(MIN_PLAYERS)
                       + " players but I only counted " + str(GameInformation.playerCount))
        reset()
        return False

    init()
    return True


# TheGameSequence
# This function is the meat of the game. Super fast breakdown without explaining rules go! Shuffle player list to use as
# seating order for rest of game, shuffle the card deck, distribute roles to everyone, display seating order, store team
# strings immediately for end of game message later Start infinite loop of Election into Legislative into Executive
# sessions checking if any win condition is met when appropriate breaking the loop when one is met. Game is only over
# when loop is broken so display game result and show the teams after the loop and reset the variables incase a new game
# is started.
async def TheGameSequence(ctx):
    global gameStarted
    gameStarted = True
    random.shuffle(GameInformation.playerList)
    random.shuffle(GameInformation.deck)
    await DistributeRoles()
    await ctx.send("Here is the seating order (order in which President's will be in office) use "
                   "$seating to view again at any time.")
    await SeatingChart(ctx)
    legislativeSessionCount = 1
    electionSessionCount = 1
    TheTeams = Helper.genTeamString()
    while True:
        await ctx.send("------------------------------------------------------------")
        await ctx.send("ELECTION SESSION #" + str(electionSessionCount) + " HAS BEGUN")
        electionSessionCount += 1
        successfulElection = await ElectionSession(ctx)

        # Check for win-cons
        Results = CheckForWinConPostElection()
        if Results != 0:
            break

        powerGranted = await LegislativeSession(ctx, successfulElection, legislativeSessionCount)

        # Check for win-cons
        Results = Helper.CheckForWinConPostPolicyEnacting()
        if Results != 0:
            break

        legislativeSessionCount += 1

        Results = await ExecutiveSession(ctx, powerGranted)  # will be 0 if nothing happens, 4 if Hitler is assassinated
        if Results != 0:
            break

    await explainEndGame(ctx, Results, TheTeams)
    reset()


# ElectionSession
# Loop through at most 3 attempts to vote in a government, if successful return true, else return false. Legislative
# Session will handle chaos scenario (false returned). Successful elections will set PrevChancellor and PrevPresident
# for future reference as the most recently elected persons (also to be referenced as the current ones for functions
# like ExecutiveSession and its sub-functions
async def ElectionSession(ctx):
    global PrevPresident, PrevChancellor
    ElectionTracker = 0
    voteSucceeded = False
    while True:
        if powerUsedToPickPresident == "Used":
            President = next(presidentGenerator)
        else:
            President = powerUsedToPickPresident
        await newPresident(ctx, President)
        seatingMessage = await SeatingChart(ctx)
        await reactWithNumberedEmojis(seatingMessage, GameInformation.playerCount)

        def checkIfPresident(reaction, user):
            return user == President and str(reaction) in EmojisOneToTen[:GameInformation.playerCount]

        while True:
            try:
                reaction, user = await ctx.bot.wait_for('reaction_add', timeout=600.0, check=checkIfPresident)
            except asyncio.TimeoutError:
                await ctx.send("Timed out waiting for")
                ChosenCandidate = GameInformation.playerList[Helper.EmojiToIndex(
                    random.choice(EmojisOneToTen[:GameInformation.playerCount]))]
            else:
                ChosenCandidate = GameInformation.playerList[Helper.EmojiToIndex(reaction.emoji)]
            if ChosenCandidate == President:
                await ctx.send("You cannot elect yourself! Please try again")
            elif ChosenCandidate == PrevPresident and GameInformation.originalPlayerCount != 5:
                await ctx.send("You cannot elect the former President")
            elif ChosenCandidate == PrevChancellor:
                await ctx.send("You cannot elect the former Chancellor")
            else:
                await ctx.send(Helper.getname(President) + " has chosen " + Helper.getname(ChosenCandidate) +
                                " to be Chancellor, check your DM's and cast your votes")
                # true if vote passes, false if vote fails. Will also send vote information
                if await ChancellorVoteSequence(ctx, ChosenCandidate):
                    voteSucceeded = True
                    PrevPresident = President
                    PrevChancellor = ChosenCandidate
                else:
                    ElectionTracker += 1
                break

        if voteSucceeded:
            return True
        elif ElectionTracker == 3:  # Chaos scenario
            return False


# LegislativeSession
# If the government isn't in Chaos, send top three cards of the deck to the President who will discard one and send two
# to the chancellor. Chancellor will pick one to enact and this function will return an int that maps to any potential
# powers granted via the policy enacted. Unless vetoing is in place in which all cards may be discarded
# 0 is no power, the rest are noted in CheckForNewPower()'s notes
# If Chaos is in place, enact the top policy of the deck and ignore any possible powers resulting from it (return 0)
async def LegislativeSession(ctx, successfulElection, legislativeSessionCount):
    if successfulElection:
        # Successful election means variables PrevPresident and PrevChancellor have been set to the
        # current ones. Referencing them later means we can utilize them.
        await asyncio.sleep(2)  # small delay to pace things

        # Enact the law, shuffle in discard pile if needed, and display message + board state
        # If it's a Fascist Law check to see if any power has been granted, Helper returns 0 on no new
        # power and only gets called once
        await ctx.send("------------------------------------------------------------")
        await ctx.send("LEGISLATIVE SESSION #" + str(legislativeSessionCount) + " HAS BEGUN")
        await ctx.send("------------------------------------------------------------")
        policyToEnact = await sendThreeCards(ctx)
        if policyToEnact != "Vetoed":

            Helper.enactPolicy(policyToEnact)
            powerGranted = 0
            if policyToEnact == 'F':
                powerGranted = Helper.CheckForNewPower()

            await ctx.send("Chancellor " + Helper.getname(PrevChancellor) + " is enacting a "
                           + Helper.letterToFullName(policyToEnact) + " law.")
            await asyncio.sleep(3)
            await BoardState(ctx)

            if Helper.addDiscardPileIfNeeded():
                await ctx.send("SHUFFLING DISCARD PILE INTO DECK")
            await asyncio.sleep(2)  # pace things
            return powerGranted  # policy was enacted so we will return whatever power comes as a result, might be 0


        else:  # policy set was vetoed
            await ctx.send("POLICY SET WAS VETOED, ALL CARDS DISCARDED, BEGINNING NEXT ELECTION CYCLE")
            if Helper.addDiscardPileIfNeeded():
                await ctx.send("SHUFFLING DISCARD PILE INTO DECK")
            await asyncio.sleep(2)  # pace things

            # veto means no policy enacted, thus no new power. Regardless vetoing is only available after 5 fas policies
            # are enacted, so a liberal policy already can't give powers, and the next fascist one would end the game.
            # return 0 for no new power
            return 0

    else:  # Election unsuccessful for 3rd time, chaos scenario
        await ctx.send("GOVERNMENT HAS GONE INTO CHAOS, ENACTING TOP CARD OF DECK, ANY POWER IS IGNORED")
        policyToEnact = GameInformation.deck.pop(-1)
        Helper.enactPolicy(policyToEnact)
        await ctx.send("ENACTING A " + Helper.letterToFullName(policyToEnact) + " law.")
        await asyncio.sleep(3)
        await BoardState(ctx)

        # Powers granted via Chaos scenario are ignored, return 0
        return 0


# ExecutiveSession
# If a power is granted as a result of LegislativeSession, this will handle it accordingly. If any power is granted
# it MUST be used
async def ExecutiveSession(ctx, powerGranted):
    # Check if any powers are available
    if powerGranted != 0:
        await ctx.send("New Presidential Power is Being Granted!")
        match powerGranted:  # case 0 impossible here

            case 1:
                await investigateIdentity(ctx)
            case 2:
                await investigateIdentity(ctx)
            case 3:
                await peekAtTopThreeCards(ctx)
            case 4:
                await assassinatePlayer(ctx)
                return Helper.CheckForWinConPostAssassination()
            case 5:
                GameInformation.vetoPowerUnlocked = True
                await ctx.send("VETO POWER UNLOCKED BUT NOT IMPLEMENTED YET SOZ")
                await assassinatePlayer(ctx)
                return Helper.CheckForWinConPostAssassination()
    return 0  # if there was no power granted/power does not result in possible win condition, return 0


# distributeRoles
# Role distribution takes a list of players, assigns the first as Hitler, the next few as however many fascists there
# are (based on player count), and the rest are liberal. To prevent predictability of knowing who is assigned what,
# Role distribution is done by taking the player list (shuffled already for seating order), copying it and shuffling
# again using that list to decide roles. Thus, it does not necessarily correlate to the order which players joined/are
# seated (but it still could!)
async def DistributeRoles():
    randomizedList = GameInformation.playerList.copy()
    random.shuffle(randomizedList)
    await dmHitler(randomizedList)
    await dmFascists(randomizedList)
    await dmLiberals(randomizedList)


# dmHitler
# First person is hitler, so we can use index 0. Hitler will always be the first person in the fascistList
# Will send Hitler role card along with a message detailing number of allies as well as his objective,
# The only situation in which hitler gets to know who his fascist buddy is, is when there is only 1, if that's the case
# the additional information is appended to the message sent.
async def dmHitler(randomizedList):

    hitler = randomizedList[0]
    GameInformation.fascistList.append(hitler)
    numFascists = roleDistribution[GameInformation.playerCount][1]
    await hitler.send(file=discord.File(HCARD))
    hitlerInformation = "You are Hitler! You will be working together with " + str(numFascists) + (" Fascist(s) "
                        " who know who you are. You must work together with your fellow Fascist(s) to defeat the "
                        " liberals. You win by either enacting 6 Fascist policies, or by being elected Chancellor while"
                        " at least 3 Fascist policies have been enacted. Be careful not to get assassinated or to let"
                        " pesky liberals enact 5 Liberal Policies.")
    if numFascists == 1:
        hitlerInformation += ("\n You have only one ally, which means you get to know who they are! \n Fascist: " +
                              Helper.getname(randomizedList[1]))
    await hitler.send(hitlerInformation)


# dmFascists
# The next (numFascists) people after Hitler are Fascist who always get to know who each other and who Hitler are,
# dmFascists first builds strings that contains the name of all Fascist party members, including Hitler. Then it
# will send everyone their role cards, a message detailing their objective with slight variation based on whether or not
# hitler knows their identities, as well as the built strings of fellow party members
async def dmFascists(randomizedList):

    numFascists = roleDistribution[GameInformation.playerCount][1]

    fascistTeam = "Fascist Team (of " + str(numFascists-1) + ") : "
    hitlerTeam = "Hitler : " + Helper.getname(GameInformation.fascistList[0])
    for num in range(1, numFascists + 1):  # First build the Fascist team string to send to all Fascists

        fascistTeam += Helper.getname(randomizedList[num]) + ", "
        GameInformation.fascistList.append(randomizedList[num])

    for num in range(1, numFascists + 1):
        fascist = GameInformation.fascistList[num]
        await fascist.send(file=discord.File(FCARD))
        fascistInformation = "You are a Fascist! You will be working together with your fellow Fascist(s) and Hitler"
        " (listed below) to defeat the liberals. Your job is to enact 6 Fascist Policies or elect your Hitler as"
        " Chancellor while at least 3 Fascist Policies are in play."

        if numFascists == 1:
            fascistInformation += " Hitler DOES know who you are."
        else:
            fascistInformation += " Hitler does NOT know who you are."

        fascistInformation += "Make sure to avoid suspicion while working towards your goal. You lose if Hitler is"
        " assassinated or if 5 Liberal policies are enacted. \n" + hitlerTeam + "\n" + fascistTeam
        await fascist.send(fascistInformation)


# dmLiberals
# Everyone else is liberal, send role cards and a message about goals/how many people are Liberal (but not who they are)
async def dmLiberals(randomizedList):

    # number of fascists + hitler corresponds to starting index of libs
    for num in range(len(GameInformation.fascistList), GameInformation.playerCount):
        liberal = randomizedList[num]
        GameInformation.liberalList.append(liberal)
        await liberal.send(file=discord.File(LCARD))
        await liberal.send("You are one of " + str(GameInformation.playerCount - len(GameInformation.fascistList)) +
                        " liberals! You must work to find out"
                        " who your allies are and who is secretly a fascist, or even worse, Hitler! You win by either "
                        " enacting 5 liberal policies, or assassinating Hitler. Be careful not to allow those scum to "
                        "enact 6 Fascist polices or allow Hitler to become Chancellor while at least 3 Fascist Policies"
                        " are in play, because if so, you lose!")


# SeatingChart
# sends the seating order and returns the message id of the display. Used for displaying options when president elects
# chancellor, needs to assassinate, or just at request of user via bot's '$seating' command
async def SeatingChart(ctx):
    return await ctx.send(Helper.seatingOrder())



# sendThreeCards
# File names start with the letters of the policies, ie. LFL.png is Liberal Fascist Liberal, so by getting the reaction
# we can index the string to remove the desired discarded one, and then send the rest to Chancellor, adding removed
# to discard pile
async def sendThreeCards(ctx):
    cardFileName = str(GameInformation.deck.pop()) + str(GameInformation.deck.pop()) + str(GameInformation.deck.pop()) + '.png'
    message = await PrevPresident.send(file=discord.File(cardFileName))
    await reactWithNumberedEmojis(message, 3)
    await PrevPresident.send("Select a policy to DISCARD, the others will be sent to the Chancellor")

    def checkIfValidEmoji(reaction, user):
        return str(reaction) in EmojisOneToTen[0:3] and user == PrevPresident # make sure its emojis 1, 2 or 3


    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', timeout=180.0, check=checkIfValidEmoji)
    except asyncio.TimeoutError:
        await PrevPresident.send("Timed out random card will be discarded!")
        discardedCardIndex = Helper.EmojiToIndex(random.choice(EmojisOneToTen[0:3]))
    else:
        discardedCardIndex = Helper.EmojiToIndex(str(reaction.emoji))

    discardedCardLetter = cardFileName[discardedCardIndex]
    GameInformation.discard_pile.append(discardedCardLetter)
    await PrevPresident.send("Discarding a " + Helper.letterToFullName(discardedCardLetter) + " law. Sending"
                    " remaining to Chancellor " + Helper.getname(PrevChancellor))

    cardFileName = cardFileName[:discardedCardIndex] + cardFileName[discardedCardIndex+1:]  # slice string to remove discarded
    return await sendTwoCards(ctx, cardFileName, False)  # will return the Letter of the policy to enact


# sendTwoCards
# Chancellor must pick between the two policies on what to enact, if vetoing is enabled. Chancellor can request to veto
# and discard all cards. If the president agrees, all cards are discarded and "Vetoed" is returned, else the Chancellor
# is presented with the same cards again but without the option to try and veto again.
async def sendTwoCards(ctx, cardFileName, attemptedVeto):

    message = await PrevChancellor.send(file=discord.File(cardFileName))
    await reactWithNumberedEmojis(message, 2)

    # add an X when vetoing is allowed and veto hasn't been tried
    if GameInformation.vetoPowerUnlocked and not attemptedVeto:
        await message.add_reaction(EmojisCheckAndX[1])
        await PrevChancellor.send("You now have the option to veto, react with \'" + EmojisCheckAndX[1] + ("\' to start"
                                " request the President to veto the vote"))
    await PrevChancellor.send("Select a policy to ENACT, the other will be discarded")

    def checkIfValidEmoji(reaction, user):
        return user == PrevChancellor and ((str(reaction) in EmojisOneToTen[0:2]) or # make sure its emojis 1, 2
           (str(reaction) == EmojisCheckAndX[1] and GameInformation.vetoPowerUnlocked and not attemptedVeto))  # or X while vetoing is allowed

    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', timeout=180.0,
                                          check=checkIfValidEmoji)  # deal with timeout lta
    except asyncio.TimeoutError:
        await PrevChancellor.send("Timed out random card will be enacted!")
        enactedCardIndex = Helper.EmojiToIndex(random.choice(EmojisOneToTen[0:2]))
    else:
        if str(reaction) in EmojisOneToTen[0:2]:
            enactedCardIndex = Helper.EmojiToIndex(str(reaction.emoji))
        else:
            agreedToVeto = await veto(ctx)
            await asyncio.sleep(3)
            if agreedToVeto:
                await ctx.send("---------------------------------------------------------")
                await ctx.send("Policies have been vetoed!")
                await ctx.send("---------------------------------------------------------")
                GameInformation.discard_pile += cardFileName[0] + cardFileName[1]
                return "Vetoed"
            else:
                await ctx.send("---------------------------------------------------------")
                await ctx.send("Veto Rejected, Chancellor must pick a policy to enact")
                await ctx.send("---------------------------------------------------------")
                return await sendTwoCards(ctx, cardFileName, True)

    enactedCardLetter = cardFileName[enactedCardIndex]
    # enacted card will be either 1 or 0, and will need to discard its complement "(enactedCardIndex - 1) * -1" will
    # always convert 1 to 0 and 0 to 1
    GameInformation.discard_pile.append(cardFileName[(enactedCardIndex - 1) * -1])

    return enactedCardLetter


# ChancellorVoteSequence
# Will create a small profile of the chosen Chancellor candidate with default avatar if the user does not have one and
# send it to all players to vote on. Voting among players must be simultaneous so this is accomplished through
# asyncio tasks which function very much like threads. Once all tasks are done (all votes in) will calculate outcome
# send the results, clear the lists, and return the result.
async def ChancellorVoteSequence(ctx, ChosenCandidate):
    global VotedJa, VotedNein, DidNotVote
    pfp = ChosenCandidate.avatar
    if pfp is None:  # default
        pfp = ("https://images-ext-1.discordapp.net/external/ajAF5AMiCpYHipGTTPkcu0Xw4ScWQnS9XEkZ7BKcEXE/%3Fsize%3D1024"
               "/https/cdn.discordapp.com/avatars/928812928000462868/f01e69f0d4b3776c36afdc9c96b218b7.png?format=webp&q"
               "uality=lossless&width=426&height=426")
    CandidateEmbed = discord.Embed(title="Chancellor Candidate, {}".format(Helper.getname(ChosenCandidate)),
                          description="React with \'✅\' to vote JA, or react with \'❌\' to vote NEIN", color=0x003333FF)
    CandidateEmbed.set_image(url=pfp)
    async with asyncio.TaskGroup() as TaskManager:
        for player in GameInformation.playerList:
            TaskManager.create_task(RecordVote(ctx, player, CandidateEmbed))
    await ctx.send(genVoteResultString())
    Success = (len(VotedJa) > len(VotedNein))
    VotedJa.clear()
    VotedNein.clear()
    DidNotVote.clear()
    return Success


# RecordVote
# Task function which sends the profile and records the vote, using a lock when recording to prevent data loss
async def RecordVote(ctx, player, ChosenCandidateEmbedProfile):

    await player.send("You have 60 seconds to vote! If you don't choose any option, one will be picked at random!")
    embedMsg = await player.send(embed=ChosenCandidateEmbedProfile)
    await reactWithCheckAndX(embedMsg)

    def checkValidReaction(reaction, user):
        return user == player and str(reaction.emoji) in EmojisCheckAndX

    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', timeout=60.0, check=checkValidReaction)
    except asyncio.TimeoutError:
        await player.send("Timed out! Your vote will be chosen at random now")
    else:
        await player.send("Thank you for your vote")
        async with VoteLock:
            addToVoteList(str(reaction.emoji), player)
        return

    # if timed out pick a random one and add them
    async with VoteLock:
        addToVoteList(random.choice(EmojisCheckAndX), player)
        DidNotVote.append(player)



# REACT FUNCTIONS
# Reactions are used all throughout as the medium in which players make their choices, the below functions will react to
# a specified message with it's emoji set. Numbered emojis takes in a parameter to allow dynamically reacting, like only
# 3 for card choices, or 10 for all players, etc.
async def reactWithCheckAndX(message):
    for emoji in EmojisCheckAndX:
        await message.add_reaction(emoji)


async def reactWithNumberedEmojis(message, count):  # range is non-inclusive so + 1 if you need exactly the amount
    for num in range(0, count):
        await message.add_reaction(EmojisOneToTen[num])


# newPresident
# Simple message displaying who is next to run for president as well as who was last in office
async def newPresident(ctx, President):
    await ctx.send(President.mention + ", You are the new President, please select a Chancellor as your council.")
    await ctx.send("Previous President: " + Helper.getname(PrevPresident) + "\n" + "Previous Chancellor: "
                   + Helper.getname(PrevChancellor))




# veto
# If the Chancellor wants to veto, when vetoing is enabled, send a message to the President to see if they will agree
# return true if they do, false if not, false if timeout
async def veto(ctx):
    await ctx.send("Chancellor " + Helper.getname(PrevChancellor) + " has requested to veto this set of policies!")
    await asyncio.sleep(3)
    message = await PrevPresident.send("Do you agree to veto this set of policies? Vetoed policies"
                                       " are thrown into the discard pile. Check means yes, X means no")
    await reactWithCheckAndX(message)

    def checkIfValidEmoji(reaction, user):
        return str(reaction) in EmojisCheckAndX  # make sure its emojis 1, 2

    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', timeout=180.0,
                                          check=checkIfValidEmoji)  # deal with timeout lta
    except asyncio.TimeoutError:
        await ctx.send("Timed out! Veto is automatically denied")
        return False
    else:
        if str(reaction) == EmojisCheckAndX[0]:
            return True
        return False


# pickNextPresidentPower
# In the context of when this function gets called, PrevPresident is the current President.
# President can pick anyone but themselves, but the following election will follow standard rules
# And the next president will return to the original cycle possible even resulting in a person being president twice in
# a row
async def pickNextPresidentPower(ctx):
    global powerUsedToPickPresident
    powerUsedToPickPresident = await presidentChooseAnyoneButYourself(ctx)
    await ctx.send(Helper.getname(PrevPresident) + " has chosen " + Helper.getname(powerUsedToPickPresident) +
                   " to be President. This does NOT throw off the original cycle.")


# assassinatePlayer
# President gets to assassinate any player but himself, game will end if Hitler is killed
async def assassinatePlayer(ctx):
    await ctx.send(Helper.getname(PrevPresident) + " gets to assassinate a player!")
    target = await presidentChooseAnyoneButYourself(ctx)
    await ctx.send(Helper.getname(PrevPresident) + " has chosen " + Helper.getname(target) +
                   " to be Assassinated. See ya later stinky " + target.mention)

    GameInformation.playerList.remove(target)

    try:
        GameInformation.fascistList.remove(target)
    except ValueError:
        pass
    try:
        GameInformation.liberalList.remove(target)
    except ValueError:
        pass
    GameInformation.playerCount -= 1


# investigateIdentity
# Current President gets to see the identity of a player (Fascist or Liberal, can't see if Hitler) that hasn't
# already been investigated
async def investigateIdentity(ctx):
    global investigated
    await ctx.send(Helper.getname(PrevPresident) + " gets to check the identity card of a player!")
    while True:
        target = await presidentChooseAnyoneButYourself(ctx)
        if target != investigated:
            break
        else:
            await ctx.send(Helper.getname(target) + " was already investigated once this game, try again")
            await asyncio.sleep(3)
    investigated = target
    await investigateIdentityHelper(target)



async def investigateIdentityHelper(player):
    roleCardFileName = Helper.getIdentity(player)
    roleName = roleCardFileName[:-12]  # slicing -12 drops the letters "RoleCard.png"
    await PrevPresident.send(file=discord.File(roleCardFileName))
    await PrevPresident.send(Helper.getname(player) + " is a " + roleName)


# peekAtTopThreeCards
# Current President gets to peek at the top three cards of the deck before next election.
async def peekAtTopThreeCards(ctx):
    await peekAtTopThreeCardsHelper(ctx)
    await ctx.send(Helper.getname(PrevPresident) + " has peeked (sent a picture) the top 3 cards of the deck, now it is"
                " now time for the next election.")


async def peekAtTopThreeCardsHelper(ctx):
    cardFileName = GameInformation.deck[-3] + GameInformation.deck[-2] + GameInformation.deck[-1] + '.png'
    await PrevPresident.send(file=discord.File(cardFileName))
    await PrevPresident.send("Here are the top 3 cards of the deck")


# presidentChooseAnyoneButYourself
# 3 of the powers require the president to choose a player that is not himself, this function generalizes that and
# returns the player (or a random one if timed out)
async def presidentChooseAnyoneButYourself(ctx):
    seatingMessage = await SeatingChart(ctx)
    await reactWithNumberedEmojis(seatingMessage, GameInformation.playerCount)

    def checkIfPresident(reaction, user):
        return user == PrevPresident and str(reaction) in EmojisOneToTen[:GameInformation.playerCount]

    while True:
        try:
            reaction, user = await ctx.bot.wait_for('reaction_add', timeout=600.0, check=checkIfPresident)
        except asyncio.TimeoutError:
            await ctx.send("Timed out waiting for")
            ChosenCandidate = GameInformation.playerList[Helper.EmojiToIndex(random.choice(EmojisOneToTen[:GameInformation.playerCount]))]
        else:
            ChosenCandidate = GameInformation.playerList[Helper.EmojiToIndex(reaction.emoji)]

        if ChosenCandidate == PrevPresident:
            await ctx.send("You choose yourself! Please try again")
        else:
            return ChosenCandidate


# BoardState
# Used inside bot command "$board" and automatically within GameSequence, simply displays the Liberal and Fascist Boards
# with any policies enacted on them.
async def BoardState(ctx):
    LibBoardFasBoard = Helper.genBoardStatePngStrings()
    await ctx.send(file=discord.File(LibBoardFasBoard[0]))  # lib board first
    await ctx.send(file=discord.File(LibBoardFasBoard[1]))
    await ctx.send("There are " + str(GameInformation.enactedLiberalPolices) + " Liberal Policies in play and "
                   + str(GameInformation.enactedFascistPolices) + " Fascist Policies in play")


# explainEndGame
# Based on mapped results return from the varying WinCon checking functions, will send a message explaining why the game
# ended
async def explainEndGame(ctx, Reason, teamString):

    match Reason:

        case 1 | 2:
            await ctx.send("FASCIST TEAM HAS WON\n")
            if Reason == 1:
                await ctx.send("Hitler was elected as chancellor, you liberals have failed democracy")
            else:
                await ctx.send("6 Fascist policies were enacted, how could you liberals let Fascism take over!")
        case 3 | 4:
            await ctx.send("LIBERAL TEAM HAS WON\n")
            if Reason == 3:
                await ctx.send("5 Liberal Policies have been enacted, you fascists played the long con real well.")
            else:
                await ctx.send("Hitler was assassinated, how could you fascists allow your leader to fall!")
        case _:
            await ctx.send("UH OH TODD SUMFING WENT WRONG WITH CODE")
    await ctx.send(teamString)


# HELPERS SECTION
# Based on a read reaction, adds a player to the respective List
def addToVoteList(emoji, player):
    global VotedJa, VotedNein
    if emoji == EmojisCheckAndX[0]:
        VotedJa.append(player)
    else:
        VotedNein.append(player)


# init
# Initialization function to be called after enough players have joined the game, will hold onto the number of players
# at start of game since it could change with assassinations, yet the original is still needed to determine certain
# aspects like which board is used and eligibility for elections. Will also set the started game state to reject
# late attempts to join the game.
def init():
    global gameStarted
    GameInformation.originalPlayerCount = GameInformation.playerCount
    gameStarted = True


# Creates a string that shows who voted for what. People who did not vote ge their vote chosen randomly and will show
# up in the Did not vote List and one of the other two
def genVoteResultString():

    JaVoteCount = len(VotedJa)
    NeinVoteCount = len(VotedNein)
    SuccessfulVote = JaVoteCount > NeinVoteCount

    if SuccessfulVote:
        VoteResult = "Passed"
    else:
        VoteResult = "Failed"

    CompleteVoteInformation = "Vote {} {}-{}".format(VoteResult, JaVoteCount, NeinVoteCount)

    CompleteVoteInformation += "\n--------------------------\nJa Voters: "
    for voter in VotedJa:
        CompleteVoteInformation += Helper.getname(voter) + ", "

    CompleteVoteInformation += "\n--------------------------\nNein Voters: "
    for voter in VotedNein:
        CompleteVoteInformation += Helper.getname(voter) + ", "

    CompleteVoteInformation += "\n--------------------------\nDid not Vote: "
    for voter in DidNotVote:
        CompleteVoteInformation += Helper.getname(voter) + ", "
    return CompleteVoteInformation


def CheckForWinConPostElection():
    if GameInformation.enactedFascistPolices >= 3 and PrevChancellor == GameInformation.fascistList[0]:
        return 1
    return 0


# reset
# resets relevant global/local variables, to be called once game is over allowing another to be run
def reset():

    # local globals
    global gameActive,  gameStarted, VotedJa, VotedNein, DidNotVote, powerUsedToPickPresident, investigated
    global PrevPresident, PrevChancellor, presidentGenerator
    gameActive = False
    gameStarted = False
    VotedJa = []
    VotedNein = []
    DidNotVote = []
    powerUsedToPickPresident = "Used"
    investigated = "Investigated"
    PrevPresident = "None"
    PrevChancellor = "None"
    presidentGenerator = "None"

    # module globals
    GameInformation.playerList = []
    GameInformation.liberalList = []
    GameInformation.fascistList = []
    GameInformation.playerCount = 0
    GameInformation.originalPlayerCount = 0
    GameInformation.deck = ['L', 'L', 'L', 'L', 'L', 'L', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F',
                 'F', ]  # 6 liberal 11 Fascist
    GameInformation.discard_pile = []
    GameInformation.enactedFascistPolices = 0
    GameInformation.enactedLiberalPolices = 0
    GameInformation.vetoPowerUnlocked = False
    return


