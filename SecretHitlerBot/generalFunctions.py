import generalVariables as GameVars
import random


# Return the name of a user, guarding against not having set variables like PrevChancellor/PrevPresident, and users not
# having a global (profile) name set
def getname(user):
    if isinstance(user, str):
        return "None"
    tempName = user.global_name
    if tempName is None:
        tempName = user.name
    return tempName


# Generator function used to cycle the order of presidents, as playerList possibly changes throughout the game, this
# function still sees those changes
def getNextPresident():
    while True:
        for player in GameVars.playerList:
            yield player


# Creates and returns a string with the numbered order of players in the game representing the seating order
def seatingOrder():
    seatingString = ""
    depth = 1
    for player in GameVars.playerList:
        pName = player.global_name
        if pName is None:
            pName = player.name
        seatingString += str(depth) + ". " + pName + "\n"
        depth += 1
    return seatingString


# Translating an emoji to an index, used for when players choose another player from the seating order list via reaction
# this function translates the emoji of the reaction into the chosen players index within the playerList
def EmojiToIndex(emoji):
    match emoji:
        case "1️⃣":
            return 0
        case "2️⃣":
            return 1
        case "3️⃣":
            return 2
        case "4️⃣":
            return 3
        case "5️⃣":
            return 4
        case "6️⃣":
            return 5
        case "7️⃣":
            return 6
        case "8️⃣":
            return 7
        case "9️⃣":
            return 8
        case "🔟":
            return 9


# The fascist board is different based on how many players started the game, this function returns a list of the liberal
# board png and fascist board png, adding the enacted policies into the string to differentiate which image will be sent
def genBoardStatePngStrings():
    match GameVars.originalPlayerCount:
        case 5 | 6:
            FascistBoard = "5-6FasBoard"
        case 7 | 8:
            FascistBoard = "7-8FasBoard"
        case 9 | 10:
            FascistBoard = "9-10FasBoard"
        case _:
            FascistBoard = "5-6FasBoard"
    FascistBoard += str(GameVars.enactedFascistPolices) + '.png'
    LiberalBoard = 'LibBoard' + str(GameVars.enactedLiberalPolices) + '.png'
    tempList = [LiberalBoard, FascistBoard]
    return tempList


# Checks to see if there aren't enough cards to be able to draw 3 next turn, adds the discard pile, shuffles the deck
# and clears the discard pile. Returns True/False so a message can be sent to users notifying them of the discard pile
# being shuffled in
def addDiscardPileIfNeeded():
    deck_size = len(GameVars.deck)
    if deck_size < 3:
        GameVars.deck += GameVars.discard_pile
        random.shuffle(GameVars.deck)
        GameVars.discard_pile = []
        return True
    return False


# Converts policy letter to its full name equivalent, used for generalizing messages detailing what laws are getting
# enacted
def letterToFullName(letter):
    if letter == 'F':
        return "Fascist"
    return "Liberal"


# Need to check for win-cons at different times, After election check if 3 Fascist policies enacted and if hitler is
# chancellor, after policy is enacted check if either 5 Liberal or 6 Fascist total have been enacted, and after
# assassination power is used, check if Hitler died.
# MAPPING LOGIC
# 0 -> No win condition met
# 1 -> Hitler is Chancellor AFTER 3 Fascist Policies enacted
# 2 -> Six Fascist policies have been enacted
# 3 -> Five Liberal Policies have been enacted
# 4 -> Hitler was assassinated

# CheckForWinConPostElection defined in async because it requires knowledge of The chancellor
def CheckForWinConPostPolicyEnacting():
    if GameVars.enactedFascistPolices == 6:  # max fas policies reached
        return 2
    if GameVars.enactedLiberalPolices == 5:  # max lib policies reached
        return 3
    return 0


def CheckForWinConPostAssassination():
    if GameVars.fascistList[0] not in GameVars.playerList:  # hitler assassinated
        return 4
    return 0


def enactPolicy(policyFirstLetter):
    if policyFirstLetter == 'F':
        GameVars.enactedFascistPolices += 1
    else:
        GameVars.enactedLiberalPolices += 1


"""
 After a Fascist policy is enacted, need to check if a new power is available, that depends on the amount of players
 that were there at the start of the game (could be more than active players if any get assassinated)
 POWER GRANTED MAPPING FORMAT
 (number of enacted fascist polices) + (condition) -> (return value)
 1 + 9-10 players -> 1
 2 + 7-10 players -> 1
 3 + 7-10 players -> 2
 3 + 5-6 players -> 3
 4 -> 4
 5 -> 4 and 5
 6 will be checked prior to calling this function
 0 is not a possible case as this function is only called AFTER a Fascist policy is enacted
 
 POWER TRANSLATOR
 (return value) -> (description of power)
 1 -> President must view identity card (liberal or fascist, can't tell if Hitler) of a player that has not already
 been viewed before
 2 -> President must to pick the next Presidential candidate. This does not restart the order of presidents thereafter
 3 -> President must view top 3 cards of the deck before the next election cycle
 4 -> President must assassinate a player that is not themselves
 5 -> The only power that cannot be used before next election is this. Now after any future president views three cards
 and discards one, while the chancellor has the two remaining cards they may ask the President about Veto-ing this set.
 If both the President and Chancellor agree to Veto, then both cards the Chancellor holds get discarded and the next 
 election cycle begins
"""
def CheckForNewPower():
    match GameVars.enactedFascistPolices:

        case 1 if GameVars.playerCount >= 9:
            return 1
        case 2 if GameVars.playerCount >= 7:
            return 1
        case 3 if GameVars.playerCount >= 7:
            return 2
        case 3 if GameVars.playerCount >= 5:
            return 3
        case 4:
            return 4
        case 5:
            return 5  # although this also grants assassination, return 5 to differentiate veto power now existing
        case _:
            return 0


# returns file name of role card of player
def getIdentity(player):
    if player in GameVars.fascistList:
        return "FascistRoleCard.png"
    return "LiberalRoleCard.png"


# For end of game explanation, generates a string to be able to display who was on what team
def genTeamString():
    FascistTeam = "Fascist Team: "
    LiberalTeam = "Liberal Team: "
    Hitler = "Hitler: " + getname(GameVars.fascistList[0])

    for player in GameVars.fascistList[1:]:
        FascistTeam += getname(player) + ", "

    for player in GameVars.liberalList:
        LiberalTeam += getname(player) + ", "

    FinalResult = LiberalTeam + '\n' + FascistTeam + '\n' + Hitler
    return FinalResult

