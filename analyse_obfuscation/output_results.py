import datetime
import os
import re
from typing import Dict, List, Set, Tuple, Union

import colorama
import terminaltables

from .helpers import ranges

colorama.init()


def print_results(results: Dict[str, Dict[str, Union[Set[Tuple[int, str]], str, None]]]) -> None:
    """ For a dict with (test, result_dict), prepare a terminaltables AsciiTable and print to stdout """
    matrix = [['Process', 'Option Char', 'Char (insert)', 'Char (replace)', 'Quotes (insert)', 'Shorthands']]
    for display_name, test_outcomes in results.items():
        matrix.append([display_name] + [parse_outcome(test_outcome) for test_outcome in test_outcomes.values()])

    print(terminaltables.AsciiTable(matrix).table)


def parse_outcome(value: Union[Set[Tuple[int, str]], str, None]) -> str:
    """Prepare a terminal-printable output based on a given test outcome"""

    if value is None:  # If value is None, disregard
        return 'N/A'
    elif value:  # If value is positive, return Yes
        return_format = str(colorama.Back.GREEN) + '{}' + str(colorama.Style.RESET_ALL)
        if isinstance(value, str):  # If result is a string, only output Yes
            return return_format.format('Yes')
        elif isinstance(value, set):  # If result is a list, provide a count as well
            return return_format.format('Yes ({})'.format(len(value)))
        else:
            raise Exception("Unknown result type {}".format(type(value)))
    else:  # Value is negative, return No
        return str(colorama.Back.RED) + 'No' + str(colorama.Style.RESET_ALL)


def write_report(report_dir: str, name: str, command: str, char_offset: int, scan_range: List[int], test_outcomes: Dict[str, Union[Set[Tuple[int, str]], str, None]]) -> None:
    """Write a report, containing test results, to a given directory"""

    # Prepare output path
    file_name = '{}.log'.format(re.sub(r'[\\/*?:"<>|]', "", name))
    output_file = os.path.join(report_dir, file_name)

    # Open file
    with open(output_file, 'w', encoding='utf-16le') as f:
        # Print header
        f.write('PROCESS OBFUSCATION REPORT FOR {}\n'.format(name))
        f.write('- Generated on {}\n'.format(datetime.datetime.now().isoformat()))
        f.write('- Command used      : {}\n'.format(command))
        f.write('- Insertion position: {}\n'.format((' '*char_offset)+'^'))
        f.write('- Char ranges scanned: {}\n'.format(ranges(scan_range)))

        # Dash/hypten test
        if 'option_char' in test_outcomes:
            f.write('\n:: Option Char Substitution\n')
            outcomes = test_outcomes['option_char']
            if outcomes is not None:
                if outcomes:
                    f.write('The following {} commands were found to be working:\n'.format(len(outcomes)))
                    for identifier, command in sorted(outcomes, key=lambda x: x[0]):
                        f.write('0x{:0>4X} : {}\n'.format(identifier, command))
                else:
                    f.write('No alternative commands were found.\n')
            else:
                f.write('The command does not contain any arguments starting with a slash or dash.\n')

        # Character insertion test
        outcomes = test_outcomes.get('char_insert')
        if outcomes is not None:
            f.write('\n:: Character Insertion\n')
            if outcomes:
                f.write('The following {} commands were found to be working:\n'.format(len(outcomes)))
                for identifier, command in sorted(outcomes, key=lambda x: x[0]):
                    try:
                        f.write('0x{:0>4X} : {}\n'.format(identifier, command))
                    except:
                        f.write('0x{:0>4X} : (character can not be printed)\n'.format(identifier))
            else:
                f.write('No alternative commands were found.\n')

        # Character substitution test
        outcomes = test_outcomes.get('char_substitute')
        if outcomes is not None:
            f.write('\n:: Character Substitution\n')
            if outcomes:
                f.write('The following commands were found to be working:\n')
                for identifier, command in sorted(outcomes, key=lambda x: x[0]):
                    try:
                        f.write('0x{:0>4X} : {}\n'.format(identifier, command))
                    except:
                        f.write('0x{:0>4X} : (character can not be printed)\n'.format(identifier))
            else:
                f.write('No alternative commands were found.\n')

        # Quote insertion test
        outcome = test_outcomes.get('quotes')
        if outcome is not None:
            f.write('\n:: Quote Insertion\n')
            if outcome:
                f.write('Inserting quotes in the first argument did work, such as:\n')
                f.write('{}\n'.format(outcome))
            else:
                f.write('Inserting quotes in the first argument did not appear to be working.\n')

        # Shorthand commands
        outcomes = test_outcomes.get('shorthands')
        f.write('\n:: Shorthand Commands\n')
        if outcomes is not None:
            if outcomes:
                f.write('The following {} commands were found to be working:\n'.format(len(outcomes)))
                for identifier, command in sorted(outcomes, key=lambda x: len(x[1])):
                    f.write('{}\n'.format(command))
            else:
                f.write('No alternative commands were found.\n')
        else:
            f.write('The command is too short to be further shortened.\n')
