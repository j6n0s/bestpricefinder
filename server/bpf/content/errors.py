"""Error reporting for the content loader: every problem is collected, then reported together.

The loader validates **everything** before it writes anything (docs/DATA.md). Validators therefore append
messages to a :class:`Problems` collector instead of raising on the first one, and
:meth:`Problems.raise_if_any` turns the collection into a single :class:`ContentError` listing all of them.
"""

from __future__ import annotations

from collections.abc import Iterable

MAX_SHOWN = 50
"""``str(ContentError)`` lists at most this many problems (all of them stay in ``.problems``)."""


class ContentError(ValueError):
    """Content files are invalid. ``problems`` holds one human-readable message per problem."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems: tuple[str, ...] = tuple(problems)
        if not self.problems:
            raise ValueError("ContentError needs at least one problem")
        super().__init__(self._render())

    def _render(self) -> str:
        shown = self.problems[:MAX_SHOWN]
        lines = [f"{len(self.problems)} content problem(s):", *(f"- {p}" for p in shown)]
        if len(self.problems) > MAX_SHOWN:
            lines.append(f"- ... and {len(self.problems) - MAX_SHOWN} more")
        return "\n".join(lines)


class Problems:
    """An append-only list of problem messages, each prefixed with where it was found."""

    def __init__(self) -> None:
        self._items: list[str] = []

    def add(self, where: str, message: str) -> None:
        self._items.append(f"{where}: {message}" if where else message)

    def extend(self, other: Problems) -> None:
        self._items.extend(other._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def items(self) -> tuple[str, ...]:
        return tuple(self._items)

    def raise_if_any(self) -> None:
        if self._items:
            raise ContentError(self._items)
