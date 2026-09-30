import os
import sys
import time
import select
import termios
import tty
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config_loader import load_workspaces, get_default_index

# Load environment variables
load_dotenv()

# Workspace definitions come from config/workspaces.json (git-ignored), not
# hardcoded here.
WORKSPACES = load_workspaces()
DEFAULT_INDEX = get_default_index(WORKSPACES)

# Also delete uploaded files (not just the text messages) when possible.
DELETE_FILES = "--files" in sys.argv


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
            msg = f"\rUsando '{WORKSPACES[DEFAULT_INDEX]['label']}' em {remaining}s (digite 1-{len(WORKSPACES)} para trocar): "
            sys.stdout.write(msg)
            sys.stdout.flush()

            ready, _, _ = select.select([sys.stdin], [], [], 1.0)
            if ready:
                char = sys.stdin.read(1)
                sys.stdout.write("\r" + " " * len(msg) + "\r")
                sys.stdout.flush()
                try:
                    idx = int(char) - 1
                    if 0 <= idx < len(WORKSPACES):
                        print(f"Selecionado: {WORKSPACES[idx]['label']}")
                        return idx
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


def get_own_identity(client):
    """Return (own_user_id, dm_channel_id) for the token owner's own direct-message conversation."""
    try:
        auth = client.auth_test()
    except SlackApiError as e:
        print(f"Erro no auth_test: {e.response['error']}")
        sys.exit(1)

    own_user_id = auth["user_id"]

    # Find the token owner's own direct-message conversation via conversations.list
    # (needs only im:read), avoiding conversations.open which requires im:write.
    dm_channel_id = None
    cursor = None
    try:
        while True:
            resp = client.conversations_list(
                types="im", limit=200, cursor=cursor
            )
            for ch in resp.get("channels", []):
                if ch.get("user") == own_user_id:
                    dm_channel_id = ch["id"]
                    break
            if dm_channel_id:
                break
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError as e:
        print(f"Erro ao listar DMs: {e.response['error']}")
        sys.exit(1)

    if not dm_channel_id:
        print("Nenhuma DM consigo mesmo encontrada (nada a apagar).")
        return own_user_id, None

    return own_user_id, dm_channel_id


def fetch_all_messages(client, channel_id):
    """Get every message in the conversation, handling pagination."""
    messages = []
    cursor = None

    while True:
        try:
            resp = client.conversations_history(
                channel=channel_id,
                limit=200,
                cursor=cursor,
            )
        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 2))
                print(f"  Rate limited no history. Aguardando {retry_after}s...")
                time.sleep(retry_after)
                continue
            print(f"Erro ao ler o histórico: {e.response['error']}")
            break

        messages.extend(resp.get("messages", []))

        if resp.get("has_more"):
            cursor = resp["response_metadata"]["next_cursor"]
        else:
            break

    return messages


def delete_message(client, channel_id, ts):
    """Delete a single message, retrying on rate limit. Returns True on success."""
    while True:
        try:
            client.chat_delete(channel=channel_id, ts=ts)
            return True
        except SlackApiError as e:
            err = e.response["error"]
            if err == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 2))
                print(f"  Rate limited no delete. Aguardando {retry_after}s...")
                time.sleep(retry_after)
                continue
            print(f"  ✗ Falha ao deletar ts={ts}: {err}")
            return False


def delete_file(client, file_id):
    """Delete an uploaded file, retrying on rate limit. Returns True on success."""
    while True:
        try:
            client.files_delete(file=file_id)
            return True
        except SlackApiError as e:
            err = e.response["error"]
            if err == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", 2))
                print(f"  Rate limited no files.delete. Aguardando {retry_after}s...")
                time.sleep(retry_after)
                continue
            print(f"  ✗ Falha ao deletar arquivo {file_id}: {err}")
            return False


def confirm_deletion(count, timeout=15):
    """Ask for y/Y within `timeout` seconds. Returns True only if confirmed.

    Any other key, invalid input, or timeout cancels the operation.
    """
    if count == 0:
        print("Nenhuma mensagem para apagar.")
        return False

    print(f"\n>>> {count} mensagens serão APAGADAS permanentemente (irreversível).")

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)

        for remaining in range(timeout, 0, -1):
            msg = f"\rDigite 'y' para confirmar em {remaining:2d}s (qualquer outra tecla ou timeout cancela): "
            sys.stdout.write(msg)
            sys.stdout.flush()

            ready, _, _ = select.select([sys.stdin], [], [], 1.0)
            if ready:
                char = sys.stdin.read(1)
                sys.stdout.write("\r" + " " * len(msg) + "\r")
                sys.stdout.flush()
                if char in ("y", "Y"):
                    print("Confirmado. Iniciando deleção...")
                    return True
                print("Operação cancelada (tecla diferente de 'y').")
                return False

        sys.stdout.write("\r" + " " * 90 + "\r")
        sys.stdout.flush()
        print("Tempo esgotado. Operação cancelada.")
        return False

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def process_workspace(ws):
    token = os.getenv(ws["token_env"])
    print("\n" + "=" * 60)
    print(f"Workspace: {ws['label']}")
    print("=" * 60)

    if not token:
        print(f"Token '{ws['token_env']}' não encontrado no .env. Pulando.")
        return

    client = WebClient(token=token)
    own_user_id, dm_channel_id = get_own_identity(client)
    if dm_channel_id is None:
        return
    print(f"[LOG] user_id={own_user_id} dm_channel={dm_channel_id}")

    messages = fetch_all_messages(client, dm_channel_id)
    print(f"[LOG] {len(messages)} mensagens encontradas na conversa.")

    # Only delete messages authored by the token owner. chat.delete cannot
    # remove messages posted by others with a user token.
    own_messages = [m for m in messages if m.get("user") == own_user_id]
    print(f"[LOG] {len(own_messages)} são suas (deletáveis).")

    # Collect uploaded files referenced by those messages (optional deletion).
    file_ids = []
    for m in own_messages:
        for f in m.get("files", []) or []:
            if f.get("id"):
                file_ids.append(f["id"])

    # Show the count and ask for confirmation (y/Y within 15s).
    print(f"\nResumo para '{ws['label']}':")
    print(f"  - {len(own_messages)} mensagens")
    if DELETE_FILES:
        print(f"  - {len(file_ids)} arquivos")

    if not confirm_deletion(len(own_messages), timeout=15):
        return

    print(f"\n[EXECUTANDO] Deletando {len(own_messages)} mensagens...")
    deleted = 0
    for m in own_messages:
        ts = m.get("ts")
        if ts and delete_message(client, dm_channel_id, ts):
            deleted += 1
        # chat.delete is Tier 3 (~50/min). A small pause avoids hammering it.
        time.sleep(1.1)
    print(f"✓ {deleted}/{len(own_messages)} mensagens deletadas.")

    if DELETE_FILES and file_ids:
        print(f"\n[EXECUTANDO] Deletando {len(file_ids)} arquivos...")
        deleted_files = 0
        for fid in file_ids:
            if delete_file(client, fid):
                deleted_files += 1
            time.sleep(1.1)
        print(f"✓ {deleted_files}/{len(file_ids)} arquivos deletados.")


def main():
    # By default the script asks which workspace to use, like audio_convert.py.
    # Pass --all to run over every workspace in one go.
    if "--all" in sys.argv:
        for ws in WORKSPACES:
            process_workspace(ws)
    else:
        idx = select_workspace_with_countdown(timeout=5)
        process_workspace(WORKSPACES[idx])

    print("\nConcluído.")


if __name__ == "__main__":
    main()
