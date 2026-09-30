#!/usr/bin/env python3
"""
zip_practice_exams.py

Walks the '../practice_exams' folder (relative to this script), where each
subfolder is named after a practice-exam instructor and, inside it, holds the
sets of each practice exam.

A valid "set" is a folder that contains at least one .html file OR at least one
.md (markdown) file. HTML sets typically also carry an assets folder (named
'<name>_files', produced when saving a web page), while markdown sets may hold
only the .md file. For each valid set, the script creates a .zip with the entire
folder contents and writes it to '../practice_exams/00_zip/<Instructor>/<Set>.zip'.

The script is idempotent: sets that are already zipped (existing .zip) are
skipped.
"""

import sys
import zipfile
from pathlib import Path

# Source folder: goes up one level (code -> project root) and into
# 'practice_exams'. The script lives in a shared toolkit that is symlinked as
# 'code/' inside each certification-study project, so resolving the parent of
# the symlinked location points back into the project, not into the toolkit
# clone.
#
# Expected structure:
#   <Project>/
#   ├── code/                (symlink to this toolkit, where this script lives)
#   └── practice_exams/
#       └── <Instructor>/
#           └── <Set>/
#               ├── page.html
#               └── page_files/   (assets)
SCRIPT_DIR = Path(__file__).parent
SOURCE_DIR = (SCRIPT_DIR.parent / "practice_exams").resolve()

# Output folder: lives INSIDE 'practice_exams', in a '00_zip' subfolder. The
# '00_' prefix keeps the folder at the top of the listing and is used to
# exclude it from the instructor scan (it is not an instructor).
OUTPUT_DIR_NAME = "00_zip"
OUTPUT_DIR = (SOURCE_DIR / OUTPUT_DIR_NAME).resolve()


def is_valid_set(set_dir: Path) -> bool:
    """A set is valid when it has at least one .html OR at least one .md file."""
    if not set_dir.is_dir():
        return False
    files = [child for child in set_dir.iterdir() if child.is_file()]
    has_html = any(child.suffix.lower() == ".html" for child in files)
    has_markdown = any(child.suffix.lower() == ".md" for child in files)
    return has_html or has_markdown


def zip_set(set_dir: Path, zip_path: Path) -> int:
    """Zip the entire contents of set_dir into zip_path. Returns the file count."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(set_dir.rglob("*")):
            if item.is_file():
                # arcname keeps the internal structure rooted at the set name
                arcname = item.relative_to(set_dir.parent)
                zf.write(item, arcname)
                file_count += 1
    return file_count


def main() -> None:
    print(f"[INFO] Source folder: {SOURCE_DIR}")
    print(f"[INFO] Output folder: {OUTPUT_DIR}\n")

    if not SOURCE_DIR.is_dir():
        print(f"[ERROR] Source folder not found: {SOURCE_DIR}")
        sys.exit(1)

    total_zipped = 0
    total_skipped = 0
    total_sets = 0

    # Each subfolder of 'practice_exams' is an instructor (except the output folder itself).
    for instructor_dir in sorted(p for p in SOURCE_DIR.iterdir() if p.is_dir()):
        if instructor_dir.name == OUTPUT_DIR_NAME:
            continue
        instructor_name = instructor_dir.name
        print(f"[INSTRUCTOR] {instructor_name}")

        # Each subfolder of the instructor is a candidate set.
        for set_dir in sorted(p for p in instructor_dir.iterdir() if p.is_dir()):
            if not is_valid_set(set_dir):
                print(f"  - Skipped (no .html or .md file): {set_dir.name}")
                continue

            total_sets += 1
            zip_path = OUTPUT_DIR / instructor_name / f"{set_dir.name}.zip"

            if zip_path.exists():
                print(f"  - Already exists, skipping: {zip_path.relative_to(OUTPUT_DIR)}")
                total_skipped += 1
                continue

            count = zip_set(set_dir, zip_path)
            size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"  Done: {set_dir.name} -> {zip_path.relative_to(OUTPUT_DIR)} ({count} files, {size_mb:.1f} MB)")
            total_zipped += 1

        print()

    print(f"[INFO] Finished. Valid sets: {total_sets} | zipped now: {total_zipped} | already present: {total_skipped}")


if __name__ == "__main__":
    main()
