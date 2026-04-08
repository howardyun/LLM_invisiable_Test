#!/usr/bin/env python3
"""
检测多个 PDF → Markdown/JSON 解析器是否受到隐藏文本（OOB）注入攻击。
假设所有需要的包已通过 pip 安装。
"""
import os
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
import json
from typing import Callable, Dict, Any

os.environ[
    "GITHUB_TOKEN"] = "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"

# 配置
PDF_PATH = "../../attackFile/oob_poc_base.pdf"
TARGET_STRING = "HIDDEN OOB TEXT"  # 要检测的注入字符/字符串


def extract_text_from_json(obj: Any) -> str:
    """递归提取 JSON 对象中的所有字符串值，拼接返回"""
    texts = []
    if isinstance(obj, dict):
        for v in obj.values():
            texts.append(extract_text_from_json(v))
    elif isinstance(obj, list):
        for item in obj:
            texts.append(extract_text_from_json(item))
    elif isinstance(obj, str):
        texts.append(obj)
    return " ".join(texts)


# ---------- 定义各个包的解析函数 ----------
def test_pdf4llm(pdf_path: str) -> str:
    import pdf4llm
    md_text = pdf4llm.to_markdown(pdf_path)
    print(f"pdf4llm输出的文本:")
    print(md_text)
    return md_text


def test_kreuzberg(pdf_path: str) -> str:
    from kreuzberg import extract_file_sync
    # 同步提取 PDF 文本
    result = extract_file_sync(pdf_path)
    # 打印提取的文本内容
    print(f"kreuzberg输出的文本:")
    print(result.content)
    return result.content


def test_rpaframework_pdf(pdf_path: str) -> str:
    from RPA.PDF import PDF
    pdf = PDF()
    text_dict = pdf.get_text_from_pdf(pdf_path)
    # 将所有页的文本按页码顺序拼接成一个字符串
    full_text = '\n'.join(text_dict.values())
    print(f"rpaframework输出的文本:")
    print(full_text)
    return full_text


def extract_pdf_text_from_md_file(md_file_path: Path) -> str:
    """
    从 folder2md4llms 生成的 Markdown 文件中提取 PDF 正文文本。
    """
    with open(md_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    extracted_lines = []
    in_pdf_content = False

    for line in lines:
        # 检测是否进入 PDF 文档内容区域（以 "--- Page " 开头）
        if re.match(r'^--- Page \d+ ---', line.strip()):
            in_pdf_content = True
            continue  # 不保留页码标记

        # 如果遇到新的文档标题，说明当前 PDF 结束
        if in_pdf_content and line.strip().startswith('### 📋'):
            in_pdf_content = False
            continue

        # 如果在 PDF 内容区域内，保留该行文本
        if in_pdf_content:
            extracted_lines.append(line.rstrip('\n'))

    return '\n'.join(extracted_lines).strip()


def test_folder2md4llms(pdf_path: str) -> str:
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    # 创建临时目录（用于存放 PDF 副本和输出的 md 文件）
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        # 1. 复制 PDF 到临时目录
        dest_pdf = tmpdir_path / pdf_path.name
        shutil.copy2(pdf_path, dest_pdf)
        # 2. 定义临时 Markdown 输出文件路径
        md_output_path = tmpdir_path / "output.md"
        # 3. 调用 folder2md4llms，指定 --output 参数
        cmd = [
            sys.executable, "-m", "folder2md4llms",
            str(tmpdir_path),
            "--output", str(md_output_path)
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=False
            )
        except Exception as e:
            raise RuntimeError(f"执行 folder2md4llms 失败: {e}")
        if result.returncode != 0:
            raise RuntimeError(
                f"folder2md4llms 处理失败 (returncode={result.returncode})\n"
                f"stderr: {result.stderr}"
            )
        # 4. 检查生成的 Markdown 文件是否存在
        if not md_output_path.exists():
            raise RuntimeError(f"未生成预期的 Markdown 文件: {md_output_path}")
        # 5. 提取 PDF 正文文本
        pdf_text = extract_pdf_text_from_md_file(md_output_path)
        # 6. 打印预览（可选）
        print("folder2md4llms输出的文本:")
        print(pdf_text)
        # 7. 返回文本（临时目录和其中的 md 文件会在 with 块结束时自动删除）
        return pdf_text


def test_smart_file2md(pdf_path: str) -> str:
    from markdown_convert import convert_pdf
    # 调用转换函数，返回生成的 md 文件路径
    md_file_path = convert_pdf(pdf_path)
    # 确保路径是字符串/Path对象，并检查存在性
    md_file_path = Path(md_file_path)
    if not md_file_path.exists():
        raise FileNotFoundError(f"转换失败或未生成文件: {md_file_path}")
    # 读取 Markdown 内容
    with open(md_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 删除生成的 md 文件
    md_file_path.unlink()  # 等同于 os.remove
    # 如果父目录为空，也删除父目录（谨慎使用）
    parent_dir = md_file_path.parent
    try:
        parent_dir.rmdir()  # 仅当目录为空时才会成功
    except OSError:
        pass  # 目录非空或有其他文件，不删除
    print("smart_file2md 提取的文本内容:")
    print(content)
    return content


def test_any2md(pdf_path: str) -> str:
    # 获取 PDF 文件名（不含扩展名）
    pdf_name = Path(pdf_path).stem

    # 调用 any2md 生成 Markdown 文件
    # 注意：确保 any2md 已安装，并且其所在目录在系统 PATH 中
    cmd = [sys.executable, "-m", "any2md", pdf_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"any2md 转换失败: {e.stderr}")

    # any2md 默认的输出目录是 ./Text/
    # 根据 any2md 的行为，Markdown 文件会放在 ./Text/ 目录下，文件名可能是 <pdf_name>.md
    md_file_path = Path.cwd() / "Text" / f"{pdf_name}.md"
    if not md_file_path.exists():
        raise FileNotFoundError(f"Markdown 文件未生成: {md_file_path}")

    # 读取 Markdown 文件内容
    with open(md_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 清理：删除 Markdown 文件和 Text 目录
    md_file_path.unlink()  # 删除文件
    try:
        shutil.rmtree(Path.cwd() / "Text")  # 递归删除整个 Text 目录
    except OSError:
        pass  # 目录可能非空，忽略错误

    print("any2md 提取的文本内容:")
    print(content)
    return content


def test_contaix(pdf_path: str) -> str:
    from contaix import bytes_to_markdown
    # 假设你有一个 PDF 文件的字节流
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    markdown_text = bytes_to_markdown(pdf_bytes, input_format="pdf")
    print("markdown_text提取的文本内容:")
    print(markdown_text)
    return markdown_text


def test_dd_extract(pdf_path: str) -> str:
    from dd_extract import PDFExtractor
    extractor = PDFExtractor(engine="pypdf")
    text = extractor.from_file(pdf_path)
    print("dd_extract提取的文本:")
    print(text)
    return text


def test_pdf2llm(pdf_path: str) -> str:
    from pdf2llm import PDFExtractor
    extractor = PDFExtractor()
    result = extractor.extract(Path(pdf_path), output_format="markdown")
    print("result.content提取的文本:")
    print(result.content)
    # 清理生成的空目录
    pdf_stem = Path(pdf_path).stem  # 获取文件名（不含扩展名）
    extracted_dir = Path("extracted") / pdf_stem  # 构造默认生成的目录路径
    if extracted_dir.exists() and extracted_dir.is_dir():
        extracted_dir.rmdir()  # 删除空目录
        # 如果 extracted 目录本身也为空
        if Path("extracted").exists() and not any(Path("extracted").iterdir()):
            Path("extracted").rmdir()
    return result.content


# ---------- 注册所有测试函数 ----------
TESTERS: Dict[str, Callable[[str], str]] = {
    "pdf4llm": test_pdf4llm,
    "kreuzberg": test_kreuzberg,
    "rpaframework-pdf": test_rpaframework_pdf,
    "folder2md4llms": test_folder2md4llms,
    "smart-file2md": test_smart_file2md,
    "any2md": test_any2md,
    "contaix": test_contaix,
    "dd-extract": test_dd_extract,
    "pdf2llm": test_pdf2llm,
}


def main():
    print(f"Testing PDF: {PDF_PATH}")
    print(f"Looking for target string: {repr(TARGET_STRING)}\n")

    for name, func in TESTERS.items():
        try:
            extracted = func(PDF_PATH)
            if TARGET_STRING in extracted:
                print(f"[❌ ATTACK SUCCESS] {name} 提取的内容中发现目标字符串")
            else:
                print(f"[✅ ATTACK FAILED] {name} 提取的内容中未发现目标字符串")
        except Exception as e:
            print(f"[⚠️ ERROR] {name} 解析失败: {e}")


if __name__ == "__main__":
    main()
