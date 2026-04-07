"""
建立时间: 2026-4-2
作用: 以https://deps.dev网页数据为标准,进行爬虫获取数据,获取包内所有版本的反向依赖包数据
     例如:pypdf,获取所有版本的反向依赖数据,合并去重后生成CSV文件
"""
import requests
import time
import csv
import os


def get_all_versions(system: str, package: str) -> list:
    """获取包的所有版本号列表（按发布时间降序）"""
    url = f"https://deps.dev/_/s/{system}/p/{package}/versions"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    versions = [v["version"] for v in data["versions"]]
    return versions


def get_direct_dependents(system: str, package: str, version: str) -> list:
    """获取指定版本的反向依赖 directSample"""
    url = f"https://deps.dev/_/s/{system}/p/{package}/v/{version}/dependents"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("directSample", [])


def save_to_csv(package_name: str, dependents: list, output_dir: str = "../outPutFile/allVersions"):
    """将反向依赖列表保存为CSV文件，包含name和version两列。
       即使dependents为空，也会创建仅含表头的文件。
       依赖包将先按name字段字母顺序排序，再按version字段排序。"""
    os.makedirs(output_dir, exist_ok=True)
    # 先按 name 排序，再按 version 排序
    sorted_dependents = sorted(dependents, key=lambda x: (x["package"]["name"], x["version"]))
    filename = os.path.join(output_dir, f"{package_name}.csv")
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "version"])
        for dep in sorted_dependents:
            name = dep["package"]["name"]
            version = dep["version"]
            writer.writerow([name, version])
    print(f"  [{package_name}] 已保存 {len(dependents)} 条记录到 {filename}")


def main():
    system = "pypi"
    packages = [
        "pypdf",
        "pdfplumber",
        "pypdfium2",
        "pymupdf",
        "pymupdf4llm",
        "pdfminer",
        "opendataloader-pdf",
        "unstructured",
        "docling",
        "undatasio"
    ]
    output_dir = "../outPutFile/allVersions"
    global_deps_set = set()  # 全局去重集合，用于 all.csv

    for package in packages:
        print(f"\n========== 处理包: {package} ==========")
        # 1. 获取所有版本
        try:
            versions = get_all_versions(system, package)
            print(f"共 {len(versions)} 个版本")
        except Exception as e:
            print(f"获取版本列表失败: {e}")
            save_to_csv(package, [], output_dir=output_dir)
            continue

        # 2. 遍历所有版本，收集反向依赖（去重）
        all_deps_set = set()
        for ver in versions:
            try:
                dependents = get_direct_dependents(system, package, ver)
                print(f"  版本 {ver}: {len(dependents)} 个直接反向依赖")
                for dep in dependents:
                    name = dep["package"]["name"]
                    version = dep["version"]
                    all_deps_set.add((name, version))
                    global_deps_set.add((name, version))  # 添加到全局集合
                time.sleep(0.5)
            except Exception as e:
                print(f"  版本 {ver}: 获取失败 - {e}")
                continue

        # 3. 保存该包的 CSV
        dependents_list = [{"package": {"name": n}, "version": v} for n, v in all_deps_set]
        save_to_csv(package, dependents_list, output_dir=output_dir)
        time.sleep(1)

    # 4. 生成总体文件 all.csv（先按 name 排序，再按 version 排序）
    os.makedirs(output_dir, exist_ok=True)
    all_csv_path = os.path.join(output_dir, "all.csv")
    with open(all_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "version"])
        if global_deps_set:
            for name, version in sorted(global_deps_set, key=lambda x: (x[0], x[1])):
                writer.writerow([name, version])
    print(f"\n总体文件已保存到 {all_csv_path}，共 {len(global_deps_set)} 条唯一记录")


if __name__ == "__main__":
    main()
