from discord.ext import commands
from datetime import timedelta
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


def escape(message):
    message = message.replace('_', '\\_')
    return message


async def peringatan(channel, total, ketika_sisa, testing=False):
    if not testing:
        await asyncio.sleep(total - ketika_sisa)
    embed = discord.Embed(
        description=f'Waktu diskusi tersisa {ketika_sisa} detik',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)


async def voting(message):
    while True:
        done, pending = await asyncio.wait([asyncio.create_task(bot.wait_for('reaction_add'))])
        for task in pending:
            try:
                task.cancel()
            except asyncio.CancelledError:
                pass
        reaction, user = list(done)[0].result()
        if reaction.emoji in emojis:
            cache_msg = discord.utils.get(bot.cached_messages, id=reaction.message.id)

            for r in cache_msg.reactions:
                if user in [user async for user in r.users()] and not user.bot and str(r) != str(reaction.emoji):
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

        check = lambda r, u: r.message == poll and r.emoji == '☝️' and not u.bot
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
                    await ctx.send(f'({len(users)}/5) {user.display_name} telah bergabung ke dalam permainan')
            elif finished.get_name() == 'r_rem':
                reaction, user = finished.result()
                if user in users:
                    users.remove(user)
                    await ctx.send(f'({len(users)}/5) {user.display_name} telah meninggalkan permainan')
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
        state = 'playing'
        global testing, channel, players, emoji_to_player, users, isGameEnded, emoji, killed, roles, seer, werewolf, guard
        
        guild = ctx.guild
        channel = discord.utils.get(guild.channels, name='werewolf')
        role = discord.utils.get(guild.roles, name='Playing Werewolf')
        dead_role = discord.utils.get(guild.roles, name='dead')

        if not channel:
            channel = await guild.create_text_channel('werewolf')
        if not role:
            role = await guild.create_role(name='Playing Werewolf')
        if not dead_role:
            dead_role = await guild.create_role(name='dead')
        #await guild.edit_role_positions(positions={role: 10, dead_role:9})

        await channel.purge()
        await channel.set_permissions(role, read_messages=True, send_messages=False, add_reactions=False)
        await channel.set_permissions(dead_role, read_messages=True, send_messages=False, add_reactions=False)
        for user in users:
            await user.add_roles(role)
            await user.remove_roles(dead_role)
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
                    werewolf = player
                case 'bodyguard':
                    guard = player
        await channel.set_permissions(guild.default_role, read_messages=False)

        embed = discord.Embed(
            title='Players',
            description='\n'.join(f'{emoji} {name}' for emoji, name in zip((player.emoji for player in players), (player.user.display_name for player in players))),
            color=discord.Color.blue()
        )
        embed.add_field(name='Perhatian', value='Permainan akan dimulai dalam 10 detik')
        dm_seer = await seer.user.create_dm()
        dm_wolf = await werewolf.user.create_dm()
        dm_guard = await guard.user.create_dm()
        await asyncio.wait([
            asyncio.create_task(channel.send(embed=embed)),
            asyncio.create_task(dm_seer.send(embed=embed)),
            asyncio.create_task(dm_wolf.send(embed=embed)),
            asyncio.create_task(dm_guard.send(embed=embed))
        ])
        if not testing:
            await asyncio.sleep(10)

        embed = discord.Embed(
            description='Malam telah tiba. Seer silakan bangun',
            color=discord.Color.blue()
        )
        await channel.send(embed=embed)
        if seer.alive:
            _, pending = await asyncio.wait([asyncio.create_task(seerTurn(channel))], timeout=30)
            for task in pending:
                try:
                    task.cancel()
                except asyncio.CancelledError:
                    pass

        hasil = ''
        hari = 1
        while state == 'playing':
            await diskusi(channel, hari, role, dead_role, hasil)
            if (message := checkGameState()) is not None:
                break
            embed = discord.Embed(
                description='Malam telah tiba\nSeer, werewolf, dan bodyguard silakan bangun',
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)
            await asyncio.sleep(5)
            tasks = [asyncio.create_task(wolfTurn(channel), name='wolf')]
            if seer.alive:
                tasks.append(asyncio.create_task(seerTurn(channel)))
            if guard.alive:
                tasks.append(asyncio.create_task(guardTurn(channel), name='guard'))
            done, pending = await asyncio.wait(tasks, timeout=30)
            for task in pending:
                try:
                    task.cancel()
                except asyncio.CancelledError:
                    pass
            wolf_choice = [task for task in done if task.get_name() == 'wolf']
            if len(wolf_choice) == 0:
                hasil = 'Tidak ada yang dibunuh'
            elif guard.alive:
                guard_choice = [task for task in done if task.get_name() == 'guard']
                if len(guard_choice) == 0:
                    hasil = f'{emoji_to_player[wolf_choice[0].result()].user.display_name} telah dibunuh'
                elif wolf_choice[0].result() == guard_choice[0].result():
                    hasil = 'Bodyguard telah berhasil menyelamatkan seseorang'
                else:
                    emoji_to_player[wolf_choice[0].result()].alive = False
                    await emoji_to_player[wolf_choice[0].result()].user.add_roles(dead_role)
                    await emoji_to_player[wolf_choice[0].result()].user.timeout(timedelta(days=1))
                    hasil = f'{emoji_to_player[wolf_choice[0].result()].user.display_name} telah dibunuh'
            else:
                emoji_to_player[wolf_choice[0].result()].alive = False
                await emoji_to_player[wolf_choice[0].result()].user.timeout(timedelta(days=1))
                await emoji_to_player[wolf_choice[0].result()].user.add_roles(dead_role)
                hasil = f'{emoji_to_player[wolf_choice[0].result()].user.display_name} telah dibunuh'
            if (message := checkGameState()) is not None:
                break
            hari += 1
        embed = discord.Embed(
            title=message,
            description='Channel ini akan ditutup 20 detik lagi',
            color=discord.Color.blue()
        )
        await channel.send(embed=embed)
        for player in players:
            await player.user.remove_roles(dead_role)
            await player.user.timeout(None)
        await channel.set_permissions(role, read_messages=True, send_messages=True)
        await asyncio.sleep(20)
        for player in players:
            await player.user.remove_roles(role)
        users.clear()
        players.clear()
        emoji_to_player.clear()
        testing = False
        roles = ['werewolf', 'seer', 'bodyguard', 'villager', 'lycan']
        state = 'not playing'
        await channel.set_permissions(guild.default_role, read_messages=True, send_messages=False, add_reactions=False)


def checkGameState():
    global werewolf, players
    if not werewolf.alive:
        return 'Selamat, Penduduk menang!'
    elif len([player for player in players if player.alive]) == 2:
        return 'Selamat, Werewolf menang!'


async def diskusi(channel, hari, role, dead_role, hasil):
    global players, emoji_to_player

    embed = discord.Embed(
        title=f'Day #{hari}',
        description='Pagi telah tiba, silakan berdiskusi selama 2 menit',
        color=discord.Color.blue()
    )
    if hasil != '':
        embed.add_field(name='Berita', value=hasil)
    await channel.send(embed=embed)
    await channel.set_permissions(role, read_messages=True, send_messages=True, attach_files=False, create_private_threads=False, create_public_threads=False)

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
    await channel.set_permissions(role, read_messages=True, send_messages=False, add_reactions=False)
    embed = discord.Embed(
        title='Waktu diskusi habis',
        description='Silakan melakukan voting dengan memberikan reaksi\n' + '\n'.join(f'{emoji} {name}' for emoji, name in zip((player.emoji for player in players if player.alive), (player.user.display_name for player in players if player.alive))),
        color=discord.Color.blue()
    )
    poll = await channel.send(embed=embed)
    
    for player in players:
        if player.alive:
            await poll.add_reaction(player.emoji)

    #await asyncio.sleep(20)

    #embed = discord.Embed(
    #    description='Waktu voting tersisa 10 detik',
    #    color=discord.Color.blue()
    #)
    #await channel.send(embed=embed)
    #await asyncio.sleep(10)

    await asyncio.wait([asyncio.create_task(voting(poll)), asyncio.create_task(peringatan(channel, 30, 10))], timeout=30)

    poll = discord.utils.get(bot.cached_messages, id=poll.id)
    votes = {reaction.emoji: reaction.count-1 for reaction in poll.reactions if reaction.emoji in emojis}

    hasil = None if (terurut := (sorted(votes.items(), key=lambda item: item[1])[::-1]))[0][1] == terurut[1][1] else terurut[0][0]
    if hasil != None:
        emoji_to_player[hasil].alive = False
        await emoji_to_player[hasil].user.add_roles(dead_role)
        await emoji_to_player[hasil].user.timeout(timedelta(days=1))
        hasil = f'{emoji_to_player[hasil].user.display_name} akan ditendang dari desa'
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
    
    reaction, _ = await bot.wait_for('reaction_add', check = lambda r, u: r.message == poll and str(r.emoji) in players_emo and not u.bot)

    chosen_player = emoji_to_player[str(reaction.emoji)]

    if chosen_player == None:
        await channel.send("Tidak ada pemain tersebut dalam game ini")

    if chosen_player.role == 'werewolf' or chosen_player.role == 'lycan':
        role_msg = f"{chosen_player.user.display_name}   adalah orang jahat"
    else:
        role_msg = f"{chosen_player.user.display_name}   adalah orang baik"
    embed = discord.Embed(description=role_msg, color=discord.Color.blue())
    await dm.send(embed=embed)


async def wolfTurn(channel):
    global werewolf, emoji_to_player
    dm = await werewolf.user.create_dm()
    embed = discord.Embed(
        description='Pilih siapa yang ingin kamu bunuh dengan bereaksi pada pesan ini',
        color=discord.Color.blue()
    )
    poll = await dm.send(embed=embed)

    players_emo = []
    for player in players:
        if player.role != 'werewolf' and player.alive:
            players_emo.append(player.emoji)
            await poll.add_reaction(player.emoji)
    
    reaction, _ = await bot.wait_for('reaction_add', check = lambda r, u: r.message == poll and str(r.emoji) in players_emo and not u.bot)

    chosen_player = emoji_to_player[str(reaction.emoji)]

    if chosen_player == None:
        await channel.send("Tidak ada pemain tersebut dalam game ini")

    embed = discord.Embed(description=f'Kamu memilih {emoji_to_player[reaction.emoji].user.display_name}', color=discord.Color.blue())
    await dm.send(embed=embed)
    return reaction.emoji


async def guardTurn(channel):
    global guard, emoji_to_player
    dm = await guard.user.create_dm()
    embed = discord.Embed(
        description='Pilih siapa yang ingin kamu selamatkan dengan bereaksi pada pesan ini',
        color=discord.Color.blue()
    )
    poll = await dm.send(embed=embed)

    players_emo = []
    for player in players:
        if player.alive:
            players_emo.append(player.emoji)
            await poll.add_reaction(player.emoji)
    
    reaction, _ = await bot.wait_for('reaction_add', check = lambda r, u: r.message == poll and str(r.emoji) in players_emo and not u.bot)

    chosen_player = emoji_to_player[str(reaction.emoji)]

    if chosen_player == None:
        await channel.send("Tidak ada pemain tersebut dalam game ini")

    embed = discord.Embed(description=f'Kamu memilih {emoji_to_player[reaction.emoji].user.display_name}', color=discord.Color.blue())
    await dm.send(embed=embed)
    return reaction.emoji


async def draw(user):
    global roles
    role = random.choice(roles)
    roles.remove(role)
    print(f"assigned {user} {role}")
    return role


bot.run(BOT_TOKEN)
