import json

from . import base_struct



def create_base_field_from_string_spec(spec: str) -> base_struct.StructField:
    """
    Create a StructField from the first string in a JSON field value --
    i.e. ignoring transformation modifiers for now
    """

    first_half, second_half = spec.split('@')

    type_name = '_'.join(first_half.strip().split()).lower()
    type_class = base_struct.FIELD_TYPES_BY_NAME[type_name]

    offset = int(second_half, 16)

    return type_class(offset)


def create_field_from_json_spec(spec: object) -> base_struct.StructField:
    """
    Create a StructField from a JSON field value (str or list[str])
    """
    if isinstance(spec, str):
        return create_base_field_from_string_spec(spec)

    field = create_base_field_from_string_spec(spec[0])

    for transform in spec[1:]:
        spl = transform.split()
        name = spl[0]
        args = spl[1:]
        field = field.transform(name, *args)

    return field


def create_struct_class(name: str, definition: dict) -> type:
    """
    Create a BaseStruct subclass from a json definition
    """
    fields = {}
    for key, value in definition.items():
        if key.startswith('_'):
            # Names starting with _ are reserved
            continue

        fields[key] = create_field_from_json_spec(value)

    return base_struct.create_basestruct_subclass(name, definition['_length'], fields)

    return new_cls
