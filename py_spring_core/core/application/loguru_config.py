from enum import Enum
from typing import Optional

from pydantic import BaseModel


class LogLevel(str, Enum):
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    TEXT = "text"
    JSON = "json"

class LoguruConfig(BaseModel):
    log_format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    log_level: LogLevel = LogLevel.DEBUG  # Use the Enum for log levels
    log_rotation: Optional[str] = "1 day"  # Set to None to disable rotation
    log_retention: Optional[str] = "7 days"  # Set to None to disable retention
    log_file_path: Optional[str] = "./logs/app.log"
    enable_backtrace: bool = True
    enable_diagnose: bool = True
    format: LogFormat = LogFormat.TEXT
