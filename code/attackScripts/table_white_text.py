import camelot
import json
import pandas as pd
from img2table.document import PDF
from typing import Dict, Callable
from kreuzberg import extract_file_sync, ExtractionConfig

# 文件路径
PDF_PATH = "../../attackFile/test_table_document_white_text.pdf"


def test_kreuzberg(pdf_path: str):
    """
    kreuzberg 同步提取表格，返回是带格式化纯文本
    """
    config = ExtractionConfig(force_ocr=False)
    # 同步调用
    result = extract_file_sync(pdf_path, config=config)
    return result.content


def test_img2table(pdf_path: str):
    """
    img2table提取表格，输出是dataframe数组，长文本可能被截断到多个dataframe里面
    """
    # 禁用pandas文本截断，显示/保存完整内容
    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    # 加载 PDF
    pdf = PDF(src=pdf_path)
    # 提取表格
    extracted_tables = pdf.extract_tables()
    all_dfs = []
    for page_num, tables in extracted_tables.items():
        for table in tables:
            all_dfs.append(table.df)
    return all_dfs


def test_camelot(pdf_path: str):
    """
    camelot提取表格，输出是dataframe
    """
    # 禁用pandas文本截断，显示/保存完整内容
    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    tables = camelot.read_pdf(pdf_path, flavor='stream')
    df = tables[0].df
    return df


# 导入的函数名称
TESTERS: Dict[str, Callable] = {
    "camelot": test_camelot,
    "img2table": test_img2table,
    "kreuzberg": test_kreuzberg
}


def main():
    print(f"Testing PDF: {PDF_PATH}")

    for name, func in TESTERS.items():
        try:
            extracted = func(PDF_PATH)
            print(f"============{name}输出的结果===========")
            print(f"{extracted}")
        except Exception as e:
            print(f"[⚠️ ERROR] {name} 解析失败: {e}")


if __name__ == "__main__":
    main()
