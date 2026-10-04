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
