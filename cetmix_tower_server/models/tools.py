from random import choices

CHARS = "23456789acefhjkmnprtvwxyz"


def generate_random_id(sections=1, population=4, separator="-"):
    """Generates random id
        eg 'ahj2-jer83'

    Args:
        sections (int, optional): number of sections. Defaults to 1.
        population (int, optional): number of symbols per section. Defaults to 4.
        separator (str, optional): section separator. Defaults to "-".

    Returns:
        Str: generated id
    """
    if sections < 1 or population < 0:
        return None

    def get_section():
        return "".join(choices(CHARS, k=population))

    # Single section
    if sections == 1:
        return get_section()

    # Multiple sections
    result = []
    for i in range(1, sections):
        result.append("".join(choices(CHARS, k=population)))
        i += 1

    return separator.join(result)
