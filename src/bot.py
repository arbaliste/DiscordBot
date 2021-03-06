import asyncio
import importlib
import shlex
import json
import glob
from os import path
from . import util
from . import api

commands = []
tasks = []

async def set_environment(key, value):
    global environment
    environment[key] = value

async def import_dir(dir):
    files = glob.glob('%s/%s/*.py' % (path.dirname(__file__), dir))
    items = [path.basename(f)[:-3] for f in files if path.isfile(f) and not f.endswith('__init__.py')]
    return { x: importlib.import_module('.' + dir + '.' + x, __name__[:__name__.rfind('.')]) for x in items }

async def task_loop():
    while True:
        for name, task in tasks.items():
            await task.run(commands, environment)
        await asyncio.sleep(60*60)

async def check_access(command, user):
    if (user == environment['botId']) \
    or (command.access == util.levels.owner and user != environment['ownerId']) \
    or (command.access == util.levels.none):
        return False
    return True

async def on_init():
    global commands, tasks, environment
    with open('secret.json') as secret:
        environment = json.loads(secret.read())
    command_dict = await import_dir('commands')
    commands = { v.command.prog: v.command for _, v in command_dict.items() }
    task_dict = await import_dir('tasks')
    tasks = { v.task.name: v.task for _, v in task_dict.items() }
    await api.on_init(environment['token'])

async def on_connect():
    await util.log('Connected!')

async def on_message(message):
    if message['content'].startswith(environment['commandStart']):
        commandstr = message['content'][len(environment['commandStart']):]
        for name, command in commands.items():
            if commandstr.startswith(name):
                if not await check_access(command, message['user']):
                    command.channel = message['channel']
                    command.error('unauthorized')
                    return
                try:
                    parsedargs = shlex.split(commandstr[len(name) + 1:])
                except ValueError:
                    command.channel = message['channel']
                    command.error('malformed command string')
                    return
                with util.CommandContext(command, message['channel']):
                    try:
                        args = command.parse_args(parsedargs)
                    except ValueError:
                        # Printing is handled by the callback
                        return
                    await command.run(args, message['user'], message['channel'], commands, environment)
                break
