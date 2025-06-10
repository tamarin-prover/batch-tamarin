from pathlib import Path

from pydantic import BaseModel

from modules.tamarin_cmd import extract_tamarin_version, launch_tamarin_test


class TamarinPath(BaseModel):
    path: Path
    version: str = ""
    test_success: bool = False

    @classmethod
    def create_from_data(
        cls, path: Path, version: str, test_success: bool
    ) -> "TamarinPath":
        """Create a TamarinPath instance from saved data without validation."""
        return cls(path=path, version=version, test_success=test_success)

    async def test_tamarin(self) -> None:
        """Call the Tamarin executable to extract version and test its functionality."""
        self.version = await extract_tamarin_version(self.path)
        self.test_success = await launch_tamarin_test(self.path)

    @classmethod
    async def create(cls, path: Path) -> "TamarinPath":
        """Factory method to create and validate a TamarinPath asynchronously."""
        instance = cls(path=path)
        await instance.test_tamarin()
        return instance

    def __str__(self) -> str:
        return f"TamarinPath(path={self.path}, version={self.version}, test_success={self.test_success})"

    def __repr__(self) -> str:
        return self.__str__()
