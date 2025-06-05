from pathlib import Path

from modules.tamarin_cmd import extract_tamarin_version, launch_tamarin_test


class TamarinPath:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.version = extract_tamarin_version(path)
        self.test_success = launch_tamarin_test(path)

    def __str__(self) -> str:
        return f"TamarinPath(path={self.path}, version={self.version}, test_success={self.test_success})"

    def __repr__(self) -> str:
        return self.__str__()
