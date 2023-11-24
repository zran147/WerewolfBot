from discord.ext import commands
import discord
import asyncio
import time
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
roles = ['werewolf', 'seer', 'bodyguard', 'villager', 'lycan']
emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']


def escape(message):
    message = message.replace('_', '\\_')
    return message


def to_thread(func: typing.Callable) -> typing.Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


@to_thread
def sleep(seconds):
    time.sleep(seconds)


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
    global state
    if state == 'not playing':
        state = 'waiting for players'
        embed = discord.Embed(
            description='Berikan reaksi ☝️  untuk mengikuti permainan',
            color=discord.Color.blue()
        )
        poll = await ctx.send(embed=embed)
        #poll = await ctx.send('Berikan reaksi ☝️ untuk mengikuti permainan')
        await poll.add_reaction('☝️')

        check = lambda r, u: r.emoji == '☝️' and u != bot.user
        if arg == 'test':
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
        global playing, channel, players, users, isGameEnded, emoji, killed, roles
        
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

        embed = discord.Embed(
            title='Players',
            description='\n'.join(f'{emoji} {name}' for emoji, name in zip((player.emoji for player in players), (player.user.display_name for player in players))),
            color=discord.Color.blue()
        )
        embed.add_field(name='Perhatian', value='Permainan akan dimulai dalam 10 detik')
        await channel.send(embed=embed)
        await sleep(10)

        embed = discord.Embed(
            description='Malam telah tiba. Seer silakan bangun',
            color=discord.Color.blue()
        )
        await channel.send(embed=embed)
        await asyncio.wait_for(seerTurn(channel), timeout=30)

        hari = 1
        while playing:
            await diskusi(channel, hari, role)
            await ctx.send("Malam telah tiba, Silakan tutup mata kalian")
            time.sleep(5)
            await wolfTurn(ctx)
            await seerTurn(ctx)
            await guardTurn(ctx)
            hari += 1


async def diskusi(channel, hari, role):
    embed = discord.Embed(
        title=f'Day #{hari}',
        description='Pagi telah tiba, silakan berdiskusi selama 2 menit',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)
    await channel.set_permissions(role, read_messages=True, send_messages=True)

    await sleep(60)
    embed = discord.Embed(
        description='Waktu diskusi tersisa 1 menit',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)
    
    await sleep(50)
    embed = discord.Embed(
        description='Waktu diskusi tersisa 10 detik',
        color=discord.Color.blue()
    )
    await channel.send(embed=embed)
    
    await sleep(10)
    await channel.set_permissions(role, read_messages=True, send_messages=False)
    embed = discord.Embed(
        description='Waktu diskusi habis. Silakan melakukan voting dengan memberikan reaksi',
        color=discord.Color.blue()
    )
    poll = await channel.send(embed=embed)

    players_emo = []
    for player in players and player.alive:
        players_emo.append(player.emoji)
        await poll.add_reaction(player.emoji)
    #vote func
    

async def seerTurn(channel):
    seer = next(player for player in players if player.role == "seer")

    #fungsi terawang
    async def see_role():
        nonlocal seer
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
        
        reaction, seer = await bot.wait_for('reaction_add', check = lambda r, u: str(r.emoji) in players_emo and u != bot.user)

        chosen_player = None
        for player in players:
            if player.emoji == str(reaction.emoji):
                chosen_player = player
                break

        #print(poll.reactions)
        #for r in poll.reactions:
        #    if r.emoji != reaction.emoji:
        #        poll.clear_reaction(r.emoji)

        #kirim hasil terawang
        if chosen_player == None:
            await ctx.send("Tidak ada pemain tersebut dalam game ini")

        if chosen_player.role == 'werewolf' or chosen_player.role == 'lycan':
            role_msg = f"{reaction.emoji}   adalah orang jahat"
        else:
            role_msg = f"{reaction.emoji}   adalah orang baik"
        embed = discord.Embed(description=role_msg, color=discord.Color.blue())
        await dm.send(embed=embed)

    if seer.alive:
        await see_role()


async def wolfTurn(ctx):
    werewolf = next(player for player in players if player.role == "werewolf")
    await ctx.send("Werewolf silakan bangun")


async def draw(user):
    global roles
    role = random.choice(roles)
    roles.remove(role)
    print(f"assigned {user} {roles}")
    return role


bot.run(BOT_TOKEN)
