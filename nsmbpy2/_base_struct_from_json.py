"""
This file implements a system for creating base_struct.BaseStructs from
struct definitions in a particular JSON format.
"""

from typing import Dict, List, Union

from . import base_struct


def create_base_field_from_string_spec(spec: str, *, default_endianness:str=None) -> base_struct.StructField:
    """
    Create a StructField from the first string in a JSON field value --
    i.e. ignoring transformation modifiers for now
    """

    first_half, second_half = spec.split('@')

    offset = int(second_half, 16)

    first_half_tokens = first_half.strip().split()

    if first_half_tokens[0] == 'bytestring':
        length = int(first_half_tokens[1], 0)
        return base_struct.BytestringField(offset, length)

    elif first_half_tokens[0] == 'string':
        length = int(first_half_tokens[1], 0)
        encoding = first_half_tokens[2]
        return base_struct.BytestringField(offset, length).decode(encoding)

    else:
        basic_type_classes = {
            'u8': (base_struct.BE_U8, base_struct.LE_U8),
            's8': (base_struct.BE_S8, base_struct.LE_S8),
            'u16': (base_struct.BE_U16, base_struct.LE_U16),
            's16': (base_struct.BE_S16, base_struct.LE_S16),
            'u32': (base_struct.BE_U32, base_struct.LE_U32),
            's32': (base_struct.BE_S32, base_struct.LE_S32),
            'u64': (base_struct.BE_U64, base_struct.LE_U64),
            's64': (base_struct.BE_S64, base_struct.LE_S64),
            'f32': (base_struct.BE_F32, base_struct.LE_F32),
            'f64': (base_struct.BE_F64, base_struct.LE_F64),
        }

        rest = first_half_tokens

        if rest[0] in {'le', 'be'}:
            endianness = rest.pop(0)
        elif default_endianness:
            endianness = {'big': 'be', 'little': 'le'}[default_endianness]
        elif rest[0] in {'u8', 's8'}:
            endianness = 'be'
        else:
            raise ValueError(f'Unable to resolve struct field type {rest} without a default endianness')

        if rest[0] not in basic_type_classes:
            raise ValueError(f'Unrecognized start of field type: {first_half_tokens[0]}')
        type_class = basic_type_classes[rest.pop(0)][0 if endianness == 'be' else 1]

        return type_class(offset)


def create_field_from_json_spec(spec: object, *, enums:Dict[str, type]=None, default_endianness:str=None) -> base_struct.StructField:
    """
    Create a StructField from a JSON field value (str or list[str])
    """
    if isinstance(spec, str):
        return create_base_field_from_string_spec(spec, default_endianness=default_endianness)

    if enums is None:
        enums = {}

    field = create_base_field_from_string_spec(spec[0], default_endianness=default_endianness)

    for transform in spec[1:]:
        spl = transform.split()
        name = spl[0]
        args = spl[1:]

        if name == '&':
            field = field.mask(int(args[0], 0))
        elif name == '<<':
            field = field.lshift(int(args[0], 0))
        elif name == '>>':
            field = field.rshift(int(args[0], 0))
        elif name == 'bool':
            field = field.bool()
        elif name == 'mask_bool':
            field = field.mask_bool(int(args[0], 0))
        elif name == 'enum':
            enum_type = enums.get(args[0])
            if enum_type is None:
                raise ValueError(f'Unknown enum: "{args[0]}"')
            field = field.enum(enum_type)
        else:
            raise ValueError(f'Unknown transformation: {name}')

    return field


def create_struct_class(name: str, definition: Dict[str, Union[str, List[str], Dict]], *,
        mixins:List[type]=None, enums:Dict[str, type]=None, default_endianness:str=None) -> type:
    """
    Create a BaseStruct subclass from a json definition
    """
    fields = {}
    for key, value in definition.items():
        if key.startswith('_'):
            # Names starting with _ are reserved
            continue

        if isinstance(value, dict):
            field_def = value['def']
            field_config = value
        else:
            field_def = value
            field_config = {}

        field = create_field_from_json_spec(field_def, enums=enums, default_endianness=default_endianness)

        field.is_alternate = field_config.get('alternate', False)

        fields[key] = field

    return base_struct.create_basestruct_subclass(name, definition['_length'], fields, mixins=mixins)

    return new_cls
