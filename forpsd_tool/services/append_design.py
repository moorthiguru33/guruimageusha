import sys
import json
import os
import shutil
import time
import re
import openpyxl

def clean_val(v, default=""):
    if v is None:
        return default
    s = str(v).strip()
    if s.lower() in ("none", "null", "undefined"):
        return default
    return s

def extract_number(id_str):
    m = re.search(r'\d+', str(id_str))
    return m.group(0) if m else ''

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"status": "ERROR", "message": "Usage: append_design.py <xlsx_path> [item_json]"}), file=sys.stderr)
        sys.exit(1)

    xlsx_path = os.path.abspath(sys.argv[1])

    # Read JSON payload: prefer stdin (UTF-8 safe, no length limit), fallback to sys.argv[2]
    item = None
    if len(sys.argv) >= 3 and sys.argv[2].strip():
        try:
            item = json.loads(sys.argv[2])
        except Exception:
            pass

    if item is None:
        try:
            stdin_data = sys.stdin.buffer.read().decode('utf-8')
            if stdin_data.strip():
                item = json.loads(stdin_data)
        except Exception as e:
            print(json.dumps({"status": "ERROR", "message": f"Failed to read input JSON from stdin: {e}"}), file=sys.stderr)
            sys.exit(1)

    if not item or not isinstance(item, dict):
        print(json.dumps({"status": "ERROR", "message": "No valid item JSON provided"}), file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(xlsx_path):
        print(json.dumps({"status": "ERROR", "message": f"File not found: {xlsx_path}"}), file=sys.stderr)
        sys.exit(1)

    # 1. Create .bak backup safely
    try:
        shutil.copyfile(xlsx_path, xlsx_path + '.bak')
    except Exception as e:
        print(f"Warning: Could not create .bak backup: {e}", file=sys.stderr)

    # 2. Load workbook
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active

    # 3. Build Column Map
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    col_map = {str(name).strip(): idx + 1 for idx, name in enumerate(headers) if name}

    required_headers = [
        'ID', 'Download URL', 'Title', 'Category', 'Tags',
        'Description', 'Dimensions', 'DPI', 'File Size',
        'Color Mode', 'Software', 'Fonts Used', 'Preview URL'
    ]

    for rh in required_headers:
        if rh not in col_map:
            new_col = ws.max_column + 1
            ws.cell(1, new_col, rh)
            col_map[rh] = new_col

    # 4. Standardize Target ID (must be tam-ab-XXX)
    raw_id = clean_val(item.get('id', ''))
    target_num = extract_number(raw_id)
    if not target_num:
        target_num = str(int(time.time()))[-4:]
    target_id = f"tam-ab-{target_num}"

    # 5. Determine Target Row (update existing tam-ab or old tamilpsd, otherwise append)
    target_row = None
    action = "appended"
    id_col = col_map['ID']

    # Fast row lookup
    for r in range(2, ws.max_row + 1):
        val = str(ws.cell(r, id_col).value or '').strip()
        if not val:
            continue
        # Exact match
        if val.lower() == target_id.lower():
            target_row = r
            action = "updated"
            break
        # Match old format (e.g. tamilpsd-638 matches tam-ab-638)
        val_num = extract_number(val)
        if val_num and val_num == target_num:
            target_row = r
            action = f"updated_legacy ({val} -> {target_id})"
            break

    if target_row is None:
        target_row = ws.max_row + 1
        action = "appended"

    # 6. Sanitize and assign cell values
    ws.cell(target_row, col_map['ID'], target_id)
    ws.cell(target_row, col_map['Download URL'], clean_val(item.get('downloadUrl')))
    ws.cell(target_row, col_map['Title'], clean_val(item.get('title')))
    ws.cell(target_row, col_map['Category'], clean_val(item.get('category'), 'Design'))
    ws.cell(target_row, col_map['Tags'], clean_val(item.get('tags')))
    ws.cell(target_row, col_map['Description'], clean_val(item.get('description')))
    ws.cell(target_row, col_map['Dimensions'], clean_val(item.get('dimensions'), '1800x1200 pixels'))
    ws.cell(target_row, col_map['DPI'], clean_val(item.get('dpi'), '300 DPI'))
    ws.cell(target_row, col_map['File Size'], clean_val(item.get('fileSize'), '45.00 MB'))
    ws.cell(target_row, col_map['Color Mode'], clean_val(item.get('colorMode'), 'CMYK'))
    ws.cell(target_row, col_map['Software'], clean_val(item.get('software'), 'Adobe Photoshop CC'))
    ws.cell(target_row, col_map['Fonts Used'], clean_val(item.get('fontsUsed'), 'None'))
    ws.cell(target_row, col_map['Preview URL'], clean_val(item.get('previewUrl')))

    # 7. Save Workbook with Retry (Handling Excel File Locks)
    saved = False
    for attempt in range(6):
        try:
            wb.save(xlsx_path)
            wb.close()
            saved = True
            break
        except PermissionError:
            if attempt < 5:
                print(f"File locked (Excel might be open). Retrying in 2s... (Attempt {attempt+1}/6)", file=sys.stderr)
                time.sleep(2)
            else:
                print(json.dumps({
                    "status": "ERROR",
                    "code": "LOCKED",
                    "message": "Permission denied on designs.xlsx. Please CLOSE Microsoft Excel if it is open."
                }), file=sys.stderr)
                sys.exit(13)
        except Exception as e:
            print(json.dumps({"status": "ERROR", "message": f"Error saving workbook: {e}"}), file=sys.stderr)
            sys.exit(1)

    # 8. Post-Write Verification
    try:
        verify_wb = openpyxl.load_workbook(xlsx_path, read_only=True)
        verify_ws = verify_wb.active
        written_id = str(verify_ws.cell(target_row, col_map['ID']).value or '').strip()
        written_dl = str(verify_ws.cell(target_row, col_map['Download URL']).value or '').strip()
        written_prev = str(verify_ws.cell(target_row, col_map['Preview URL']).value or '').strip()
        verify_wb.close()

        if written_id != target_id:
            raise ValueError(f"Verification failed: expected ID '{target_id}', found '{written_id}'")
        
        result_payload = {
            "status": "SUCCESS",
            "id": target_id,
            "row": target_row,
            "action": action,
            "totalRows": verify_ws.max_row,
            "hasDownloadUrl": bool(written_dl),
            "hasPreviewUrl": bool(written_prev)
        }
        print(json.dumps(result_payload))
        sys.exit(0)

    except Exception as ve:
        print(json.dumps({"status": "ERROR", "message": f"Verification error after save: {ve}"}), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
