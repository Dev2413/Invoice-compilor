#!/usr/bin/env python3
"""
invoice_combiner_zip.py (updated - v2)

Same functionality as before but ensures the Title column is sanitized by removing
any trailing commas and quotes (including common curly quotes) that sometimes
appear due to malformed CSV rows.

Usage examples:
    python invoice_combiner_zip.py --zip /path/to/USA.zip --outdir /path/to/output_dir
    python invoice_combiner_zip.py --data-dir /path/to/invoices_folder --outdir /path/to/output_dir
"""

import argparse
import csv
import re
import sys
import tempfile
import zipfile
from pathlib import Path
import pandas as pd
import shutil

ASIN_PATTERN = r"[A-Z0-9]{10}"
EXPECTED_COLS = ["PO #","External ID","Title","ASIN","Model #","Freight Term","Qty","Unit Cost","Amount","Invoice Number"]

def sanitize_title(s):
    if s is None:
        return ''
    t = str(s).strip()
    # Remove common trailing characters that appear due to malformed CSV exports
    return t.rstrip(' ,\"\\u201c\\u201d')  # strips spaces, commas, straight and curly quotes

def parse_line_with_regex(line):
    s = line.strip()
    if s.endswith(','):
        s = s[:-1]
    pat1 = re.compile(
        r'^\\s*\"(?P<po>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<external>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<title>.*?)'
        r'(?P<asin>' + ASIN_PATTERN + r')'
        r'\"\\s*,\\s*'
        r'\"(?P<model>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<freight>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<qty>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<unit>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<amount>[^\"]*)\"\\s*$',
        flags=re.DOTALL
    )
    m = pat1.match(s)
    if m:
        g = m.groupdict()
        title = sanitize_title(g['title'])
        return [
            g['po'].strip(), g['external'].strip(), title, g['asin'].strip(),
            g['model'].strip(), g['freight'].strip(), g['qty'].strip(), g['unit'].strip(), g['amount'].strip()
        ]

    pat2 = re.compile(
        r'^\\s*\"(?P<po>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<external>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<title_asin>.*?)\"\\s*,\\s*'
        r'\"(?P<model>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<freight>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<qty>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<unit>[^\"]*)\"\\s*,\\s*'
        r'\"(?P<amount>[^\"]*)\"\\s*$',
        flags=re.DOTALL
    )
    m2 = pat2.match(s)
    if m2:
        g = m2.groupdict()
        title_asin = g['title_asin']
        asin_search = re.search(ASIN_PATTERN, title_asin)
        if asin_search:
            asin = asin_search.group(0)
            title = sanitize_title(title_asin[:asin_search.start()])
            return [
                g['po'].strip(), g['external'].strip(), title, asin.strip(),
                g['model'].strip(), g['freight'].strip(), g['qty'].strip(), g['unit'].strip(), g['amount'].strip()
            ]

    parts = [p.strip().strip('\"') for p in re.split(r',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', s)]
    if len(parts) >= 9:
        for i, p in enumerate(parts):
            if re.fullmatch(ASIN_PATTERN, p):
                if i >= 3:
                    po = parts[0]
                    external = parts[1]
                    title = sanitize_title(",".join(parts[2:i]).strip())
                    asin = parts[i]
                    remainder = parts[i+1:i+6]
                    while len(remainder) < 5:
                        remainder.append('')
                    model, freight, qty, unit, amount = remainder[:5]
                    return [po, external, title, asin, model, freight, qty, unit, amount]

    return None

def clean_numeric(x):
    if x is None:
        return ''
    s = str(x).strip().replace('\"','').replace('$','').replace(',','')
    return s

def process_file(path: Path):
    rows = []
    m = re.match(r\"^(\\d{6})\", path.name)
    invoice_num = m.group(1) if m else ''
    header_found = False
    with path.open('r', encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.rstrip('\\n')
            if not line.strip():
                continue
            if not header_found and 'PO #' in line and 'External ID' in line and 'ASIN' in line:
                header_found = True
                continue
            if not header_found:
                continue

            parsed = None
            try:
                parsed = next(csv.reader([line]))
            except Exception:
                parsed = None

            if parsed and len(parsed) == 9:
                po, external, title, asin, model, freight, qty, unit, amount = [p.strip().strip('\"') for p in parsed]
                title = sanitize_title(title)
                rows.append([po, external, title, asin, model, freight, clean_numeric(qty), clean_numeric(unit), clean_numeric(amount), invoice_num])
                continue

            repaired = parse_line_with_regex(line)
            if repaired:
                po, external, title, asin, model, freight, qty, unit, amount = repaired
                title = sanitize_title(title)
                rows.append([po, external, title, asin, model, freight, clean_numeric(qty), clean_numeric(unit), clean_numeric(amount), invoice_num])
                continue

            joined = line
            success = False
            for i in range(4):
                try:
                    nxt = next(fh)
                except StopIteration:
                    nxt = ''
                if not nxt:
                    break
                joined += nxt.rstrip('\\n')
                try:
                    parsed2 = next(csv.reader([joined]))
                except Exception:
                    parsed2 = None
                if parsed2 and len(parsed2) == 9:
                    po, external, title, asin, model, freight, qty, unit, amount = [p.strip().strip('\"') for p in parsed2]
                    title = sanitize_title(title)
                    rows.append([po, external, title, asin, model, freight, clean_numeric(qty), clean_numeric(unit), clean_numeric(amount), invoice_num])
                    success = True
                    break
                repaired2 = parse_line_with_regex(joined)
                if repaired2:
                    po, external, title, asin, model, freight, qty, unit, amount = repaired2
                    title = sanitize_title(title)
                    rows.append([po, external, title, asin, model, freight, clean_numeric(qty), clean_numeric(unit), clean_numeric(amount), invoice_num])
                    success = True
                    break
            if success:
                continue

            parts = [p.strip().strip('\"') for p in re.split(r',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', line)]
            while len(parts) < 9:
                parts.append('')
            parts = parts[:9]
            po, external, title, asin, model, freight, qty, unit, amount = parts
            title = sanitize_title(title)
            rows.append([po, external, title, asin, model, freight, clean_numeric(qty), clean_numeric(unit), clean_numeric(amount), invoice_num])
    return rows

def process_directory(dir_path: Path):
    csv_files = sorted([p for p in dir_path.glob('*invoice_details.csv') if p.is_file()])
    all_rows = []
    for f in csv_files:
        print(f\"Processing file: {f}\")
        all_rows.extend(process_file(f))
    return all_rows

def process_zip(zip_path: Path, extract_to: Path):
    print(f\"Extracting ZIP: {zip_path} to {extract_to}\")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_to)
    csv_files = sorted([p for p in extract_to.rglob('*invoice_details.csv') if p.is_file()])
    print(f\"Found {len(csv_files)} invoice CSV files in extracted ZIP.\")
    all_rows = []
    for f in csv_files:
        print(f\"Processing file: {f}\")
        all_rows.extend(process_file(f))
    return all_rows

def main(args):
    outdir = Path(args.outdir) if args.outdir else Path.cwd()
    outdir.mkdir(parents=True, exist_ok=True)

    tempdir = None
    all_rows = []

    if args.zip:
        zip_path = Path(args.zip)
        if not zip_path.exists():
            print(f\"ZIP file not found: {zip_path}\", file=sys.stderr)
            return 2
        tempdir = Path(tempfile.mkdtemp(prefix='invoices_extract_'))
        try:
            all_rows = process_zip(zip_path, tempdir)
        finally:
            if not args.keep_temp:
                shutil.rmtree(tempdir, ignore_errors=True)
    else:
        data_dir = Path(args.data_dir) if args.data_dir else Path('/mnt/data')
        if not data_dir.exists() or not data_dir.is_dir():
            print(f\"Data directory not found: {data_dir}\", file=sys.stderr)
            return 3
        all_rows = process_directory(data_dir)

    if not all_rows:
        print(\"No invoice rows were extracted.\", file=sys.stderr)
        return 4

    df = pd.DataFrame(all_rows, columns=EXPECTED_COLS)
    df['Qty'] = pd.to_numeric(df['Qty'].replace('', pd.NA))
    df['Unit Cost'] = pd.to_numeric(df['Unit Cost'].replace('', pd.NA))
    df['Amount'] = pd.to_numeric(df['Amount'].replace('', pd.NA))

    out_csv = outdir / 'master_invoice_combined_cleaned.csv'
    out_xlsx = outdir / 'master_invoice_combined_cleaned.xlsx'
    df.to_csv(out_csv, index=False)
    df.to_excel(out_xlsx, index=False)
    print(f\"Wrote combined CSV: {out_csv}\")
    print(f\"Wrote combined Excel: {out_xlsx}\")
    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Combine invoice CSVs from a folder or ZIP into a clean master file.')
    parser.add_argument('--zip', type=str, help='Path to invoice ZIP file (e.g. /path/to/USA.zip)')
    parser.add_argument('--data-dir', type=str, help='Path to folder containing invoice CSV files (default: /mnt/data)')
    parser.add_argument('--outdir', type=str, help='Output directory (defaults to current working directory)')
    parser.add_argument('--keep-temp', action='store_true', help='Keep extracted temporary folder for debugging')
    args = parser.parse_args()
    sys.exit(main(args))
