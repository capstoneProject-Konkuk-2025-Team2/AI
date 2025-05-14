import pandas as pd
import os

def convert_all_xlsx_to_csv(source_folder="my_excel_folder", dest_folder="my_csv_folder"):
    os.makedirs(dest_folder, exist_ok=True)

    for file in os.listdir(source_folder):
        if file.endswith(".xlsx"):
            file_path = os.path.join(source_folder, file)
            df = pd.read_excel(file_path)

            # 파일 이름에서 확장자 제거 후 csv로 저장
            csv_filename = os.path.splitext(file)[0] + ".csv"
            output_path = os.path.join(dest_folder, csv_filename)

            # utf-8-sig로 저장해서 한글 깨짐 방지
            df.to_csv(output_path, index=False, encoding='utf-8-sig')

            print(f" 변환 완료: {file} → {csv_filename}")

if __name__ == "__main__":
    convert_all_xlsx_to_csv()