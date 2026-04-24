from pydantic import BaseModel


class ApplicationEvent(BaseModel): ...


class _ShutdownSentinel(ApplicationEvent): ...
