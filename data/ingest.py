from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "docs" / "Helpdesk.xlsx"
OUT = ROOT / "data" / "helpdesk.parquet"

SYSTEM_ALIASES = {
    "outlook": "Outlook",
    "teams": "Teams",
    "email": "Email",
    "microsoft": "Microsoft",
    "one drive ppt": "OneDrive",
}


def normalize_system(raw):
    if not isinstance(raw, str):
        return "Unknown"
    s = raw.strip()
    return SYSTEM_ALIASES.get(s.lower(), s)


def build_text(row):
    parts = [f"[{row['system']}] {row['question']}"]
    if row["reply"]:
        parts.append(f"處理紀錄: {row['reply']}")
    return "\n".join(parts)


def load_and_clean():
    df = pd.read_excel(XLSX)
    df = df.rename(columns={
        "系統\xa0 System": "system",
        "問題\xa0 Question": "question",
        "工號\xa0 WorkID": "work_id",
        "完成時間": "completed_at",
        "回覆": "reply",
        "分配": "assignee",
    })
    df["system"] = df["system"].map(normalize_system)
    df["reply"] = df["reply"].fillna("").astype(str)
    df["assignee"] = df["assignee"].fillna("").astype(str)
    df["question"] = df["question"].astype(str).str.strip()
    df = df[df["question"].str.len() > 0].copy()
    df["text"] = df.apply(build_text, axis=1)
    df["completed_at"] = df["completed_at"].astype(str)
    return df[["Id", "system", "question", "reply", "assignee", "completed_at", "text"]]


if __name__ == "__main__":
    df = load_and_clean()
    df.to_parquet(OUT, index=False)
    print(f"wrote {len(df)} records -> {OUT}")
    print("\ntop systems:")
    print(df["system"].value_counts().head(10).to_string())
