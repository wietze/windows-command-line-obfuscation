# Windows Command-Line Obfuscation

## Background

`analyse_obfuscation` is a python3 module for finding common command-line obfuscation techniques for a given program, as described in [this](https://wietze.github.io/blog/windows-command-line-obfuscation) blog post.

By providing one or more commands, `analyse_obfuscation` will test if the following obfuscation techniques can be applied:

1) **Option Char substitution**

   _e.g. `ping -n 1 localhost` == `ping /n 1 localhost`_

2) **Character substitution**

   _e.g. `reg eˣport HKCU out.reg` == `reg export HKCU out.reg`_

3) **Character insertion**

   _e.g. `wevtutil gࢯli (…)` == `wevtutil gli (…)`_

4) **Quotes insertion**

   _e.g. `netsh ad"vfi"rewall show (…)` == `netsh advfirewall show (…)`_

5) **Shorthands**

   _e.g. `powershell /encod (…)` == `powershell /encodedcommand (…)`_

## Goals

Note that the goal of this project is to show that a given executable/command line can be obfuscated, not to give a complete list of possible obfuscations for a given command. It should however be possible to derive different obfuscation opportunities from `analyse_obfuscation`'s output.

Blue teamers 🔵 may want to use this tool, for example, to check if an executable they have written a detection rule is vulnerable to command-line obfuscation, meaning the rule should be improved or additional rules are needed. Note that in some cases this game is unwinnable - please take a look at the recommendations in the [blog post](https://wietze.github.io/blog/windows-command-line-obfuscation) for suggestions on how to tackle this.

Red teamers 🔴 may want to use this tool to find opportunities for bypassing simple detection rules.

## Usage

### Run

The simplest way to use this project is by running it (without installation).

* **Run script**: clone the entire repository, install all dependencies (`python3 -m pip install -r requirements.txt`) and run via:

  ```bash
  python3 -m analyse_obfuscation.run --help
  ```

### Install

By installing the project, it will be possible to simply call `analyse_obfuscation` from the command line.

* **Via PyPI**: install the application via for example pip:

  ```bash
  python3 -m pip install analyse_obfuscation
  ```

* **From source**: you can install a local version of the module by cloning the entire repository, followed by these commands:
  (note that this requires `setuptools` to be installed)

  ```bash
  python3 setup.py sdist bdist_wheel
  python3 -m pip install dist/analyse_obfuscation-*-py3-none-any.whl --upgrade
  ```

## Examples

![Screenshot](docs/screenshot.png)
_Sample execution output of `analyse_obfuscation`_

Each execution generates a high-level result overview on the stdout, as can be seen in the screenshot. Additionally a .log file providing examples of commands found to be working is created. Sample report files generated by the below commands can be found in the [sample_results/](sample_results/) folder.

```bash
# Check simple 'ping' command
analyse_obfuscation --command "ping /n 1 localhost"

# Check 'net share' command using {random}, which will be replaced by random string for each execution
analyse_obfuscation --command "net share x=c:\ /remark:{random}"

# Check 'powershell /encodedcommand' command with increased timeout, as executions tend to take long
analyse_obfuscation --command "powershell /encodedcommand ZQBjAGgAbwAgACIAQAB3AGkAZQB0AHoAZQAiAA==" --timeout 5

# Check 'systeminfo' command by only looking at the exit code, not the output - since every output will be different due to (changing) timestamps
analyse_obfuscation --command "systeminfo /s localhost" --timeout 5 --exit_code_only

# Check all commands as specified in sample.json, saving all reports in 'reports/'
analyse_obfuscation --json_file sample/sample.json --report_dir reports/
```

**Note** that the results may contain false positives - especially when single-character command-line options are being tested (such as `/n` in `ping /n 1 localhost`). In such cases, character insertion (method 3) may contain whitespace characters, which doesn't really 'count' as insertion character as whitespaces between command-line arguments are usually filtered out anyway. Similarly, character substitution (method 2) may change the entire option: e.g. `ping /s 1 localhost` and `ping /r 1 localhost` are functionally different, but happen to give the same output.

## All options

All command-line options of this project can be requested by using the `--help` option:

```
usage: analyse_obfuscation [--threads n] [--verbose] [--quiet] [--report_dir c:\path\to\dir] [--log_file c:\path\to\file.log] [--help] [--command "proc /arg1 /arg2"]
                           [--range {full,educated,ascii,custom}] [--custom_range 0x??..0x?? [0x??..0x?? ...]] [--char_offset n] [--pre_command process_name]
                           [--post_command process_name] [--exit_code_only] [--timeout n] [--json_file c:\path\to\file.jsonl]

Tool for identifying executables that have command-line options that can be obfuscated.

required arguments (either is required):
  --command "proc /arg1 /arg2"
                        Single command to test
  --json_file c:\path\to\file.jsonl
                        Path to JSON file (JSON Line formatted) containing commands config

optional --command arguments:
  --range {full,educated,ascii,custom}
                        Character range to scan (default=educated)
  --custom_range 0x??..0x?? [0x??..0x?? ...]
                        Range to scan
  --char_offset n       Character position used for insertion and replacement
  --pre_command process_name
                        Command to run unconditionally before each attempt, piping the result to the stdin
  --post_command process_name
                        Command to run unconditionally after each attempt (e.g. to clean up)
  --exit_code_only      Only base success on the exit code (and not the output of the command)
  --timeout n           Number of seconds per execution before timing out.

optional arguments:
  --threads n           Number of threads to use
  --verbose             Increase output verbosity
  --quiet               Decrease output verbosity
  --report_dir c:\path\to\dir
                        Path to save report files to
  --log_file c:\path\to\file.log
                        Path to save log to
  --help                Show this help message and exit
```

## Repository Contents

Item|Description
-|-
[analyse_obfuscation/](analyse_obfuscation) | Code for python3 module, enabling one to analyse executables for common command-line obfuscation techniques.
[sample/](sample/) | Sample config file to analyse built-in Windows executables, as well as related input files.  Used to generate results in the above folder.
[sample_results/](sample_results/) | Report files generated using the JSONL file in the above sample folder.
