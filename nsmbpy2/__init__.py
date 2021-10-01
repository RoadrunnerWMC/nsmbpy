# Copyright 2019 RoadrunnerWMC
#
# This file is part of nsmbpy.
#
# nsmbpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# nsmbpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with nsmbpy.  If not, see <https://www.gnu.org/licenses/>.
"""
Functions and classes that don't need their own modules.
"""

import enum


class Game(enum.Enum):
    """
    Enumeration for distinguishing the various NSMB games
    """
    NEW_SUPER_MARIO_BROS = 'NSMB'
    NEW_SUPER_MARIO_BROS_WII = 'NSMBW'
    NEW_SUPER_MARIO_BROS_2 = 'NSMB2'
    NEW_SUPER_MARIO_BROS_U = 'NSMBU'
    NEW_SUPER_LUIGI_U = 'NSLU'
    NEW_SUPER_MARIO_BROS_U_DELUXE = 'NSMBUDX'


    def __str__(self):
        return {
            self.NEW_SUPER_MARIO_BROS: 'New Super Mario Bros.',
            self.NEW_SUPER_MARIO_BROS_WII: 'New Super Mario Bros. Wii',
            self.NEW_SUPER_MARIO_BROS_2: 'New Super Mario Bros. 2',
            self.NEW_SUPER_MARIO_BROS_U: 'New Super Mario Bros. U',
            self.NEW_SUPER_LUIGI_U: 'New Super Luigi U',
            self.NEW_SUPER_MARIO_BROS_U_DELUXE: 'New Super Mario Bros. U Deluxe',
        }[self]


    def endianness(self):
        return {
            self.NEW_SUPER_MARIO_BROS: '<',
            self.NEW_SUPER_MARIO_BROS_WII: '>',
            self.NEW_SUPER_MARIO_BROS_2: '<',
            self.NEW_SUPER_MARIO_BROS_U: '>',
            self.NEW_SUPER_LUIGI_U: '>',
            self.NEW_SUPER_MARIO_BROS_U_DELUXE: '<',
        }[self]


    def is_wii_u(self):
        """
        Returns True for NSMBU and NSLU.
        """
        return self in [self.NEW_SUPER_MARIO_BROS_U, self.NEW_SUPER_LUIGI_U]

    def is_like_nsmbu(self):
        """
        Returns True for NSMBU, NSLU, and NSMBUDX.
        """
        return self in [self.NEW_SUPER_MARIO_BROS_U, self.NEW_SUPER_LUIGI_U, self.NEW_SUPER_MARIO_BROS_U_DELUXE]


# I would like these to be class-level @properties, but you can't do
# that without metaclasses, and metaclasses clash with subclassing Enum,
# so... this is how we're doing it.
Game.all = set(m for m in Game)
Game.all_wii_u = set(m for m in Game if m.is_wii_u())
Game.all_like_nsmbu = set(m for m in Game if m.is_like_nsmbu())
