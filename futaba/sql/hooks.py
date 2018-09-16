#
# sql/hooks.py
#
# futaba - A Discord Mod bot for the Programming server
# Copyright (c) 2017-2018 Jake Richardson, Ammon Smith, jackylam5
#
# futaba is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

'''
Hooks that trigger on certain events to ensure database consistency.
'''

import logging

__all__ = [
    'HOOK_NAMES',
    'register_hook',
    'run_hooks',
]

HOOK_NAMES = (
    'on_guild_join',
    'on_guild_leave',
)

_hooks = {name: [] for name in HOOK_NAMES}
logger = logging.getLogger(__name__)

def register_hook(name, hook):
    if name not in HOOK_NAMES:
        raise ValueError(f"No such hook type: {name}")

    logger.info("Register hook %r for '%s'", hook, name)
    _hooks[name].append(hook)

def run_hooks(name, *args, **kwargs):
    logger.info("Running hooks for '%s'...", name)
    for hook in _hooks[name]:
        try:
            hook(*args, **kwargs)
        except Exception as error:
            logger.error("Error running hook %r!", hook, exc_info=error)
    logger.debug("Finished '%s' hooks.", name)
