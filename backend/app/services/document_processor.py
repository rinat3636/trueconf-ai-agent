import os
from typing import List, Tuple

import pandas as pd
from docx import Document as DocxDocument
from PyPDF2 import PdfReader


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)
    return "\n\n".join(texts)


def extract_text_from_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    texts = []
    for para in doc.paragraphs:
        if para.text.strip():
            texts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_data:
                texts.append(" | ".join(row_data))
    return "\n\n".join(texts)


def extract_text_from_xlsx(file_path: str) -> str:
    texts = []
    try:
        xls = pd.ExcelFile(file_path, engine="openpyxl")
    except Exception:
        xls = pd.ExcelFile(file_path, engine="xlrd")

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        texts.append(f"=== {sheet_name} ===")
        for _, row in df.iterrows():
            row_values = [str(v) for v in row.values if pd.notna(v) and str(v).strip()]
            if row_values:
                texts.append(" | ".join(row_values))
    return "\n".join(texts)


def extract_text_from_csv(file_path: str) -> str:
    texts = []
    for encoding in ["utf-8", "cp1251", "latin-1"]:
        try:
            df = pd.read_csv(file_path, encoding=encoding, header=None)
            for _, row in df.iterrows():
                row_values = [str(v) for v in row.values if pd.notna(v) and str(v).strip()]
                if row_values:
                    texts.append(" | ".join(row_values))
            return "\n".join(texts)
        except UnicodeDecodeError:
            continue
    return ""


def extract_text_from_txt(file_path: str) -> str:
    for encoding in ["utf-8", "cp1251", "latin-1"]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    extractors = {
        ".pdf": extract_text_from_pdf,
        ".docx": extract_text_from_docx,
        ".xlsx": extract_text_from_xlsx,
        ".xls": extract_text_from_xlsx,
        ".csv": extract_text_from_csv,
        ".txt": extract_text_from_txt,
    }
    extractor = extractors.get(ext)
    if not extractor:
        raise ValueError(f"Unsupported file type: {ext}")
    return extractor(file_path)


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    if not text:
        return []

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += ("\n\n" + para) if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            if len(para) > chunk_size:
                words = para.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= chunk_size:
                        current_chunk += (" " + word) if current_chunk else word
                    else:
                        chunks.append(current_chunk.strip())
                        overlap_text = " ".join(current_chunk.split()[-chunk_overlap // 5:])
                        current_chunk = overlap_text + " " + word
            else:
                overlap_text = current_chunk[-chunk_overlap:] if current_chunk else ""
                current_chunk = overlap_text + "\n\n" + para if overlap_text else para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _get_row_outline_levels_xls(file_path: str) -> dict:
    """Read XLS row outline levels using xlrd (formatting_info)."""
    import xlrd

    levels = {}
    try:
        wb = xlrd.open_workbook(file_path, formatting_info=True)
        sheet = wb.sheet_by_index(0)
        for row_idx in range(sheet.nrows):
            ri = sheet.rowinfo_map.get(row_idx)
            if ri:
                levels[row_idx] = ri.outline_level
    except Exception:
        pass
    return levels


def _get_row_outline_levels_xlsx(file_path: str) -> dict:
    """Read XLSX row outline levels using openpyxl."""
    import openpyxl

    levels = {}
    try:
        wb = openpyxl.load_workbook(file_path, read_only=False, data_only=True)
        ws = wb.active
        for row_idx, rd in ws.row_dimensions.items():
            levels[row_idx - 1] = rd.outline_level
        wb.close()
    except Exception:
        pass
    return levels


def parse_sales_report(file_path: str) -> Tuple[List[dict], dict]:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".xls":
        outline_levels = _get_row_outline_levels_xls(file_path)
    elif ext == ".xlsx":
        outline_levels = _get_row_outline_levels_xlsx(file_path)
    else:
        outline_levels = {}

    try:
        if ext == ".xls":
            df = pd.read_excel(file_path, engine="xlrd", header=None)
        elif ext == ".xlsx":
            df = pd.read_excel(file_path, engine="openpyxl", header=None)
        else:
            df = pd.read_csv(file_path, header=None)
    except Exception:
        df = pd.read_csv(file_path, header=None)

    records = []
    metadata = {}

    for idx, row in df.iterrows():
        values = [v for v in row.values if pd.notna(v)]
        if not values:
            continue
        if "Период:" in str(row.values):
            for v in row.values:
                if pd.notna(v) and "Период:" in str(v):
                    metadata["period"] = str(v).replace("Период:", "").strip()

    header_row = None
    for idx, row in df.iterrows():
        vals = [str(v).strip() for v in row.values if pd.notna(v)]
        combined = " ".join(vals).lower()
        if "количество" in combined and ("стоимость" in combined or "прибыль" in combined):
            header_row = idx
            break

    if header_row is None:
        return records, metadata

    has_outline = bool(outline_levels)

    current_manager = None
    current_client = None

    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        values = list(row.values)

        name_val = str(values[1]).strip() if len(values) > 1 and pd.notna(values[1]) else ""
        if not name_val:
            continue

        is_total = "итого" in name_val.lower() or name_val.lower() == "итог"
        if is_total:
            continue

        nums = []
        for v in values[2:]:
            if pd.notna(v):
                try:
                    nums.append(float(v))
                except (ValueError, TypeError):
                    nums.append(None)
            else:
                nums.append(None)

        has_numbers = any(n is not None for n in nums)
        if not has_numbers:
            continue

        quantity = nums[0] if len(nums) > 0 else None
        tonnage = nums[1] if len(nums) > 1 else None
        revenue = nums[2] if len(nums) > 2 else None
        profit = nums[3] if len(nums) > 3 else None
        margin = nums[4] if len(nums) > 4 else None

        if has_outline:
            level = outline_levels.get(idx, 0)
            if level == 0:
                current_manager = name_val
                current_client = None
                records.append({
                    "manager_name": current_manager,
                    "client_name": None,
                    "product_name": None,
                    "quantity": quantity,
                    "tonnage": tonnage,
                    "revenue": revenue,
                    "profit": profit,
                    "margin_pct": margin,
                    "record_level": "manager",
                })
            elif level == 1:
                current_client = name_val
                records.append({
                    "manager_name": current_manager,
                    "client_name": current_client,
                    "product_name": None,
                    "quantity": quantity,
                    "tonnage": tonnage,
                    "revenue": revenue,
                    "profit": profit,
                    "margin_pct": margin,
                    "record_level": "client",
                })
            elif level >= 2 and current_manager and current_client:
                records.append({
                    "manager_name": current_manager,
                    "client_name": current_client,
                    "product_name": name_val,
                    "quantity": quantity,
                    "tonnage": tonnage,
                    "revenue": revenue,
                    "profit": profit,
                    "margin_pct": margin,
                    "record_level": "product",
                })
        else:
            # Fallback for CSV or files without outline levels.
            # Use first data row as manager, subsequent rows as products.
            if current_manager is None:
                current_manager = name_val
                current_client = None
                records.append({
                    "manager_name": current_manager,
                    "client_name": None,
                    "product_name": None,
                    "quantity": quantity,
                    "tonnage": tonnage,
                    "revenue": revenue,
                    "profit": profit,
                    "margin_pct": margin,
                    "record_level": "product",
                })
            else:
                records.append({
                    "manager_name": current_manager,
                    "client_name": current_client,
                    "product_name": name_val,
                    "quantity": quantity,
                    "tonnage": tonnage,
                    "revenue": revenue,
                    "profit": profit,
                    "margin_pct": margin,
                    "record_level": "product",
                })

    if records:
        manager_records = [r for r in records if r["record_level"] == "manager"]
        metadata["total_revenue"] = sum(r["revenue"] or 0 for r in manager_records)
        metadata["total_profit"] = sum(r["profit"] or 0 for r in manager_records)
        metadata["total_managers"] = len(manager_records)
        client_records = [r for r in records if r["record_level"] == "client"]
        metadata["total_clients"] = len(client_records)
        product_records = [r for r in records if r["record_level"] == "product"]
        unique_products = set(r["product_name"] for r in product_records if r["product_name"])
        metadata["total_skus"] = len(unique_products)

    return records, metadata
