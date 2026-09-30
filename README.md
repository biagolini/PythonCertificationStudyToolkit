# Certification Study Toolkit

**Author:** Carlos Biagolini-Jr.

**LinkedIn:** [https://www.linkedin.com/in/biagolini/](https://www.linkedin.com/in/biagolini/)

**Medium:** [https://medium.com/@biagolini](https://medium.com/@biagolini)

## Overview

A small toolkit of Python scripts to support studying for certification exams. The scripts are meant to be reused across separate certification-study projects, so you can keep a single copy of the code and link it into each project (see "Reuse across projects" below).

The core utility packages saved practice-exam folders into per-set `.zip` archives, which makes it easy to back up or share study material. The toolkit also bundles a set of Slack helpers that are handy when you distribute study audio and manage content across Slack workspaces: convert audio files and upload them to Slack, split large audio files for easier sharing, and bulk-delete your own messages, all while letting you pick which workspace to act on.

The Slack helpers read workspace definitions (labels and which environment variable holds each token) from an external JSON file that is not tracked by Git, so no workspace-specific data is hardcoded in the scripts. Tokens are read from environment variables, never stored in the repository. You can register as many workspaces as you like: Workspace 1, Workspace 2, Workspace 3, and so on.

## Scripts

| Script | What it does |
|---|---|
| `zip_practice_exams.py` | Packages saved practice-exam folders into per-set `.zip` archives (no Slack, no external dependencies). |
| `audio_convert.py` | Converts `.m4a` files to `.mp3` (via FFmpeg) and uploads each one to the selected Slack workspace. |
| `audio_split.py` | Splits `.mp3` files larger than a size limit into smaller parts (useful for messaging apps). |
| `delete_messages.py` | Lists and deletes your own messages in the selected Slack workspace, with an interactive confirmation. |

## Prerequisites

- Python 3.12 installed
- The practice-exam packager (`zip_practice_exams.py`) uses the standard library only, so it has no extra prerequisites.
- The Slack helpers additionally require:
  - FFmpeg installed (required by `audio_convert.py` and `audio_split.py`)
    - macOS: `brew install ffmpeg`
    - Ubuntu/Debian: `sudo apt install ffmpeg`
  - A Slack app with a user token (`xoxp-...`) per workspace you want to use

### Required Slack scopes

The Slack helper scripts use user token scopes. For the full feature set, add:

- `chat:write` (send and delete messages)
- `files:write` (upload files)
- `im:read` (locate the target conversation)
- `im:history` (read the conversation history, required to delete messages)
- `users:read` (used when resolving the target user)

After adding scopes, reinstall the app to the workspace and copy the new user token.

## Setup

1. Clone this repository:

```bash
git clone https://github.com/biagolini/PythonCertificationStudyToolkit.git
cd PythonCertificationStudyToolkit
```

2. Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

> Steps 4 and 5 configure the Slack helpers. If you only need the practice-exam packager (`zip_practice_exams.py`), you can stop here.

4. Configure your workspaces. Copy the example and edit it with your labels and the environment variable names that hold each token:

```bash
mkdir -p config
cp config-example/workspaces.json config/workspaces.json
```

Edit `config/workspaces.json`:

```json
{
  "workspaces": [
    { "label": "Workspace 1", "token_env": "WORKSPACE_1_TOKEN", "default": true },
    { "label": "Workspace 2", "token_env": "WORKSPACE_2_TOKEN" }
  ]
}
```

Add as many workspaces as you need (Workspace 3, Workspace 4, and so on), each with its own `token_env`.

5. Create your `.env` with the actual tokens (the variable names must match `token_env` above):

```bash
cp .env.example .env
```

Edit `.env`:

```
WORKSPACE_1_TOKEN="xoxp-your-token-for-workspace-1"
WORKSPACE_2_TOKEN="xoxp-your-token-for-workspace-2"
```

Both `.env` and `config/` are git-ignored, so your tokens and workspace labels stay out of version control.

## Reuse across projects (symbolic link)

If you keep several separate project folders and want to reuse this toolkit in each of them without copying the code, create a symbolic link that points to your local clone of this repository. You edit the code in one place, and every project sees the change.

Clone the repository once to a central location, then link it from any project:

```bash
# 1. Clone the toolkit once (adjust the destination path)
git clone https://github.com/biagolini/PythonCertificationStudyToolkit.git /path/to/PythonCertificationStudyToolkit

# 2. From inside any project that should reuse it, create the link
cd /path/to/your/project
ln -s /path/to/PythonCertificationStudyToolkit code
```

You can now run the scripts through the link, for example:

```bash
python code/zip_practice_exams.py
```

Notes:

- Run the scripts from your project folder. Working files such as `audio/input`, `audio/output`, and `practice_exams/` are created or read relative to where you run the command, so each project keeps its own data.
- Keep the `.env` and `config/workspaces.json` inside the toolkit clone (they are git-ignored there), or provide a per-project copy if different projects need different tokens.
- On macOS/Linux `ln -s` works out of the box. On Windows, use `mklink /D code C:\path\to\PythonCertificationStudyToolkit` from an elevated prompt, or enable Developer Mode.

## Usage

### Package practice exams

Package practice-exam folders into per-set zip archives:

```bash
python zip_practice_exams.py
```

This script is independent of Slack and has no external dependencies (standard library only). It expects to run from a project that reuses this toolkit through the `code/` symbolic link (see "Reuse across projects" above), with a sibling `practice_exams/` folder next to it:

```
<Project>/
├── code/                      # symlink to this toolkit
└── practice_exams/
    └── <Instructor>/
        └── <Set>/
            ├── page.html
            └── page_files/    # assets saved with the page
```

Run it from the project root so the relative path resolves correctly:

```bash
python code/zip_practice_exams.py
```

A "set" is any folder that contains at least one `.html` or `.md` file. For each valid set the script writes `practice_exams/00_zip/<Instructor>/<Set>.zip`. The `00_zip` output folder is excluded from the instructor scan. The script is idempotent: sets already zipped are skipped, so you can safely re-run it after adding new exams.

### Slack helpers

Convert audio and send to Slack:

```bash
python audio_convert.py
```

Split large audio files:

```bash
python audio_split.py
```

Delete your own messages in the selected workspace:

```bash
python delete_messages.py            # asks which workspace, deletes messages only
python delete_messages.py --files    # also deletes the uploaded files
python delete_messages.py --all      # runs over every workspace, one confirmation each
```

`delete_messages.py` first shows how many messages would be deleted, then asks you to press `y`/`Y` within 15 seconds. Any other key, or a timeout, cancels the operation. Deletion is permanent and cannot be undone.

## Project Structure

```
.
├── zip_practice_exams.py      # Package practice-exam folders into per-set zip archives
├── audio_convert.py           # M4A -> MP3, upload to the selected Slack workspace
├── audio_split.py             # Split large MP3 files into parts
├── delete_messages.py         # Delete your own messages in the selected Slack workspace
├── config_loader.py           # Loads workspaces from config/workspaces.json
├── config-example/
│   └── workspaces.json        # Versioned template (placeholders)
├── config/                    # Real workspaces.json (git-ignored)
├── .env.example               # Template for tokens
├── .gitignore
├── requirements.txt
├── LICENSE
└── README.md
```

## License

This project is open source and available under the [MIT License](LICENSE).
