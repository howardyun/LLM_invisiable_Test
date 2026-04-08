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
import textwrap
from pathlib import Path
import json
from typing import Callable, Dict, Any

os.environ[
    "GITHUB_TOKEN"] = "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"

# 配置
PDF_PATH = "../../attackFile/test_misaligned.pdf"
TARGET_STRING = "This is invisble"  # 要检测的注入字符/字符串


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
    # 先尝试默认的 Layout 模式（ONNX）
    try:
        md_text = pdf4llm.to_markdown(pdf_path)
        print("✅ 使用 Layout 模式（ONNX）解析成功")
    except Exception as e:
        # 捕获所有异常，但特别提示 ONNX 相关错误
        if "ONNX" in str(e) or "onnxruntime" in str(e).lower():
            print(f"⚠️ Layout 模式触发 ONNX 错误，自动切换到传统模式: {e}")
        else:
            print(f"⚠️ Layout 模式解析失败，尝试切换到传统模式: {e}")
        # 强制切换到传统模式（Legacy）
        pdf4llm.use_layout(False)
        try:
            md_text = pdf4llm.to_markdown(pdf_path)
            print("✅ 使用传统模式（Legacy）解析成功")
        except Exception as e2:
            print(f"❌ 传统模式也解析失败: {e2}")
            raise e2  # 如果连传统模式都失败，向上抛出异常
    # 统一输出结果
    print(f"pdf4llm 输出的文本:")
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
    pdf_name = Path(pdf_path).stem
    cmd = [sys.executable, "-m", "any2md", pdf_path]

    # 内部函数：读取生成的 .md 文件并清理临时目录
    def read_and_clean():
        md_file_path = Path.cwd() / "Text" / f"{pdf_name}.md"
        if not md_file_path.exists():
            raise FileNotFoundError(f"Markdown 文件未生成: {md_file_path}")
        with open(md_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        md_file_path.unlink()
        try:
            shutil.rmtree(Path.cwd() / "Text")
        except OSError:
            pass
        return content

    # ------------------- 第一次尝试：默认模式（不修改源码）-------------------
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        print("✅ any2md 默认模式转换成功")
        content = read_and_clean()
        print("any2md 提取的文本内容:")
        print(content)
        return content
    except subprocess.CalledProcessError as e:
        stderr = e.stderr
        # 判断是否为我们已知的 ONNX 类型错误
        if "ONNXRuntimeError" in stderr and "Unexpected input data type" in stderr:
            print("⚠️ 默认模式触发 ONNX 错误，自动切换到传统模式重试...")
        else:
            # 其他错误直接抛出，不再降级
            raise RuntimeError(f"any2md 默认模式转换失败: {stderr}")

    # ------------------- 第二次尝试：强制传统模式（动态修改源码）-------------------
    import any2md.converters.pdf as any2md_pdf_module
    pdf_py_path = Path(any2md_pdf_module.__file__)

    # 读取原始文件内容
    with open(pdf_py_path, 'r', encoding='utf-8') as f:
        original_code = f.read()

    # 构造修改后的代码：在 "import pymupdf4llm" 之后插入一行
    modified_code = original_code.replace(
        "import pymupdf4llm",
        "import pymupdf4llm\npymupdf4llm.use_layout(False)"
    )

    try:
        # 写入修改后的文件
        with open(pdf_py_path, 'w', encoding='utf-8') as f:
            f.write(modified_code)

        # 再次执行 any2md
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
            print("✅ any2md 传统模式转换成功")
            content = read_and_clean()
            print("any2md 提取的文本内容:")
            print(content)
            return content
        except subprocess.CalledProcessError as e2:
            raise RuntimeError(f"any2md 传统模式也失败: {e2.stderr}")
    finally:
        # 无论第二次成功与否，都要恢复原始文件
        with open(pdf_py_path, 'w', encoding='utf-8') as f:
            f.write(original_code)


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

    def read_and_clean():
        extracted_dir = Path("extracted") / Path(pdf_path).stem
        if extracted_dir.exists():
            try:
                shutil.rmtree(extracted_dir)
            except Exception as e:
                print(f"删除目录失败（可忽略）: {e}")
        parent_dir = Path("extracted")
        if parent_dir.exists() and not any(parent_dir.iterdir()):
            try:
                parent_dir.rmdir()
            except Exception:
                pass

    # ---------- 第一次尝试：默认模式 ----------
    try:
        extractor = PDFExtractor()
        result = extractor.extract(Path(pdf_path), output_format="markdown")
        print("✅ pdf2llm 默认模式提取成功")
        content = result.content
        print("pdf2llm提取的文本:")
        print(content)
        read_and_clean()
        return content
    except Exception as e:
        err_msg = str(e)
        if "ONNXRuntimeError" in err_msg and "Unexpected input data type" in err_msg:
            print("⚠️ 默认模式触发 ONNX 错误，准备动态修改源码并通过子进程重试...")
        else:
            raise

    # ---------- 第二次尝试：动态修改源码 + 子进程执行 ----------
    import pdf2llm.core.extractor as pdf2llm_extractor_module
    source_file = Path(pdf2llm_extractor_module.__file__)

    # 读取原始文件内容
    with open(source_file, 'r', encoding='utf-8') as f:
        original_code = f.read()

    # 构造修改后的代码：在 "import pymupdf4llm" 之后插入一行
    modified_code = original_code.replace(
        "import pymupdf4llm",
        "import pymupdf4llm\npymupdf4llm.use_layout(False)"
    )

    try:
        # 写入修改
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(modified_code)

        # 构建子进程内联脚本
        inline_script = textwrap.dedent(f"""
            import json
            from pathlib import Path
            from pdf2llm import PDFExtractor

            extractor = PDFExtractor()
            result = extractor.extract(Path(r"{pdf_path}"), output_format="markdown")
            output = {{
                "content": result.content,
                "token_estimate": result.token_estimate,
                "page_count": result.page_count,
                "has_images": result.has_images,
                "has_tables": result.has_tables
            }}
            print(json.dumps(output, ensure_ascii=False))
        """).strip()

        cmd = [sys.executable, "-c", inline_script]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=False
        )

        if proc.returncode != 0:
            raise RuntimeError(f"pdf2llm 子进程执行失败: {proc.stderr}")

        raw_output = proc.stdout.strip()
        # 打印原始输出前200字符用于调试（可选）
        # print(f"[DEBUG] 子进程原始输出前200字符: {raw_output[:200]}")

        # 健壮提取 JSON：找到第一个 '{' 和最后一个 '}' 之间的内容
        match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if not match:
            raise RuntimeError(f"子进程输出中未找到 JSON 对象: {raw_output}")

        json_str = match.group(0)
        try:
            output_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 解析失败: {e}\n尝试解析的字符串: {json_str[:500]}")

        content = output_data["content"]
        print("✅ pdf2llm 传统模式提取成功（已动态修改源码 + 子进程）")

    finally:
        # 恢复原始文件
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(original_code)

    print("pdf2llm提取的文本:")
    print(content)
    read_and_clean()
    return content


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
