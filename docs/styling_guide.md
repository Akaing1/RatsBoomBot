# RatsBoomBot Code Style Guide

This document defines the preferred Python formatting and code organization
style for RatsBoomBot.

The overall goal is:

> Keep the code compact, readable, and consistent without unnecessarily
> spreading simple Python statements across many lines.


## 1. General Formatting

Files should be as compact as reasonably possible.

Prefer fewer lines when the compact version remains easy to understand.

Avoid vertically expanding simple statements, function signatures, and
function calls unnecessarily.


## 2. Function and Method Definitions

Keep function and method signatures on a single line whenever reasonably
possible.

Preferred:

    async def get_administrator_by_username(db: asqlite.Pool, username: str) -> Administrator | None:

Avoid:

    async def get_administrator_by_username(
        db: asqlite.Pool,
        username: str
    ) -> Administrator | None:

The same applies to regular methods:

    def is_enabled(self, feature: FeatureName) -> bool:

rather than spreading the arguments across multiple lines.


## 3. Function and Method Calls

Keep function and method calls on one line whenever reasonably possible.

Preferred:

    row = await connection.fetchone(query, (username,))

    cursor = await connection.execute(query, (username, password_hash, role))

    profile = get_active_profile(broadcaster_id)

Avoid:

    row = await connection.fetchone(
        query,
        (username,)
    )

and:

    cursor = await connection.execute(
        query,
        (
            username,
            password_hash,
            role
        )
    )


## 4. Conditional Statements

Conditional expressions may be broken across multiple lines when doing so
improves readability.

For example:

    if (
        administrator is None
        or not administrator.is_enabled
        or administrator.role not in allowed_roles
    ):
        return None

Simple conditions should remain compact:

    if administrator is None:
        return None


## 5. Logging

Logger calls are allowed to span multiple lines.

This is especially useful when the log message contains several parameters.

Preferred:

    LOGGER.info(
        "[Administrators] Created account %s with ID %s.",
        username,
        administrator_id
    )

Short logger calls can stay on one line:

    LOGGER.debug("[Administrators] Loading administrator accounts.")

Use the existing RatsBoomBot logging category format:

    [Database]
    [Administrators]
    [OAuth]
    [Profiles]
    [Services]
    [Shutdown]
    [Deploy]

Choose a category appropriate for the subsystem producing the message.


## 6. Database Code

Database operations are allowed to use additional vertical space when it
improves SQL readability.

SQL queries should generally be stored in a `query` variable when appropriate:

    query = """
    SELECT id, username, password_hash, role, is_enabled, created_at
    FROM administrators
    WHERE username = ?
    """

The actual database call should remain compact:

    async with db.acquire() as connection:
        row = await connection.fetchone(query, (username,))

For inserts:

    query = """
    INSERT INTO administrators (username, password_hash, role)
    VALUES (?, ?, ?)
    """

    async with db.acquire() as connection:
        cursor = await connection.execute(query, (username, password_hash, role))

Do not vertically expand SQL parameters unless doing so is necessary for
readability.


## 7. SQL Formatting

SQL itself does not need to follow the compact Python rule.

Prioritize readable SQL.

Preferred:

    query = """
    SELECT id, username, password_hash, role, is_enabled, created_at
    FROM administrators
    WHERE username = ?
    """

For more complicated queries, indentation and additional lines are acceptable:

    query = """
    SELECT id, username, password_hash, role, is_enabled, created_at
    FROM administrators
    ORDER BY
        CASE role
            WHEN 'owner' THEN 0
            ELSE 1
        END,
        username
    """


## 8. Dataclasses

Use compact, normal dataclass definitions.

Immutable configuration/data objects should generally use:

    @dataclass(frozen=True)
    class Administrator:
        id: int
        username: str
        password_hash: str
        role: str
        is_enabled: bool
        created_at: str

Do not add options such as `slots=True` unless there is a specific reason for
the project to use them.


## 9. Comprehensions

Keep simple comprehensions on one line.

Preferred:

    administrators = [administrator_from_row(row) for row in rows]

Avoid:

    administrators = [
        administrator_from_row(row)
        for row in rows
    ]

Complex comprehensions may be expanded if the one-line version becomes
difficult to understand.


## 10. Imports

Keep imports grouped using normal Python conventions:

1. Standard library
2. Third-party packages
3. RatsBoomBot/project imports

Example:

    import logging
    from dataclasses import dataclass

    import asqlite

    from bot.profiles import ChannelProfile
    from config.settings import Settings

Separate each import group with one blank line.


## 11. Type Hints

Use Python type hints consistently.

Preferred:

    async def get_administrator_by_id(db: asqlite.Pool, administrator_id: int) -> Administrator | None:

Use modern union syntax:

    Administrator | None

rather than:

    Optional[Administrator]

Use built-in generic types:

    list[Administrator]
    dict[str, ChannelProfile]
    tuple[int, ...]

rather than older `typing.List`, `typing.Dict`, etc.


## 12. Early Returns

Prefer early returns when they reduce nesting.

Preferred:

    administrator = await get_administrator_by_username(db, username)

    if administrator is None:
        return None

    if not administrator.is_enabled:
        return None

    return administrator

Avoid unnecessarily nesting the successful path inside several `if` blocks.


## 13. Exceptions

Do not add `try/except` blocks merely to log and immediately re-raise an
exception.

Allow exceptions to propagate when the caller is responsible for handling
them.

Use exception handling when the function can:

- recover from the error,
- provide meaningful domain-specific handling,
- translate the exception,
- or intentionally change application behavior.

Avoid unnecessary patterns such as:

    try:
        ...
    except Exception:
        LOGGER.exception(...)
        raise

unless the additional logging provides genuinely useful context.


## 14. Naming

Use descriptive names rather than unnecessary abbreviations.

Preferred:

    administrator_id
    broadcaster_id
    password_hash
    is_enabled

Avoid names such as:

    admin_id
    bid
    pwd
    enabled_flag

unless an abbreviation is already an established project term.


## 15. Constants and Logging

Module-level constants use uppercase names:

    LOGGER = logging.getLogger("RatBoomBot")

    MAX_BACKUPS = 3

    DEFAULT_ROLE = "admin"


## 16. Blank Lines

Use blank lines to separate logical sections, but avoid excessive vertical
spacing.

A function should generally read as a few logical blocks:

    query = ...

    LOGGER.debug(...)

    async with db.acquire() as connection:
        ...

    if row is None:
        return None

    return administrator_from_row(row)

The goal is visual separation of ideas, not maximizing whitespace.


## 17. Comments

Do not add comments that simply repeat what the code already says.

Avoid:

    # Get the administrator
    administrator = await get_administrator_by_id(db, administrator_id)

Comments should explain WHY something is being done when that reason is not
obvious from the code itself.


## 18. Project Consistency

Before adding a new component:

1. Inspect nearby RatsBoomBot files.
2. Follow existing architecture and naming conventions.
3. Follow this style guide for formatting.
4. Do not introduce a new abstraction or pattern unless it solves a real
   project need.
5. Prefer extending an established RatsBoomBot pattern over introducing a
   generic framework pattern.

## 19. Function and Method Calls

Keep function and method calls on a single line whenever the complete call remains
reasonably readable. Do not expand calls merely because they contain multiple
arguments or a moderately long value.

Preferred:

    self._collect_command(subcommand, command_names)

    return RedirectResponse(url="/channel?queue_result=remove_failed&queue_message=The+bot+runtime+is+unavailable.", status_code=303)

Avoid:

    self._collect_command(
        subcommand,
        command_names
    )

    return RedirectResponse(
        url=(
            "/channel?"
            "queue_result=remove_failed&"
            "queue_message=The+bot+runtime+is+unavailable."
        ),
        status_code=303
    )

Split a call across multiple lines only when keeping it on one line would make the
code genuinely difficult to read, such as calls containing complex nested
expressions, callbacks, or several lengthy arguments.


## Quick Reference

Prefer:

    async def example(db: asqlite.Pool, user_id: str) -> User | None:
        query = """
        SELECT user_id, username
        FROM users
        WHERE user_id = ?
        """

        LOGGER.debug(
            "[Users] Loading user %s.",
            user_id
        )

        async with db.acquire() as connection:
            row = await connection.fetchone(query, (user_id,))

        if row is None:
            return None

        return user_from_row(row)


Avoid unnecessarily expanding it into:

    async def example(
        db: asqlite.Pool,
        user_id: str
    ) -> User | None:
        query = """
        SELECT
            user_id,
            username
        FROM users
        WHERE user_id = ?
        """

        LOGGER.debug(
            "[Users] Loading user %s.",
            user_id
        )

        async with db.acquire() as connection:
            row = await connection.fetchone(
                query,
                (
                    user_id,
                )
            )

        if row is None:
            return None

        return user_from_row(row)


## Core Rule

When choosing between two equivalent styles:

> Prefer the more compact version unless breaking it across lines makes the
> code meaningfully easier to read.

Exceptions explicitly include:

- SQL/database query formatting
- logger calls
- complex `if` conditions
- genuinely long or complicated expressions