from pathlib import Path
from bs4 import BeautifulSoup   # to parse HTML and XML documents. It creates a parse tree that can be used to extract data from HTML, don't need to manually parse strings
from pydantic import BaseModel, ValidationError # BaseModel: schema definition and data validation, ValidationError: catch invalid structured data
import json     # to read and write JSON files
import sqlite3

# Defines the structure of data
class JobListing(BaseModel):
    source_id: str
    job_title: str
    company: str
    description: str

def clean_text(element):
    """
    Cleans text by extracting it from the HTML element, removing extra whitespace
    """
    if not element:
        return ""   # Handle None values

    return element.get_text(separator=" ", strip=True) # extracts all the text from the HTML element, separator=" " ensures that text from different tags is separated by a space, strip=True removes leading and trailing whitespace

def extract_source_id(soup):
    """
    Extracts source_id from the og:url meta tag
    """
    og_url = soup.find("meta", property="og:url")   # looks for tags like <meta property="og:url" content="...">

    if not og_url:
        return ""  # Handle missing meta tag

    url = og_url.get("content", "") # gets the content (url)

    if not url:
        return ""   # Handle missing content

    return url.rstrip("/").split("/")[-1]   # removes trailing slash, splits the URL by slashes, and takes the last item as the source_id

def process_all_html(input_dir, output_dir): 
    """
    Reads HTML files and converts them into structured JSON
    """
    print("Start processing...\n")

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # Create silver directory if missing
    output_path.mkdir(parents=True, exist_ok=True)

    # Handle missing directory
    if not input_path.exists():
        print(f"⚠️ Input directory does not exist: {input_path}")
        return

    # get all extracted HTML documents
    html_files = list(input_path.glob("*.html"))

    # Handle empty directory
    if not html_files:
        print("⚠️ No HTML files found.")
        return

    total = len(html_files)
    processed = 0
    skipped = 0

    for file_path in html_files:
        try:
            with open(file_path, "r", encoding="utf-8") as file:    # opens the HTML file to read
                soup = BeautifulSoup(file, "html.parser")   # converts raw HTML into a searchable tree

            source_id = extract_source_id(soup)

            title_element = soup.find(attrs={"data-automation": "job-detail-title"})
            company_element = soup.find(attrs={"data-automation": "advertiser-name"})
            description_element = soup.find(attrs={"data-automation": "jobAdDetails"})

            # Converts HTML elements into normalized strings
            job_title = clean_text(title_element)
            company = clean_text(company_element)
            description = clean_text(description_element)

            # Check validation
            missing_fields = []

            if not source_id:
                missing_fields.append("source_id")

            if not job_title:
                missing_fields.append("job_title")

            if not company:
                missing_fields.append("company")

            if not description:
                missing_fields.append("description")

            if missing_fields:
                print(
                    f"⚠️ Missing {', '.join(missing_fields)} in: {file_path.name}"
                )
                skipped += 1
                continue    # skip processing if any required field is missing

            # Pydantic validation, verify fields exist, correct types
            job_listing = JobListing(
                source_id=source_id,
                job_title=job_title,
                company=company,
                description=description,
            )

            output_file = output_path / f"{file_path.stem}.json"  # file_path.stem gives the filename without the extension

            with open(output_file, "w", encoding="utf-8") as json_file:
                json.dump(
                    job_listing.model_dump(),
                    json_file,
                    indent=2,
                    ensure_ascii=False,
                )  # model_dump() converts Pydantic model into a dictionary, which can then be serialized into JSON format

            print(f"✅ Processed: {file_path.name}")
            processed += 1

        # Validation errors from Pydantic
        except ValidationError as error:
            print(f"❌ Validation failed: {file_path.name}")
            print(error)
            skipped += 1

        # Other unexpected errors
        except Exception as error:
            print(f"❌ Failed: {file_path.name} | Error: {error}")
            skipped += 1

    print("\n📊 Processing Summary:")
    print(f"Total: {total} | Processed: {processed} | Skipped: {skipped}")

def create_table(cursor):
    """
    Creates the jobs table if it doesn't exist
    """
    cursor.execute(     # Sends SQL command to SQLite
        """
        CREATE TABLE IF NOT EXISTS jobs (
            source_id TEXT PRIMARY KEY,
            job_title TEXT NOT NULL,
            company TEXT NOT NULL,
            description TEXT NOT NULL,
            tech_stack TEXT 
        )
        """
    ) # prevents crashes if DB already exists

def load_all_jsons(input_dir, output_dir):
    """
    Reads JSON records and inserts into DB
    """
    print("Start database load...\n")

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # Create gold directory if missing
    output_path.mkdir(parents=True, exist_ok=True)

    # Handle missing silver directory
    if not input_path.exists():
        print(f"⚠️ Input directory does not exist: {input_path}")
        return

    json_files = list(input_path.glob("*.json"))    # get all processed JSON files

    # Handle empty directory, stop if no JSON files to load
    if not json_files:
        print("⚠️ No JSON files found.")
        return

    db_path = output_path / "jobs.db" # database file will be created in the gold directory

    connection = sqlite3.connect(db_path)   # opens/create SQLite database
    cursor = connection.cursor()    # cursor executes SQL commands

    create_table(cursor)

    total = len(json_files)
    inserted = 0
    skipped = 0

    # Iterates through each JSON file and attempts to insert into the database
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)  # load JSON file into a Python dictionary

            cursor.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    source_id,
                    job_title,
                    company,
                    description,
                    tech_stack
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    data["source_id"],
                    data["job_title"],
                    data["company"],
                    data["description"],
                    None,
                ),
            ) # skip insertion if duplicate source_id exists

            # rowcount = 1 means inserted, rowcount = 0 means ignore duplicate
            if cursor.rowcount == 1:
                print(f"✅ Inserted: {file_path.name}")
                inserted += 1
            else:
                print(f"⏭️ Skipped (duplicate): {file_path.name}")
                skipped += 1

        except Exception as error:
            print(f"❌ Failed: {file_path.name} | Error: {error}")

    connection.commit()  # saves changes to the database
    connection.close()  # closes the database connection

    print("\nDatabase Load Summary:")
    print(f"Total: {total} | Inserted: {inserted} | Skipped: {skipped}")