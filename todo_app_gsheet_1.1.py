# todo_app_gsheet

import streamlit as st
import gspread  # type: ignore
from google.oauth2.service_account import Credentials  # type: ignore
from datetime import date, datetime

# === Google Sheets 設定 ===
SHEET_NAME = "my-todo-service"
SPREADSHEET_KEY = "1Fds4YElXO_z2djG2kaib8tQeMKd_I-TuBEIbhi38DQ4"

def get_worksheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_KEY)
    try:
        return sh.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        sh.add_worksheet(title=SHEET_NAME, rows="100", cols="4")
        return sh.worksheet(SHEET_NAME)

def load_data(ws):
    records = ws.get_all_records()
    for r in records:
        r["done"] = str(r.get("完了", "")).lower() == "true"
        r["task"] = r.get("タスク", "")
        r["due"] = r.get("締切日", "")
        r["tag"] = r.get("属性", "その他")
    return records

def save_data(ws, data):
    ws.clear()
    ws.append_row(["タスク", "締切日", "完了", "属性"])
    for row in data:
        ws.append_row([row["task"], row["due"], str(row["done"]), row["tag"]])

# === GUI ===
st.title("🖘️ マイTO-DOリスト（Google Sheets連携）")

try:
    ws = get_worksheet()
    data = load_data(ws)
except Exception as e:
    st.error(f"Google Sheets の接続に失敗しました: {e}")
    st.stop()

# 新規追加
st.write("### 新しいタスクを追加")
new_task = st.text_input("タスク内容", "")
due_date = st.date_input("締切日", value=date.today())
tag = st.selectbox("属性", ["仕事", "プライベート", "その他"])

if st.button("➕ 追加"):
    if new_task.strip():
        data.append({"task": new_task.strip(), "due": due_date.isoformat(), "done": False, "tag": tag})
        save_data(ws, data)
        st.rerun()

# 編集状態
if "edit_index" not in st.session_state:
    st.session_state["edit_index"] = -1
edit_index = st.session_state["edit_index"]

st.write("### タスク一覧")
for i, item in enumerate(data):
    col1, col2, col3, col4, col5 = st.columns([0.4, 0.15, 0.15, 0.15, 0.15])

    is_overdue = not item["done"] and item["due"] and item["due"] < date.today().isoformat()
    display_task = f"🔖 {item['tag']}｜{item['task']}（締切: {item['due']}）"
    style = "color:red;" if is_overdue else ""

    with col1:
        if i == edit_index:
            edited_task = st.text_input("タスク編集", value=item["task"], key=f"edit_task_{i}")
            edited_due = st.date_input("締切日編集", value=date.fromisoformat(item["due"]), key=f"edit_due_{i}")
            tag_options = ["仕事", "プライベート", "その他"]
            current_tag = item.get("tag", "その他")
            if current_tag not in tag_options:
                current_tag = "その他"
            edited_tag = st.selectbox("属性編集", tag_options,
                                      index=tag_options.index(current_tag),
                                      key=f"edit_tag_{i}")
        else:
            st.markdown(f"<span style='{style}'>{display_task}</span>", unsafe_allow_html=True)
            data[i]["done"] = st.checkbox("完了", value=item["done"], key=f"chk{i}")

    with col2:
        if i == edit_index:
            if st.button("💾 保存", key=f"save{i}"):
                data[i]["task"] = edited_task
                data[i]["due"] = edited_due.isoformat()
                data[i]["tag"] = edited_tag
                st.session_state["edit_index"] = -1
                save_data(ws, data)
                st.rerun()
        else:
            if st.button("✏️ 編集", key=f"edit{i}"):
                st.session_state["edit_index"] = i
                st.rerun()

    with col3:
        if st.button("🗑️ 削除", key=f"del{i}"):
            data.pop(i)
            st.session_state["edit_index"] = -1
            save_data(ws, data)
            st.rerun()

    with col4:
        if st.button("⬆️ 上へ", key=f"up{i}") and i > 0:
            data[i - 1], data[i] = data[i], data[i - 1]
            save_data(ws, data)
            st.rerun()

    with col5:
        if st.button("⬇️ 下へ", key=f"down{i}") and i < len(data) - 1:
            data[i + 1], data[i] = data[i], data[i + 1]
            save_data(ws, data)
            st.rerun()







