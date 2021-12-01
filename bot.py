import asyncio
import dataclasses
import datetime
import logging
import math
import multiprocessing
import os
import random
import signal
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
         'natural-language-processing': 762042825260007446, 'meetup': 782362139087208478,
         'verified': 821375158295592961, 'homebrew-nlp': 911661603190079528,
         'world-modelz': 914229949873913877}
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


@dataclasses.dataclass
class Context:
    client: discord.Client
    message: discord.Message
    sources: dict
    settings: dict

    fired_messages: typing.List[typing.Coroutine]


def fire(ctx: Context, *coroutine: typing.Union[typing.Coroutine, typing.Iterable[typing.Coroutine]]) -> None:
    if len(coroutine) == 0:
        coroutine = coroutine[0]
    ctx.fired_messages.extend(coroutine)


def debug(message: typing.Any):
    if LOG_LEVEL <= logging.DEBUG:
        print(message)


async def discord_check(ctx: Context, check: bool, response: str):
    if check:
        channel: discord.TextChannel = ctx.message.channel
        fire(ctx, channel.send(response, reference=ctx.message))
        raise ExitFunctionException


def local_check(check: bool, message: str):
    if check:
        debug(message)
        raise ExitFunctionException


def call_gpt(prompt, settings):
    debug(settings)
    return openai.Completion.create(prompt=prompt, **settings['gpt3'])['choices'][0]['text']


async def basic_check(ctx: Context, permission, dm=False):
    channel: discord.TextChannel = ctx.message.channel
    await discord_check(ctx, not dm and not hasattr(channel, "guild"), "This command can't be used in DM.")
    await discord_check(ctx, dm and hasattr(channel, "guild"), "This command only be used in DM.")
    if not dm:
        guild: discord.Guild = channel.guild
        await discord_check(ctx, not channel.id == MESSAGE_CHANNEL or not guild.id == ALLOWED_GUILD,
                            "Insufficient permission. This bot can only be used in its dedicated channel on the "
                            "\"Yannic Kilcher\" discord server.")
    if permission:
        author: discord.User = ctx.message.author
        await discord_check(ctx, author.id not in ADMIN_USER,
                            "Insufficient permission. Only the owners of this bot are allowed to run this command. "
                            "Try .add instead")


async def prune(ctx: Context):
    channel: discord.TextChannel = ctx.message.guild.get_channel(SHITPOSTING_CHANNEL)
    deletions = []
    async for msg in channel.history(limit=None,
                                     before=datetime.datetime.now() - datetime.timedelta(days=PRUNING_DAYS)):
        try:
            deletions.append(msg.delete())
        except discord.errors.NotFound:
            break
    fire(ctx, deletions)


async def complete(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.",
                           reference=ctx.message))
    # await basic_check(message, True)
    # await channel.send(call_gpt(message.content[len('.complete '):], settings))


async def verify(ctx: Context):
    if ctx.message.channel.id == VERIFY_CHANNEL:
        fire(ctx,
             ctx.message.author.add_roles(discord.utils.get(ctx.message.guild.roles, id=VERIFIED_ROLE)),
             ctx.message.delete(delay=1))


async def add(ctx: Context):
    await basic_check(ctx, False, True)

    query = ctx.message.content[len('.add '):]
    author_id = ctx.message.author.id
    reply = await CHANNEL.send(f"<@{author_id}> added ```\n{query}``` to the queue. You can vote on it by clicking the "
                               f":{APPROVAL_EMOJI.name}: or :{DISAPPROVAL_EMOJI.name}: reactions.\n\nTo add a query "
                               f"yourself, send me a message like `.add YOUR PROMPT HERE` via DM!")
    fire(ctx, reply.add_reaction(APPROVAL_EMOJI), reply.add_reaction(DISAPPROVAL_EMOJI))

    ctx.sources[reply.id] = (query, author_id)


async def delete(ctx: Context):
    await basic_check(ctx, False, True)
    channel: discord.TextChannel = ctx.message.channel
    query = ctx.message.content[len('.delete '):]
    author_id = ctx.message.author.id
    deleted = False
    ops = []
    for reply_id, (qry, qry_author_id) in ctx.sources.items():
        if author_id == qry_author_id and qry == query:
            del ctx.sources[reply_id]
            ops.extend([channel.send(f"Removed query.", reference=ctx.message),
                        CHANNEL.fetch_message(reply_id).delete()])
            deleted = True
            break
    if not deleted:
        ops.append(channel.send(f"Didn't find query.", reference=ctx.message))
    fire(ctx, ops)


async def role(ctx: Context):
    await basic_check(ctx, False)
    query = ctx.message.content[len('.role '):]
    channel: discord.TextChannel = ctx.message.channel

    if query in ROLES:
        author: discord.Member = ctx.message.author
        guild: discord.Guild = ctx.message.guild
        queried_role: discord.Role = guild.get_role(ROLES[query])
        for role in author.roles:
            role: discord.Role = role
            if role == queried_role:
                fire(ctx, author.remove_roles(role), channel.send(f"Removed role", reference=ctx.message))
                return
        fire(ctx, author.add_roles(queried_role), channel.send(f"Added role", reference=ctx.message))
    else:
        fire(ctx, channel.send(f"Couldn't find role", reference=ctx.message))


async def add_fallback(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    await basic_check(ctx, True)

    query = ctx.message.content[len('.add_fallback '):]
    FALLBACKS.append(query)

    fire(ctx, channel.send(f"Added query to the fallback list. There are now {len(FALLBACKS)} queries in said list.",
                           reference=ctx.message))


async def await_ctx(ctx: Context):
    for msg in ctx.fired_messages:
        await msg


async def restart(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    await basic_check(ctx, True)

    fire(ctx, channel.send(f"Restarting", reference=ctx.message), dump_queue(ctx))
    await await_ctx(ctx)

    os.system("python3 bot.py")
    os.kill(os.getppid(), signal.SIGTERM)


async def settings(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx, channel.send(''.join(["gpt3:\n\t", '\n\t'.join(sorted([f"{k}={v}" for k, v in settings['gpt3'].items()])),
                                    '\n'
                                    'bot:\n\t', '\n\t'.join(sorted([f"{k}={v}" for k, v in settings['bot'].items()]))]),
                           reference=ctx.message))


async def dump_queue(ctx: Context):
    await basic_check(ctx, True)
    with open("queue_dump.json", 'w') as f:
        f.write(jsonpickle.dumps(dict(ctx.sources), indent=4))
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx, channel.send("Dumped queue.", reference=ctx.message))


async def dump_settings(ctx: Context):
    await basic_check(ctx, True)
    with open("setting_dump.json", 'w') as f:
        f.write(jsonpickle.dumps({key: dict(val) for key, val in settings.items()}, indent=4))
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx, channel.send("Dumped settings.", reference=ctx.message))


async def dump_fallbacks(ctx: Context):
    await basic_check(ctx, True)
    with open("fallbacks.json", 'w') as f:
        f.write(jsonpickle.dumps(FALLBACKS, indent=4))
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx, channel.send("Dumped fallbacks.", reference=ctx.message))


async def load_fallbacks(ctx: Context):
    await basic_check(ctx, True)
    with open("fallbacks.json", 'w') as f:
        fallbacks = jsonpickle.loads(f.read())
    FALLBACKS.clear()
    FALLBACKS.extend(fallbacks)
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx, channel.send("Loaded fallbacks.", reference=ctx.message))


async def load_settings(ctx: Context):
    with open("setting_dump.json", 'r') as f:
        tmp = jsonpickle.loads(f.read())
    for top_key, top_val in tmp.items():
        for key, val in top_val.items():
            ctx.settings[top_key][key] = val
    await basic_check(ctx, True)
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx, channel.send("Loaded settings.", reference=ctx.message))


async def load_queue(ctx: Context):
    with open("queue_dump.json", 'r') as f:
        tmp = jsonpickle.loads(f.read())
    for key, val in tmp.items():
        ctx.sources[key] = val
    await basic_check(ctx, True)
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx, channel.send("Loaded queue.", reference=ctx.message))


async def eval_queue(ctx: Context):
    proposals = {}
    for answer_id, (prompt, user_id) in ctx.sources.items():
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


async def queue(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    proposals = await eval_queue(ctx)
    proposals = sorted([(count, prompt) for _, (count, _, prompt) in proposals.items()], reverse=True)
    if len(proposals) == 0:
        fire(ctx, channel.send("Queue is empty", reference=ctx.message))
        return
    fire(ctx, channel.send('\n\n\n'.join([f'PROMPT: ```\n{prompt[:40]}```Score: {count}'
                                          for count, prompt in proposals[:10]])
                           + f'..and {len(proposals) - 10} more' * (len(proposals) > 10), reference=ctx.message))


async def start(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    await discord_check(ctx, ctx.settings['bot']['started'], "Not starting another thread.")
    await discord_check(ctx, not hasattr(channel, "guild"), "The bot can't be used in DM.")

    guild: discord.Guild = channel.guild
    author: discord.User = ctx.message.author
    await discord_check(ctx, not channel.id == ALLOWED_CHANNEL or not guild.id == ALLOWED_GUILD,
                        "Insufficient permission. This bot can only be used in its dedicated channel on the "
                        "\"Yannic Kilcher\" discord server.")
    await discord_check(ctx, author.id not in ADMIN_USER,
                        "Insufficient permission. Only the owner of this bot is allowed to run this command. "
                        "Try .add instead")
    ctx.settings['bot']['started'] = 1
    fire(ctx, channel.send("Starting the listener for this channel.", reference=ctx.message),
         prune(ctx))

    while True:
        proposals = await eval_queue(ctx)
        if proposals:
            _, (count, _, _) = max(proposals.items(), key=lambda x: x[1][0])
            best, message_id, author = random.choice([(prompt, message_id, author_id)
                                                      for message_id, (score, author_id, prompt)
                                                      in proposals.items()
                                                      if score == count])
            if count < ctx.settings['bot']['min_score'] and ctx.settings['bot']['use_fallback']:
                prompt = random.choice(FALLBACKS)
                response = call_gpt(prompt, ctx.settings)
                prompt: discord.Message = await channel.send(f"PROMPT:\n```\n{prompt}```")
                await channel.send(f"RESPONSE:\n```\n{response}```", reference=prompt)
            elif count < ctx.settings['bot']['min_score'] and ctx.settings['bot']['show_no_score']:
                await channel.send("Nothing has any score, skipping this one.")
            else:
                response = call_gpt(best, ctx.settings)
                await channel.send(f"<@{author}>\nRESPONSE:```\n{response}```",
                                   reference=await channel.fetch_message(message_id))
                del ctx.sources[message_id]
        elif ctx.settings['bot']['use_fallback']:
            prompt = random.choice(FALLBACKS)
            response = call_gpt(prompt, ctx.settings)
            prompt: discord.Message = await channel.send(f"PROMPT:\n```\n{prompt}```")
            await channel.send(f"RESPONSE:\n```\n{response}```", reference=prompt)
        elif ctx.settings['bot']['show_empty']:
            await channel.send("No prompts in queue, skipping this one.")

        min_ln = math.log(ctx.settings['bot']['min_response_time'])
        max_ln = math.log(ctx.settings['bot']['max_response_time'])
        delay = math.e ** (random.random() * (max_ln - min_ln) + min_ln)
        print(f"Next delay: {int(delay / 60):3d} minutes")
        start_time = time.time()
        time.sleep(delay + start_time - time.time())  # Ensure delay stays the same


async def change_setting(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    author: discord.User = ctx.message.author
    arguments = ctx.message.content.split(' ')[1:]
    await discord_check(ctx, len(arguments) != 3,
                        "Invalid number of arguments. Should be `group_name parameter_name value`")
    await discord_check(ctx, author.id not in ADMIN_USER,
                        "Invalid number of arguments. Should be `group_name parameter_name value`")
    group_name, parameter_name, value = arguments
    previous_value = ctx.settings[group_name][parameter_name]
    ctx.settings[group_name][parameter_name] = type(previous_value)(value)
    fire(ctx, channel.send(f"Changed {parameter_name} from {previous_value} to {value}", reference=ctx.message))


COMMANDS = {'change_setting': change_setting, 'settings': settings, 'add': add, 'complete': complete,
            'queue': queue, 'start': start, 'dump_queue': dump_queue, 'load_queue': load_queue,
            'dump_settings': dump_settings, 'load_settings': load_settings,
            'dump_fallbacks': dump_fallbacks, 'load_fallbacks': load_fallbacks, 'add_fallback': add_fallback,
            'delete': delete, 'role': role,
            'restart': restart, 'verify': verify
            }


async def bot_help(ctx: Context):
    fire(ctx, ctx.message.channel.send(f'Available Commands: `{"` `".join(sorted(list(COMMANDS.keys())))}`',
                                       reference=ctx.message))


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
            local_check(message.id in handled_messages, "handled already")
            local_check(message.id % len(available_workers) != available_workers.index(idx), f"Not mine {idx}")
        except ExitFunctionException:
            return

        handled_messages[message.id] = time.time()
        available_workers.remove(idx)
        ctx: Context = Context(client, message, sources, settings, [])

        try:
            fire(ctx, COMMANDS[fn_name](ctx))
        except ExitFunctionException:
            pass
        except Exception as exc:
            if LOG_LEVEL <= logging.ERROR:
                traceback.print_exc()

        await_ctx(ctx)

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
