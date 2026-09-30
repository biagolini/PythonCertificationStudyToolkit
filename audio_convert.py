import os
import sys
import select
import subprocess
import termios
import tty
from pathlib import Path
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config_loader import load_workspaces, get_default_index

# Load environment variables
load_dotenv()

# Configuration
INPUT_FOLDER = "audio/input"
OUTPUT_FOLDER = "audio/output"

# Workspace definitions come from config/workspaces.json (git-ignored), not
# hardcoded here.
WORKSPACES = load_workspaces()
DEFAULT_INDEX = get_default_index(WORKSPACES)


def select_workspace_with_countdown(timeout=5):
    """Show workspace selection with countdown. Default is selected if no input."""
    print("Selecione o workspace do Slack:")
    for i, ws in enumerate(WORKSPACES):
        marker = " [default]" if i == DEFAULT_INDEX else ""
        print(f"  {i + 1}. {ws['label']}{marker}")
    print()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)

        for remaining in range(timeout, 0, -1):
            msg = f"\rEnviando para '{WORKSPACES[DEFAULT_INDEX]['label']}' em {remaining}s (digite 1-{len(WORKSPACES)} para trocar): "
            sys.stdout.write(msg)
            sys.stdout.flush()

            ready, _, _ = select.select([sys.stdin], [], [], 1.0)
            if ready:
                char = sys.stdin.read(1)
                sys.stdout.write("\r" + " " * len(msg) + "\r")
                sys.stdout.flush()
                try:
                    choice = int(char) - 1
                    if 0 <= choice < len(WORKSPACES):
                        print(f"Selecionado: {WORKSPACES[choice]['label']}")
                        return choice
                    print("Opção inválida. Usando default.")
                    return DEFAULT_INDEX
                except ValueError:
                    print("Entrada inválida. Usando default.")
                    return DEFAULT_INDEX

        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        print(f"Timeout. Usando default: {WORKSPACES[DEFAULT_INDEX]['label']}")
        return DEFAULT_INDEX

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# Workspace selection with countdown
choice = select_workspace_with_countdown(timeout=5)
selected_workspace = WORKSPACES[choice]
slack_token = os.getenv(selected_workspace['token_env'])

if not slack_token:
    print(f"Token não encontrado para '{selected_workspace['label']}'. Verifique o arquivo .env (variável {selected_workspace['token_env']}).")
    exit(1)

print(f"\n[LOG] Workspace selecionado: {selected_workspace['label']}\n")

# Initialize Slack client
client = WebClient(token=slack_token)


# Get target user ID (handles both user tokens and bot tokens)
def get_target_user_id():
    try:
        response = client.auth_test()
        # If token is a bot token (xoxb-), auth_test returns the bot's user ID.
        # We need to find the actual human user to send DMs to.
        if response.get('bot_id'):
            try:
                users_response = client.users_list()
                for member in users_response['members']:
                    if (not member.get('is_bot', False)
                            and member['id'] != 'USLACKBOT'
                            and not member.get('deleted', False)):
                        return member['id']
            except SlackApiError:
                pass
            return response['user_id']
        else:
            return response['user_id']
    except SlackApiError as e:
        print(f"Error getting user ID: {e.response['error']}")
        exit(1)


MY_USER_ID = get_target_user_id()
print(f"[LOG] Target user ID: {MY_USER_ID}\n")

# Define paths
input_folder = Path(INPUT_FOLDER)
output_folder = Path(OUTPUT_FOLDER)

# Check if input folder exists
if not input_folder.exists():
    input_folder.mkdir(parents=True, exist_ok=True)
    print(f"A pasta '{INPUT_FOLDER}' não existia no diretório.")
    print(f"Ela foi criada. Por favor, adicione os arquivos de áudio (.m4a) dentro da pasta '{INPUT_FOLDER}' e execute o script novamente.")
    exit(0)

# Create output folder if it doesn't exist
output_folder.mkdir(parents=True, exist_ok=True)

# Find all .m4a files and sort alphabetically
m4a_files = sorted(list(input_folder.glob("*.m4a")))
generated_files = []

if not m4a_files:
    print("No .m4a files found")
else:
    print(f"Found {len(m4a_files)} .m4a files")

    for m4a_file in m4a_files:
        mp3_file = output_folder / f"{m4a_file.stem}.mp3"

        if mp3_file.exists():
            print(f"Skipped: {mp3_file.name} (already exists)")
            continue

        print(f"Converting: {m4a_file.name} -> {mp3_file.name}")

        cmd = ["ffmpeg", "-i", str(m4a_file), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_file), "-y"]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✓ Converted: {mp3_file.name}")
            generated_files.append(mp3_file.stem)

            # Send to Slack
            try:
                upload_response = client.files_upload_v2(
                    file_uploads=[
                        {"file": str(mp3_file), "title": mp3_file.stem}
                    ]
                )

                files = upload_response.get('files', [])
                if files:
                    audio_link = files[0].get('permalink', '')
                    client.chat_postMessage(
                        channel=MY_USER_ID,
                        text=f"{mp3_file.stem}\n\n{audio_link}"
                    )
                    print(f"✓ Sent to Slack: {mp3_file.name}")
                else:
                    print(f"✗ Could not get file link")

            except SlackApiError as e:
                print(f"✗ Error sending to Slack: {e.response['error']}")

        except subprocess.CalledProcessError as e:
            print(f"✗ Error converting {m4a_file.name}")

print("Conversion completed!")

if generated_files:
    print(f"\nGenerated files:")
    for file in generated_files:
        print(file)
