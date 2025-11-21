import streamlit as st
from pathlib import Path
import tempfile
import shutil
import os
import sys

st.set_page_config(page_title="Invoice Combiner", layout="wide")

st.title("Invoice Combiner — ZIP / Folder processor")

st.markdown("""
Upload a ZIP containing your `*invoice_details.csv` files (or upload individual CSVs).
This app will extract them, run the combiner, and provide a downloadable combined CSV and Excel file.
**Files required in the repo:** `invoice_combiner_zip_clean.py` (the processor script).
""")

uploaded = st.file_uploader("Upload a ZIP file containing invoices", type=["zip"], accept_multiple_files=False)

# If the script is in the same folder, import functions
try:
    from invoice_combiner_zip_clean import process_zip, process_dir  # functions from the combiner script
    processor_available = True
except Exception as e:
    processor_available = False
    st.warning("Processor script not found or failed to import. Make sure `invoice_combiner_zip_clean.py` is in the app root. Error: " + str(e))

if uploaded and processor_available:
    tmpdir = Path(tempfile.mkdtemp())
    zip_path = tmpdir / uploaded.name
    with open(zip_path, "wb") as f:
        f.write(uploaded.getbuffer())

    st.info(f"Saved uploaded ZIP to {zip_path}")
    try:
        rows = process_zip(zip_path, tmpdir)
        import pandas as pd
        df = pd.DataFrame(rows, columns=["Invoice Number","PO #","External ID","Title","ASIN","Model #","Freight Term","Qty","Unit Cost","Amount"])
        out_csv = tmpdir / "master_invoice_combined_cleaned.csv"
        out_xlsx = tmpdir / "master_invoice_combined_cleaned.xlsx"
        df.to_csv(out_csv, index=False)
        df.to_excel(out_xlsx, index=False)
        st.success("Processing complete — download results below")
        with open(out_csv, "rb") as f:
            st.download_button("Download combined CSV", f, file_name="master_invoice_combined_cleaned.csv")
        with open(out_xlsx, "rb") as f:
            st.download_button("Download combined XLSX", f, file_name="master_invoice_combined_cleaned.xlsx")
    except Exception as e:
        st.error("Processing failed: " + str(e))
    finally:
        # clean up tempdir
        shutil.rmtree(tmpdir, ignore_errors=True)
elif not processor_available:
    st.info("Place `invoice_combiner_zip_clean.py` in the repository root to enable processing.")
else:
    st.info("Upload a ZIP file to begin processing.")
