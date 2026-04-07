#!/usr/bin/env python3
"""
筛选具有 PDF 文本提取功能的 Python 包
使用 DeepSeek API 进行智能判断，支持结果缓存
自动安装缺失的包，生成并执行 PDF 文本提取代码（检测隐藏文本）
"""

import csv
import json
import os
import sys
import time
import subprocess
import re
import tempfile
from typing import List, Dict, Any

import requests

# ==================== 配置区域 ====================
DEEPSEEK_API_KEY = "sk-555d91686fda4d4e8ff96ab09e4ec67b"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL_NAME = "deepseek-chat"
CSV_PATH = "../outPutFile/newVersion/pypdf.csv"

REQUEST_DELAY = 0.5
MAX_RETRIES = 3
RETRY_DELAY = 2
CACHE_DIR = "../outPutFile/newPackageCache"
RESULT_DIR = "../outPutFile/newPackageResult"  # 新增：结果CSV存储目录


# ==================== 工具函数 ====================
def load_packages(csv_path: str) -> List[Dict[str, str]]:
    """从 CSV 文件中读取包名和版本"""
    packages = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            packages.append({
                "name": row["name"].strip(),
                "version": row["version"].strip()
            })
    return packages


def get_cache_path(csv_path: str) -> str:
    """根据 CSV 文件路径生成缓存文件路径，例如 pypdf.csv -> pypdf.txt"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    base_name = os.path.basename(csv_path)
    name_without_ext = os.path.splitext(base_name)[0]
    cache_file = f"{name_without_ext}.txt"
    return os.path.join(CACHE_DIR, cache_file)


def load_cache(cache_path: str) -> List[str]:
    """读取缓存文件，返回包列表（每行 name==version）"""
    with open(cache_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines


def save_cache(cache_path: str, packages: List[Dict[str, str]]) -> None:
    """将符合条件的包列表写入缓存文件（每行 name==version）"""
    with open(cache_path, 'w', encoding='utf-8') as f:
        for pkg in packages:
            f.write(f"{pkg['name']}=={pkg['version']}\n")


def build_prompt(pkg_name: str, pkg_version: str) -> str:
    """构建发送给模型的提示词，用于判断包是否具备 PDF 文本提取能力"""
    return f"""你是一位 Python 生态专家。请判断以下 Python 包是否具备**从 PDF 文件中提取所有可见文本内容**的功能，类似 pypdf 库中的 `extract_text()` 方法。

要求：
- 必须能够解析 PDF 并提取其中用户可见的文本（如段落、标题等）。
- 排除以下类型：
  * OCR 工具（依赖图像识别提取文字，如 Tesseract 包装器）
  * PDF 生成工具（如 reportlab, fpdf）
  * PDF 转换工具（如 pdf2image, pdf2html）
  * PDF 排版/编辑工具（如调整布局、合并拆分、加水印）

只考虑**纯解析 + 文本提取**的包。

包名: {pkg_name}
版本: {pkg_version}

请以**严格 JSON 格式**输出，不要包含其他任何文字：
{{"has_extract_text": true/false, "reason": "简要说明判断依据"}}
"""


def query_deepseek(prompt: str) -> Dict[str, Any]:
    """调用 DeepSeek API 并返回解析后的 JSON"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            if "has_extract_text" not in result or "reason" not in result:
                raise ValueError("API 返回的 JSON 缺少必要字段")
            return result
        except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
            print(f"尝试 {attempt + 1}/{MAX_RETRIES} 失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                return {"has_extract_text": False, "reason": f"API 调用失败: {str(e)}"}


def filter_packages(packages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """逐个调用 API，筛选符合条件的包"""
    valid_packages = []
    total = len(packages)

    for idx, pkg in enumerate(packages, 1):
        name = pkg["name"]
        version = pkg["version"]
        print(f"[{idx}/{total}] 正在分析: {name}=={version}")

        prompt = build_prompt(name, version)
        result = query_deepseek(prompt)

        if result.get("has_extract_text"):
            print(f"  ✓ 符合条件: {result['reason']}")
            valid_packages.append(pkg)
        else:
            print(f"  ✗ 不符合: {result['reason']}")

        time.sleep(REQUEST_DELAY)

    return valid_packages


def get_installed_packages() -> set:
    """通过 pip list 获取当前环境已安装的包名集合（小写）"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        installed = set()
        for line in result.stdout.splitlines():
            if "==" in line:
                pkg_name = line.split("==")[0].strip().lower()
                installed.add(pkg_name)
        return installed
    except subprocess.CalledProcessError as e:
        print(f"获取已安装包列表失败: {e}", file=sys.stderr)
        return set()


def install_missing_packages(cache_path: str) -> None:
    """
    读取缓存文件中的包名（忽略版本），检查是否已安装。
    未安装则尝试 pip install --user，失败时提示手动安装。
    """
    if not os.path.exists(cache_path):
        print(f"缓存文件不存在: {cache_path}，跳过安装步骤。")
        return

    print("\n" + "=" * 50)
    print("开始检查并安装缺失的包...")
    lines = load_cache(cache_path)
    if not lines:
        print("缓存文件中没有包，无需安装。")
        return

    # 提取包名（小写，忽略版本）
    required_packages = set()
    for line in lines:
        if "==" in line:
            name = line.split("==")[0].strip()
        else:
            name = line.strip()
        if name:
            required_packages.add(name.lower())

    installed = get_installed_packages()
    missing = [pkg for pkg in required_packages if pkg.lower() not in installed]

    if not missing:
        print("所有需要的包均已安装。")
        return

    print(f"发现 {len(missing)} 个未安装的包:")
    for pkg in missing:
        print(f"  - {pkg}")

    answer = input("\n是否尝试自动安装这些包？(y/N): ").strip().lower()
    if answer != 'y':
        print("跳过自动安装。")
        return

    for pkg in missing:
        print(f"\n正在安装: {pkg}")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--user", pkg],
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            print(f"  ✓ {pkg} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ {pkg} 安装失败 (错误码: {e.returncode})")
            print(f"    错误信息: {e.stderr.strip() if e.stderr else e.stdout.strip()}")
            print(f"    请手动安装: pip install {pkg}")


def generate_extraction_code(package_names: List[str]) -> None:
    """
    为每个包生成 PDF 文本提取代码（原有风格），执行后解析输出，
    将结果保存到独立的 CSV 文件中。
    CSV 路径: ../outPutFile/newPackageResult/{包名}.csv
    表头: code, raw, format, result
    """
    if not package_names:
        print("没有可用的包，跳过代码生成。")
        return

    os.makedirs(RESULT_DIR, exist_ok=True)

    # 构建原来的提示词（不要求 JSON 输出）
    packages_list = "\n".join([f"- {pkg}" for pkg in package_names])
    prompt = f"""你是一位 Python 专家。请为以下每个 Python 包生成一段可运行的代码，演示如何使用该包从 PDF 文件中提取所有可见文本，并检测隐藏文本。

包列表：
{packages_list}

要求：
- 每个包的代码独立成块，使用 markdown 代码块（```python ... ```）包裹。
- **在代码块的前一行，必须写上 `# package: 包名`**，以便识别该代码块对应的包。
- PDF 文件路径固定为：../attackFile/oob_poc_base.pdf
- 代码必须包含以下内容：
  1. 导入必要的模块。
  2. 打开 PDF 文件，提取全部的文本。
  3. 使用 `repr(text)` 打印原始提取的文本（以便看到换行等隐藏字符），输出格式示例：`print("=== Raw extracted text (with repr) ==="); print(repr(text))`。
  4. 打印普通格式的文本，输出格式示例：`print("=== Formatted extracted text ==="); print(text)`。
  5. 检测提取的文本中是否包含字符串 "HIDDEN OOB TEXT"，并打印相应的提示信息（例如 `print("[+] Hidden OOB text FOUND!")` 或 `print("[-] Hidden OOB text NOT found")`）。
- **重要：所有打印输出和信息请使用英文，不要使用中文，以避免编码问题。**
- 代码应尽可能简单直接，避免无关输出。
- 如果某个包不适用于文本提取，请在代码中捕获异常并打印错误信息，但仍然按照上述格式输出（原始文本和格式化文本可以为空）。

请直接输出代码块和包名标注，不要有多余的解释。"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    try:
        print("\n" + "=" * 50)
        print("正在请求 DeepSeek API 生成 PDF 文本提取代码...")
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print("\n生成的原始响应：\n")
        print(content)
        print("=" * 50)

        # 解析代码块和包名
        pattern = r'# package:\s*(\S+)\s*\n```python\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

        if not matches:
            print("未找到符合格式的代码块（需要 '# package: 包名' 标记）。")
            return

        print(f"\n开始执行生成的代码块（共 {len(matches)} 个）...")
        for pkg_name, code in matches:
            pkg_name = pkg_name.strip()
            print(f"\n--- 处理包: {pkg_name} ---")
            csv_file = os.path.join(RESULT_DIR, f"{pkg_name}.csv")

            # 执行代码并捕获输出
            stdout = ""
            stderr = ""
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_file = f.name

            try:
                proc = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding='utf-8',
                    errors='replace',
                    cwd=os.getcwd()
                )
                stdout = proc.stdout
                stderr = proc.stderr
                if stderr:
                    print(f"  [stderr]: {stderr[:200]}...")  # 调试用
            except subprocess.TimeoutExpired:
                stdout = ""
                stderr = "Execution timeout (30s)"
            except Exception as e:
                stdout = ""
                stderr = str(e)
            finally:
                try:
                    os.unlink(temp_file)
                except:
                    pass

            # 解析输出：提取 raw（repr 后的文本）、format（普通文本）、result
            raw_text = ""
            formatted_text = ""
            found = False

            # 1. 提取 raw text：匹配 "=== Raw extracted text (with repr) ===" 之后的内容，直到下一个 "===" 或文件结束
            raw_match = re.search(r"=== Raw extracted text \(with repr\) ===\s*\n(.*?)(?=\n===|\Z)", stdout, re.DOTALL)
            if raw_match:
                raw_text = raw_match.group(1).strip()
            else:
                # 没找到标记，尝试将整个 stdout 作为 raw（降级）
                raw_text = stdout.strip()

            # 2. 提取 formatted text：匹配 "=== Formatted extracted text ===" 之后的内容
            format_match = re.search(r"=== Formatted extracted text ===\s*\n(.*?)(?=\n===|\Z)", stdout, re.DOTALL)
            if format_match:
                formatted_text = format_match.group(1).strip()
            else:
                formatted_text = stdout.strip()  # 降级

            # 3. 检测 result：查找 "[+] Hidden OOB text FOUND!"
            if re.search(r"\[\+\] Hidden OOB text FOUND!", stdout):
                found = True
            else:
                found = False

            # 如果 stderr 有内容且 stdout 为空，则将错误信息写入
            if stderr and not stdout.strip():
                raw_text = repr(stderr)
                formatted_text = stderr
                found = False

            # 写入 CSV
            try:
                with open(csv_file, 'w', newline='', encoding='utf-8') as csv_f:
                    writer = csv.writer(csv_f)
                    writer.writerow(["code", "raw", "format", "result"])
                    writer.writerow([code, raw_text, formatted_text, str(found)])
                print(f"  ✓ 结果已保存到: {csv_file}")
            except Exception as e:
                print(f"  ✗ 写入 CSV 失败: {e}")

            print("-" * 40)

    except Exception as e:
        print(f"生成代码时出错: {e}", file=sys.stderr)
        print("请稍后重试或手动编写代码。")


def main():
    if not DEEPSEEK_API_KEY:
        print("错误: 请设置环境变量 DEEPSEEK_API_KEY", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(CSV_PATH):
        print(f"错误: 找不到 CSV 文件 '{CSV_PATH}'", file=sys.stderr)
        sys.exit(1)

    cache_path = get_cache_path(CSV_PATH)

    if os.path.exists(cache_path):
        print(f"发现缓存文件: {cache_path}")
        print("直接从缓存读取结果，不再调用 API。\n")
        cached_lines = load_cache(cache_path)
        print("=" * 50)
        print(f"缓存中的符合条件的包共 {len(cached_lines)} 个：")
        for line in cached_lines:
            print(f"  {line}")
        print("=" * 50)
        print(f"\n缓存文件位置: {cache_path}")

        install_missing_packages(cache_path)

        # 获取包名列表（不含版本）用于生成代码
        package_names = [line.split("==")[0].strip() if "==" in line else line.strip() for line in cached_lines]
        generate_extraction_code(package_names)
        return

    print(f"未找到缓存，开始调用 API 进行分析...")
    print(f"正在加载包列表: {CSV_PATH}")
    packages = load_packages(CSV_PATH)
    print(f"共加载 {len(packages)} 个包\n")

    valid = filter_packages(packages)

    save_cache(cache_path, valid)
    print(f"\n已将结果写入缓存文件: {cache_path}")

    print("\n" + "=" * 50)
    print(f"筛选完成。符合条件的包共 {len(valid)} 个：")
    for pkg in valid:
        print(f"  {pkg['name']}=={pkg['version']}")
    print("=" * 50)

    install_missing_packages(cache_path)

    # 获取包名列表并生成代码
    package_names = [pkg["name"] for pkg in valid]
    generate_extraction_code(package_names)


if __name__ == "__main__":
    main()
