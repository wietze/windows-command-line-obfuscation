import argparse
import json
import logging
import os
import re
import shlex
from argparse import Namespace
from typing import List, Tuple

import tqdm

from .helpers import SpecialCharOperation, TqdmHandler
from .output_results import print_results, write_report
from .test_process_obfuscation import TestCase, TestProcessObfuscation


def run_tests(test_cases: List[TestCase], threads: int, report_dir: str, log: logging.Logger) -> None:
    """ For a list of commands: run tests, create reports, write summary to stdout """
    result = {}
    with tqdm.tqdm(test_cases, position=0, disable=len(test_cases) <= 1) as pbar:
        for test_case in pbar:
            # Extract display name
            _, display_name = os.path.split(test_case.command[0].strip('"'))
            pbar.set_description('Testing {}'.format(display_name))

            try:
                # Create test class
                test = TestProcessObfuscation(test_case, threads, log)

                # Run individual tests
                test_outcomes = {'option_char': test.check_option_char(test_case.arg_index),
                                 'char_insert': test.check_special_chars(test_case.char_offset, SpecialCharOperation.INSERT),
                                 'char_substitution': test.check_special_chars(test_case.char_offset, SpecialCharOperation.REPLACE),
                                 'quotes': test.check_quote_injection(test_case.arg_index),
                                 'shorthand_command': test.check_shortened_option(test_case.arg_index)
                                 }

                # Parse results
                result[display_name] = test_outcomes

                # Write report
                write_report(report_dir, display_name, ' '.join(test_case.command), test_case.char_offset, test_case.scan_range, test_outcomes)
            except Exception:
                log.error("Unexpected error when executing", exc_info=True)

    # Print results to stdout
    print_results(result)


def prepare_command(parser: argparse.ArgumentParser, command_flat: str, char_offset: int) -> Tuple[List[str], int, int]:
    """ Turns a flattened command string into a list, and generates a character offset in case none was provided """
    log.info("Preparing parameters for {}".format(command_flat))
    command_list = shlex.split(command_flat, posix=os.sep == '/')
    arg_index = -1
    if char_offset is not None:
        if not (0 <= char_offset and char_offset < len(command_flat)):
            parser.error("char offset not within bounds of (0 .. command length)")
        else:
            selected_char = command_flat[char_offset]
            if (0 <= char_offset and char_offset < len(command_list[0])):
                parser.error("cannot add characters to process name")
            if not re.findall(r'[a-zA-Z0-9]', selected_char):
                parser.error("selected char '{}' is not alphanumeric".format(selected_char))

            i = 0
            for arg_index, arg in enumerate(command_list):
                i += len(arg)
                if i > char_offset:
                    break
    else:
        # Second char of first argument (not counting process name)
        arg_index = TestProcessObfuscation.select_arg_index(command_list, None)
        command_part_offset = TestProcessObfuscation.get_command_part_offset(command_list[arg_index].split(':')[0])

        char_offset = len(' '.join(command_list[0:arg_index])) + command_part_offset

        log.info("No char offset specified - using second char of first argument instead")
    log.info("Char offset = {} (char '{}', argument index = {})".format(char_offset, command_flat[char_offset], arg_index))
    return (command_list, char_offset, arg_index)


def create_test_case(args: Namespace, parser: argparse.ArgumentParser, json_file: bool) -> TestCase:
    """Generates a TestCase object based on the given arguments (either on the command line or in the JSON file)"""

    command = None
    if args.command:
        command, char_offset, arg_index = prepare_command(parser, args.command, args.char_offset)
    else:
        raise ValueError("'--command' is required" if not json_file else "'command' should be specified")

    # Parse char scan range options
    scan_range = None

    if args.custom_range:
        if (args.range is None or args.range == 'custom'):
            scan_range = sum(args.custom_range, [])
            if 0 in scan_range:
                parser.error("null bytes can not be included in custom ranges. Try starting from 1 instead.")
        else:
            raise ValueError("--custom_range can not be set when --range is not set to 'custom'.")
    elif args.range is None or args.range == 'educated':
        scan_range = list(range(0x01, 0xFF)) + list(range(0x0100, 0x052F)) + list(range(0x2070, 0x218F)) + list(range(0xFF00, 0xFFEF))
    elif args.range == 'full':
        scan_range = list(range(0x01, 0xFFFF))
    elif args.range == 'ascii':
        scan_range = list(range(0x01, 0xFF))
    else:
        raise ValueError("Unexpected range '{}'".format(args.range))

    log.info('{} range selected ({} values)'.format(args.range, len(scan_range)))

    # Parse report output dir
    log.info('Report files will be stored in {}'.format(os.path.abspath(args.report_dir)))
    if not os.path.isdir(args.report_dir):
        parser.error("path specified in --report_dir does not exist.")

    return TestCase(command=command, char_offset=char_offset, arg_index=arg_index, scan_range=scan_range, pre_command=args.pre_command, post_command=args.post_command, exit_code_only=args.exit_code_only, timeout=args.timeout)


# Prepare logger
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def parse_arguments() -> None:
    # Prepare arguments
    parser = argparse.ArgumentParser(add_help=False, description='Tool for identifying executables that have command-line options that can be obfuscated.')

    parser._action_groups.pop()
    required = parser.add_argument_group('required arguments (either is required)')
    optional_c = parser.add_argument_group('optional --command arguments')
    optional = parser.add_argument_group('optional arguments')

    # Global settings
    optional.add_argument('--threads', metavar='n', type=int, help='Number of threads to use', default=None)
    optional.add_argument('--verbose', action='store_true', help='Increase output verbosity')
    optional.add_argument('--quiet', action='store_true', help='Decrease output verbosity')
    optional.add_argument('--report_dir', metavar='c:\\path\\to\\dir', type=str, help='Path to save report files to', default="."+os.sep)
    optional.add_argument('--log_file', metavar='c:\\path\\to\\file.log', type=str, help='Path to save log to')
    optional.add_argument('--help', action='help', default=argparse.SUPPRESS, help='Show this help message and exit')

    # Single command options
    required.add_argument('--command', metavar='"proc /arg1 /arg2"', type=str, help='Single command to test')
    optional_c.add_argument('--range', choices=['full', 'educated', 'ascii', 'custom'], help='Character range to scan (default=educated)')
    optional_c.add_argument('--custom_range', metavar='0x??..0x??', type=lambda x: list(range(int(x.split('..')[0], 0), int(x.split('..')[1], 0))), nargs='+', help='Range to scan')
    optional_c.add_argument('--char_offset', metavar='n', type=int, help='Character position used for insertion and replacement')
    optional_c.add_argument('--pre_command', metavar='process_name', type=str, help='Command to run unconditionally before each attempt, piping the result to the stdin')
    optional_c.add_argument('--post_command', metavar='process_name', type=str, help='Command to run unconditionally after each attempt (e.g. to clean up)')
    optional_c.add_argument('--exit_code_only', action='store_true', help='Only base success on the exit code (and not the output of the command)')
    optional_c.add_argument('--timeout', metavar='n', type=float, help='Number of seconds per execution before timing out.', default=2)

    # JSON File options
    required.add_argument('--json_file', metavar='c:\\path\\to\\file.jsonl', type=str, help='Path to JSON file (JSON Line formatted) containing commands config')

    args = parser.parse_args()

    tests = []

    # Parse verbosity options
    stream_handler = TqdmHandler()
    stream_handler.setFormatter(logging.Formatter("[%(levelname)-.4s] %(message)s"))
    if args.verbose:
        stream_handler.setLevel(logging.DEBUG)
    elif args.quiet:
        stream_handler.setLevel(logging.ERROR)
    else:
        stream_handler.setLevel(logging.WARNING)
    log.addHandler(stream_handler)

    # Parse log file options
    if args.log_file:
        file_path = os.path.abspath(args.log_file)
        file_handler = logging.FileHandler(file_path, 'w', encoding='utf-16le')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-.4s] (%(threadName)-10s) %(message)s'))
        log.addHandler(file_handler)

    if args.json_file:
        single_command_args = ['command', 'range', 'custom_range', 'char_offset', 'pre_command', 'post_command', 'exit_code_only']
        given_args = {key: value for (key, value) in args._get_kwargs()}
        if any([given_args[x] for x in single_command_args]):
            raise ValueError("When --json_file is specified, the following arguments should not be specified on the command line but in the JSON file: {}".format(', '.join(single_command_args)))

        with open(args.json_file, 'rt') as f:
            for line in f.readlines():
                if not line.strip():
                    continue
                t_args = argparse.Namespace()
                t_args.__dict__.update(json.loads(line))
                args = parser.parse_args(namespace=t_args)
                tests.append(create_test_case(args, parser, True))
    else:
        tests = [create_test_case(args, parser, False)]

    run_tests(tests, threads=args.threads, report_dir=args.report_dir, log=log)


if __name__ == "__main__":
    parse_arguments()
