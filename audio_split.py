import subprocess
import json
from pathlib import Path

# Configuration
INPUT_FOLDER = "audio/output"
OUTPUT_FOLDER = "audio/output/whatsapp"
MAX_SIZE_MB = 15
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


def get_audio_duration(file_path):
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", str(file_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def split_audio(input_file, output_dir, max_size_bytes):
    """Split audio file into chunks of max_size_bytes."""
    file_size = input_file.stat().st_size
    stem = input_file.stem

    # File is already within limit
    if file_size <= max_size_bytes:
        print(f"  OK: {input_file.name} ({file_size / (1024*1024):.1f} MB) - within limit")
        return []

    # Get duration and calculate chunk duration based on proportional size
    duration = get_audio_duration(input_file)
    num_chunks = -(-file_size // max_size_bytes)  # ceil division
    chunk_duration = duration / num_chunks

    print(f"  Splitting: {input_file.name} ({file_size / (1024*1024):.1f} MB) -> {num_chunks} parts (~{chunk_duration:.0f}s each)")

    generated = []
    for i in range(num_chunks):
        start_time = i * chunk_duration
        part_num = i + 1
        output_file = output_dir / f"{stem}_{part_num}.mp3"

        if output_file.exists():
            print(f"    Skipped: {output_file.name} (already exists)")
            generated.append(output_file)
            continue

        cmd = [
            "ffmpeg", "-i", str(input_file),
            "-ss", str(start_time),
            "-t", str(chunk_duration),
            "-c", "copy",
            str(output_file), "-y"
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            actual_size = output_file.stat().st_size / (1024 * 1024)
            print(f"    Created: {output_file.name} ({actual_size:.1f} MB)")
            generated.append(output_file)
        except subprocess.CalledProcessError as e:
            print(f"    Error: {output_file.name} - {e.stderr.decode()[:100]}")

    return generated


def main():
    input_folder = Path(INPUT_FOLDER)
    output_folder = Path(OUTPUT_FOLDER)

    if not input_folder.exists():
        print(f"Input folder '{INPUT_FOLDER}' not found.")
        exit(1)

    output_folder.mkdir(parents=True, exist_ok=True)

    mp3_files = sorted(list(input_folder.glob("*.mp3")))

    if not mp3_files:
        print(f"No .mp3 files found in '{INPUT_FOLDER}'")
        exit(0)

    print(f"Found {len(mp3_files)} .mp3 files in '{INPUT_FOLDER}'")
    print(f"Max size per chunk: {MAX_SIZE_MB} MB")
    print(f"Output folder: '{OUTPUT_FOLDER}'\n")

    total_generated = []
    total_skipped = 0

    for mp3_file in mp3_files:
        file_size = mp3_file.stat().st_size

        if file_size <= MAX_SIZE_BYTES:
            # Small file: copy as-is (single part, no suffix needed)
            dest = output_folder / mp3_file.name
            if dest.exists():
                print(f"  Skipped: {mp3_file.name} (already in output)")
                total_skipped += 1
            else:
                # Copy without re-encoding
                cmd = ["ffmpeg", "-i", str(mp3_file), "-c", "copy", str(dest), "-y"]
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"  Copied: {mp3_file.name} ({file_size / (1024*1024):.1f} MB)")
                total_generated.append(dest)
        else:
            parts = split_audio(mp3_file, output_folder, MAX_SIZE_BYTES)
            total_generated.extend(parts)

    print(f"\nDone! Generated {len(total_generated)} files, skipped {total_skipped}.")


if __name__ == "__main__":
    main()
