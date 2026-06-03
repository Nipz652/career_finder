from email import message_from_binary_file # parses a binary file into an email/MIME message object, because .mhtml files are structured like MIME email messages
from pathlib import Path # Path libraries automatically use the correct separators for the system they are running on
import quopri # decodes "quoted-printable" encoding, which is commonly used in MHTML files to encode special characters and binary data within the HTML content

def ingest_all_mhtml(input_dir, output_dir):
    """
    reads .mhtml files from input_dir
    writes extracted .html files into output_dir
    """
    print("Start ingestion...\n")

    # Turns folder strings into Path objects
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # Create output directory if missing
    # parents=True allows creation of any necessary parent directories, exist_ok=True prevents crashing if the directory already exists
    output_path.mkdir(parents=True, exist_ok=True)

    # Handle missing source directory
    if not input_path.exists():
        print(f"⚠️ Source directory does not exist: {input_path}")
        return # Early exit if source directory is missing

    # List all .mhtml files in the source directory
    mhtml_files = list(input_path.glob("*.mhtml")) # glob() finds all the pathnames matching the specified pattern, all files with the .mhtml extension in the input directory

    # Handle empty source directory
    if not mhtml_files:
        print("⚠️ No MHTML files found.")
        return

    # Tracks statistics
    total = len(mhtml_files)
    extracted = 0
    failed = 0

    for file_path in mhtml_files:
        try:    # prevent crashing, if one file fails, the rest still continue
            with open(file_path, "rb") as file: # rb = read binary, opens the .mhtml file in binary mode, because MHTML contains encoded byte data
                msg = message_from_binary_file(file)    # converts the binary file into a message object 
            html_content = None

            # Loops through every part of the MHTML file / multipart message
            for part in msg.walk(): 
                content_type = part.get_content_type()  # example: "text/html", "image/png", "text/css", etc.

                if content_type == "text/html":
                    payload = part.get_payload(decode=True) # decodes the payload of the message part, which is the actual content of that part

                    if payload:
                        # Decode quoted printable, example: =3Chtml=3E becomes <html>
                        html_content = quopri.decodestring(payload).decode(
                            "utf-8",
                            errors="ignore"
                        )   # Converts bytes into a Python string
                        break

            # Handle case where no HTML part was found
            if not html_content:
                print(f"⚠️ No HTML content found in: {file_path.name}")
                failed += 1
                continue    # skips to the next file

            output_file = output_path / f"{file_path.stem}.html"    # file_path.stem gives the filename without the extension

            # Open output file for writing text
            with open(output_file, "w", encoding="utf-8") as out_file:
                out_file.write(html_content) # writes the extracted HTML content

            print(f"✅ Extracted: {file_path.name}")
            extracted += 1

        except Exception as error:
            print(f"❌ Failed: {file_path.name} | Error: {error}")
            failed += 1

    print("\n📊 Ingestion Summary:")
    print(f"Total: {total} | Extracted: {extracted} | Failed: {failed}")