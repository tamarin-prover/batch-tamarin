from pathlib import Path

from modules.tamarin_cmd import extract_tamarin_version, launch_tamarin_test


class TamarinPath:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.version = ""
        self.test_success = False

    @classmethod
    def create_from_data(
        cls, path: Path, version: str, test_success: bool
    ) -> "TamarinPath":
        """Create a TamarinPath instance from saved data without validation."""
        instance = cls(path)
        instance.version = version
        instance.test_success = test_success
        return instance

    async def validate(self) -> None:
        """Validate the Tamarin path asynchronously."""
        self.version = await extract_tamarin_version(self.path)
        self.test_success = await launch_tamarin_test(self.path)

    @classmethod
    async def create(cls, path: Path) -> "TamarinPath":
        """Factory method to create and validate a TamarinPath asynchronously."""
        instance = cls(path)
        await instance.validate()
        return instance

    def __str__(self) -> str:
        return f"TamarinPath(path={self.path}, version={self.version}, test_success={self.test_success})"

    def __repr__(self) -> str:
        return self.__str__()
