from discord.ext import commands
import discord
import asyncio
import random
import functools
import typing

BOT_TOKEN = open('token.txt', 'r').read().strip()
CHANNEL_ID = 1174972462367260675

class Player:
    def __init__(self, user, role=None, emoji=None, alive=True):
        self.user = user
        self.role = role
        self.emoji = emoji
        self.alive = alive

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
users = []
players = []
state = 'not playing'
testing = False
roles = ['werewolf', 'seer', 'bodyguard', 'villager', 'lycan']
emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
emoji_to_player = {}
werewolves = []


def escape(message):
    message = message.replace('_', '\\_')
    return message


@bot.event
async def on_reaction_add(reaction, user):
    channel = reaction.message.channel
    if user.id != bot.user.id:
        cache_msg = discord.utils.get(bot.cached_messages, id=reaction.message.id)

        for r in cache_msg.reactions:
            if user in [user async for user in r.users()] and not user.bot and str(r) != str(reaction.emoji):
                # Remove their previous reaction
                await cache_msg.remove_reaction(r.emoji, user)


@bot.event
async def on_ready():
    print('Werewolf Bot activated')
    channel = bot.get_channel(CHANNEL_ID)
    embed = discord.Embed(
        title='WerewolfBot activated!',
        description='Ketik `!play` untuk memainkan permainan WereWolf',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)


@bot.command()
async def test(ctx):
    await ctx.send('Masuk')


@bot.command()
async def play(ctx, arg=''):
    global state, testing
    if state == 'not playing':
        state = 'waiting for players'
        if arg == 'test':
            testing = True

        embed = discord.Embed(
            description='Berikan reaksi ☝️  untuk mengikuti permainan',
            color=discord.Color.blue()
        )
        poll = await ctx.send(embed=embed)
        #poll = await ctx.send('Berikan reaksi ☝️ untuk mengikuti permainan')
        await poll.add_reaction('☝️')

        check = lambda r, u: r.emoji == '☝️' and not u.bot
        if testing:
            user = ctx.author
            for _ in range(5-len(users)):
                users.append(user)
        while len(users) < 5:
            tasks = [
                asyncio.create_task(
                    bot.wait_for('reaction_add', check=check),
                    name='r_add'
                ), asyncio.create_task(
                    bot.wait_for('reaction_remove', check=check),
                    name='r_rem'
                )
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                try:
                    task.cancel()
                except asyncio.CancelledError:
                    pass

            if (finished := list(done)[0]).get_name() == 'r_add':
                reaction, user = finished.result()
                if user not in users:
                    users.append(user)
                    await ctx.send(f'({len(users)}/5) {user} telah bergabung ke dalam permainan')
            elif finished.get_name() == 'r_rem':
                reaction, user = finished.result()
                if user in users:
                    users.remove(user)
                    await ctx.send(f'({len(users)}/5) {user} telah meninggalkan permainan')
        embed = discord.Embed(
            title='List Pemain:',
            description='\n'.join([escape(user.display_name) for user in users]),
            color=discord.Color.blue()
        )
        embed.add_field(name='Pemain sudah berjumlah 5 orang', value='Ketik `!start` untuk memulai permainan')
        await ctx.send(embed=embed)
        state = 'ready to play'


@bot.command()
async def start(ctx):
    global state
    if state == 'ready to play':
        global playing, channel, players, emoji_to_player, users, isGameEnded, emoji, killed, roles, seer, werewolves, guard
        
        playing = True
        guild = ctx.guild
        channel = discord.utils.get(guild.channels, name='werewolf')
        role = discord.utils.get(guild.roles, name='Playing Werewolf')

        if not channel:
            channel = await guild.create_text_channel('werewolf')
        if not role:
            role = await guild.create_role(name='Playing Werewolf')

        await channel.purge()
        await channel.set_permissions(guild.default_role, read_messages=False)
        await channel.set_permissions(role, read_messages=True, send_messages=False)
        for user in users:
            await user.add_roles(role)
            player = Player(user, await draw(user), emojis[len(players)])
            dm = await user.create_dm()
            embed = discord.Embed(
                title=f'{player.emoji}  Role kamu adalah {player.role}',
                color=discord.Color.blue()
            )
            await dm.send(embed=embed)
            players.append(player)
            emoji_to_player[player.emoji] = player
            match player.role:
                case 'seer':
                    seer = player
                case 'werewolf':
                    werewolves.append(player)
                case 'bodyguard':
                    guard = player

        embed = discord.Embed(
            title='Players',
            description='\n'.join(f'{emoji} {name}' for emoji, name in zip((player.emoji for player in players), (player.user.display_name for player in players))),
            color=discord.Color.blue()
        )
        embed.add_field(name='Perhatian', value='Permainan akan dimulai dalam 10 detik')
        await channel.send(embed=embed)
        if not testing:
            await asyncio.sleep(10)

        embed = discord.Embed(
            description='Malam telah tiba. Seer silakan bangun',
            color=discord.Color.blue()
        )
        await channel.send(embed=embed)
        if seer.alive:
            await asyncio.wait([asyncio.create_task(seerTurn(channel))], timeout=30)

        hari = 1
        while playing:
            await diskusi(channel, hari, role)
            embed = discord.Embed(
                description='Malam telah tiba\nSeer, werewolf, dan bodyguard silakan bangun',
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)
            await asyncio.sleep(5)
            await asyncio.wait([
                    asyncio.create_task(wolfTurn(channel)),
                    asyncio.create_task(seerTurn(channel)),
                    asyncio.create_task(guardTurn(channel))
                ], timeout=30
            )
            hari += 1


async def diskusi(channel, hari, role):
    global players, emoji_to_player

    embed = discord.Embed(
        title=f'Day #{hari}',
        description='Pagi telah tiba, silakan berdiskusi selama 2 menit',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)
    await channel.set_permissions(role, read_messages=True, send_messages=True)

    if not testing:
        await asyncio.sleep(60)
    embed = discord.Embed(
        description='Waktu diskusi tersisa 1 menit',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)
    
    if not testing:
        await asyncio.sleep(50)
    embed = discord.Embed(
        description='Waktu diskusi tersisa 10 detik',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)

    if not testing:
        await asyncio.sleep(10)
    await channel.set_permissions(role, read_messages=True, send_messages=False)
    embed = discord.Embed(
        description='Waktu diskusi habis. Silakan melakukan voting dengan memberikan reaksi',
        color=discord.Color.blue()
    )
    poll = await channel.send(embed=embed)
    
    for player in players:
        if player.alive:
            await poll.add_reaction(player.emoji)

    await asyncio.sleep(20)

    embed = discord.Embed(
        description='Waktu voting tersisa 10 detik',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)
    await asyncio.sleep(10)
    poll = discord.utils.get(bot.cached_messages, id=poll.id)
    votes = {reaction.emoji: reaction.count-1 for reaction in poll.reactions}

    hasil = None if (terurut := (sorted(votes.items(), key=lambda item: item[1])[::-1]))[0][1] == terurut[1][1] else terurut[0][0]
    if hasil != None:
        hasil = f'{emoji_to_player[hasil].emoji} akan dibunuh'
    else:
        hasil = 'Tidak akan ada yang dibunuh'

    embed = discord.Embed(
        title='Hasil Voting',
        description='\n'.join([f'{key}  {value}' for key, value in votes.items()]),
        color=discord.Color.blue()
    )
    embed.add_field(name='Kesimpulan', value=hasil)
    await channel.send(embed=embed)


async def seerTurn(channel):
    global seer, emoji_to_player
    dm = await seer.user.create_dm()
    embed = discord.Embed(
        description='Pilih siapa yang ingin kamu terawang dengan bereaksi pada pesan ini',
        color=discord.Color.blue()
    )
    poll = await dm.send(embed=embed)

    players_emo = []
    for player in players:
        if player.role != "seer" and player.alive:
            players_emo.append(player.emoji)
            await poll.add_reaction(player.emoji)
    
    reaction, _ = await bot.wait_for('reaction_add', check = lambda r, u: str(r.emoji) in players_emo and not u.bot)

    chosen_player = emoji_to_player[str(reaction.emoji)]

    if chosen_player == None:
        await channel.send("Tidak ada pemain tersebut dalam game ini")

    if chosen_player.role == 'werewolf' or chosen_player.role == 'lycan':
        role_msg = f"{reaction.emoji}   adalah orang jahat"
    else:
        role_msg = f"{reaction.emoji}   adalah orang baik"
    embed = discord.Embed(description=role_msg, color=discord.Color.blue())
    await dm.send(embed=embed)


async def wolfTurn(channel):
    global werewolves


async def guardTurn(channel):
    global guard


async def draw(user):
    global roles
    role = random.choice(roles)
    roles.remove(role)
    print(f"assigned {user} {roles}")
    return role


bot.run(BOT_TOKEN)
