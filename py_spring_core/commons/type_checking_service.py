import subprocess
from enum import Enum
from typing import Optional

from loguru import logger


class MypyTypeCheckingError(str, Enum):
    NoUntypedDefs = "no-untyped-def"


class TypeCheckingErrorr(Exception): ...


class TypeCheckingService:
    def __init__(self, target_folder: str) -> None:
        self.target_folder = target_folder
        self.checking_command = ["mypy", "--disallow-untyped-defs", self.target_folder]
        self.target_typing_errors: list[MypyTypeCheckingError] = [
            MypyTypeCheckingError.NoUntypedDefs
        ]

    def type_checking(self) -> Optional[TypeCheckingErrorr]:
        logger.info("[MYPY TYPE CHECKING] Mypy checking types for projects...")
        # Run mypy and capture stdout and stderr
        result = subprocess.run(
            self.checking_command,
            capture_output=True,  # Captures both stdout and stderr
            text=True,  # Ensures output is returned as a string
            check=False,  # Avoids raising an exception on non-zero exit code
        )
        std_err_lines = result.stderr.split("\n")
        std_out_lines = result.stdout.split("\n")
        message: str = ""
        for line in [*std_err_lines, *std_out_lines]:
            if len(line) != 0:
                logger.debug(f"[MYPY TYPE CHECKING] {line}")
            for error in self.target_typing_errors:
                if error in line:
                    error_message = f"\n{line}"
                    message += error_message
        if len(message) == 0:
            return None
        return TypeCheckingErrorr(message)
