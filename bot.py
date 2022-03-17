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

DISCORD_TOKEN = "XXXXXXXXXXXXXXXXXXXXXXXX.XXXXXX.XXXXXXXXXXXXXXX-XXXXXXXXXXX"  # Get one here: https://discord.com/developers/applications/
OPENAI_API_KEY = "sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # https://beta.openai.com/account/api-keys
OPENAI_ORGANIZATION = "org-XXXXXXXXXXXXXXXXXXXXXXXX"
SETTINGS = {'temperature': 0,
                  'top_p': 1,
                  'max_tokens': 256,
                  'presence_penalty': 0.45,
                  'frequency_penalty': 0.65,
                  'best_of': 1,
                  'engine': "davinci"
                  }
PREFIX = '.'
CLEANUP = 60
VERIFY_CHANNEL = 885760989608431636  # Yannic Kilcher "_verification"
VERIFIED_ROLE = 821375158295592961  # Yannic Kilcher "verified"
ALLOWED_CHANNEL = 953216859182866502  # Yannic Kilcher "gpt3"
MESSAGE_CHANNEL = 953216859182866502  # Yannic Kilcher "bot-chat"
ALLOWED_GUILD = 950816238882418728  # Yannic Kilcher
SHITPOSTING_CHANNEL = 736963923521175612
PRUNING_DAYS = 60
ADMIN_USER = [690665848876171274, 952850561340948541]  # ClashLuke, Endomorphosis 
ROLES = {'reinforcement-learning': 760062682693894144, 'computer-vision': 762042823666171955, 'natural-language-processing': 762042825260007446, 'meetup': 782362139087208478, 'verified': 821375158295592961, 'homebrew-nlp': 911661603190079528, 'world-modelz': 914229949873913877 }

APPROVAL_EMOJI: typing.Union[str, discord.Emoji] = "yes"
DISAPPROVAL_EMOJI: typing.Union[str, discord.Emoji] = "noo"
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

    fired_messages: typing.List[asyncio.Task]


def fire(ctx: Context, *coroutine: typing.Union[typing.Coroutine, typing.Iterable[typing.Coroutine]]) -> None:
    if len(coroutine) == 0:
        coroutine = coroutine[0]
    if isinstance(coroutine, typing.Coroutine):
        coroutine = [coroutine]
    ctx.fired_messages.extend([asyncio.create_task(coro) for coro in coroutine])


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

def detect_chinese(text):
    for c in text:
        if '\u4e00' <= c <= '\u9fff':
            return True
    return False

def call_gpt(prompt, settings):
    #if detect_chinese(prompt):
    #prompt = "Translate the following into English: \n'''" + prompt + "'''\n"
    value = openai.Completion.create(prompt=prompt,  engine="text-davinci-001",  temperature=1,  max_tokens=1024,   top_p=1, frequency_penalty=0,  presence_penalty=0    )["choices"][0]["text"]
    return (value)

async def basic_check(ctx: Context, permission, dm=False):
    channel: discord.TextChannel = ctx.message.channel
    await discord_check(ctx, not dm and not hasattr(channel, "guild"), "This command can't be used in DM.")
    await discord_check(ctx, dm and hasattr(channel, "guild"), "This command only be used in DM.")
    if not dm:
        guild: discord.Guild = channel.guild
        await discord_check(ctx, not channel.id == MESSAGE_CHANNEL or not guild.id == ALLOWED_GUILD,
                            "Insufficient permission. This bot can only be used in its dedicated channel on the "
                            "\"JusticeDAO\" discord server.")
    if permission:
        author: discord.User = ctx.message.author
        await discord_check(ctx, author.id not in ADMIN_USER,
                            "Insufficient permission. Only the owners of this bot are allowed to run this command. "
                            "Try .add instead")


async def prune(ctx: Context):
    channel: discord.TextChannel = ctx.client.get_channel(SHITPOSTING_CHANNEL)
    async for msg in channel.history(limit=None,
                                     before=datetime.datetime.now() - datetime.timedelta(days=PRUNING_DAYS)):
        try:
            fire(ctx, msg.delete())
        except discord.errors.NotFound:
            break

def detect_if_english_text(text):
    for c in text:
        if '\u0041' <= c <= '\u005a' or '\u0061' <= c <= '\u007a':
            return True
    return False

def detect_if_chinese_text(text):
    for c in text:
        if '\u4e00' <= c <= '\u9fff':
            return True
    return False

def detect_if_japanese_text(text):
    for c in text:
        if '\u3041' <= c <= '\u3096':
            return True
    return False

def detect_if_korean_text(text):
    for c in text:
        if '\uac00' <= c <= '\ud7a3':
            return True
    return False

def detect_if_arabic_text(text):
    for c in text:
        if '\u0600' <= c <= '\u06ff':
            return True
    return False

def detect_if_portuguese_text(text):
    for c in text:
        if '\u0041' <= c <= '\u005a' or '\u0061' <= c <= '\u007a' or '\u00c0' <= c <= '\u00ff':
            return True
    return False

def detect_if_russian_text(text):
    for c in text:
        if '\u0400' <= c <= '\u04ff':
            return True
    return False

def detect_if_spanish_text(text):
    for c in text:
        if '\u0041' <= c <= '\u005a' or '\u0061' <= c <= '\u007a' or '\u00c0' <= c <= '\u00ff':
            return True
    return False

def detect_if_french_text(text):
    for c in text:
        if '\u0041' <= c <= '\u005a' or '\u0061' <= c <= '\u007a' or '\u00c0' <= c <= '\u00ff':
            return True
    return False

def detect_if_italian_text(text):
    for c in text:
        if '\u0041' <= c <= '\u005a' or '\u0061' <= c <= '\u007a' or '\u00c0' <= c <= '\u00ff':
            return True
    return False

def detect_if_german_text(text):
    for c in text:
        if '\u0041' <= c <= '\u005a' or '\u0061' <= c <= '\u007a' or '\u00c0' <= c <= '\u00ff':
            return True
    return False    



async def complete(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    await channel.send(call_gpt(ctx.message.content[len('.complete '):], settings))


async def ko(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en coréen \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成韩语 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на корейский \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下を韓国語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in coreano \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o coreano \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetze folgendes ins Koreanische \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 한국어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al coreano \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into korean \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    await channel.send(call_gpt(text, settings))

async def zh(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en chinois \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成中文 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на китайский \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下を中国語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in cinese \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o chinês \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetze das Folgende ins Chinesische \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 중국어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al chino \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into chinese \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    await channel.send(call_gpt(text, settings))



async def es(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en espagnol \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成西班牙语 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на испанский \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下をスペイン語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in spagnolo \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o espanhol \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetze das Folgende ins Spanische \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 스페인어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al español \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into spanish \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    await channel.send(call_gpt(text, settings))

async def pt(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en portugais \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成葡萄牙语 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на португальский \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下をポルトガル語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in portoghese \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o português \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetze das Folgende ins Portugiesische \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 포르투갈어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al portugués \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into portugese \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    await channel.send(call_gpt(text, settings))

async def it(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en italien \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成意大利语 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на итальянский \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下をイタリア語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in italiano \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o italiano \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetze das Folgende ins Italienische \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 이탈리아어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al italiano \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into italian \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    await channel.send(call_gpt(text, settings))

async def ja(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en japonais \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成日文 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на японский \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下を日本語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in giapponese \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o japonês\n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetzen Sie das Folgende ins Japanische \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 일본어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al japonés \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into japanese \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'

    await channel.send(call_gpt(text, settings))

async def en(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en anglais \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成英文 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на английский \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下を英語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in inglese \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o inglês \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetzen Sie das Folgende ins Englische \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 영어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al ingles \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into english \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    await channel.send(call_gpt(text, settings))

async def ru(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en russe \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成俄语 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на русский язык \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下をロシア語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in russo \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o russo \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetzen Sie das Folgende ins Russische \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 러시아어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al ruso \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into russian  \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'

    await channel.send(call_gpt(text, settings))

async def de(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en allemand \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成德语 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на немецкий \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下をドイツ語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in tedesco \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o alemão \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetze das Folgende ins Deutsche \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 독일어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al alemán \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into german \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    await channel.send(call_gpt(text, settings))

async def fr(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    #fire(ctx, channel.send("This command is temporarily gone, but will be back in the future! Use .add instead.", reference=ctx.message))
    #await basic_check(ctx, True)
    if detect_if_french_text(ctx.message.content[len('.complete '):]):
        text = 'Traduisez ce qui suit en français\n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_chinese_text(ctx.message.content[len('.complete '):]):
        text = '将以下内容翻译成法语 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_russian_text(ctx.message.content[len('.complete '):]):
        text = 'Переведите следующее на французский \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_japanese_text(ctx.message.content[len('.complete '):]):
        text = '以下をフランス語に翻訳する \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_italian_text(ctx.message.content[len('.complete '):]):
        text = 'Traduci quanto segue in francese \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_portuguese_text(ctx.message.content[len('.complete '):]):
        text = 'Traduza o seguinte para o francês\n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_german_text(ctx.message.content[len('.complete '):]):
        text = 'Übersetze das Folgende ins Französische\n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_korean_text(ctx.message.content[len('.complete '):]):
        text = '다음을 프랑스어로 번역 \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    if detect_if_spanish_text(ctx.message.content[len('.complete '):]):
        text = 'Traduce lo siguiente al francés \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n' 
    if detect_if_english_text(ctx.message.content[len('.complete '):]):
        text = 'Translate the following into french \n """' + ctx.message.content[len('.complete '):] + '"""' + '\n'
    await channel.send(call_gpt(text, settings))



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
    for reply_id, (qry, qry_author_id) in ctx.sources.items():
        if author_id == qry_author_id and qry == query:
            del ctx.sources[reply_id]
            fire(ctx, channel.send(f"Removed query.", reference=ctx.message),
                 (await CHANNEL.fetch_message(reply_id)).delete())
            deleted = True
            break
    if not deleted:
        fire(ctx, channel.send(f"Didn't find query.", reference=ctx.message))


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
    ctx.fired_messages.clear()


async def restart(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    await basic_check(ctx, True)

    fire(ctx, channel.send(f"Restarting", reference=ctx.message), dump_queue(ctx))
    await await_ctx(ctx)

    os.system("python3 bot.py")
    os.kill(os.getppid(), signal.SIGTERM)


async def settings(ctx: Context):
    channel: discord.TextChannel = ctx.message.channel
    fire(ctx,
         channel.send(''.join(["gpt3:\n\t", '\n\t'.join(sorted([f"{k}={v}" for k, v in ctx.settings['gpt3'].items()])),
                               '\n'
                               'bot:\n\t', '\n\t'.join(sorted([f"{k}={v}" for k, v in ctx.settings['bot'].items()]))]),
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
        f.write(jsonpickle.dumps({key: dict(val) for key, val in ctx.settings.items()}, indent=4))
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
    channel: discord.TextChannel = ctx.client.get_channel(ALLOWED_CHANNEL)
    ctx.settings['bot']['started'] = 1

    while True:
        min_ln = math.log(ctx.settings['bot']['min_response_time'])
        max_ln = math.log(ctx.settings['bot']['max_response_time'])
        delay = math.e ** (random.random() * (max_ln - min_ln) + min_ln)
        print(f"Next delay: {int(delay / 60):3d} minutes")
        start_time = time.time()

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
                fire(ctx, channel.send(f"RESPONSE:\n```\n{response}```", reference=prompt))
            elif count < ctx.settings['bot']['min_score'] and ctx.settings['bot']['show_no_score']:
                fire(ctx, channel.send("Nothing has any score, skipping this one."))
            else:
                response = call_gpt(best, ctx.settings)
                fire(ctx, channel.send(f"<@{author}>\nRESPONSE:```\n{response}```",
                                       reference=await channel.fetch_message(message_id)))
                del ctx.sources[message_id]
        elif ctx.settings['bot']['use_fallback']:
            prompt = random.choice(FALLBACKS)
            response = call_gpt(prompt, ctx.settings)
            prompt: discord.Message = await channel.send(f"PROMPT:\n```\n{prompt}```")
            fire(ctx, channel.send(f"RESPONSE:\n```\n{response}```", reference=prompt))
        elif ctx.settings['bot']['show_empty']:
            fire(ctx, channel.send("No prompts in queue, skipping this one."))

        await await_ctx(ctx)
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
        'queue': queue, 'dump_queue': dump_queue, 'load_queue': load_queue,
            'dump_settings': dump_settings, 'load_settings': load_settings,
            'dump_fallbacks': dump_fallbacks, 'load_fallbacks': load_fallbacks, 'add_fallback': add_fallback,
            'delete': delete, 'role': role,
            'restart': restart, 'verify': verify,
            'en': en, 'ru': ru, 'de': de, 'fr': fr, 'es': es, 'it': it, 'pt': pt, 'ja': ja, 'ko': ko, 'zh': zh
            }


async def bot_help(ctx: Context):
    fire(ctx, ctx.message.channel.send(f'Available Commands: `{"` `".join(sorted(list(COMMANDS.keys())))}`',
                                       reference=ctx.message))


COMMANDS['help'] = bot_help


async def process_spam(ctx: Context):
    content = ctx.message.content
    if not (('http://' in content or 'https://' in content) and ('disc' in content or 'disoc' in content) and
            ('gift' in content or 'gft' in content)):
        return
    author: discord.User = ctx.message.author
    server: discord.Guild = ctx.message.guild
    await ctx.message.delete()
    await server.kick(author, reason=f'Spam: {ctx.message.content}')


async def process_message(ctx: Context):
    fn_name = ctx.message.content[1:]

    if ' ' in fn_name:
        fn_name = fn_name[:fn_name.find(' ')]
    fire(ctx, process_spam(ctx))

    try:
        local_check(fn_name not in COMMANDS, "Unknown command")
        local_check(not ctx.message.content.startswith('.'), "Not a command")
    except ExitFunctionException:
        return

    try:
        await COMMANDS[fn_name](ctx)
    except ExitFunctionException:
        pass
    except Exception as exc:
        if LOG_LEVEL <= logging.ERROR:
            traceback.print_exc()


def init_fn(sources: dict, settings: dict, fn: typing.Union[start, prune]):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client()

    @client.event
    async def on_message(message: discord.Message):
        return

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
            CHANNEL = client.get_channel(ALLOWED_CHANNEL)
        debug(f"{fn.__name__} logged in as {client.user.name}")
        await fn(Context(client, None, sources, settings, []))

    loop.create_task(client.start(DISCORD_TOKEN))
    loop.run_forever()
    loop.close()


def init(sources: dict, settings: dict):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client()

    @client.event
    async def on_message(message: discord.Message):
        ctx: Context = Context(client, message, sources, settings, [])
        fire(ctx, process_message(ctx))
        await await_ctx(ctx)

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
            CHANNEL = client.get_channel(ALLOWED_CHANNEL)
        debug(f"Core logged in as {client.user.name}")

    loop.create_task(client.start(DISCORD_TOKEN))
    loop.run_forever()
    loop.close()


def backup(sources):
    while True:
        with open("queue_dump.json", 'w') as f:
            f.write(jsonpickle.dumps(dict(sources), indent=4))
        time.sleep(600)


if __name__ == '__main__':
    manager = multiprocessing.Manager()
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
                 'max_response_time': 60,
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

    procs = [multiprocessing.Process(target=init, args=(_sources, _settings), daemon=True),
             multiprocessing.Process(target=init_fn, args=(_sources, _settings, start), daemon=True),
             multiprocessing.Process(target=init_fn, args=(_sources, _settings, prune), daemon=True)]
    for t in procs:
        t.start()
    backup(_sources)
