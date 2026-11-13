# Troubleshooting

Every error below was really produced on a Windows 11 machine while setting up this repo from a fresh clone on
2026-10-04. Most of them were caused on purpose so we could capture them for this page (a blocked script policy, a
PATH with no Python or Git, a venv with no course packages, a fake key); the failing tests came up on their own.
Each entry gives the error as it was printed, what it means, and the fix. A fix marked **(tested)** was run
and worked; a fix marked **(not tested here)** comes from the official docs or the error itself and was not run on that
machine.

## Setting up

### PowerShell will not run the activate script

```
& : File D:\bootcamp_setup_trial\AIAgentsBootcamp\.venv\Scripts\Activate.ps1 cannot be loaded because running scripts
is disabled on this system. For more information, see about_Execution_Policies at
https:/go.microsoft.com/fwlink/?LinkID=135170.
At line:1 char:3
+ & '.\.venv\Scripts\Activate.ps1'
+   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : SecurityError: (:) [], PSSecurityException
    + FullyQualifiedErrorId : UnauthorizedAccess
```

What it means: Windows is set to block PowerShell scripts, and activating a venv in PowerShell runs one.

Fix **(not tested here)**: run this once in PowerShell, as the Python venv docs give it, then activate again:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

The test machine already had `RemoteSigned` for the current user, so this command was not run there. Fix **(tested)**:
use cmd instead, where `.venv\Scripts\activate.bat` activates the venv with no policy change and the prompt starts
with `(.venv)`.

### `python` is not recognized

```
python : The term 'python' is not recognized as the name of a cmdlet, function, script file, or operable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
```

What it means: Windows cannot find Python on your PATH, usually because it is not installed.

Fix **(not tested here)**: install Python 3.13 with the standalone installer from python.org (see `INSTALL.md`). The Python docs recommend the Python install manager from
python.org/downloads or the Microsoft Store. Their troubleshooting list for this error also says to check
"Manage app execution aliases" for "Python (default)" and that your PATH has
`%UserProfile%\AppData\Local\Microsoft\WindowsApps`. Open a new terminal afterwards.

### `git` is not recognized

```
git : The term 'git' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the
spelling of the name, or if a path was included, verify that the path is correct and try again.
```

What it means: Git is not installed, or not on your PATH.

Fix **(not tested here)**: install Git for Windows from https://git-scm.com/install/windows, then open a new terminal.

### `No module named 'langgraph'`

```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'langgraph'
```

What it means: you ran a Python that is not the course venv, so the course packages are not there.

Fix **(tested)**: activate the venv (`.venv\Scripts\activate`, the prompt then starts with `(.venv)`), or call its
Python directly: `.venv\Scripts\python labs\00_03_setup_check.py`. In VS Code, pick the `.venv` interpreter with
`Python: Select Interpreter`. If you have not installed yet, run `pip install -r requirements.txt` inside the venv.

### I have Python 3.11 or 3.12, not 3.13

There is no error, and you do not need to reinstall. The course recommends 3.13 because python.org still ships its
installers; 3.11 and 3.12 also work. On 2026-10-04 the full suite passed on a fresh clone with Python 3.11.9 (281
passed, 6 skipped, 1 xfailed) and with Python 3.13.14 (the same count). 3.12 was not run here.

## Running the tests

### pytest stops on 6 errors during collection

```
ERROR AIAgentsBootcamp/labs/06_01_04_invoke_and_test.py - httpx.ConnectError:...
ERROR AIAgentsBootcamp/labs/19_dataflow/starter/check/test_desk.py
ERROR AIAgentsBootcamp/labs/19_research/starter/check/test_agent.py
ERROR AIAgentsBootcamp/labs/19_talentflow/solution/check/test_pipeline.py
ERROR AIAgentsBootcamp/labs/19_talentflow/starter/check/test_pipeline.py
ERROR AIAgentsBootcamp/tests/test_foundation_llm.py - FileNotFoundError: Cann...
!!!!!!!!!!!!!!!!!!! Interrupted: 6 errors during collection !!!!!!!!!!!!!!!!!!!
```

with, among them,
`E   FileNotFoundError: Cannot find the AI Agents Bootcamp repo. Open the notebook from the cloned repo folder, or set BOOTCAMP_ROOT.`

What it means: you ran pytest from the folder above the repo, so it missed the repo's `pytest.ini` and walked into
`labs/` too. Collecting one of those labs makes a model call, so with Ollama running this would also send a request.

Fix **(tested)**: `cd AIAgentsBootcamp` and run `pytest -q` there.

### `test_root_from_viralloom_nest` fails with `IndexError: 6`

```
FAILED tests/test_paths.py::test_root_from_viralloom_nest - IndexError: 6
```

What it means: an old test checked the course team's own folder layout and broke on any clone less than seven folders
deep. Your setup is fine.

Fix **(tested)**: fixed in the repo on 2026-10-04. Run `git pull` and test again.

### `test_scripted_fix_makes_sandbox_test_pass` fails some of the time

```
FAILED tests/test_sandboxed_loop.py::test_scripted_fix_makes_sandbox_test_pass
E       assert False is True
```

What it means: Python reused a cached `.pyc` of a file that had just been edited to the same length in the same
second, so the test ran the old code. Your setup is fine.

Fix **(tested)**: fixed in the repo on 2026-10-04 (the sandbox now runs pytest with `python -B`). Run `git pull`.

### pytest prints dots but no `N passed` line

What it means: the repo's `pytest.ini` used to add `-q` too, so `pytest -q` was quiet twice and dropped the count line.

Fix **(tested)**: fixed in the repo on 2026-10-04. Run `git pull`. Until then, run plain `pytest`.

## Calling a model

### The local model cannot be reached

```
httpx.ConnectError: [WinError 10061] No connection could be made because the target machine actively refused it
```

What it means: nothing is answering at `OLLAMA_BASE_URL` (default `http://localhost:11434`), so Ollama is not
installed or not running. `labs/00_04_keys_and_config.py` does not stop on this: it prints
`local skipped: nothing answered at http://localhost:11434. Is Ollama installed and running?` and goes on to the
hosted call, so a cloud key with its model id set in `.env` still runs there. pytest is not affected: its one live
test skips with `no local model`.

Fix **(not tested here)**: install Ollama (on Windows, in PowerShell: `irm https://ollama.com/install.ps1 | iex`, or
OllamaSetup.exe from ollama.com/download), make sure it is running, then `ollama pull qwen3:8b` (5.2 GB). If you set `OLLAMA_BASE_URL` in the terminal yourself, for example `$env:OLLAMA_BASE_URL = "http://127.0.0.1:1"` in PowerShell to break a lab on purpose, that value wins over the line in `.env` (`config.py` reads `.env` only for names that are not set already), so undo it when you are done: `Remove-Item Env:OLLAMA_BASE_URL`, or open a new terminal.

The Section 4 labs end on the same `httpx.ConnectError` line (caused on the test machine on 2026-10-31 with
`OLLAMA_BASE_URL` pointed at a port where nothing runs, within a few seconds). `labs/05_03_init_chat_model.py` prints
its model and message lines first. `labs/05_12_build_the_desk.py` prints its model and the graph's nodes first, and its
very last line is `During task with name 'model' and id ...`, with the `httpx.ConnectError` line just above it.
`labs/05_32_desk_behind_a_door.py` prints `ERROR:    Exception in ASGI application` and a traceback from the door
first, then `smoke 3 reset_parked pass False | 500` and `smoke_passed 2/5` (health and the missing key need no model),
then stops in the eval set on the same last lines as 05_12. Start Ollama and run the lab again.

The Section 5 context labs end on the same `httpx.ConnectError` line too (caused on the test machine on 2026-11-02,
the same way, in about four seconds each): `labs/03_02_context_rot.py`, `03_06_fat_vs_map.py`, `03_08_compaction.py`,
`03_09_compare_compaction.py`, `03_11_notes_file.py`, `03_12_recover_from_notes.py`, `03_14_just_in_time_read.py`,
`03_16_subagent_isolation.py`, `03_18_guard_the_window.py`, `03_20_budget_and_window_log.py` and
`03_22_long_task.py`. Some print their settings first (03_02 its turns, the rule and the probe; 03_08 its three knobs;
03_20 its budget, its window and the map's owner), then each stops at its first model call. `labs/03_03_measure_tokens.py`
and `labs/03_05_map_file.py` call no model and run without Ollama.

### The model is not pulled

```
ollama._types.ResponseError: model 'not-pulled-model:latest' not found (status code: 404)
```

What it means: Ollama is running but does not have the model `config.py` asked for. Your error names your model.

Fix **(not tested here)**: `ollama pull <the model named in the error>`, for example `ollama pull qwen3:8b`. Check
what you have with `ollama list`.

The Section 4 labs `labs/05_03_init_chat_model.py` and `labs/05_12_build_the_desk.py` stop on this error within a few
seconds (caused on the test machine on 2026-10-31 with `OLLAMA_CHAT_MODEL` set to `qwen3:4b`, a tag not pulled there:
`ollama._types.ResponseError: model 'qwen3:4b' not found (status code: 404)`). It is the last line of 05_03; in 05_12 it
sits just above the last line, `During task with name 'model' and id ...`. Both print `qwen3:4b` as the model
first, read from the model they built, so that line tells you which name `config.py` asked for.

### No `.env` file

There is no error. With `.env` missing, the labs behave exactly as with the sample copied in, because every value in
`.env.sample` is also the default in `config.py`. You only need `.env` once you add a cloud key or change a model.

## Cloud keys

### OpenAI says the key is wrong

```
langchain_openai.chat_models.base.OpenAIAuthenticationError: Error code: 401 - {'error': {'message': 'Incorrect API key provided: sk-fake-*****************-lab. You can find your API key at https://platform.openai.com/account/api-keys.', 'type': 'invalid_request_error', 'code': 'invalid_api_key', 'param': None}, 'status': 401}
```

What it means: OpenAI refused the key in `OPENAI_API_KEY`. Nothing was generated, so nothing was billed.

Fix **(not tested here, no real key was used)**: make a new key in the OpenAI dashboard and paste it into `.env` as
`OPENAI_API_KEY=...` with no quotes or spaces. A key already set in your terminal wins over `.env`.

### Anthropic says the key is invalid

```
langchain_anthropic.chat_models.AnthropicAuthenticationError: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'API key is invalid.'}, 'request_id': None}
```

What it means: Anthropic refused the key in `ANTHROPIC_API_KEY`.

Fix **(not tested here, no real key was used)**: make a new key in the Claude Console under Settings, API keys. It
starts with `sk-ant-` and is shown only once. Paste it into `.env` as `ANTHROPIC_API_KEY=...`.

### `temperature` is not supported

```
ValueError: `temperature` is not supported for claude-sonnet-5-5 at non-default values.
ValueError: `temperature` is not supported for claude-fable-5-1 at non-default values.
```

What it means: `config.py` asked for temperature 0, and the langchain-anthropic library refuses that for these
models before sending anything.

Fix **(tested with a fake key, request built locally)**: fixed in `config.py` on 2026-10-04: it now uses the model's
default temperature when the library refuses 0. Run `git pull`. Whether Anthropic answers a real request was not
tested.

### A key is set but the local model answers

```
warning: OPENAI_API_KEY is set but OPENAI_CHAT_MODEL is empty, so this run uses the local model qwen3:8b. Set OPENAI_CHAT_MODEL in .env to use the hosted model.
```

What it means: a hosted model needs both the key and a model id. Before 2026-10-04 this fell back to the local model
with no message at all.

Fix **(tested with a fake key)**: set the model id next to the key in `.env`, for example
`ANTHROPIC_CHAT_MODEL=claude-opus-5-5`.

## Asking for help

If none of this fixes it, ask in the course Q&A. In the course player, click the Udemy AI Assistant icon at the top
right, then View course Q&A, then Ask a new question. Put three things in it:

- which lab or command you ran, for example `labs/00_03_setup_check.py`;
- the full output, from the command to the last line, pasted as text;
- the model you ran: `qwen3:8b` on Ollama, or the provider and the model id from your `.env`.

Never paste your API key. Delete the key line from the output before you post. Udemy's help page says Q&A is not
available in free course enrollments.

## More setup errors

These entries were added after the first setup lessons; each one says whether its error was caused on our Windows 11 test machine on 2026-10-04 or quoted from the tool's own documentation or source code.

### `git clone` says the folder already exists

Caused on the test machine.

```
fatal: destination path 'AIAgentsBootcamp' already exists and is not an empty directory.
```

What it means: you already cloned the repo into this folder, and Git will not clone over a folder that has files in it.

Fix **(tested)**: do not clone again. Go into the folder you have and update it: `cd AIAgentsBootcamp`, then
`git pull`. It answers `Already up to date.` or brings the newest files.

### `No suitable Python runtime found`

Caused on the test machine.

```
No suitable Python runtime found
Pass --list (-0) to see all detected environments on your machine
or set environment variable PYLAUNCHER_ALLOW_INSTALL to use winget
or open the Microsoft Store to the requested version.
```

What it means: you asked the `py` launcher for a Python version that is not installed, for example `py -3.13` on a
machine with no 3.13.

Fix **(tested)**: run `py --list` to see the versions you have. Install Python 3.13 from python.org (see
`INSTALL.md`), open a new terminal, and run the command again. If the list shows 3.11 or 3.12, you can use that
instead (see "I have Python 3.11 or 3.12, not 3.13" above), for example `py -3.11 -m venv .venv`. On the test machine
the message came from `py -3.12`, the version it does not have; the message names no version, so it reads the same
for a missing 3.13. After that, `py -3.13 --version` answered `Python 3.13.14`.

### `code` is not recognized

Caused on the test machine; the fix is quoted from the VS Code docs.

In cmd:

```
'code' is not recognized as an internal or external command,
operable program or batch file.
```

In PowerShell:

```
code : The term 'code' is not recognized as the name of a cmdlet, function, script file, or operable program. Check
the spelling of the name, or if a path was included, verify that the path is correct and try again.
```

What it means: the terminal cannot find VS Code on its PATH. Most often the terminal was open before VS Code was
installed, and a terminal reads PATH only when it starts.

Fix **(tested)**: close the terminal, open a new one, and run `code .` again. The VS Code docs
(https://code.visualstudio.com/docs/setup/windows) say: "Setup adds Visual Studio Code to your %PATH% environment
variable. Restart your console after installation". If it is still not found, the docs say to reinstall VS Code; the
folder that must be on PATH is `AppData\Local\Programs\Microsoft VS Code\bin` in your user folder. You can also skip
the command: open VS Code and use File, Open Folder. To confirm, `code --version` prints a version number.

### I ran `pip install` and the labs still say `No module named ...`

Caused on the test machine.

There is no error at install time. The sign is a prompt with no `(.venv)` at the start, and `pip --version` naming
the machine's Python instead of the venv. On the test machine it printed:

```
pip 24.0 from C:\Users\Admin\AppData\Local\Programs\Python\Python311\Lib\site-packages\pip (python 3.11)
```

Your path will show your own user folder. The error comes later, when a lab runs; it is the one in
"`No module named 'langgraph'`" above, with the name of whichever package the lab needs first.

What it means: the venv was not active, so `pip` was the machine's own pip and the packages went to the machine's
Python, not to the course venv.

Fix **(tested)**: activate the venv (`.venv\Scripts\activate`), check the prompt starts with `(.venv)`, then run
`pip install -r requirements.txt` again. To confirm, run `python -m pip --version` and read the path: inside the venv
it ends in `AIAgentsBootcamp\.venv\Lib\site-packages\pip`.

### The setup check says `NOT GREEN` and `No module named pytest`

Caused on the test machine.

```
pytest_exit 1
NOT GREEN: read the FAILED or ERROR lines above, look them up in TROUBLESHOOTING.md, fix, and run this check again.
```

and, on the error stream, a line ending in

```
python.exe: No module named pytest
```

The `venv` line the check prints above them names the machine's Python, not your `AIAgentsBootcamp\.venv` folder.

What it means: you ran `labs\00_03_setup_check.py` with the machine's Python, not the course venv, so pytest and the
course packages are not there. It is the same cause as "`No module named 'langgraph'`" above.

Fix **(tested)**: activate the venv (`.venv\Scripts\activate`) or run the venv's Python directly:
`.venv\Scripts\python labs\00_03_setup_check.py`. To confirm, the `venv` line ends in `.venv` and the check no
longer says `NOT GREEN`.

### `pip install` fails with a hint about Windows Long Path support

Quoted from pip's source code (pip 26.1.2, `src/pip/_internal/commands/install.py`,
https://raw.githubusercontent.com/pypa/pip/26.1.2/src/pip/_internal/commands/install.py) and Microsoft's docs; not
caused on the test machine, which already had long paths on.

pip builds the message from these two fixed pieces:

```
Could not install packages due to an OSError: <the Windows error and the long file path>
HINT: This error might have occurred since this system does not have Windows Long Path support enabled. You can find information on how to enable this at https://pip.pypa.io/warnings/enable-long-paths
```

The part after `OSError: ` is the Windows error and the file path, so it differs per machine. Look for the `HINT:`
line; pip adds it when the full path is longer than 260 characters.

What it means: the repo sits in a deep folder, so a file the install writes gets a full path longer than 260
characters, and Windows refuses it.

Fix **(not tested here)**: move or clone the repo into a short folder near the drive root, for example
`C:\code\AIAgentsBootcamp`, make the venv there and install again. Or turn long paths on. Microsoft's page
(https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation) gives this command for a
PowerShell run as Administrator, and says "a reboot might be required":

```
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

To confirm, `pip install -r requirements.txt` finishes with no `HINT:` line.

### `ollama pull` says `file does not exist`

Caused on the test machine.

```
pulling manifest
Error: pull model manifest: file does not exist
```

What it means: Ollama has no model with that exact name and tag. On the test machine `qwen3:9b` (no such size) and
`qwen3-8b` (a dash where the colon goes) both gave this.

Fix **(tested)**: copy the exact tag: `ollama pull qwen3:8b`, with a colon. https://ollama.com/library/qwen3/tags
lists every tag. To confirm, `ollama list` shows the model.

### `ollama serve` says the address is already in use

Caused on the test machine, on a spare port.

```
Error: listen tcp 127.0.0.1:11434: bind: Only one usage of each socket address (protocol/network address/port) is normally permitted.
```

The line above is written with Ollama's default port, 11434, the one you will see. On the test machine the error was
caused on a spare port, so the captured line named `127.0.0.1:11435`; the 11434 line was not captured.

What it means: Ollama is already running. On Windows the installed app starts it in the background, so a second
`ollama serve` cannot take the same port.

Fix **(tested)**: nothing to fix, and you do not need `ollama serve`. Use the one that is running. To confirm,
`ollama list` answers with a `NAME    ID    SIZE    MODIFIED` header.

### `ollama list` says `timed out waiting for server to start`

Caused on the test machine.

```
Error: timed out waiting for server to start
```

A few log lines may print above it; the line to look for is the last one.

What it means: the `ollama` command found no Ollama server answering, tried to start one, and gave up waiting. On
the test machine it was caused by pointing `OLLAMA_HOST` at a port where nothing runs. It is the command line's
version of "The local model cannot be reached" above.

Fix **(not tested here)**: start Ollama from the Start menu and wait a few seconds, then run `ollama list` again. If
you set `OLLAMA_HOST` yourself, remove it or set it to `127.0.0.1:11434`, and open a new terminal. If Ollama is not
installed, see "The local model cannot be reached" above. To confirm, `ollama list` answers with a
`NAME    ID    SIZE    MODIFIED` header.

### `ollama pull` cannot reach the registry

Caused on the test machine, with a deliberately broken proxy.

```
pulling manifest
Error: pull model manifest: Get "https://registry.ollama.ai/v2/library/qwen3/manifests/8b": proxyconnect tcp: dial tcp 127.0.0.1:9: connectex: No connection could be made because the target machine actively refused it.
```

The line above is written with the course model's tag, `8b`. On the test machine the pull was for `qwen3:0.6b`, so
the captured line ended in `manifests/0.6b`; the `8b` line was not captured. `127.0.0.1:9` was the broken proxy used
for the test. Your line will name your own model and your own proxy or network address; the part to look for is
`Error: pull model manifest: Get "https://registry.ollama.ai/`.

What it means: Ollama could not reach its registry over the internet. A proxy setting is wrong, or a company network,
VPN or firewall is in the way.

Fix **(tested for a wrong proxy)**: if you set a proxy by mistake, remove it and restart Ollama; the pull then
reaches the registry. Fix **(not tested here)** for a company network: the Ollama FAQ (https://docs.ollama.com/faq)
says "Use HTTPS_PROXY to redirect outbound requests through the proxy" and "Avoid setting HTTP_PROXY". Set
`HTTPS_PROXY` to your company's proxy and restart Ollama, or pull the model on a home network. To confirm, the pull
shows download progress instead of the error.

### The model needs more memory than the machine has

Quoted from Ollama's source code and FAQ; not caused on the test machine, which has plenty of memory.

The exact line differs by Ollama version. In versions 0.12.0 and 0.20.0 the source
(https://raw.githubusercontent.com/ollama/ollama/v0.20.0/llm/server.go) builds it from this, with the two `%s` filled
in by sizes:

```
model requires more system memory (%s) than is available (%s)
```

Version 0.35.1 no longer has that sentence. Its source treats a load error as out of memory when it contains words
such as `out of memory`, `not enough memory`, `insufficient memory`, `failed to allocate` or `allocation failed`, so
look for those words, or for `memory` and `available` together, in the error. Run `ollama --version` to see which
version you have.

What it means: the model needs more free memory than your machine has right now.

Fix **(not tested here)**: close other heavy apps and try again. The Ollama FAQ says: "Use the ollama ps command to
see what models are currently loaded into memory." Unload one with `ollama stop <model>`. If it still does not fit,
pull a smaller tag (on 2026-10-04 https://ollama.com/library/qwen3/tags lists `qwen3:4b` at 2.5GB against
`qwen3:8b` at 5.2GB) and set it in `.env`, or use a cloud key. To confirm, `ollama ps` lists the model after a lab
calls it.

### VS Code's Run button gives `No module named ...`

Quoted from the VS Code docs; it is a screen, so it was not captured.

The error is the one in "`No module named 'langgraph'`" above, while the same lab works in a terminal with `(.venv)`
active. The Status Bar at the bottom of VS Code shows a Python that is not `.venv`.

What it means: VS Code picked the machine's Python and not the course venv.

Fix **(not tested here)**: open the `AIAgentsBootcamp` folder itself with File, Open Folder, not a single file and
not the folder above it. Then, as the docs (https://code.visualstudio.com/docs/python/environments) put it: "Status
Bar: select the Python version shown at the bottom of the window", or "Command Palette: run Python: Select
Interpreter and choose from the list". Pick the entry that shows `.venv`. To confirm, the Status Bar shows `.venv`.

### A notebook says `Running cells with '...' requires the ipykernel package.`

Quoted from the VS Code Jupyter extension's source code and docs; it is a screen, so it was not captured.

The extension's source
(https://raw.githubusercontent.com/microsoft/vscode-jupyter/main/src/platform/common/utils/localize.ts) builds the
prompt from this, with `{0}` filled in by the Python environment's name and `{1}` by the package name:

```
Running cells with '{0}' requires the {1} package.
```

What it means: the notebook's kernel is a Python that has no `ipykernel`, the package a notebook needs to run a
cell. The course install puts `ipykernel` into `.venv`, so this almost always means the notebook is on the wrong
Python.

Fix **(not tested here)**: look at the name inside the quotes. If it is not `.venv`, do not click Install: click the
kernel name at the top right of the notebook, choose Select Another Kernel, then Python Environments, then `.venv`.
If the name is `.venv`, the install did not finish: activate the venv and run `pip install -r requirements.txt`
again. The docs (https://code.visualstudio.com/docs/datascience/jupyter-kernel-management) say: "Only the IPyKernel
package is required to launch a Python process as a kernel". To confirm, a cell runs and prints its output.

### A raw lab ends in `openai.APIConnectionError: Connection error.`

Caused on the test machine on 2026-10-05, with `OLLAMA_BASE_URL` pointed at a port where nothing runs.

```
openai.APIConnectionError: Connection error.
```

That is the last line. `labs/01_06_first_raw_api_call.py`, `labs/01_08_structured_output_raw.py` and
`labs/01_10_raw_tool_call.py` call Ollama through the OpenAI Python SDK, which tries again before it gives up, so the
terminal sat quiet for about 14 seconds and then printed a traceback of about 90 lines. Higher up in it, twice, is the
same Windows sentence as in "The local model cannot be reached" above:

```
[WinError 10061] No connection could be made because the target machine actively refused it
```

`labs/01_04_tokens_and_window.py` asks Ollama directly. It prints its first four lines and then stops with:

```
urllib.error.URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
```

What it means: nothing is answering at `OLLAMA_BASE_URL`, so Ollama is not installed or not running. It is the cause
of "The local model cannot be reached" above, printed by a different library.

Fix **(not tested here)**: start Ollama as that entry says, then run the lab again. Fix **(tested)**: on the test
machine, with an Ollama server answering at `OLLAMA_BASE_URL`, the same four labs ran to the end. To confirm,
`ollama list` answers with a `NAME    ID    SIZE    MODIFIED` header. The Section 3 labs `labs/02_03_scratch_agent.py`, `labs/02_04_second_tool.py`, `labs/02_06_break_the_loop.py` and `labs/02_13_loop_as_a_class.py` call Ollama through the same SDK and end on the same last line (caused on the test machine on 2026-10-29, all four, with nothing answering at `OLLAMA_BASE_URL`); like the raw labs, they always call your local Ollama, so a cloud key does not help here.

### A raw lab ends in `openai.NotFoundError: Error code: 404`

Caused on the test machine on 2026-10-05, with Ollama running and `OLLAMA_CHAT_MODEL` set to `qwen3:4b`, a tag that
was not pulled there.

```
openai.NotFoundError: Error code: 404 - {'error': {'message': "model 'qwen3:4b' not found", 'type': 'not_found_error', 'param': None, 'code': None}}
```

The three raw labs print this within a few seconds. `labs/01_04_tokens_and_window.py` prints its first four lines and
then this, which does not name the model:

```
urllib.error.HTTPError: HTTP Error 404: Not Found
```

What it means: Ollama is running but does not have the model `config.py` asked for. It is the cause of "The model is
not pulled" above, printed by a different library. The model asked for is the one in `OLLAMA_CHAT_MODEL` in `.env`,
or `qwen3:8b` when that line is not set.

Fix **(tested for a wrong name)**: compare `OLLAMA_CHAT_MODEL` in `.env` with what `ollama list` shows; with it back on
a model that was pulled, the labs ran. Fix **(not tested here)** for a model you never pulled: `ollama pull` and the
model's name, for example `ollama pull qwen3:8b`. The Section 3 labs `labs/02_03_scratch_agent.py`, `labs/02_04_second_tool.py`, `labs/02_06_break_the_loop.py` and `labs/02_13_loop_as_a_class.py` end on the same line within a few seconds (caused on the test machine on 2026-10-29, all four, with `OLLAMA_CHAT_MODEL` set to `qwen3:4b`).

### A hosted call says the account has no credit

Caused on the test machine on 2026-10-05 with real keys from accounts that have no API credit, running
`labs/00_04_keys_and_config.py`.

OpenAI, with `OPENAI_CHAT_MODEL=gpt-6-luna`:

```
langchain_openai.chat_models.base.OpenAIRateLimitError: Error code: 429 - {'error': {'message': 'You have no credits remaining. Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/.', 'type': 'insufficient_quota', 'param': None, 'code': 'credit_balance_exhausted'}}
```

Anthropic, with `ANTHROPIC_CHAT_MODEL=claude-haiku-4-5-20251001`:

```
langchain_anthropic.chat_models.AnthropicInvalidRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}, 'request_id': 'req_011CfiSBaBG2aFUAktkkiJZX'}
```

Your `request_id` will be different. The lab prints its local lines first (`local_model` and `local_reply` when
Ollama is running), then the traceback, and never prints `hosted_model`. OpenAI's error says `RateLimitError` and 429,
but its message and its `insufficient_quota` type are about credit, not about sending too fast.

What it means: the key is real and the provider read it, but the account has no API credit to spend.

Fix **(not tested here, no credit was added)**: add credit on the provider's billing page. OpenAI's error gives the
address; Anthropic's names Plans & Billing. Fix **(tested)** to go on at no cost: empty the key line in `.env` (and
remove the key from your terminal if you set it there). The lab then ends with `hosted skipped: no cloud key set` and
the labs run on the local model.

### A hosted call says the model does not exist

Caused on the test machine on 2026-10-05 with a real OpenAI key and `OPENAI_CHAT_MODEL=gpt6-luna`, the id
`gpt-6-luna` with its first dash dropped.

```
langchain_openai.chat_models.base.OpenAIModelNotFoundError: Error code: 404 - {'error': {'message': 'The model `gpt6-luna` does not exist or you do not have access to it.', 'type': 'invalid_request_error', 'param': None, 'code': 'model_not_found'}}
```

OpenAI checked the model id before the credit: the same key with no credit gave this 404, not the 429 in the entry
above. Anthropic checked the credit first: with `ANTHROPIC_CHAT_MODEL=claude-haiku-4-5-2025101` (one digit dropped)
the same kind of key gave the credit error above, so Anthropic's wrong-model message was not captured.

What it means: the model id in `.env` is mistyped, retired, or not open to your account.

Fix **(not tested here)**: copy the id exactly as the provider's models page writes it into `OPENAI_CHAT_MODEL` (or
`ANTHROPIC_CHAT_MODEL`), save `.env`, and run the lab again.

### After `make_twins.py`, `git status` lists the twin as changed

Caused on the test machine on 2026-10-05, in a clone made before the fix below.

```
 M labs/00_05_notebook_twin_demo.ipynb
```

`git diff` on the file shows no changed line, only
`warning: in the working copy of 'labs/00_05_notebook_twin_demo.ipynb', LF will be replaced by CRLF the next time Git touches it`.

What it means: the test machine's Git for Windows has the system setting `core.autocrlf=true`, so Git checked the
twin out with CRLF line endings. `make_twins.py` writes LF, so the rebuilt twin had a different size from the one Git
checked out and `git status` listed it, though its content is the same. Since 2026-10-05 the repo's `.gitattributes`
checks every `.ipynb` out with LF, and a clone made after that prints nothing here.

Fix **(tested)**: run `git pull`, then `git checkout -- labs/00_05_notebook_twin_demo.ipynb`, which checks the twin
out again with LF. After that, delete it, run `python scripts/make_twins.py`, and `git status --short` prints nothing.

### `test_config_has_local_default_and_import_does_not_need_a_key` fails

Caused on the test machine on 2026-10-05, with `OLLAMA_BASE_URL=http://127.0.0.1:11435`.

```
FAILED tests/test_smoke.py::test_config_has_local_default_and_import_does_not_need_a_key
E       AssertionError: assert 'localhost' in 'http://127.0.0.1:11435'
```

What it means: this test checks that `OLLAMA_BASE_URL` contains the word `localhost`. An address written as
`127.0.0.1` reaches the same machine but fails the check. Your setup is fine.

Fix **(tested)**: write the address with `localhost`, in `.env` or in your terminal, for example
`OLLAMA_BASE_URL=http://localhost:11434`, and run pytest again.

Since 2026-10-05 the test accepts `127.0.0.1` too, so a clone made after that does not stop here; in an older clone,
`git pull` brings the change.

### pytest stops on 5 errors during collection

Caused on the test machine on 2026-10-05, from the folder above the repo, with Ollama not running.

```
ERROR AIAgentsBootcamp/labs/19_dataflow/starter/check/test_desk.py
ERROR AIAgentsBootcamp/labs/19_research/starter/check/test_agent.py
ERROR AIAgentsBootcamp/labs/19_talentflow/solution/check/test_pipeline.py
ERROR AIAgentsBootcamp/labs/19_talentflow/starter/check/test_pipeline.py
ERROR AIAgentsBootcamp/tests/test_foundation_llm.py - FileNotFoundError: Cann...
!!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!!!
```

What it means: the same mistake as pytest stops on 6 errors during collection. Since 2026-10-05 the repo's `conftest.py` keeps pytest out of the scripts in `labs/`, so the `06_01_04` line is gone, no lab calls your model, and the run stops in seconds. The `E   FileNotFoundError: Cannot find the AI Agents Bootcamp repo` line is still among the five.

Fix **(tested)**: `cd AIAgentsBootcamp` and run `pytest -q` there.

## The RAG labs (Sections 22 to 25, and 31.5)

### `docker compose` cannot start Postgres (lab 23.4)

Caused on the test machine on 2026-11-02 with Docker Desktop installed and not running, on
`labs/08_02_04_pgvector.py`:

```
compose_returncode 1
compose_said unable to get image 'pgvector/pgvector:pg16': error during connect: ... open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
BLOCKED ON DOCKER
docker compose could not start Postgres (its last line is above); if Docker is not running, start Docker Desktop and run this lab again.
```

What it means: your width check ran (it needs no Docker), and then nothing answered on Docker's pipe, so compose
could not even fetch the Postgres image. The lab stops cleanly with exit code 0. If the `docker` command itself is
missing, the lab prints `BLOCKED ON DOCKER` and `docker is not installed or not on PATH`.

Fix **(not tested here)**: start Docker Desktop, wait until it says it is running, and run the lab again. The first
`docker compose up` downloads the `pgvector/pgvector:pg16` image, which takes a while once.

### The pgvector lab prints `Collection not found` (lab 23.4)

Caused on the test machine on 2026-11-12, on the first run of `labs/08_02_04_pgvector.py` against a new Postgres
volume, with Docker Desktop running:

```
Collection not found
Collection not found
```

What it means: not an error. The lab opens each of its two collections with "delete it first if it is there", and on
a new database there is nothing to delete, so the library says so once per collection. The run carries on: the lines
to read are the ones after it (`inserted 37`, the three hits, the desk's reply). On the second run the collections
exist and the two lines are gone.

Fix: none needed.

### The json loader says `jq package not found` (lab 22.3)

```
JSONLoader_error ImportError: jq package not found, please install it with `pip install jq`
```

What it means: nothing is wrong. Caused on purpose by `labs/08_01_03_load_knowledge_base.py` (run on the test
machine on 2026-11-02): LangChain's `JSONLoader` needs the `jq` package, which this course does not install, so the
lab prints `jq_installed False` and loads the json files with its own `load_json`.

Fix: none needed, and do not install `jq`: the lecture's run is the one without it. If you installed it, the lab
prints `JSONLoader_loaded (jq is installed on this machine)` instead.

### The embedder is not pulled

```
ollama._types.ResponseError: model 'nomic-embed-text:v1.5-not-pulled' not found (status code: 404)
```

What it means: Ollama is running, but it does not have the embedding model `config.py` asked for. Every RAG lab
that builds or loads an index stops here. Caused on the test machine on 2026-11-02 on `labs/08_02_02_index_faiss.py`
with `OLLAMA_EMBED_MODEL` set to a tag that machine had not pulled; the lab printed
`embedder OllamaEmbeddings nomic-embed-text:v1.5-not-pulled` first, read off the embedder it built, so that line
names the model it asked for.

Fix **(not tested here)**: `ollama pull nomic-embed-text` (274 MB), and if you set `OLLAMA_EMBED_MODEL` yourself,
remove it so the default is used.

### A lab prints `rebuilding_index` or `refreshed_index`

```
rebuilding_index customer the index on disk has no index_meta.json, so nothing says what built it
```

What it means: not an error. The desk's indexes under `dataflow/data/` carry `index_meta.json`, which says which
folders and which embedder built them and what every file's contents were. When there is no index yet, or it came
from other folders or another embedder, or from before 2026-11-02 (no `index_meta.json`), the lab rebuilds it once and
says why; when a knowledge base file changed, it re-embeds only that file and prints `refreshed_index` with the file.
Caused on the test machine on 2026-11-02 on `labs/08_02_02_index_faiss.py` after deleting the customer index's
`index_meta.json`; the rebuild took about half a minute there.

Fix: none needed. Never copy an index folder from someone else's machine: loading one unpickles it.

### An index build stops on `tokenize ... (status code: 400)`

```
ollama._types.ResponseError: Post "http://127.0.0.1:49313/tokenize": dial tcp 127.0.0.1:49313: connectex: No connection could be made because the target machine actively refused it. (status code: 400)
```

What it means: Ollama's own embedding worker stopped answering while the index was being built (the port in the line
is Ollama's internal one, not yours). Caused once on the test machine on 2026-11-02, on the first run of
`labs/08_04_06_portfolio_knowledge_desk.py`, while Ollama was loading the chat model beside the embedder.

Fix **(tested)**: run the lab again. An index is saved only when its build finishes, so nothing half-built is left;
on the test machine the second run built it.

## The MCP labs (Section 28)

### A stdio MCP lab says `Connection closed` and `No module named 'dataflow'` (lab 28.7)

```
D:\...\.venv\Scripts\python.exe: Error while finding module specification for 'dataflow.mcp.server' (ModuleNotFoundError: No module named 'dataflow')
client_error MCPError Connection closed
```

What it means: the client started the server, and the server could not import the course's own code. A stdio
server is a child process that sees only a short list of your environment (on Windows PATH, SYSTEMROOT, TEMP and a
few more; elsewhere HOME, PATH, SHELL and a few more), not your PYTHONPATH and not your `.env`, and a host starts it
from its own folder, not from the repo. Caused on the test machine on 2026-11-13 by deleting the
`server["env"] = stdio_env()` line in `labs/13_01_04_mcp_client.py`, whose config starts the server from the temp
folder; the client gave up after 0.1 seconds.

Fix **(tested)**: give the server its environment in the config, the way `dataflow/mcp/client.py` does with
`"env": stdio_env()` (it carries PYTHONPATH), or a `"cwd"` at the repo root. A server you add to a host such as
Claude Desktop needs the same two keys.

### `ValueError: MCP target 'dataflow/mcp/server.py' is not a valid URL` (lab 28.8)

```
ValueError: MCP target 'dataflow/mcp/server.py' is not a valid URL. To run a local MCP server over stdio, ask for it explicitly with `Path('server.py')`, a `fastmcp` transport, or an `MCPConfig`
```

What it means: `MCPAdapter` reads a string target as a URL and accepts only http and https, so that a string from a
config file or from a model can never quietly start a program on your machine. Caused on the test machine on
2026-11-13 by passing `"dataflow/mcp/server.py"` to `mcp_tools` in `labs/13_01_06_mcpadapter.py`.

Fix **(tested)**: pass the config dict from `load_config()` (or a `ClientGroup`, lab 28.9). A `Path` also works for
a server file that runs on its own.

### `git status` lists `dataflow/mcp/runs/server.pid` after an MCP lab

What it means: the DataFlow server writes its process id there when it starts and removes the file when it exits.
The file stays when the server is killed instead. FastMCP keeps a stdio server running after the client leaves, so
it can be reused (`keep_alive`, on by default), and when your Python ends, the MCP library ends that server with a
hard kill, which leaves the file. Caused on the test machine on 2026-11-13 by a first draft of
`labs/13_01_04_mcp_client.py` with `keep_alive` left on.

Fix **(tested)**: delete the file; every MCP lab also deletes it at the end. A lab that should stop its server when
the call is done sets `"keep_alive": False` in the server's config, as lab 28.7 does, or closes the client the way
`close_mcp()` in `dataflow/mcp/bind.py` does.

### `LangChainBetaWarning: langchain.mcp is in beta` (labs 28.8 and 28.9)

```
LangChainBetaWarning: `langchain.mcp` is in beta. It is actively being worked on, so the API may change.
```

What it means: not an error. `MCPAdapter` arrived in LangChain 1.4 as a beta, and LangChain says so once per run.
The course pins the version its labs ran on (`constraints.txt`), so the lab you run is the one on screen.

Fix: none needed.

### `RuntimeError: Client failed to connect: fileno` from an MCP lab

```
io.UnsupportedOperation: fileno
RuntimeError: Client failed to connect: fileno
```

What it means: a stdio client hands the server its own stderr, and that has to be a real file handle. A Jupyter
kernel does not have one, which is why the stdio MCP labs carry a `no-twin` line and run from the terminal. Caused on
the test machine on 2026-11-13 under pytest's `capsys`, which replaces stderr the same way.

Fix **(tested)**: run the lab from the terminal, `python labs/<lab>.py`. In a test, use `capfd` instead of `capsys`.

## The LangGraph labs (Sections 9 to 11)

### `ValueError: Found edge ending at unknown node` (lab 10.3)

```
ValueError: Found edge ending at unknown node `replly`
```

What it means: an `add_edge` names a node that no `add_node` added, usually a typo. `compile()` checks that every
edge starts and ends at a node it knows, and stops before anything runs. Caused on the test machine on 2026-11-13 by
writing `builder.add_edge("lookup", "replly")` in `labs/06_01_03_build_triage_graph.py`.

Fix **(tested)**: spell the node the way its `add_node` names it. `print(list(graph.get_graph().nodes))` on a graph
that compiles lists the names. Note what compile does not check: delete the edge from the last node to `END` and the
graph still compiles and runs, and the drawing still shows the run ending, because a node with no way out simply ends
the run on this version (same lab, langgraph 1.2.11).

### `httpx.ConnectError` from a node test that was meant to need no model (lab 10.4)

```
FAIL test_classify_alone httpx.ConnectError: [WinError 10061] No connection could be made because the target machine actively refused it
```

What it means: the test called `classify` without `model=`, so `classify` asked `config` for the real model, and
nothing was listening on the model's port. Caused on
the test machine on 2026-11-13 by deleting `, model=FakeChatModel(route="policy")` from `test_classify_alone` in
`labs/06_01_04_invoke_and_test.py`, with `OLLAMA_BASE_URL` pointed at a closed port.

Fix **(tested)**: pass the scripted model, `classify(state, model=FakeChatModel(route="policy"))`. A node test that
needs a model always gets it injected, which is how it runs on a laptop with Ollama off and in CI. If the error comes
from a lab that should call your model, start Ollama (`ollama serve`, or the Ollama app).

### `KeyError` with a route name, raised during task `classify` (lab 11.2)

```
KeyError: 'billing'
During task with name 'classify' and id '...'
```

What it means: the routing function of an `add_conditional_edges` returned a label that its path map does not have.
`compile()` cannot know what your function will return, so the graph compiles and fails on the first ticket that
takes that label. Caused on the test machine on 2026-11-13 by making `route_after_classify` in
`labs/06_02_02_route_three_ways.py` return `"billing"`.

Fix **(tested)**: add the label to the path map, or end the router with a safe default that is in the map (the lab's
router sends any unknown label to `escalate`). Typing the router's return as `Literal[...]` lists the labels for the
reader and for the drawing.

### A tool cycle ends on a `tool` message with no answer (lab 11.4)

```
2 tool lookup_order {"found": true, "order_id": "DF-1002", ...}
message_count 3
last_is_answer False
```

What it means: the edge from the tools node back to the model node is missing, so the tool runs and the run ends
there, with nobody to read the result. No error is raised, and the drawing shows `tools --> __end__`. Caused on the
test machine on 2026-11-13 by deleting `builder.add_edge("tools", "agent")` in `labs/06_02_04_tool_cycle.py`.

Fix **(tested)**: put the edge back, `builder.add_edge("tools", "agent")`. If instead the run never ends and stops on
`GraphRecursionError: Recursion limit of 10 reached`, the model keeps calling a tool; that is the cap doing its job.

### The drawing shows `classify --> __end__` and the desks stand alone, yet the ticket still reaches a desk (lab 11.6)

```
	__start__ --> classify;
	classify --> __end__;
```

What it means: the node routes with `Command(goto=...)`, and nothing declares where it can go. A `Command` road is not
an edge you drew, so the drawing knows it only from the node's return type, `Command[Literal["orders_desk", ...]]`,
or from `destinations=` on `add_node`. Without either, the run still follows `goto` (the ticket in the capture
reached `orders_desk`), but the drawing shows none of the roads. Caused on the test machine on 2026-11-13 by changing
the return type of `classify_command` in `labs/06_02_06_command_vs_edge.py` to a plain `-> Command`.

Fix **(tested)**: declare the roads, in the return type as the lab does, or as
`add_node("classify", classify_command, destinations=("orders_desk", "policy_desk", "escalate_desk"))` as
`dataflow/graphs/v2_command.py` does. The drawing then shows three dotted roads out of `classify`.

## The LangGraph streaming labs (Section 15)

### `ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id` on a resume stream (lab 15.4)

```
run approve
ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id
```

What it means: the graph has a checkpointer, so every run needs a thread, and the resume stream was opened with no
config. The traceback points into the code that reads the stream (`for part in stream`), not the line that opened
it, because a stream starts only when it is read. Caused on the test machine on 2026-11-13 by deleting
`refund_thread, ` from the resume line of `full_run` in `labs/06_06_06_full_run.py`.

Fix **(tested)**: pass the same config the refund parked on, `graph.stream(Command(resume="approve"), refund_thread,
...)`. A config with a different `thread_id` does not raise: it starts that thread fresh and parks again, and the
approval is lost (lab 14.3).

### A parked run is shown as finished, with `reply None` (lab 15.3)

```
output_keys ['route', 'ticket']
interrupted False
done route refund reply None
status done
refunds_rows 0
thread_next ('refund',)
```

What it means: the code read `stream.output` without first asking `stream.interrupted`. On a parked run `output`
is the state so far (a route and no reply), so it looks like a finished run with no answer, while the thread is
still waiting at `refund`. Caused on the test machine on 2026-11-13 by changing `parked = stream.interrupted` to
`parked = False` in `labs/06_06_03_stream_events.py`.

Fix **(tested)**: check `stream.interrupted` before you read `output`; when it is True, show `stream.interrupts`
and wait for the person, then resume with `Command(resume=...)` on the same thread.

### A stream shows no tokens, only `values keys [...]` lines (lab 15.2)

```
values keys ['last_ticket', 'messages', 'ticket', 'turns']
node read_pref wrote []
node classify wrote ['route']
values keys ['last_ticket', 'messages', 'route', 'ticket', 'turns']
```

What it means: the stream was asked for `values` instead of `messages`. `values` sends the whole state after each
step that changed it; the model's tokens only come on `messages`. Nothing is wrong with the model. Caused on the
test machine on 2026-11-13 by changing `"messages"` to `"values"` in `watch` in `labs/06_06_02_stream.py`.

Fix **(tested)**: put `"messages"` in `stream_mode`, `stream_mode=["updates", "messages", "custom"]`.

### A streamed tool cycle prints no tool-call pieces, and `same_call False` (lab 15.2, second file)

```
pieces 0 text_tokens 0 quiet_chunks 0
call_from_pieces []
same_call False
```

What it means: the stream has no `messages` lane, so no chunk of the model's output arrives while it works; the
call is seen only in the agent's update once the step is over. Caused on the test machine on 2026-11-13 by
deleting `"messages"` from `stream_mode` in `labs/06_06_07_stream_the_tool_cycle.py`.

Fix **(tested)**: `stream_mode=["messages", "updates"]`. With qwen3:8b on Ollama the call then arrives as one
piece with the whole arguments; a provider that streams arguments sends the id and name first and the rest in pieces. Act on
the finished call either way.

## The MCP labs (Section 29)

### `ToolError: Unknown tool: 'refund'` over HTTP, though the server has a refund (lab 29.4)

```
read_only_clerk refund_refused ToolError Unknown tool: 'refund'
wire status 200
wire isError True
```

What it means: your token does not carry the scope the tool needs. On FastMCP 4.0.3 a tool whose scope the token
lacks is hidden: it is missing from the tool list and a call to it is answered as an unknown tool, with HTTP status
200 and `isError` true, not with a 403. The same rule hides a scoped tool from every client that has no token at all,
which is why the scopes live on the HTTP build only (`build_http_server` in `dataflow/mcp/http.py`); put
`require_scopes` on the stdio server and the refund disappears from the Section 28 labs. A scope required by the
whole server (`JWTVerifier(required_scopes=...)`) is different: a token without it is refused with 401
`invalid_token`, again not 403. Caused on the test machine on 2026-11-13 by lab 29.4's read-only clerk, and by a probe
with `required_scopes=["orders:read"]` and a token carrying only `orders:refund`.

Fix **(tested)**: mint the token with the scope the tool needs (`TOOL_SCOPES` names them), as the refund clerk's
token in lab 29.4 does.

### `MCPError: Server returned an error response` when a client connects with a token (lab 29.3)

```
other_service refused MCPError Server returned an error response
```

What it means: the server refused the token, and the reason is only in the server's own log, printed on stderr in a
box: `Bearer token rejected for client agent-desk: audience mismatch (got 'https://billing.dataflow.test/mcp',
expected 'http://127.0.0.1:50859/mcp')`. The audience a token names must be this server's full URL, port and `/mcp`
included. Caused on the test machine on 2026-11-13 by lab 29.3's token minted for the billing service.

Fix **(tested)**: mint the token with `audience=url`, where `url` is the address the server was started on
(`url_for(port)` in `dataflow/mcp/http.py`), as lab 29.3's second token does. If the log says the issuer or the
signature is wrong instead, the token came from a different key pair or issuer than the one `build_auth` was given.

### `httpx.ConnectError: [WinError 10061] ... actively refused it` just after starting an HTTP lab server

What it means: nothing listens on the address you called. `start_http(server)` with no port picks a free port of its
own, so a URL or a token audience you built from another port points at nothing. Caused on the test machine on
2026-11-13 by a probe that built its token audience from `free_port()` and then started the server without passing
that port.

Fix **(tested)**: pick the port once and pass it everywhere: `port = free_port()`, `url = url_for(port)`, the token's
audience, and `start_http(server, port)`, the order labs 29.3, 29.4 and 29.9 use.

### `400` with error `-32020`, `mcp-name header does not match the request body's 'name' parameter` (lab 29.2)

What it means: over Streamable HTTP the `Mcp-Method` and `Mcp-Name` headers must say what the body says, so a gateway
can route on them; the server refuses a request whose header disagrees. Caused on the test machine on 2026-11-13 by
lab 29.2's BREAK, `Mcp-Name` fixed to `lookup_order` while the body called `refund`. A missing `Mcp-Name` on a
`tools/call` is refused the same way.

Fix **(tested)**: build the headers from the body, as `mcp_headers` in `dataflow/mcp/http.py` does. A FastMCP or
`httpx`-based MCP client does this for you; it matters when you write requests by hand or put a proxy in front.

### `tests/test_lab_13_03_07.py` fails with `changed since it was approved` after you edit a tool

```
AssertionError: assert ['dataflow.lookup_order changed since it was approved'] == []
```

What it means: the allowlist is doing its job. `dataflow/mcp/allowlist.json` pins each tool of the dataflow and kb
servers by the SHA-256 of its name, description and input schema, and you changed one of the three in
`dataflow/mcp/server.py` or `dataflow/mcp/kb_server.py`. Caused on the test machine on 2026-11-13 by lab 29.7's
updated `lookup_order`, whose description gained one sentence.

Fix **(tested)**: read the new description first. Then pin it again from the repo root:

```
python -c "import json; from dataflow.mcp.allowlist import ALLOWLIST_PATH, approve, load_allowlist; from dataflow.mcp.bind import bind_mcp_tools, close_mcp; from dataflow.mcp.server import mcp; a = approve(load_allowlist(), 'dataflow', bind_mcp_tools(mcp)); ALLOWLIST_PATH.write_text(json.dumps(a, indent=2) + chr(10), encoding='utf-8'); close_mcp()"
```

### A `traceparent` you sent arrives as `None` in your own middleware (lab 29.9)

What it means: on FastMCP 4.0.3 `context.message.meta` (the tool call's `_meta`) is `None` inside `on_call_tool`
even when the client sent `meta={"traceparent": ...}`; the whole `_meta`, protocol keys included, is on the request
context instead. Caused on the test machine on 2026-11-13 by a probe middleware that read `context.message.meta` while its
client sent a traceparent.

Fix **(tested)**: read `context.fastmcp_context.request_context.meta`, as `request_meta()` in `dataflow/mcp/audit.py`
does.

## The LangGraph labs (Sections 12 and 13)

### `InvalidUpdateError: At key 'log': Can receive only one value per step` (lab 12.4)

```
langgraph.errors.InvalidUpdateError: At key 'log': Can receive only one value per step. Use an Annotated key to handle multiple values.
For troubleshooting, visit: https://docs.langchain.com/oss/python/langgraph/errors/INVALID_CONCURRENT_GRAPH_UPDATE
```

What it means: two nodes ran in the same step and both wrote the key named in the message, and that key has no
reducer, so it keeps one value and LangGraph will not pick which one. The traceback ends in
`langgraph/channels/last_value.py`: the key's channel is a `LastValue`. Caused on the test machine on 2026-11-13 by
changing `log: Annotated[list[str], operator.add]` to `log: list[str]` in `labs/06_03_04_plant_a_collision.py`.

Fix **(tested)**: give the key a reducer that says how two writes combine, `log: Annotated[list[str], operator.add]`,
and have each node return a list (`{"log": ["policy read"]}`). For a message list the reducer is `add_messages`.
`type(graph.channels["log"]).__name__` prints `BinaryOperatorAggregate` once the reducer is on.

### The conversation stays at one message, turn after turn (lab 12.3)

```
  count 1 newest human
  count 1 newest ai
  count 1 newest ai note
...
thread_count 1
```

What it means: no error is raised, but each write replaces the whole list. The `messages` key has no reducer, so the
agent's answer wipes the question, the note wipes the answer, and turn two wipes turn one. Caused on the test machine
on 2026-11-13 by changing `messages: Annotated[list, add_messages]` to `messages: list` in
`labs/06_03_03_add_messages_on_the_thread.py`.

Fix **(tested)**: `messages: Annotated[list, add_messages]`. Each node then returns only its new message and the
count grows 1, 2, 3, then 4, 5, 6 on turn two of the same thread.

### A resumed thread comes back empty: `saved turns None`, `rows_in_file 0`, `turns 1` (lab 13.2)

```
process 56884 saved turns None reply None
rows_in_file 0
turn 2 turns 1 reply ...
```

What it means: the second process asked the checkpointer for a thread id that has nothing saved under it, so it
started a new conversation. Nothing fails, and the reply can still look fine, because a follow-up ticket often names
its own order; the proof is `turns 1`. Caused on the test machine on 2026-11-13 by changing `thread = THREAD` in
`resume` to `{"configurable": {"thread_id": "lab-13-2-other"}}` in `labs/06_04_03_sqlite_kill_and_resume.py`, after
`--start` had saved turn one under `lab-13-2`.

Fix **(tested)**: resume with the exact thread id the first process used, on the same database file (the lab prints
the file on its `db` line, and `DATAFLOW_CHECKPOINTS_PATH` moves it). `SELECT COUNT(*) FROM checkpoints WHERE
thread_id = ?` on that file shows whether anything is saved for an id.

### A preference written on one thread is missing on the customer's next thread (lab 13.3)

```
thread lab-13-3-b customer C-2001 ticket Where is order DF-1001?
   read_pref {'preference': None}
   store ('customers', 'lab-13-3-a') preferences {'channel': 'email', 'stated': True}
```

What it means: the fact was written, but onto a shelf named after the thread, so only that thread would ever find it.
The store line shows the namespace the item really sits under. Caused on the test machine on 2026-11-13 by making
`owner` return `("customers", get_config()["configurable"]["thread_id"])` in `labs/06_04_05_store_facts.py`.

Fix **(tested)**: namespace a fact by its owner, `("customers", runtime.context.customer_id)`, and pass the customer
in the run's context, `context=DeskContext(customer_id="C-2001")`. Thread B then reads `{'channel': 'email', ...}`.
If a `search` seems to lose items, check its `limit`: it returns 10 unless you ask for more, and says nothing about
the rest (the same lab prints 10 of 12, then 12 with `limit=20`).

### A fork's reply is just the text you wrote, and the node you wanted never ran again (lab 13.5)

```
forked_from 1f1df790-5ebd-66b7-8006-7bd64d43a507 next ()
...
fork_reply The return window is 30 days and the lamp qualifies.
```

What it means: the fork started from a save point after the node had already run (`next ()`, the finished run), so
`update_state` wrote your value onto a finished notebook and `invoke(None, fork_config)` had nothing left to run.
Caused on the test machine on 2026-11-13 by changing the `before = ...` line of `fork_before` to
`before = history[0]` in `labs/06_06_05_fork.py`.

Fix **(tested)**: fork from the save point whose `next` is the node you want to run again,
`next(s for s in history if s.next == ("speak",))`. The fork's reply is then the model's new answer, and every old
save point reads back as it was. Replaying a point before a node that pauses runs the pause again: on the refund
desk the replay parks with the same question and the ledger keeps one row.
