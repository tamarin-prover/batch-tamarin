"""
Tests for the init command error handling and fallback mechanisms.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from batch_tamarin.commands.init import InitCommand
from batch_tamarin.model.tamarin_recipe import Task


class TestInitCommandErrorHandling:
    """Test error handling in the InitCommand."""

    def test_collect_tasks_returns_tuple_format(self):
        """Test that _collect_tasks returns the correct tuple format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a valid spthy file
            valid_file = temp_path / "valid.spthy"
            valid_file.write_text(
                """
rule test_rule:
    [ Fr(~a) ]
    --[ Test(~a) ]
    <  Fr(~a) >
"""
            )

            init_cmd = InitCommand()

            # Mock user inputs for task configuration
            mock_inputs = ["test_task", "test_task", "all", "n", "n", "n", "n", "n"]

            with patch("rich.prompt.Prompt.ask", side_effect=mock_inputs):
                with patch("rich.prompt.Confirm.ask", return_value=False):
                    with patch("rich.console.Console.print"):
                        tasks, failed_files = init_cmd._collect_tasks(
                            [valid_file], ["default"]
                        )

            # Verify return types and content
            assert isinstance(tasks, dict), "tasks should be a dictionary"
            assert isinstance(failed_files, list), "failed_files should be a list"
            assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)}"
            assert (
                len(failed_files) == 0
            ), f"Expected 0 failed files, got {len(failed_files)}"
            assert (
                "test_task" in tasks
            ), "Task should be created with the specified name"

    def test_collect_tasks_handles_task_creation_failure(self):
        """Test that _collect_tasks handles Task creation failures gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            valid_file = temp_path / "valid.spthy"
            valid_file.write_text("rule test: [] --> <>")

            invalid_file = temp_path / "invalid.spthy"
            invalid_file.write_text("rule invalid: [] --> <>")

            init_cmd = InitCommand()

            # Mock user inputs for both files
            mock_inputs = [
                "valid_task",
                "valid_task",
                "all",
                "n",
                "n",
                "n",
                "n",
                "n",  # valid file
                "invalid_task",
                "invalid_task",
                "all",
                "n",
                "n",
                "n",
                "n",
                "n",  # invalid file
            ]

            # Mock Task creation to fail for the invalid file
            original_task_new = Task.__new__

            def mock_task_new(cls, *args, **kwargs):
                if "invalid" in str(kwargs.get("theory_file", "")):
                    raise ValueError("Simulated task creation failure")
                return original_task_new(cls)

            with patch.object(Task, "__new__", side_effect=mock_task_new):
                with patch("rich.prompt.Prompt.ask", side_effect=mock_inputs):
                    with patch("rich.prompt.Confirm.ask", return_value=False):
                        with patch("rich.console.Console.print") as mock_print:
                            tasks, failed_files = init_cmd._collect_tasks(
                                [valid_file, invalid_file], ["default"]
                            )

            # Verify results
            assert len(tasks) == 1, "Only valid task should be created"
            assert len(failed_files) == 1, "One file should have failed"
            assert "valid_task" in tasks, "Valid task should be created"
            assert failed_files[0][0] == invalid_file, "Failed file should be recorded"
            assert (
                "Simulated task creation failure" in failed_files[0][1]
            ), "Error message should be recorded"

            # Verify appropriate messages were printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            success_found = any("created successfully" in call for call in print_calls)
            failure_found = any("Failed to create task" in call for call in print_calls)
            assert success_found, "Success message should be printed"
            assert failure_found, "Failure message should be printed"

    def test_display_failed_files_summary(self):
        """Test the _display_failed_files_summary method."""
        init_cmd = InitCommand()

        # Create mock failed files
        failed_files = [
            (Path("123invalid.spthy"), "Validation error: invalid file format"),
            (Path("bad_syntax.spthy"), "Parse error: unexpected token"),
        ]

        with patch("rich.console.Console.print") as mock_print:
            init_cmd._display_failed_files_summary(failed_files)

        # Verify the summary was displayed
        assert mock_print.called, "Print should be called"

        # Check that the summary title was printed
        calls = [str(call) for call in mock_print.call_args_list]
        summary_title_found = any(
            "Files Skipped During Initialization" in call for call in calls
        )
        assert summary_title_found, "Summary title should be displayed"

        # Check that failed files were listed
        invalid_file_found = any("123invalid.spthy" in call for call in calls)
        bad_syntax_found = any("bad_syntax.spthy" in call for call in calls)
        assert invalid_file_found, "First failed file should be listed"
        assert bad_syntax_found, "Second failed file should be listed"

    def test_run_handles_no_valid_tasks(self):
        """Test that run() handles the case where no valid tasks are created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a file that will cause task creation to fail
            problematic_file = temp_path / "problematic.spthy"
            problematic_file.write_text("rule problematic: [] --> <>")

            init_cmd = InitCommand()

            # Mock user inputs
            mock_inputs = [
                "max",
                "max",
                "3600",
                "result",
                "tamarin-prover",
                "default",
                "n",
                "task",
                "task",
                "all",
                "n",
                "n",
                "n",
                "n",
                "n",
            ]

            # Mock Task creation to always fail
            def mock_task_new(cls, *args, **kwargs):
                raise ValueError("All tasks fail")

            with patch.object(Task, "__new__", side_effect=mock_task_new):
                with patch("rich.prompt.Prompt.ask", side_effect=mock_inputs):
                    with patch("rich.prompt.Confirm.ask", return_value=False):
                        with patch("rich.console.Console.print") as mock_print:
                            with patch.object(init_cmd, "_save_config") as mock_save:
                                init_cmd.run(
                                    [str(problematic_file)], "test_recipe.json"
                                )

            # Verify that no config was saved and appropriate message was shown
            mock_save.assert_not_called()  # No config should be saved when no valid tasks

            calls = [str(call) for call in mock_print.call_args_list]
            no_tasks_message = any(
                "No valid tasks were created" in call for call in calls
            )
            assert (
                no_tasks_message
            ), "Should inform user when no valid tasks are created"

    def test_run_with_mixed_success_and_failure(self):
        """Test run() with some successful and some failed tasks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            valid_file = temp_path / "valid.spthy"
            valid_file.write_text("rule valid: [] --> <>")

            invalid_file = temp_path / "invalid.spthy"
            invalid_file.write_text("rule invalid: [] --> <>")

            init_cmd = InitCommand()

            # Mock user inputs
            mock_inputs = [
                "max",
                "max",
                "3600",
                "result",  # Global config
                "tamarin-prover",
                "default",
                "n",  # Tamarin version
                "valid_task",
                "valid_task",
                "all",
                "n",
                "n",
                "n",
                "n",
                "n",  # Valid file
                "invalid_task",
                "invalid_task",
                "all",
                "n",
                "n",
                "n",
                "n",
                "n",  # Invalid file
            ]

            # Mock Task creation to fail for invalid file
            original_task_new = Task.__new__

            def mock_task_new(cls, *args, **kwargs):
                if "invalid" in str(kwargs.get("theory_file", "")):
                    raise ValueError("Task creation failed")
                return original_task_new(cls)

            with patch.object(Task, "__new__", side_effect=mock_task_new):
                with patch("rich.prompt.Prompt.ask", side_effect=mock_inputs):
                    with patch("rich.prompt.Confirm.ask", return_value=False):
                        with patch("rich.console.Console.print") as mock_print:
                            with patch.object(init_cmd, "_save_config") as mock_save:
                                init_cmd.run(
                                    [str(valid_file), str(invalid_file)],
                                    "test_recipe.json",
                                )

            # Verify that config was saved and summary was shown
            mock_save.assert_called_once()  # Config should be saved when some tasks are valid

            calls = [str(call) for call in mock_print.call_args_list]
            summary_found = any("Files Skipped" in call for call in calls)
            assert summary_found, "Summary of skipped files should be displayed"

    def test_init_command_with_input_fallbacks(self):
        """Test that the init command has proper fallbacks for input failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a valid spthy file
            valid_file = temp_path / "valid.spthy"
            valid_file.write_text(
                """
rule test_rule:
    [ Fr(~a) ]
    --[ Test(~a) ]
    <  Fr(~a) >
"""
            )

            init_cmd = InitCommand()

            # Test with empty inputs (should use defaults)
            mock_inputs = [
                "",
                "",
                "",
                "",  # Global config (should use defaults)
                "",
                "",
                "n",  # Tamarin version (should use defaults)
                "",
                "",
                "all",
                "n",
                "n",
                "n",
                "n",
                "n",  # Task config
            ]

            with patch("rich.prompt.Prompt.ask", side_effect=mock_inputs):
                with patch("rich.prompt.Confirm.ask", return_value=False):
                    with patch("rich.console.Console.print"):
                        with patch.object(init_cmd, "_save_config"):
                            # This should not raise an exception even with empty inputs
                            init_cmd.run([str(valid_file)], "test_recipe.json")

    def test_init_command_handles_keyboard_interrupt(self):
        """Test that the init command handles keyboard interrupts gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            valid_file = temp_path / "valid.spthy"
            valid_file.write_text("rule test: [] --> <>")

            init_cmd = InitCommand()

            # Mock KeyboardInterrupt during user input
            call_count = []

            def mock_keyboard_interrupt(*args, **kwargs):
                if len(call_count) == 0:
                    call_count.append(1)
                    raise KeyboardInterrupt()
                return "default"

            with patch("rich.prompt.Prompt.ask", side_effect=mock_keyboard_interrupt):
                with patch("rich.prompt.Confirm.ask", return_value=False):
                    with patch("rich.console.Console.print") as mock_print:
                        # Should handle KeyboardInterrupt gracefully, not raise it
                        init_cmd.run([str(valid_file)], "test_recipe.json")

                        # Verify that the fallback behavior was triggered
                        calls = [str(call) for call in mock_print.call_args_list]
                        fallback_message = any(
                            "input cancellation" in call for call in calls
                        )
                        assert (
                            fallback_message
                        ), f"Should show fallback message. Got calls: {calls}"

    def test_validate_spthy_files_with_nonexistent_files(self):
        """Test file validation with nonexistent files."""
        init_cmd = InitCommand()

        nonexistent_file = "/path/to/nonexistent/file.spthy"
        existing_file = __file__  # This file exists

        with patch("rich.console.Console.print"):
            validated = init_cmd._validate_spthy_files(
                [nonexistent_file, str(existing_file)]
            )

        # Should only return the existing file
        assert len(validated) == 1, "Only existing files should be validated"
        assert str(existing_file) in [
            str(v) for v in validated
        ], "Existing file should be in validated list"

    def test_collect_tasks_with_empty_tamarin_versions(self):
        """Test task collection with empty tamarin versions list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            valid_file = temp_path / "valid.spthy"
            valid_file.write_text("rule test: [] --> <>")

            init_cmd = InitCommand()

            with patch("rich.prompt.Prompt.ask", return_value="test_task"):
                with patch("rich.prompt.Confirm.ask", return_value=False):
                    with patch("rich.console.Console.print"):
                        # Empty tamarin versions should be handled gracefully
                        tasks, failed_files = init_cmd._collect_tasks([valid_file], [])

            # Should handle empty versions without crashing
            assert isinstance(tasks, dict), "Should return tasks dict"
            assert isinstance(failed_files, list), "Should return failed files list"
