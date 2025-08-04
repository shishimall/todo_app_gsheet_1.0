# todo_app_gsheet.py

import streamlit as st
import gspread  # type: ignore
from google.oauth2.service_account import Credentials  # type: ignore
from datetime import date

# === Google Sheets 設定 ===
SHEET_NAME = "my-todo-service"
SPREADSHEET_KEY = "1Fds4YElXO_z2djG2kaib8tQeMKd_I-TuBEIbhi38DQ4"

# Google Sheets 接続関数
def get_worksheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # ✅ secrets.toml に定義した service_account 情報から認証
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_KEY)
    
    try:
        return sh.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        sh.add_worksheet(title=SHEET_NAME, rows="100", cols="3")
        return sh.worksheet(SHEET_NAME)

# データ読み込み
def load_data(ws):
    records = ws.get_all_records()
    for r in records:
        r["done"] = str(r.get("完了", "")).lower() == "true"
        r["task"] = r.get("タスク", "")
        r["due"] = r.get("締切日", "")
    return records

# データ保存（全上書き）
def save_data(ws, data):
    ws.clear()
    ws.append_row(["タスク", "締切日", "完了"])
    for row in data:
        ws.append_row([row["task"], row["due"], str(row["done"])])

# === Streamlit GUI ===
st.title("🖘️ マイTO-DOリスト（Google Sheets連携）")

try:
    ws = get_worksheet()
    data = load_data(ws)
except Exception as e:
    st.error(f"Google Sheets の接続に失敗しました: {e}")
    st.stop()

new_task = st.text_input("新しいタスクを追加", "")
due_date = st.date_input("締切日", value=date.today())

if st.button("➕ 追加"):
    if new_task.strip():
        data.append({"task": new_task.strip(), "due": due_date.isoformat(), "done": False})
        save_data(ws, data)
        st.rerun()

st.write("### タスク一覧")
for i, item in enumerate(data):
    col1, col2 = st.columns([0.8, 0.2])

    with col1:
        checked = st.checkbox(f"{item['task']}（締切: {item['due']}）", value=item["done"], key=f"chk{i}")
        data[i]["done"] = checked

    with col2:
        if st.button("🗑️ 削除", key=f"del{i}"):
            data.pop(i)
            save_data(ws, data)
            st.rerun()

save_data(ws, data)


