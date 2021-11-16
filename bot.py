import datetime
import signal
import os
import asyncio
import logging
import math
import multiprocessing
import random
import time
import traceback
import typing

import discord
import jsonpickle
import openai
from discord import state as discord_state

DISCORD_TOKEN = "XXXXXXXXXXXXXXXXXXXXXXXX.XXXXXX.XXXXXXXXXXXXXXX-XXXXXXXXXXX"  # Get one here: https://discord.com/developers/applications/
OPENAI_API_KEY = "sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # https://beta.openai.com/account/api-keys
OPENAI_ORGANIZATION = "org-XXXXXXXXXXXXXXXXXXXXXXXX"
PREFIX = '.'
CLEANUP = 60
VERIFY_CHANNEL = 885760989608431636  # Yannic Kilcher "_verification"
VERIFIED_ROLE = 821375158295592961  # Yannic Kilcher "verified"
ALLOWED_CHANNEL = 800329398691430441  # Yannic Kilcher "gpt3"
MESSAGE_CHANNEL = 760062431858262066  # Yannic Kilcher "bot-chat"
ALLOWED_GUILD = 714501525455634453  # Yannic Kilcher
SHITPOSTING_CHANNEL = 736963923521175612
PRUNING_DAYS = 60
ADMIN_USER = [690665848876171274, 191929809444667394, 699606075023949884]  # ClashLuke, XMaster, Yannic
ROLES = {'reinforcement-learning': 760062682693894144, 'computer-vision': 762042823666171955,
         'natural-language-processing': 762042825260007446, 'meetup': 782362139087208478, 'verified': 821375158295592961
         }
APPROVAL_EMOJI: typing.Union[str, discord.Emoji] = "yes"
DISAPPROVAL_EMOJI: typing.Union[str, discord.Emoji] = "noo"
THREADS = 16
LOG_LEVEL = logging.DEBUG

openai.api_key = OPENAI_API_KEY
openai.organization = OPENAI_ORGANIZATION

FALLBACKS = []
CHANNEL: typing.Optional[discord.TextChannel] = None


class ExitFunctionException(Exception):
    pass


def debug(message: typing.Any):
    if LOG_LEVEL <= logging.DEBUG:
        print(message)


def discord_check(check: bool, message: discord.Message, response: str):
    if check:
        channel: discord.TextChannel = message.channel
        await channel.send(response, reference=message)
        raise ExitFunctionException


def local_check(check: bool, message: str):
    if check:
        debug(message)
        raise ExitFunctionException


def call_gpt(prompt, settings):
    debug(settings)
    return openai.Completion.create(prompt=prompt, **settings['gpt3'])['choices'][0]['text']


def basic_check(message: discord.Message, permission, dm=False):
    channel: discord.TextChannel = message.channel
    discord_check(not dm and not hasattr(channel, "guild"), message, "This command can't be used in DM.")
    discord_check(dm and hasattr(channel, "guild"), message, "This command only be used in DM.")
    if not dm:
        guild: discord.Guild = channel.guild
        discord_check(not channel.id == MESSAGE_CHANNEL or not guild.id == ALLOWED_GUILD, message,
                            "Insufficient permission. This bot can only be used in its dedicated channel on the "
                            "\"Yannic Kilcher\" discord server.")
    if permission:
        author: discord.User = message.author
        discord_check(author.id not in ADMIN_USER, message,
                            "Insufficient permission. Only the owners of this bot are allowed to run this command. "
                            "Try .add instead")


async def complete(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    channel: discord.TextChannel = message.channel
    await channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.",
                       reference=message)
    # basic_check(message, True)
    # await channel.send(call_gpt(message.content[len('.complete '):], settings))


async def verify(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    if message.channel.id == VERIFY_CHANNEL:
        await message.author.add_roles(discord.utils.get(message.guild.roles, id=VERIFIED_ROLE))
        await message.delete(delay=1)


async def prune(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    basic_check(message, True)
    server: discord.Guild = message.guild
    channel: discord.TextChannel = server.get_channel(SHITPOSTING_CHANNEL)
    now = datetime.datetime.now()
    async for msg in channel.history(limit=None):
        msg: discord.Message = msg
        created_at: datetime.datetime = msg.created_at
        if created_at > now + datetime.timedelta(days=PRUNING_DAYS):
            await msg.delete()



async def add(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    basic_check(message, False, True)

    query = message.content[len('.add '):]
    author_id = message.author.id
    reply = await CHANNEL.send(f"<@{author_id}> added ```\n{query}``` to the queue. You can vote on it by clicking the "
                               f":{APPROVAL_EMOJI.name}: or :{DISAPPROVAL_EMOJI.name}: reactions.\n\nTo add a query "
                               f"yourself, send me a message like `.add YOUR PROMPT HERE` via DM!")
    await reply.add_reaction(APPROVAL_EMOJI)
    await reply.add_reaction(DISAPPROVAL_EMOJI)

    sources[reply.id] = (query, author_id)


async def delete(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    basic_check(message, False, True)
    channel: discord.TextChannel = message.channel
    query = message.content[len('.delete '):]
    author_id = message.author.id
    deleted = False
    for reply_id, (qry, qry_author_id) in sources.items():
        if author_id == qry_author_id and qry == query:
            del sources[reply_id]
            await channel.send(f"Removed query.", reference=message)
            await CHANNEL.fetch_message(reply_id).delete()
            deleted = True
            break
    if not deleted:
        await channel.send(f"Didn't find query.", reference=message)


async def role(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    basic_check(message, False)
    query = message.content[len('.role '):]
    channel: discord.TextChannel = message.channel
    if query in ROLES:
        author: discord.Member = message.author
        guild: discord.Guild = message.guild
        queried_role: discord.Role = guild.get_role(ROLES[query])
        for role in author.roles:
            role: discord.Role = role
            if role == queried_role:
                await author.remove_roles(role)
                await channel.send(f"Removed role", reference=message)
                return
        await author.add_roles(queried_role)
        await channel.send(f"Added role", reference=message)
    else:
        await channel.send(f"Couldn't find role", reference=message)


async def add_fallback(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    channel: discord.TextChannel = message.channel
    basic_check(message, True)

    query = message.content[len('.add_fallback '):]
    FALLBACKS.append(query)

    await channel.send(f"Added query to the fallback list. There are now {len(FALLBACKS)} queries in said list.",
                       reference=message)


async def restart(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    channel: discord.TextChannel = message.channel
    basic_check(message, True)

    await channel.send(f"Restarting", reference=message)
    await dump_queue(client, message, sources, settings)

    os.system("python3 bot.py")
    os.kill(os.getppid(), signal.SIGTERM)


async def settings(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    channel: discord.TextChannel = message.channel
    await channel.send(''.join(["gpt3:\n\t", '\n\t'.join(sorted([f"{k}={v}" for k, v in settings['gpt3'].items()])),
                                '\n'
                                'bot:\n\t', '\n\t'.join(sorted([f"{k}={v}" for k, v in settings['bot'].items()]))]),
                       reference=message)


async def dump_queue(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    basic_check(message, True)
    with open("queue_dump.json", 'w') as f:
        f.write(jsonpickle.dumps(dict(sources), indent=4))
    channel: discord.TextChannel = message.channel
    await channel.send("Dumped queue.", reference=message)


async def dump_settings(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    basic_check(message, True)
    with open("setting_dump.json", 'w') as f:
        f.write(jsonpickle.dumps({key: dict(val) for key, val in settings.items()}, indent=4))
    channel: discord.TextChannel = message.channel
    await channel.send("Dumped settings.", reference=message)


async def dump_fallbacks(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    basic_check(message, True)
    with open("fallbacks.json", 'w') as f:
        f.write(jsonpickle.dumps(FALLBACKS, indent=4))
    channel: discord.TextChannel = message.channel
    await channel.send("Dumped fallbacks.", reference=message)


async def load_fallbacks(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    basic_check(message, True)
    with open("fallbacks.json", 'w') as f:
        fallbacks = jsonpickle.loads(f.read())
    FALLBACKS.clear()
    FALLBACKS.extend(fallbacks)
    channel: discord.TextChannel = message.channel
    await channel.send("Loaded fallbacks.", reference=message)


async def load_settings(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    with open("setting_dump.json", 'r') as f:
        tmp = jsonpickle.loads(f.read())
    for top_key, top_val in tmp.items():
        for key, val in top_val.items():
            settings[top_key][key] = val
    basic_check(message, True)
    channel: discord.TextChannel = message.channel
    await channel.send("Loaded settings.", reference=message)


async def load_queue(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    with open("queue_dump.json", 'r') as f:
        tmp = jsonpickle.loads(f.read())
    for key, val in tmp.items():
        sources[key] = val
    basic_check(message, True)
    channel: discord.TextChannel = message.channel
    await channel.send("Loaded queue.", reference=message)


async def eval_queue(client, sources):
    proposals = {}
    for answer_id, (prompt, user_id) in sources.items():
        message: discord.Message = await CHANNEL.fetch_message(answer_id)
        proposals[answer_id] = [0, user_id, prompt]
        for r in message.reactions:
            r: discord.Reaction = r
            e: discord.Emoji = r.emoji
            if e.name == DISAPPROVAL_EMOJI.name:
                proposals[answer_id][0] -= r.count
            elif e.name == APPROVAL_EMOJI.name:
                proposals[answer_id][0] += r.count
    return proposals


async def queue(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    channel: discord.TextChannel = message.channel
    proposals = await eval_queue(client, sources)
    proposals = sorted([(count, prompt) for _, (count, _, prompt) in proposals.items()], reverse=True)
    if len(proposals) == 0:
        await channel.send("Queue is empty", reference=message)
        return
    await channel.send('\n\n\n'.join([f'PROMPT: ```\n{prompt[:40]}```Score: {count}'
                                      for count, prompt in proposals[:10]])
                       + f'..and {len(proposals) - 10} more' * (len(proposals) > 10), reference=message)


async def start(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    channel: discord.TextChannel = message.channel
    discord_check(settings['bot']['started'], message, "Not starting another thread.")
    discord_check(not hasattr(channel, "guild"), message, "The bot can't be used in DM.")

    guild: discord.Guild = channel.guild
    author: discord.User = message.author
    discord_check(not channel.id == ALLOWED_CHANNEL or not guild.id == ALLOWED_GUILD, message,
                        "Insufficient permission. This bot can only be used in its dedicated channel on the "
                        "\"Yannic Kilcher\" discord server.")
    discord_check(author.id not in ADMIN_USER, message,
                        "Insufficient permission. Only the owner of this bot is allowed to run this command. "
                        "Try .add instead")
    settings['bot']['started'] = 1
    await channel.send("Starting the listener for this channel.", reference=message)

    while True:
        proposals = await eval_queue(client, sources)
        if proposals:
            _, (count, _, _) = max(proposals.items(), key=lambda x: x[1][0])
            best, message_id, author = random.choice([(prompt, message_id, author_id)
                                                      for message_id, (score, author_id, prompt)
                                                      in proposals.items()
                                                      if score == count])
            if count < settings['bot']['min_score'] and settings['bot']['use_fallback']:
                prompt = random.choice(FALLBACKS)
                response = call_gpt(prompt, settings)
                prompt: discord.Message = await channel.send(f"PROMPT:\n```\n{prompt}```")
                await channel.send(f"RESPONSE:\n```\n{response}```", reference=prompt)
            elif count < settings['bot']['min_score'] and settings['bot']['show_no_score']:
                await channel.send("Nothing has any score, skipping this one.")
            else:
                response = call_gpt(best, settings)
                await channel.send(f"<@{author}>\nRESPONSE:```\n{response}```",
                                   reference=await channel.fetch_message(message_id))
                del sources[message_id]
        elif settings['bot']['use_fallback']:
            prompt = random.choice(FALLBACKS)
            response = call_gpt(prompt, settings)
            prompt: discord.Message = await channel.send(f"PROMPT:\n```\n{prompt}```")
            await channel.send(f"RESPONSE:\n```\n{response}```", reference=prompt)
        elif settings['bot']['show_empty']:
            await channel.send("No prompts in queue, skipping this one.")

        min_ln = math.log(settings['bot']['min_response_time'])
        max_ln = math.log(settings['bot']['max_response_time'])
        delay = math.e ** (random.random() * (max_ln - min_ln) + min_ln)
        print(f"Next delay: {int(delay / 60):3d} minutes")
        start_time = time.time()
        await prune(client, message, sources, settings)
        time.sleep(delay + start_time - time.time())  # Ensure delay stays the same


async def change_setting(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    channel: discord.TextChannel = message.channel
    author: discord.User = message.author
    arguments = message.content.split(' ')[1:]
    discord_check(len(arguments) != 3, message,
                        "Invalid number of arguments. Should be `group_name parameter_name value`")
    discord_check(author.id not in ADMIN_USER, message,
                        "Invalid number of arguments. Should be `group_name parameter_name value`")
    group_name, parameter_name, value = arguments
    previous_value = settings[group_name][parameter_name]
    settings[group_name][parameter_name] = type(previous_value)(value)
    await channel.send(f"Changed {parameter_name} from {previous_value} to {value}", reference=message)


COMMANDS = {'change_setting': change_setting, 'settings': settings, 'add': add, 'complete': complete,
            'queue': queue, 'start': start, 'dump_queue': dump_queue, 'load_queue': load_queue,
            'dump_settings': dump_settings, 'load_settings': load_settings,
            'dump_fallbacks': dump_fallbacks, 'load_fallbacks': load_fallbacks, 'add_fallback': add_fallback,
            'delete': delete, 'role': role,
            'restart': restart, 'verify': verify
            }


async def bot_help(client: discord.Client, message: discord.Message, sources: dict, settings: dict):
    await message.channel.send(f'Available Commands: `{"` `".join(sorted(list(COMMANDS.keys())))}`', reference=message)


COMMANDS['help'] = bot_help


def init(idx: int, available_workers: list, handled_messages: dict, sources: dict, settings: dict):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client()

    @client.event
    async def on_message(message: discord.Message):
        fn_name = message.content[1:]

        if ' ' in fn_name:
            fn_name = fn_name[:fn_name.find(' ')]

        try:
            local_check(fn_name not in COMMANDS, "Unknown command")
            local_check(idx not in available_workers, "I'm already working. Skipping task.")
            local_check(not message.content.startswith('.'), "Not a command")
            time.sleep(idx * settings['bot']['max_synchronisation_delay_ms'] / THREADS / 1000)
            local_check(message.id in handled_messages, "handled already")
            local_check(message.id % len(available_workers) != available_workers.index(idx), f"Not mine {idx}")
        except ExitFunctionException:
            return
        handled_messages[message.id] = time.time()
        available_workers.remove(idx)

        try:
            await COMMANDS[fn_name](client, message, sources, settings)
        except ExitFunctionException:
            pass
        except Exception as exc:
            if LOG_LEVEL <= logging.ERROR:
                traceback.print_exc()

        if idx not in available_workers:
            available_workers.append(idx)

    @client.event
    async def on_ready():
        global APPROVAL_EMOJI, DISAPPROVAL_EMOJI, CHANNEL
        if isinstance(APPROVAL_EMOJI, str):
            for emoji in client.emojis:
                emoji: discord.Emoji = emoji
                if emoji.name == APPROVAL_EMOJI:
                    APPROVAL_EMOJI = emoji
                if emoji.name == DISAPPROVAL_EMOJI:
                    DISAPPROVAL_EMOJI = emoji
            connection: discord_state.ConnectionState = client._connection
            guild: discord.Guild = connection._get_guild(ALLOWED_GUILD)
            CHANNEL = guild.get_channel(ALLOWED_CHANNEL)
        if idx not in available_workers:
            available_workers.append(idx)
        debug(f"Instance {idx} ({len(available_workers)}/{THREADS}) logged in as {client.user.name}")

    loop.create_task(client.start(DISCORD_TOKEN))
    loop.run_forever()
    loop.close()


def clean_handled_messages(handled_messages):
    while True:
        for msg_id, timestamp in handled_messages.items():
            if timestamp + CLEANUP > time.time():
                del handled_messages[msg_id]
        time.sleep(CLEANUP)


def backup(sources):
    while True:
        with open("queue_dump.json", 'w') as f:
            f.write(jsonpickle.dumps(dict(sources), indent=4))
        time.sleep(600)


if __name__ == '__main__':
    manager = multiprocessing.Manager()
    _workers = manager.list([])
    _handled_messages = manager.dict({})
    _sources = manager.dict({})
    _gpt3 = manager.dict({})
    _bot = manager.dict({})
    _settings = manager.dict({})
    _gpt3.update({'temperature': 0.5,
                  'top_p': 1,
                  'max_tokens': 256,
                  'presence_penalty': 0.45,
                  'frequency_penalty': 0.65,
                  'best_of': 1,
                  'engine': "davinci"
                  })
    _bot.update({'min_response_time': 60,
                 'max_response_time': 60 * 60 * 24,
                 "started": 0,
                 'min_score': 0,
                 'show_no_score': 0,
                 'show_empty': 0,
                 'use_fallback': 0,
                 'max_synchronisation_delay_ms': 2000,
                 })
    _settings.update({'gpt3': _gpt3,
                      'bot': _bot
                      })
    procs = [
        multiprocessing.Process(target=init, args=(idx, _workers, _handled_messages, _sources, _settings), daemon=True)
        for idx in range(THREADS)]
    procs.append(multiprocessing.Process(target=clean_handled_messages, args=(_handled_messages,), daemon=True))
    procs.append(multiprocessing.Process(target=backup, args=(_sources,), daemon=True))
    for t in procs:
        t.start()
    for t in procs:
        t.join()
