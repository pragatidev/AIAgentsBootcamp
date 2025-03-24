# AI Agents Bootcamp: Build and Deploy Workflow Automation

Welcome to the official course repository! This guide will help you get started with setting up your development environment in **Visual Studio Code (VS Code)**.

## ✅ Project Structure

```
AI-Agents-Bootcamp/
├── .vscode/
│   ├── extensions.json
│   └── settings.json
├── Section_1_Introduction/
│   └── section_1_intro_ai_agents.ipynb
├── Section_2_Setup/
│   ├── Lecture_1_Setup_Env.ipynb
│   ├── Lecture_2_Intro_LangChain.ipynb
│   ├── Lecture_4_GPT_Setup.ipynb
│   └── Lecture_5_First_Agent_Workflow.ipynb
├── .env
├── .gitignore
├── README.md
└── requirements.txt
```

## 🚀 Open the Project in VS Code

1. Launch **VS Code**.
2. Click on `File` > `Open Folder...` and select the root folder of this project (`AI-Agents-Bootcamp/`).
3. VS Code will detect the `.vscode/` folder and automatically recommend the extensions listed.

## 🧩 Recommended Extensions (Auto-Installed via VS Code)

These are specified in `.vscode/extensions.json`:

- **ms-python.python** – Python support in VS Code.
- **ms-toolsai.jupyter** – Jupyter Notebooks support.
- **ms-python.vscode-pylance** – Type checking and IntelliSense.
- **donjayamanne.python-environment-manager** – Easily switch between virtual environments.
- **dotenv.dotenv-vscode** – Read .env files for environment variable support.

To install manually, just hit "Install All" when VS Code prompts you.

## 🐍 Using Your Virtual Environment

1. Open a terminal inside VS Code (`Terminal > New Terminal`).
2. If not already activated, activate your virtual environment:
   - Windows: `myenv\Scripts\activate`
   - macOS/Linux: `source myenv/bin/activate`

VS Code will also prompt you to select the interpreter (`Ctrl+Shift+P > Python: Select Interpreter`). Choose the one inside your `.venv` folder.

## 📄 .env File

Your `.env` file should look like this:

```
OPENAI_API_KEY=your_openai_key_here
```

Keep this file safe and never share your API key publicly.

---

Ready to build your first agent? Start with the notebooks in the `notebooks/` folder!
