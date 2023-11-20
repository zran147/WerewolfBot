from discord.ext import commands
import discord
import asyncio
import time
import random

BOT_TOKEN = open('token.txt', 'r').read().strip()
CHANNEL_ID = 1174972462367260675

class Player:
    def __init__(self, user, role=None, emoji=None):
        self.user = user
        self.role = role
        self.emoji = emoji

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
users = []
players=[]
state = 'not playing'
roles = ['werewolf', 'seer', 'bodyguard', 'villager', 'lycan']

@bot.event
async def on_ready():
    print('Werewolf Bot activated')
    channel = bot.get_channel(CHANNEL_ID)
    await channel.send('WerewolfBot activated! Ketik `!play` untuk memainkan permainan WereWolf.')

@bot.command()
async def test(ctx):
    await ctx.send('Masuk')


@bot.command()
async def play(ctx):
    global state
    if state == 'not playing':
        state = 'waiting for players'
        poll = await ctx.send('Berikan reaksi ☝️ untuk mengikuti permainan')
        await poll.add_reaction('☝️')

        check = lambda r, u: r.emoji == '☝️' and u != bot.user
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
        await ctx.send('Pemain berjumlah 5 orang. Ketik `!start` untuk memulai permainan.')
        await ctx.send('```' + 'List Pemain:\n\n' + '\n'.join([str(user) for user in users]) + '```')
        state = 'ready to play'


@bot.command()
async def start(ctx):
    global players, users, isGameEnded, emoji, killed, roles
    for user in users:
        player = Player(user, await draw(user), users.index(user))
        players.append(player)

    await ctx.send('Permainan dimulai')
    #malam 1
    await ctx.send('Malam telah tiba')
    time.sleep(3)
    await ctx.send('Seer silahkan bangun')
    await seerTurn(ctx)
    time.sleep(5)

    #pagi 1
    await ctx.send('Pagi telah tiba, silakan kalian berdiskusi selama 2 menit')
    time.sleep(60)
    await ctx.send('Waktu diskusi tersisa 1 menit')
    time.sleep(50)
    await ctx.send('Waktu diskusi tersisa 10 detik')
    time.sleep(10)
    await ctx.send('Waktu habis silakan melakukan voting')

    #vote func

    while isGameEnded == False:
        await ctx.send("Malam telah tiba, Silakan tutup mata kalian")
        time.sleep(5)
        await wolfTurn(ctx)
        await seerTurn(ctx)
        await guardTurn(ctx)


async def draw(user):
    global roles
    
    role = random.choice(roles)
    roles.remove(role)

    print(f"assigned {user} {roles}")

    if role != None:
        await send_msg(user, f"Role kamu adalah {role}")
    return role

async def send_msg(user, msg):
    dm = await user.create_dm()
    await dm.send(msg)

bot.run(BOT_TOKEN)
