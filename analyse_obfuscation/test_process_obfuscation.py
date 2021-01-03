import logging
import os
import random
import re
import subprocess
from multiprocessing.pool import ThreadPool
from typing import List, Set, Tuple, Union

import tqdm

from .helpers import SpecialCharOperation


class TestCase():
    def __init__(self, command: List[str], char_offset: int, arg_index: int, scan_range: List[int], post_command: List[str], exit_code_only: bool, timeout: int):
        self.command = command
        self.char_offset = char_offset
        self.arg_index = arg_index
        self.scan_range = scan_range
        self.post_command = post_command
        self.exit_code_only = exit_code_only
        self.timeout = timeout


class TestProcessObfuscation():
    def __init__(self, test_case: TestCase, threads: int, log: logging.Logger):
        self.log = log
        self.command = test_case.command
        self.command_flat = ' '.join(test_case.command)
        self.post_command = test_case.post_command
        self.expected_code, self.expected_output = self.__get_expected_result__()
        self.exit_code_only = test_case.exit_code_only
        self.scan_range = test_case.scan_range
        self.timeout = test_case.timeout
        self.threads = threads
        self.tqdm = None

    # Class Methods
    @classmethod
    def __randomise__(cls, command_parts: Union[List[str], str]) -> Union[List[str], str]:
        randomised = ''.join(random.choices('0123456789ABCDEF', k=10))
        if isinstance(command_parts, str):
            return command_parts.replace('{random}', randomised)
        else:
            result = []
            for command_part in command_parts:
                result.append(command_part.replace('{random}', randomised))
            return result

    @classmethod
    def select_arg_index(cls, command: List[str], arg_index: Union[int, None]) -> int:
        # Iterate over command-line arguments
        for i, command_part in enumerate(command):
            # The first argument will be the process, so ignore
            if i == 0 or (arg_index is not None and i != arg_index):
                continue
            # Check if the first character is a slash or hyphen - if so, select it
            if command_part[0] in ['/', '-']:
                return i
        # If no option char was found, fall back to the first argument
        #  (least likely to be something like a filename)
        return 1

    @classmethod
    def get_command_part_offset(cls, command_part: str) -> int:
        # We prefer the below chars, because they have 'equivalents' in the Spacing Modifier Letters range (0x02B0 - 0x02FF)
        preferred_chars = 'hjrwyxsl'
        # Iterate over each char in the given command-line optoin
        for i, char in enumerate(command_part.lower()):
            # Ignore the first one - it will either be an option char, or
            #  the first char of a keyword which is usually not the best candidate
            if i == 0:
                continue
            if any([char == preferred_char for preferred_char in preferred_chars]):
                return i+1
        return 2 if len(command_part) > 1 else 1

    def __get_expected_result__(self) -> Tuple[int, str]:
        # Prepare command to run
        command = self.__randomise__(self.command)
        self.log.info('About to run command "{}"'.format(' '.join(command)))
        # Run 'normal' command to get expected exit code
        try:
            result = subprocess.run(command, capture_output=True)
            exit_code, stdout = result.returncode, "{} / {}".format(result.stdout, result.stderr)
            # Check if observed exit code is 0
            if exit_code != 0:
                self.log.warning("Observed exit code is {}, which is not 0 as usual".format(exit_code))
                self.log.warning("Test outcome may contain unexpected results")
        except FileNotFoundError:
            self.log.error("Command \"{}\" could not be executed: file not found".format(command))
            raise
        return exit_code, stdout

    # Private Methods
    def __test_commands__(self, test: str, commands: List[Tuple[int, str]]) -> Set[Tuple[int, str]]:
        self.log.info('Preparing {} commands to run'.format(len(commands)))
        # Prepare ThreadPool
        with ThreadPool(self.threads) as thread_pool:
            # Prepare progress bar
            with tqdm.tqdm(total=len(commands), desc=test, position=1, leave=False) as self.tqdm:
                # Submit all commands to ThreadPool, collect results
                outcomes = list(thread_pool.map(self.__run_command__, [command for _, command in commands]))
        # Return all results when output was True
        return set([(identifier, command) for outcome, (identifier, command) in zip(outcomes, commands) if outcome])

    def __run_command__(self, command: str):
        # Prepare command
        command = self.__randomise__(command)
        self.log.info('About to run command "{}"'.format(command))
        try:
            # Run command
            import shlex
            result = subprocess.run(shlex.split(command, posix=os.sep=='/'), capture_output=True, timeout=self.timeout)
            exit_code, stdout = result.returncode, "{} / {}".format(result.stdout, result.stderr)
            self.log.info('Exit code {} observed ({} desired)'.format(exit_code, self.expected_code))
            # Return result
            return exit_code == self.expected_code and (self.exit_code_only or stdout == self.expected_output)
        except subprocess.TimeoutExpired:
            self.log.warning('Timeout ({}s) elapsed for command "{}"'.format(self.timeout, command))
            return False
        except Exception as e:
            self.log.info("Exception when executing \"{}\": {}".format(command, e))
            return False
        finally:
            if self.post_command:
                result = None
                try:
                    result = subprocess.run(self.post_command, capture_output=True)
                except Exception as e:
                    self.log.warning("Post command caused exception ({})".format(e))
                finally:
                    self.log.info("Post command exited with exit code {}".format(result.returncode if result else "?"))
            if self.tqdm:
                self.tqdm.update()

    def __get_option_argument__(self, arg_index: int) -> int:
        return self.select_arg_index(self.command, arg_index)

    # Public Methods
    def check_special_chars(self, char_at_position: int, operation: SpecialCharOperation) -> Set[Tuple[int, str]]:
        # Prepare operation
        op = None
        if operation == SpecialCharOperation.INSERT:
            op = "insert"
            command_parts = self.command_flat[:char_at_position+1], self.command_flat[char_at_position+1:]
        elif operation == SpecialCharOperation.REPLACE:
            op = "replace"
            command_parts = self.command_flat[:char_at_position], self.command_flat[char_at_position+1:]
        else:
            raise ValueError('Unexpected operation {}'.format(operation))
        self.log.info("Starting 'special chars ({})' test".format(op))
        # Prepare commands to run (excluding 'original' command)
        new_commands = [(ordinal, chr(ordinal).join(command_parts)) for ordinal in self.scan_range if operation != SpecialCharOperation.REPLACE or chr(ordinal).lower() != self.command_flat[char_at_position].lower()]
        # Run commands, return results
        return self.__test_commands__("Special chars ({})".format(op), new_commands)

    def check_quote_injection(self, arg_index: int) -> Union[str, None]:
        self.log.info("Starting 'quote insertion' test")
        # Check if valid command was given
        if not self.command or len(self.command) < 2:
            return None
        # Simply add quotes between 0,1 and 1,2 of first argument - e.g. net s"t"art
        command_part = self.__get_option_argument__(arg_index)
        test_arg = self.command[command_part][:1] + '"' + self.command[command_part][1] + '"' + self.command[command_part][2:]
        new_command = ' '.join(self.command[:command_part] + [test_arg] + self.command[command_part+1:])
        # Quotes don't work in subprocess when using lists
        result = self.__run_command__(new_command)
        # Return command if working, blank string if not
        return new_command if result else ''

    def check_shortened_option(self, arg_index: int) -> Union[None, Set[Tuple[int, str]]]:
        self.log.info("Starting 'shortened option' test")
        # Check if valid command was given
        if not self.command or len(self.command) < 2:
            raise ValueError('Unexpected length {}'.format(len(self.command)))
        # Shorten the second argument by [1..len(command)-1] chars
        selected_command_part_index = self.__get_option_argument__(arg_index)
        selected_command_part = self.command[selected_command_part_index]
        new_commands = []
        # check if there are any colons or equal signs in there (e.g. /active:true)
        selected_command_part_split = list(filter(None, re.split("[:=]", selected_command_part)))
        if len(selected_command_part_split) > 1:
            # If so, only try to shorten the first bit - leave the argument intact (e.g. /activ:true.../a:true)
            size = len(selected_command_part_split[0])
            # Check if argument is long enough
            if size <= 2:
                self.log.info("Length of selected command-line option is {}, cannot be further shortened".format(size))
                return None
            for i in range(size-1):
                test_arg = selected_command_part[0:(i+1)] + selected_command_part[size:]
                new_commands.append((i, ' '.join(self.command[:selected_command_part_index] + [test_arg] + self.command[(selected_command_part_index+1):])))
        else:
            # If not, just shorten the full argument
            size = len(selected_command_part)
            # Check if argument is long enough
            if size <= 2:
                self.log.info("Length of selected command-line option is {}, cannot be further shortened".format(size))
                return None
            for i in range(size-1):
                test_arg = selected_command_part[0:(i+1)]
                new_commands.append((i, ' '.join(self.command[:selected_command_part_index] + [test_arg] + self.command[(selected_command_part_index+1):])))
        # Return results of commands if any were generated, None if not
        return self.__test_commands__("Shorthand command", new_commands) if new_commands else None

    def check_option_char(self, arg_index_start: int = 1) -> Union[None, Set[Tuple[int, str]]]:
        self.log.info("Starting 'option char subtitution' test")

        delimiters_alternative = ['/', '\\', '\u2215', '\u244a', '\u2044', '\u29F8', '\u002D', '\u007E', '\u00AD', '\u058A', '\u05BE', '\u1400', '\u1806', '\u2010', '\u2010', '\u2012', '\u2013', '\u2014', '\u2015', '\u2053', '\u2212', '\u2212', '\u2212', '\u2E17', '\u2E3A', '\u2E3B', '\u301C', '\u3030', '\u30A0', '\uFE31', '\uFE32', '\uFE58', '\uFE63', '\uFF0D']
        delimiters_standard = ['/', '-']
        self.log.info("Looking for arguments starting with one of: {}".format(' '.join(delimiters_standard)))

        # Iterate over command-line arguments
        for i, command in enumerate(self.command[arg_index_start:], start=arg_index_start):
            # Check if delimiter is present
            if any([command.startswith(delimiter) for delimiter in delimiters_standard]):
                # If so, find its position
                pos = sum([len(c)+1 for c in self.command[:i]])
                # Break command in two parts
                command_parts = self.command_flat[:pos], self.command_flat[pos+1:]
                self.log.info("Argument found ({})".format(command))
                self.log.info("Preparing {} alternative signs to test".format(len(delimiters_alternative)))
                break
        else:
            self.log.info("No arguments found")
            return None  # No option char found

        # Prepare commands to test
        new_commands = [(ord(char), char.join(command_parts)) for char in delimiters_alternative]
        return self.__test_commands__("Dash/hyphen", [command for command in new_commands if command[1] != self.command_flat])
