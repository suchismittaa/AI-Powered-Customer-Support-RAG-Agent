"""
scripts/download_kaggle_data.py — Download real customer support datasets from Kaggle

HOW TO USE:
  1. Install Kaggle CLI:        pip install kaggle
  2. Get your Kaggle API key:   kaggle.com → Account → API → Create New Token
                                 This downloads kaggle.json
  3. Place kaggle.json at:      ~/.kaggle/kaggle.json   (Mac/Linux)
                                 C:\\Users\\YOU\\.kaggle\\kaggle.json  (Windows)
  4. Run this script:           python scripts/download_kaggle_data.py

This downloads and converts two real Kaggle customer support datasets into
text files compatible with the RAG ingestion pipeline.
"""

import os
import sys
import json
import csv
import subprocess
from pathlib import Path

OUTPUT_DIR = Path("data/support_docs")

DATASETS = [
    {
        "name": "Customer Support on Twitter",
        "slug": "thoughtvector/customer-support-on-twitter",
        "file": "twcs.csv",
        "output": "twitter_support_tickets.txt",
        "description": "Real customer support conversations from Twitter (2M+ tweets)",
    },
    {
        "name": "Customer Support Ticket Dataset",
        "slug": "suraj520/customer-support-ticket-dataset",
        "file": "customer_support_tickets.csv",
        "output": "customer_support_tickets.txt",
        "description": "8,469 support tickets with categories, priorities, and resolutions",
    },
]


def check_kaggle_installed() -> bool:
    """Check if the Kaggle CLI is installed and configured."""
    try:
        result = subprocess.run(["kaggle", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_kaggle_credentials() -> bool:
    """Check if Kaggle API credentials file exists."""
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    return kaggle_json.exists()


def download_dataset(slug: str, output_dir: Path) -> bool:
    """
    Download a Kaggle dataset to a local directory.

    Args:
        slug: Kaggle dataset slug (e.g., 'thoughtvector/customer-support-on-twitter')
        output_dir: Directory to download files into.

    Returns:
        True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ["kaggle", "datasets", "download", "-d", slug, "-p", str(output_dir), "--unzip"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False


def convert_twitter_support(csv_path: Path, output_path: Path, max_rows: int = 2000) -> int:
    """
    Convert the Twitter customer support CSV into a RAG-friendly text format.

    Args:
        csv_path: Path to the downloaded twcs.csv file.
        output_path: Path to write the converted text file.
        max_rows: Maximum number of conversation pairs to include.

    Returns:
        Number of conversation pairs written.
    """
    conversations = {}
    count = 0

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if count >= max_rows * 2:
                break
            # Group by conversation — match inbound (customer) with response (support)
            in_response_to = row.get("in_response_to_tweet_id", "")
            tweet_id = row.get("tweet_id", "")
            text = row.get("text", "").strip()
            author = row.get("author_id", "")

            if not text or not tweet_id:
                continue

            conversations[tweet_id] = {"author": author, "text": text, "response": ""}
            if in_response_to and in_response_to in conversations:
                conversations[in_response_to]["response"] = text

    with open(output_path, "w", encoding="utf-8") as out:
        out.write("REAL CUSTOMER SUPPORT CONVERSATIONS — TWITTER DATASET\n")
        out.write("Source: Kaggle — Customer Support on Twitter (thoughtvector)\n")
        out.write("=" * 70 + "\n\n")

        written = 0
        for tweet_id, data in conversations.items():
            if data["response"] and written < max_rows:
                out.write(f"CUSTOMER INQUIRY:\n{data['text']}\n\n")
                out.write(f"SUPPORT RESPONSE:\n{data['response']}\n\n")
                out.write("-" * 50 + "\n\n")
                written += 1

    return written


def convert_ticket_dataset(csv_path: Path, output_path: Path, max_rows: int = 1000) -> int:
    """
    Convert the customer support tickets CSV into a RAG-friendly text format.

    Args:
        csv_path: Path to the downloaded CSV file.
        output_path: Path to write the converted text file.
        max_rows: Maximum number of tickets to include.

    Returns:
        Number of tickets written.
    """
    count = 0
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        with open(output_path, "w", encoding="utf-8") as out:
            out.write("REAL CUSTOMER SUPPORT TICKETS — STRUCTURED DATASET\n")
            out.write("Source: Kaggle — Customer Support Ticket Dataset (suraj520)\n")
            out.write("=" * 70 + "\n\n")

            for row in reader:
                if count >= max_rows:
                    break

                out.write(f"TICKET #{count + 1}\n")
                for field in fieldnames:
                    val = row.get(field, "").strip()
                    if val:
                        out.write(f"{field.upper()}: {val}\n")
                out.write("\n" + "-" * 50 + "\n\n")
                count += 1

    return count


def main():
    """Main entry point — check prerequisites and download + convert datasets."""
    print("=" * 60)
    print("  Kaggle Dataset Downloader for RAG Knowledge Base")
    print("=" * 60)

    # Check prerequisites
    if not check_kaggle_installed():
        print("\n❌ Kaggle CLI not installed.")
        print("   Run: pip install kaggle")
        sys.exit(1)

    if not check_kaggle_credentials():
        print("\n❌ Kaggle credentials not found.")
        print("   1. Go to: https://www.kaggle.com/account")
        print("   2. Click 'Create New Token' under API section")
        print("   3. Save kaggle.json to: ~/.kaggle/kaggle.json")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    download_dir = Path("data/kaggle_raw")
    download_dir.mkdir(parents=True, exist_ok=True)

    print("\n✅ Prerequisites satisfied. Starting downloads...\n")

    for dataset in DATASETS:
        print(f"📥 Downloading: {dataset['name']}")
        print(f"   Slug: {dataset['slug']}")

        success = download_dataset(dataset["slug"], download_dir)
        if not success:
            print(f"   ⚠️  Skipping {dataset['name']} — download failed.")
            continue

        csv_path = download_dir / dataset["file"]
        if not csv_path.exists():
            # Try to find it
            found = list(download_dir.glob("*.csv"))
            if found:
                csv_path = found[0]
            else:
                print(f"   ⚠️  CSV file not found after download. Skipping.")
                continue

        output_path = OUTPUT_DIR / dataset["output"]
        print(f"   🔄 Converting to RAG format...")

        if "twitter" in dataset["output"]:
            count = convert_twitter_support(csv_path, output_path)
        else:
            count = convert_ticket_dataset(csv_path, output_path)

        print(f"   ✅ Written {count} entries → {output_path}")

    print("\n" + "=" * 60)
    print("  Done! Now run: python ingest.py")
    print("  to rebuild the knowledge base with real data.")
    print("=" * 60)


if __name__ == "__main__":
    main()
