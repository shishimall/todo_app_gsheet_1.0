# todo_app_gsheet

import streamlit as st
import gspread  # type: ignore
from google.oauth2.service_account import Credentials  # type: ignore
from datetime import date, datetime
import time
import pandas as pd  # type: ignore
import os
import platform
import io
import subprocess
from typing import List, Dict
from pathlib import Path

# === Google Sheets 設定 ===
SHEET_NAME = "my-todo-service"
SPREADSHEET_KEY = "1Fds4YElXO_z2djG2kaib8tQeMKd_I-TuBEIbhi38DQ4"


def get_worksheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
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


# ======= 読み書き（日本語列を正として統一） =======
def load_data(ws) -> List[Dict]:
    records = ws.get_all_records()
    return [
        {
            "task": r.get("タスク", r.get("task", "")),
            "due": r.get("締切日", r.get("due", "")),
            "done": str(r.get("完了", r.get("done", ""))).lower() == "true",
            "tag": r.get("属性", r.get("tag", "未設定")),
        }
        for r in records
    ]


def save_data(ws, data: List[Dict]):
    ws.clear()
    ws.append_row(["タスク", "締切日", "完了", "属性"])
    for row in data:
        ws.append_row([
            row.get("task", ""),
            row.get("due", ""),
            str(bool(row.get("done", False))),
            row.get("tag", "未設定"),
        ])


# ======= 共通ユーティリティ =======
def _as_dataframe(data: List[Dict]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame(columns=["タスク", "締切日", "完了", "属性"])
    return pd.DataFrame(
        [
            {
                "タスク": r.get("task", ""),
                "締切日": r.get("due", ""),
                "完了": bool(r.get("done", False)),
                "属性": r.get("tag", "未設定"),
            }
            for r in data
        ]
    )


def _open_folder(path: str) -> None:
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


# === 修正版バックアップ ===
IS_CLOUD = Path.home().as_posix() == "/home/appuser"  # 簡易クラウド判定

def backup_to_xlsx(data: List[Dict]):
    """ローカルなら Downloads に保存、CloudならDLボタン用バッファを返す"""
    df = _as_dataframe(data)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"todo_backup_{ts}.xlsx"

    # メモリに一旦書く（共通処理）
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="backup")
    buf.seek(0)
    data_bytes = buf.getvalue()

    if IS_CLOUD:
        # Cloud環境はファイル保存せずDLボタンで提供
        return (None, fname, data_bytes)

    # ローカル環境は Downloads に保存
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    fpath = downloads / fname
    with open(fpath, "wb") as f:
        f.write(data_bytes)

    return (str(fpath), fname, None)


def _normalize_restored_df(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for col in df.columns:
        c = str(col).strip()
        if c in ["タスク", "task"]:
            col_map[col] = "タスク"
        elif c in ["締切日", "due"]:
            col_map[col] = "締切日"
        elif c in ["完了", "done"]:
            col_map[col] = "完了"
        elif c in ["属性", "tag"]:
            col_map[col] = "属性"

    df = df.rename(columns=col_map)
    for c in ["タスク", "締切日", "完了", "属性"]:
        if c not in df.columns:
            df[c] = "" if c != "完了" else False

    df["完了"] = df["完了"].astype(str).str.lower().isin(
        ["true", "1", "t", "y", "yes", "真", "完了"]
    )
    df["締切日"] = (
        df["締切日"].astype(str).str.replace("NaT", "").str.replace("nan", "", regex=False)
    )
    return df[["タスク", "締切日", "完了", "属性"]]


def restore_from_excel(ws, file_bytes: bytes):
    df = pd.read_excel(io.BytesIO(file_bytes))
    df = _normalize_restored_df(df)
    ws.clear()
    ws.update([df.columns.tolist()] + df.astype(object).values.tolist())


def _sort_key_due(r: Dict):
    d = (r.get("due") or "").strip()
    return (d == "", d)


# ======= GUI =======
st.title("🖘️ マイTO-DOリスト（Google Sheets連携）— v1.3")

try:
    ws = get_worksheet()
    data = load_data(ws)
except Exception as e:
    st.error(f"Google Sheets の接続に失敗しました: {e}")
    st.stop()

# --- クイック操作 ---
st.subheader("⚡ クイック操作")
c1, c2, c3 = st.columns([0.4, 0.3, 0.3])

# 1) バックアップ保存
with c1:
    if st.button("💾 バックアップ(.xlsx)作成", use_container_width=True):
        fpath, fname, buf = backup_to_xlsx(data)
        if fpath:
            st.success(f"保存しました：{fpath}")
            _open_folder(os.path.dirname(fpath))
        else:
            st.success("バックアップを作成しました。下からダウンロードできます。")
            st.download_button(
                label=f"⬇️ {fname} をダウンロード",
                data=buf,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

# 2) 締切日で並べ替え
with c2:
    if st.button("📅 締切日で並べ替え", use_container_width=True):
        data.sort(key=_sort_key_due)
        save_data(ws, data)
        st.success("締切日順に並べ替えました")
        st.rerun()

# 3) バックアップから復元
with c3:
    up = st.file_uploader("復元（.xlsx）", type=["xlsx"], label_visibility="collapsed", key="restore_uploader")
    if up and st.button("⏮️ バックアップから復元", use_container_width=True, key="restore_btn"):
        try:
            restore_from_excel(ws, up.read())
            st.success("バックアップから復元しました。ページを更新します…")
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.error(f"復元に失敗しました: {e}")

# --- 新規追加 ---
st.write("### 新しいタスクを追加")
new_task = st.text_input("タスク内容", key="new_task")
due_date = st.date_input("締切日", value=date.today(), key="new_due")
tag = st.selectbox("属性", ["仕事", "プライベート", "その他"])

if st.button("➕ 追加"):
    if new_task.strip():
        data.append(
            {
                "task": new_task.strip(),
                "due": due_date.isoformat(),
                "done": False,
                "tag": tag,
            }
        )
        save_data(ws, data)
        st.success("追加完了。ページをリロード中...")
        time.sleep(0.4)
        st.rerun()

# --- 編集状態 ---
if "edit_index" not in st.session_state:
    st.session_state["edit_index"] = -1
edit_index = st.session_state["edit_index"]

st.write("### タスク一覧")
for i, item in enumerate(data):
    col1, col2, col3, col4, col5 = st.columns([0.4, 0.15, 0.15, 0.15, 0.15])

    is_overdue = (not item.get("done")) and item.get("due") and item["due"] < date.today().isoformat()
    display_task = f"🔖 {item.get('tag','')}｜{item.get('task','')}（締切: {item.get('due','')}）"
    style = "color:red;" if is_overdue else ""

    with col1:
        if i == edit_index:
            edited_task = st.text_input("タスク編集", value=item.get("task", ""), key=f"edit_task_{i}")
            try:
                _edit_due_init = date.fromisoformat(item.get("due", "")) if item.get("due") else date.today()
            except Exception:
                _edit_due_init = date.today()
            edited_due = st.date_input("締切日編集", value=_edit_due_init, key=f"edit_due_{i}")
            edited_tag = st.selectbox(
                "属性編集",
                ["仕事", "プライベート", "その他"],
                index=["仕事", "プライベート", "その他"].index(item.get("tag", "仕事")) if item.get("tag") in ["仕事", "プライベート", "その他"] else 0,
                key=f"edit_tag_{i}",
            )
        else:
            st.markdown(f"<span style='{style}'>{display_task}</span>", unsafe_allow_html=True)
            data[i]["done"] = st.checkbox("完了", value=bool(item.get("done", False)), key=f"chk{i}")

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

