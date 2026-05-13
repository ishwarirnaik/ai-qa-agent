from contextvars import ContextVar
from typing import Awaitable, Callable


EventSink = Callable[[str, str], Awaitable[None]]
event_sink: ContextVar[EventSink | None] = ContextVar("event_sink", default=None)


async def emit_event(stage: str, message: str) -> None:
    sink = event_sink.get()
    if sink:
        await sink(stage, message)
