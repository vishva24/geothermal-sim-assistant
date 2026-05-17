"""Upload existing eval_report.json and eval_chart.png to S3."""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BENCHMARK_DIR = Path(__file__).parent
run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
FILES = [
    (BENCHMARK_DIR / "eval_report.json", f"geosim-eval/{run_ts}/eval_report.json"),
    (BENCHMARK_DIR / "eval_chart.png",   f"geosim-eval/{run_ts}/eval_chart.png"),
]

bucket = os.getenv("S3_BUCKET_NAME")
if not bucket:
    print("ERROR: S3_BUCKET_NAME not set in .env")
    sys.exit(1)

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    print("ERROR: boto3 not installed. Run: pip install boto3")
    sys.exit(1)

s3 = boto3.client("s3")

for local_path, s3_key in FILES:
    if not local_path.exists():
        print(f"  SKIP  {local_path.name} (file not found)")
        continue
    try:
        s3.upload_file(str(local_path), bucket, s3_key)
        print(f"  OK    s3://{bucket}/{s3_key}")
    except (BotoCoreError, ClientError) as exc:
        print(f"  FAIL  {local_path.name}: {exc}")
