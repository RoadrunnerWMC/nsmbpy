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

import struct

from . import Game
from . import tileset


EMPTY_TILE = None



def renderObject(game, layout, width, height, *, fullslope=False):
    """
    Render a tileset object layout into a 2D list (list of lists)
    """
    if not layout:
        return [[]]

    if isinstance(layout[0], tileset.SlopeObjectLayoutStep):
        return renderSlopeObject(game, layout, width, height, fullslope)

    # Identify repeating rows with respect to Y

    repeatExists = False
    thisRowRepeats = False
    rowsBeforeRepeat = []
    rowsInRepeat = []
    rowsAfterRepeat = []

    currentRow = []
    for step in layout:
        if isinstance(step, tileset.NewlineObjectLayoutStep):
            if thisRowRepeats:
                rowsInRepeat.append(currentRow)
            elif not repeatExists:
                rowsBeforeRepeat.append(currentRow)
            else:
                rowsAfterRepeat.append(currentRow)
            currentRow = []
            thisRowRepeats = False
        else:
            if step.repeatY:
                repeatExists = True
                thisRowRepeats = True
            currentRow.append(step)

    # Render

    dest = []
    if not rowsInRepeat:
        # No Y-repeating
        for y in range(height):
            dest.append(renderStandardRow(rowsBeforeRepeat[y % len(rowsBeforeRepeat)], width))
    else:
        # Y-repeating
        for y in range(height):
            if y < len(rowsBeforeRepeat):
                dest.append(renderStandardRow(rowsBeforeRepeat[y], width))
            elif y >= height - len(rowsAfterRepeat):
                dest.append(renderStandardRow(rowsAfterRepeat[y - height + len(rowsAfterRepeat)], width))
            else:
                dest.append(renderStandardRow(rowsInRepeat[(y - len(rowsBeforeRepeat)) % len(rowsInRepeat)], width))

    return dest


def renderStandardRow(steps, width):
    """
    Render a row from an object
    """

    # Identify repeating steps

    repeatExists = False
    stepsBeforeRepeat = []
    stepsInRepeat = []
    stepsAfterRepeat = []

    for step in steps:
        if not isinstance(step, tileset.TileObjectLayoutStep):
            continue

        if step.repeatX:
            repeatExists = True
            stepsInRepeat.append(step)
        elif not repeatExists:
            stepsBeforeRepeat.append(step)
        else:
            stepsAfterRepeat.append(step)

    # Render

    dest = []
    if not stepsInRepeat:
        # No X-repeating
        for x in range(width):
            step = stepsBeforeRepeat[x % len(stepsBeforeRepeat)]
            dest.append((step.tilesetID, step.tileID))
    else:
        # X-repeating
        for x in range(width):
            if x < len(stepsBeforeRepeat):
                step = stepsBeforeRepeat[x]
            elif x >= width - len(stepsAfterRepeat):
                step = stepsAfterRepeat[x - width + len(stepsAfterRepeat)]
            else:
                step = stepsInRepeat[(x - len(stepsBeforeRepeat)) % len(stepsInRepeat)]
            dest.append((step.tilesetID, step.tileID))

    return dest


def renderSlopeObject(game, layout, width, height, fullslope):
    """
    Render a slope object
    """

    SECTION_TYPE_MAIN = tileset.SlopeObjectLayoutStep.SectionType.MAIN
    SECTION_TYPE_SUB_FILL_ALL = tileset.SlopeObjectLayoutStep.SectionType.SUB_FILL_ALL
    SECTION_TYPE_SUB = tileset.SlopeObjectLayoutStep.SectionType.SUB
    SLOPE_TYPE_FLOOR_UPWARD = tileset.SlopeObjectLayoutStep.SlopeType.FLOOR_UPWARD
    SLOPE_TYPE_FLOOR_DOWNWARD = tileset.SlopeObjectLayoutStep.SlopeType.FLOOR_DOWNWARD
    SLOPE_TYPE_CEILING_DOWNWARD = tileset.SlopeObjectLayoutStep.SlopeType.CEILING_DOWNWARD
    SLOPE_TYPE_CEILING_UPWARD = tileset.SlopeObjectLayoutStep.SlopeType.CEILING_UPWARD

    # Get sections
    sections = getSlopeSections(layout)

    mainBlock = sections.get(SECTION_TYPE_MAIN)

    fillAll = False
    if SECTION_TYPE_SUB_FILL_ALL in sections:
        raise NotImplementedError('SUB_FILL_ALL slopes cannot be rendered yet')

        if game is not Game.NEW_SUPER_MARIO_BROS:
            raise ValueError(f'Encountered a SUB_FILL_ALL slope step when rendering a slope object for {game}')

        subBlock = sections[SECTION_TYPE_SUB_FILL_ALL]
        fillAll = True

    else:
        subBlock = sections.get(SECTION_TYPE_SUB)

    # Get the first step (which defines the slope type)
    slopeStep = layout[0]

    # Decide on the amount to draw by seeing how much we can fit in each direction
    if fullslope:
        drawAmount = max(height // len(mainBlock), width // len(mainBlock[0]))
    else:
        drawAmount = min(height // len(mainBlock), width // len(mainBlock[0]))

    if game is Game.NEW_SUPER_MARIO_BROS:
        drawAmount += 1

    if slopeStep.slopeType is SLOPE_TYPE_FLOOR_UPWARD:
        # Start at the bottom left
        x = 0
        y = height - len(mainBlock)
        xi = len(mainBlock[0])
        yi = -len(mainBlock)

        if game is not Game.NEW_SUPER_MARIO_BROS and subBlock is not None:
            y -= len(subBlock)

    elif slopeStep.slopeType is SLOPE_TYPE_FLOOR_DOWNWARD:
        if game is Game.NEW_SUPER_MARIO_BROS:
            # Start at the bottom right
            x = width - len(mainBlock[0])
            y = height - len(mainBlock)
            xi = -len(mainBlock[0])
            yi = -len(mainBlock)
        else:
            # Start at the top left
            x = 0
            y = 0
            xi = len(mainBlock[0])
            yi = len(mainBlock)

    elif slopeStep.slopeType is SLOPE_TYPE_CEILING_DOWNWARD:
        # Start at the top left
        x = 0
        y = 0
        xi = len(mainBlock[0])
        yi = len(mainBlock)

        if game is not Game.NEW_SUPER_MARIO_BROS and subBlock is not None:
            y += len(subBlock)

    elif slopeStep.slopeType is SLOPE_TYPE_CEILING_UPWARD:
        if game is Game.NEW_SUPER_MARIO_BROS:
            # Start at the top right
            x = width - len(mainBlock[0])
            y = 0
            xi = -len(mainBlock[0])
            yi = len(mainBlock)
        else:
            # Start at the bottom left
            x = 0
            y = height - len(mainBlock)
            xi = len(mainBlock[0])
            yi = -len(mainBlock)

    else:
        raise ValueError(f'Unknown slope type: {slopeStep.slopeType}')


    # Create a dest and initialize it to empty tiles
    dest = []
    for _ in range(height):
        dest.append([])
        for _ in range(width):
            dest[-1].append(EMPTY_TILE)

    # Finally, draw it
    for i in range(drawAmount):
        putObjectArray(dest, x, y, mainBlock, width, height)
        if subBlock is not None:
            xb = x
            if slopeStep.slopeType in [SLOPE_TYPE_FLOOR_DOWNWARD, SLOPE_TYPE_CEILING_UPWARD]:
                xb = x + len(mainBlock[0]) - len(subBlock[0])
            if slopeStep.slopeType in [SLOPE_TYPE_FLOOR_UPWARD, SLOPE_TYPE_FLOOR_DOWNWARD]:
                putObjectArray(dest, xb, y + len(mainBlock), subBlock, width, height)
            else:
                putObjectArray(dest, xb, y - len(subBlock), subBlock, width, height)

        x += xi
        y += yi

    return dest



def getSlopeSections(layout):
    """
    Sort the slope data into sections
    """

    # Read steps
        # If we've hit a slope step:
            # If there's a current section, render it
            # Make a new current section
        # Add to the current section

    sections = {}
    currentSection = None
    for step in layout:
        if isinstance(step, tileset.SlopeObjectLayoutStep):
            # Begin new section
            currentSection = []
            sections[step.sectionType] = currentSection
        currentSection.append(step)

    return {k: renderSlopeSection(v) for k, v in sections.items()}


def renderSlopeSection(steps):
    """
    Render a slope section
    """
    # Divide into rows
    rows = [[]]
    for step in steps:
        if isinstance(step, tileset.NewlineObjectLayoutStep):
            rows.append([])
        else:
            rows[-1].append(step)
    if not rows[-1]: rows.pop()

    isTile = lambda step: isinstance(step, tileset.TileObjectLayoutStep)
    stepToTuple = lambda step: (step.tilesetID, step.tileID)

    # Calculate total width (that is, the width of the widest row)
    width = max(sum(isTile(step) for step in row) for row in rows)

    # Create the actual section
    section = []
    for row in rows:
        newRow = list(map(stepToTuple, filter(isTile, row)))
        newRow += [EMPTY_TILE] * (width - len(newRow)) # Right-pad
        section.append(newRow)

    return section


def putObjectArray(dest, xo, yo, block, width, height):
    """
    Place a block of tiles into a larger tile array
    """
    for y in range(yo, yo + len(block)):
        if y < 0: continue
        if y >= height: continue
        drow = dest[y]
        srow = block[y - yo]
        for x in range(xo, xo + len(srow)):
            if x < 0: continue
            if x >= width: continue
            drow[x] = srow[x - xo]
