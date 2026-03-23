# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from random import choices
from urllib.parse import urlparse

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
    for _ in range(sections):
        result.append(get_section())

    return separator.join(result)


def is_valid_url(url: str, no_scheme_check: bool = False) -> bool:
    """Check if a URL is valid.

    Args:
        url (str): URL to check
        no_scheme_check (bool, optional):
            If True, the scheme check will be skipped.
            Defaults to False.
    Returns:
        bool: True if URL is valid, False otherwise
    """
    if not url:
        return False

    # Add dummy scheme if missing so urlparse works
    if no_scheme_check:
        if "://" not in url:
            url = "http://" + url

    parsed = urlparse(url)

    # Must have a domain or IP
    if not parsed.netloc:
        return False

    # Basic domain validation (at least one dot OR localhost OR IP)
    host = parsed.hostname
    if not host:
        return False

    if host in ("localhost", "::1"):
        return True

    if "." in host or ":" in host:
        return True

    return False
