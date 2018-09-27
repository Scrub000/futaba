#
# cogs/settings/core.py
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
Cog for all commands that change bot settings. It ensures persistence
of configured settings in between runs of the bot.
'''

import asyncio
import logging
import re

import discord
from discord.ext import commands

from futaba import permissions
from futaba.emojis import ICONS
from futaba.enums import Reactions
from futaba.parse import get_role_id
from futaba.permissions import mod_perm
from futaba.utils import escape_backticks

logger = logging.getLogger(__name__)

__all__ = [
    'Settings',
]

class Settings:
    __slots__ = (
        'bot',
        'journal',
    )

    def __init__(self, bot):
        self.bot = bot
        self.journal = bot.get_broadcaster('/settings')

        for guild in bot.guilds:
            bot.sql.settings.get_special_roles(guild)

    @commands.command(name='prefix')
    async def prefix(self, ctx, *, prefix: str = None):
        '''
        Gets the current prefix. If you're a moderator, you can set it too.
        A trailing underscore is converted into spaces. A single '_' unsets
        the bot's prefix, and uses the default one.
        '''

        # Get prefix
        if prefix is None:
            bot_prefix = self.bot.prefix(ctx.message)
            embed = discord.Embed(colour=discord.Colour.dark_teal())
            if ctx.guild is None:
                embed.description = 'No command prefix, all messages are commands.'
            else:
                embed.description = f'Prefix for {ctx.guild.name} is `{bot_prefix}`.'
            reaction = Reactions.SUCCESS

        # Attempt to set prefix outside of guild
        elif ctx.guild is None and prefix is not None:
            embed = discord.Embed(colour=discord.Colour.dark_red())
            embed.description = 'Cannot set a command prefix outside of a server!'
            reaction = Reactions.FAIL

        # Unset prefix
        elif prefix == '_':
            with self.bot.sql.transaction():
                self.bot.sql.settings.set_prefix(ctx.guild, None)
                bot_prefix = self.bot.prefix(ctx.message)

            embed = discord.Embed(colour=discord.Colour.dark_teal())
            embed.description = f'Unset prefix for {ctx.guild.name}. (Default prefix: `{bot_prefix}`)'
            self.journal.send('prefix', ctx.guild, 'Unset bot command prefix', icon='settings',
                    prefix=None, default_prefix=self.bot.config.default_prefix)
            reaction = Reactions.SUCCESS

        # Lacking authority to set prefix
        elif not mod_perm(ctx):
            embed = discord.Embed(colour=discord.Colour.dark_red())
            embed.description = 'You do not have permission to set the prefix'
            reaction = Reactions.DENY

        # Set prefix
        else:
            bot_prefix = re.sub(r'_$', ' ', prefix)
            with self.bot.sql.transaction():
                self.bot.sql.settings.set_prefix(ctx.guild, bot_prefix)

            embed = discord.Embed(colour=discord.Colour.dark_teal())
            embed.description = f'Set prefix for {ctx.guild.name} to `{bot_prefix}`'
            self.journal.send('prefix', ctx.guild, 'Unset bot command prefix', icon='settings',
                    prefix=bot_prefix, default_prefix=self.bot.config.default_prefix)
            reaction = Reactions.SUCCESS

        await asyncio.gather(
            ctx.send(embed=embed),
            reaction.add(ctx.message),
        )

    @commands.command(name='specroles', aliases=['sroles'])
    @commands.guild_only()
    async def special_roles(self, ctx):
        ''' Retrieves all configured roles for this guild. '''

        logger.info("Sending list of all configured roles for guild '%s' (%d)",
                ctx.guild.name, ctx.guild.id)

        roles = self.bot.sql.settings.get_special_roles(ctx.guild)
        mention = lambda role: getattr(role, 'mention', '(none)')

        embed = discord.Embed(colour=discord.Colour.dark_teal())
        embed.description = '\n'.join((
            f'{ICONS["member"]} Member: {mention(roles.member)}',
            f'{ICONS["guest"]} Guest: {mention(roles.guest)}',
            f'{ICONS["mute"]} Mute: {mention(roles.mute)}',
            f'{ICONS["jail"]} Jail: {mention(roles.jail)}',
        ))

        await asyncio.gather(
            ctx.send(embed=embed),
            Reactions.SUCCESS.add(ctx.message),
        )

    async def get_role(self, ctx, name):
        role_id = get_role_id(name, ctx.guild.roles)
        role = discord.utils.get(ctx.guild.roles, id=role_id)
        embed = discord.Embed(colour=discord.Colour.dark_red())
        if role is None:
            embed.description = f'No role with description `{escape_backticks(name)}` found'
            await asyncio.gather(
                ctx.send(embed=embed),
                Reactions.FAIL.add(ctx.message),
            )
            return None
        elif role.is_default():
            embed.description = '@everyone role cannot be assigned for this purpose'
            await asyncio.gather(
                ctx.send(embed=embed),
                Reactions.FAIL.add(ctx.message),
            )
            return None

        special_roles = self.bot.sql.settings.get_special_roles(ctx.guild)
        if role in special_roles:
            embed.description = f'Cannot assign the same role for multiple purposes'
            await asyncio.gather(
                ctx.send(embed=embed),
                Reactions.FAIL.add(ctx.message),
            )
            return None

        return role

    @commands.command(name='setmember')
    @commands.guild_only()
    @permissions.check_mod()
    async def set_member_role(self, ctx, *, name: str = None):
        ''' Set the member role for this guild. No argument to unset. '''

        logger.info("Setting member role for guild '%s' (%d) to '%s'",
                ctx.guild.name, ctx.guild.id, name)

        if name is None:
            role = None
        else:
            role = await self.get_role(ctx, name)
            if role is None:
                return

        with self.bot.sql.transaction():
            self.bot.sql.settings.set_special_roles(ctx.guild, member=role)

        embed = discord.Embed(colour=discord.Colour.green())
        if role:
            embed.description = f'Set member role to {role.mention}'
            content = f'Set member role to {role.mention}'
        else:
            embed.description = 'Unset member role'
            content = 'Unset the member role'

        await asyncio.gather(
            ctx.send(embed=embed),
            Reactions.SUCCESS.add(ctx.message),
        )
        self.journal.send('roles/member', ctx.guild, content, icon='settings', role=role)

    @commands.command(name='setguest')
    @commands.guild_only()
    @permissions.check_mod()
    async def set_guest_role(self, ctx, *, name: str = None):
        ''' Set the guest role for this guild. No argument to unset. '''

        logger.info("Setting guest role for guild '%s' (%d) to '%s'",
                ctx.guild.name, ctx.guild.id, name)

        if name is None:
            role = None
        else:
            role = await self.get_role(ctx, name)
            if role is None:
                return

        with self.bot.sql.transaction():
            self.bot.sql.settings.set_special_roles(ctx.guild, guest=role)

        embed = discord.Embed(colour=discord.Colour.green())
        if role:
            embed.description = f'Set guest role to {role.mention}'
            content = f'Set the guest role to {role.mention}'
        else:
            embed.description = 'Unset guest role'
            content = 'Unset the guest role'

        await asyncio.gather(
            ctx.send(embed=embed),
            Reactions.SUCCESS.add(ctx.message),
        )
        self.journal.send('roles/guest', ctx.guild, content, icon='settings', role=role)

    @commands.command(name='setmute')
    @commands.guild_only()
    @permissions.check_mod()
    async def set_mute_role(self, ctx, *, name: str = None):
        ''' Set the mute role for this guild. No argument to unset. '''

        logger.info("Setting mute role for guild '%s' (%d) to '%s'",
                ctx.guild.name, ctx.guild.id, name)

        if name is None:
            role = None
        else:
            role = await self.get_role(ctx, name)
            if role is None:
                return

        with self.bot.sql.transaction():
            self.bot.sql.settings.set_special_roles(ctx.guild, mute=role)

        embed = discord.Embed(colour=discord.Colour.green())
        if role:
            embed.description = f'Set mute role to {role.mention}'
            content = f'Set the mute role to {role.mention}'
        else:
            embed.description = 'Unset mute role'
            content = 'Unset the mute role'

        await asyncio.gather(
            ctx.send(embed=embed),
            Reactions.SUCCESS.add(ctx.message),
        )
        self.journal.send('roles/mute', ctx.guild, content, icon='settings', role=role)

    @commands.command(name='setjail')
    @commands.guild_only()
    @permissions.check_mod()
    async def set_jail_role(self, ctx, *, name: str = None):
        ''' Set the mute role for this guild. No argument to unset. '''

        logger.info("Setting mute role for guild '%s' (%d) to '%s'",
                ctx.guild.name, ctx.guild.id, name)

        if name is None:
            role = None
        else:
            role = await self.get_role(ctx, name)
            if role is None:
                return

        with self.bot.sql.transaction():
            self.bot.sql.settings.set_special_roles(ctx.guild, jail=role)

        embed = discord.Embed(colour=discord.Colour.green())
        if role:
            embed.description = f'Set jail role to {role.mention}'
            content = f'Set the jail role to {role.mention}'
        else:
            embed.description = 'Unset jail role'
            content = 'Unset the jail role'

        await asyncio.gather(
            ctx.send(embed=embed),
            Reactions.SUCCESS.add(ctx.message),
        )
        self.journal.send('roles/jail', ctx.guild, content, icon='settings', role=role)
