import os


MODERATOR_ROLE_IDS = frozenset(
    int(role_id.strip())
    for role_id in os.getenv("MODERATOR_ROLE_IDS", "").split(",")
    if role_id.strip().isdigit()
)
MODERATOR_ROLE_NAMES = tuple(
    role_name.strip().casefold()
    for role_name in os.getenv(
        "MODERATOR_ROLE_NAMES", "Moderator,Mod,Mods,Moderators"
    ).split(",")
    if role_name.strip()
)


def has_moderator_role(member):
    """Return whether a member has a configured moderator role."""
    roles = getattr(member, "roles", ())
    if MODERATOR_ROLE_IDS:
        return any(role.id in MODERATOR_ROLE_IDS for role in roles)
    return any(role.name.casefold() in MODERATOR_ROLE_NAMES for role in roles)


def moderator_check(ctx_or_interaction):
    """Shared check for prefix, hybrid, and application commands."""
    member = getattr(ctx_or_interaction, "user", None)
    if member is None:
        member = getattr(ctx_or_interaction, "author", None)
    return has_moderator_role(member)
