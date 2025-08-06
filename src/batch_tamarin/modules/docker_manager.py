"""Docker management module for Batch Tamarin."""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from ..model.tamarin_recipe import DockerfileConfig, DockerPreset, TamarinVersion
from ..utils.notifications import notification_manager


class DockerManager:
    """Handles all Docker operations for Batch Tamarin."""

    def __init__(self):
        """Initialize the DockerManager."""
        self._image_cache: Dict[str, str] = {}

    def validate_docker_available(self) -> bool:
        """Check if Docker is available on the system.

        Returns:
            True if Docker is available, False otherwise.
        """
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            return False

    def create_docker_command(
        self,
        base_command: List[str],
        image: str,
        working_dir: Path,
        memory_limit: Optional[int] = None,
    ) -> List[str]:
        """Create a Docker run command from base tamarin command.

        Args:
            base_command: The original tamarin command
            image: Docker image to use
            working_dir: Working directory to mount as volume
            memory_limit: Memory limit in GB

        Returns:
            Complete Docker run command
        """
        docker_cmd = ["docker", "run", "--rm"]

        if memory_limit:
            docker_cmd.extend(["--memory", f"{memory_limit}g"])

        # Mount working directory
        docker_cmd.extend(
            ["-v", f"{working_dir.absolute()}:/workspace", "-w", "/workspace"]
        )

        # Add image and original command
        docker_cmd.append(image)
        docker_cmd.extend(base_command)

        return docker_cmd

    def pull_docker_image(
        self,
        image: str,
        platform: Optional[str] = None,
        force_rebuild: bool = False,
    ) -> str:
        """Pull a Docker image from registry.

        Args:
            image: Docker image name and tag
            platform: Optional platform specification
            force_rebuild: Force pull latest version

        Returns:
            Final image tag

        Raises:
            subprocess.CalledProcessError: If pull fails
        """
        pull_cmd = ["docker", "pull"]

        if platform:
            pull_cmd.extend(["--platform", platform])

        pull_cmd.append(image)

        notification_manager.info(f"Pulling Docker image: {image}")
        notification_manager.debug(f"Pull command: {' '.join(pull_cmd)}")

        try:
            subprocess.run(
                pull_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=900,  # 15 minute timeout for pulls
            )
            notification_manager.debug(f"Successfully pulled Docker image: {image}")
            return image
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(
                e.returncode,
                pull_cmd,
                f"Failed to pull Docker image '{image}': {e.stderr}",
            )

    def build_dockerfile_image(
        self, dockerfile_config: DockerfileConfig, force_rebuild: bool = False
    ) -> str:
        """Build a Docker image from Dockerfile.

        Args:
            dockerfile_config: Dockerfile configuration
            force_rebuild: Force rebuild without cache

        Returns:
            Built image tag

        Raises:
            subprocess.CalledProcessError: If build fails
        """
        dockerfile_path = Path(dockerfile_config.path)
        if not dockerfile_path.exists():
            raise FileNotFoundError(f"Dockerfile not found: {dockerfile_path}")

        build_cmd = ["docker", "build"]

        if force_rebuild:
            build_cmd.extend(["--no-cache", "--pull"])

        if dockerfile_config.platform:
            build_cmd.extend(["--platform", dockerfile_config.platform])

        build_cmd.extend(
            [
                "-t",
                dockerfile_config.tag,
                "-f",
                str(dockerfile_path),
                str(dockerfile_path.parent),
            ]
        )

        notification_manager.info(f"Building Docker image: {dockerfile_config.tag}")
        notification_manager.debug(f"Build command: {' '.join(build_cmd)}")

        try:
            subprocess.run(
                build_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=3600,  # 1 hour timeout for builds
            )
            notification_manager.debug(
                f"Successfully built Docker image: {dockerfile_config.tag}"
            )
            return dockerfile_config.tag
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(
                e.returncode,
                build_cmd,
                f"Failed to build Docker image '{dockerfile_config.tag}': {e.stderr}",
            )

    def get_cached_image_tag(self, tamarin_version: TamarinVersion) -> Optional[str]:
        """Get cached Docker image tag for a TamarinVersion configuration.

        Args:
            tamarin_version: TamarinVersion configuration

        Returns:
            Cached Docker image tag if available, None otherwise
        """
        cache_key = self._get_cache_key(tamarin_version)
        return self._image_cache.get(cache_key)

    def _get_cache_key(self, tamarin_version: TamarinVersion) -> str:
        """Generate a cache key for a TamarinVersion configuration."""
        if tamarin_version.docker_preset:
            return f"preset:{tamarin_version.docker_preset.value}"
        elif tamarin_version.docker_image:
            return f"image:{tamarin_version.docker_image.image}"
        elif tamarin_version.dockerfile:
            return f"dockerfile:{tamarin_version.dockerfile.tag}"
        else:
            raise ValueError("TamarinVersion is not configured for Docker execution")

    def ensure_docker_image(self, tamarin_version: TamarinVersion) -> str:
        """Ensure Docker image is available for a TamarinVersion configuration.

        Args:
            tamarin_version: TamarinVersion configuration

        Returns:
            Final Docker image tag to use

        Raises:
            ValueError: If not a Docker-based configuration
            subprocess.CalledProcessError: If image preparation fails
        """
        # Check cache first
        cache_key = self._get_cache_key(tamarin_version)
        cached_tag = self._image_cache.get(cache_key)
        if cached_tag:
            return cached_tag

        # Handle docker_preset
        if tamarin_version.docker_preset:
            preset_value = tamarin_version.docker_preset.value
            image = DockerPreset.get_docker_image(preset_value)

            if image is None:
                raise ValueError(f"No Docker image mapping for preset: {preset_value}")

            # Special handling for 'develop' preset - always build locally
            if preset_value == "develop":
                # Build the develop image using the included Dockerfile from tamarin-prover source
                final_tag = self._build_develop_image(
                    image, tamarin_version.force_rebuild or False
                )
            else:
                platform = DockerPreset.get_platform_flag(preset_value)
                final_tag = self.pull_docker_image(
                    image, platform, tamarin_version.force_rebuild or False
                )

        # Handle docker_image
        elif tamarin_version.docker_image:
            final_tag = self.pull_docker_image(
                tamarin_version.docker_image.image,
                tamarin_version.docker_image.platform,
                tamarin_version.force_rebuild or False,
            )

        # Handle dockerfile
        elif tamarin_version.dockerfile:
            final_tag = self.build_dockerfile_image(
                tamarin_version.dockerfile, tamarin_version.force_rebuild or False
            )

        else:
            raise ValueError("TamarinVersion is not configured for Docker execution")

        # Cache the result
        self._image_cache[cache_key] = final_tag
        return final_tag

    def _build_develop_image(self, image_tag: str, force_rebuild: bool = False) -> str:
        """Build the tamarin-prover develop image using the bundled Dockerfile.

        Args:
            image_tag: Target image tag (e.g., "tamarin-prover:develop")
            force_rebuild: Force rebuild without cache

        Returns:
            Built image tag

        Raises:
            subprocess.CalledProcessError: If build fails
            FileNotFoundError: If Dockerfile not found
        """
        # Find the develop Dockerfile in the batch-tamarin source
        dockerfile_path = (
            Path(__file__).parent.parent / "dockerfiles" / "tamarin-develop.Dockerfile"
        )

        if not dockerfile_path.exists():
            raise FileNotFoundError(
                f"Develop Dockerfile not found at: {dockerfile_path}"
            )

        build_cmd = ["docker", "build"]

        if force_rebuild:
            build_cmd.extend(["--no-cache", "--pull"])

        build_cmd.extend(
            [
                "-f",
                str(dockerfile_path),
                "-t",
                image_tag,
                str(dockerfile_path.parent),  # Build context
            ]
        )

        notification_manager.info(f"Building develop Docker image: {image_tag}")
        notification_manager.debug(f"Build command: {' '.join(build_cmd)}")

        try:
            # Build can take a very long time (30+ minutes for tamarin-prover)
            subprocess.run(
                build_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=3600,  # 1 hour timeout for develop builds
            )
            notification_manager.debug(
                f"Successfully built develop Docker image: {image_tag}"
            )
            return image_tag
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(
                e.returncode,
                build_cmd,
                f"Failed to build develop Docker image '{image_tag}': {e.stderr}",
            )
        except subprocess.TimeoutExpired:
            raise subprocess.CalledProcessError(
                1,
                build_cmd,
                "Build timeout: tamarin-prover develop build took longer than 1 hour",
            )


# Global instance for other modules to use
docker_manager = DockerManager()
