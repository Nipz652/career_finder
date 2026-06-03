import sys
from pathlib import Path

# Add backend to path for proper imports
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from src.pipeline.ingest import ingest_all_mhtml
from src.pipeline.transform import process_all_html, load_all_jsons
from src.pipeline.tag import tag_data

PROJECT_ROOT = Path(__file__).parent.parent  # Career_Finder/
SOURCE_DIR = PROJECT_ROOT / "data/source"    # source directory for .mhtml files
HTML_DIR = PROJECT_ROOT / "data/raw"
JSON_DIR = PROJECT_ROOT / "data/processed"
DB_DIR = PROJECT_ROOT / "data"
DB_NAME = "jobs.db"

def run_tag():
    db_path = DB_DIR/DB_NAME
    tag_data(db_path)

def run_load():
    input_dir = JSON_DIR
    output_dir = DB_DIR
    load_all_jsons(input_dir, output_dir)

def run_process():
    input_dir = HTML_DIR
    output_dir = JSON_DIR
    process_all_html(input_dir, output_dir)

def run_ingest():
    input_dir = SOURCE_DIR
    output_dir = HTML_DIR
    ingest_all_mhtml(input_dir, output_dir)

def run_all():
    run_ingest()
    print()

    run_process()
    print()

    run_load()
    print()

    run_tag()
    
def main():
    if len(sys.argv) < 2:  # sys.argv is list of command-line arguments. For example, ["main.py", "ingest"]
        print("Usage: python test_pipeline.py [ingest|process|load|tag|all]")
        return

    command = sys.argv[1]

    if command == "ingest":
        run_ingest()
    elif command == "process":
        run_process()
    elif command == "load":
        run_load()
    elif command == "tag":
        run_tag()
    elif command == "all":
        run_all()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()