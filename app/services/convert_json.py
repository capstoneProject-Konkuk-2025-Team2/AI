import pandas as pd
import json
import os

def convert_csv_to_json(csv_path, json_path):
    df = pd.read_csv(csv_path, encoding="utf-8")
    df.columns = df.columns.str.strip()  # 컬럼명 공백 제거
    records = []

    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            val = row[col]
            if pd.notna(val) and str(val).strip() != "":
                record[col] = str(val).strip()
        records.append(record)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"변환 완료: {os.path.basename(csv_path)} → {os.path.basename(json_path)}")

def convert_all(folder="app/data/my_csv_folder"):
    for file_name in os.listdir(folder):
        if file_name.endswith(".csv") and file_name.startswith("se_"):
            csv_path = os.path.join(folder, file_name)
            json_name = file_name.replace(".csv", ".json")
            json_path = os.path.join(folder, json_name)
            convert_csv_to_json(csv_path, json_path)

if __name__ == "__main__":
    convert_all("app/data/my_csv_folder")