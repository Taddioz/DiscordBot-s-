"""
Todd Pieper
Created on Mon-Jul-17-2024
Last edited: Sun-Jul-23-2024
Implemented using discord.py API - https://discordpy.readthedocs.io/en/latest/index.html
All work done here is my own, I do not give permission for one to copy and use it.
Uploading all work to my GitHub ---
"""

# Variables used by both asyncNonCommands and generalFunctions
playerList = []
liberalList = []
fascistList = []  # hitler will be first
deck = ['L', 'L', 'L', 'L', 'L', 'L', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F', 'F']  # 6 liberal 11 Fascist
discard_pile = []
playerCount = 0
originalPlayerCount = 0
enactedFascistPolices = 0
enactedLiberalPolices = 0
vetoPowerUnlocked = False
