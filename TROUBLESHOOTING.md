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
OllamaSetup.exe from ollama.com/download), make sure it is running, then `ollama pull qwen3:8b` (5.2 GB).

### The model is not pulled

```
ollama._types.ResponseError: model 'not-pulled-model:latest' not found (status code: 404)
```

What it means: Ollama is running but does not have the model `config.py` asked for. Your error names your model.

Fix **(not tested here)**: `ollama pull <the model named in the error>`, for example `ollama pull qwen3:8b`. Check
what you have with `ollama list`.

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
`ollama list` answers with a `NAME    ID    SIZE    MODIFIED` header.

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
model's name, for example `ollama pull qwen3:8b`.

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
