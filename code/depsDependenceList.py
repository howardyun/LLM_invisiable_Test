"""
建立时间: 2026-4-2
作用: 以https://deps.dev网页数据为标准,进行爬虫获取数据,但只获取最新包版本数据
     例如:pypdf,仅仅获取6.9.2最新版的反向依赖包数据
"""
import requests
import time
import csv
import os


def get_latest_version(system: str, package: str) -> str:
    """从内部API获取最新版本号（第一个版本）"""
    url = f"https://deps.dev/_/s/{system}/p/{package}/versions"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    # 版本列表按发布时间降序，第一个即为最新
    latest_version = data["versions"][0]["version"]
    return latest_version


def get_direct_dependents(system: str, package: str, version: str) -> list:
    """获取指定版本的反向依赖 directSample"""
    url = f"https://deps.dev/_/s/{system}/p/{package}/v/{version}/dependents"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    # 返回 directSample 列表（每个元素包含 package.name 和 version）
    return data.get("directSample", [])


def save_to_csv(package_name: str, dependents: list, output_dir: str = "../outPutFile/newVersion"):
    """将反向依赖列表保存为CSV文件，包含name和version两列。
       即使dependents为空，也会创建仅含表头的文件。
       依赖包将先按name字段字母顺序排序，再按version排序。"""
    # 确保输出目录存在
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
    pass


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
    output_dir = "../outPutFile/newVersion"
    all_deps_set = set()  # 用于去重存储 (name, version),最后生成整体的数据

    # 处理每一个包的数据
    for package in packages:
        print(f"\n========== 处理包: {package} ==========")
        try:
            latest_ver = get_latest_version(system, package)
            print(f"最新版本: {latest_ver}")
        except Exception as e:
            print(f"获取版本失败: {e}")
            save_to_csv(package, [], output_dir=output_dir)
            continue

        try:
            dependents = get_direct_dependents(system, package, latest_ver)
            print(f"获取到 {len(dependents)} 个直接反向依赖（采样）")
            save_to_csv(package, dependents, output_dir=output_dir)
            # 添加到总体集合
            for dep in dependents:
                name = dep["package"]["name"]
                version = dep["version"]
                all_deps_set.add((name, version))
        except Exception as e:
            print(f"获取反向依赖失败: {e}")
            save_to_csv(package, [], output_dir=output_dir)

        time.sleep(1)

    # 生成总体文件 all.csv（先按 name 排序，再按 version 排序）
    os.makedirs(output_dir, exist_ok=True)
    all_csv_path = os.path.join(output_dir, "all.csv")
    with open(all_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "version"])
        if all_deps_set:
            for name, version in sorted(all_deps_set, key=lambda x: (x[0], x[1])):
                writer.writerow([name, version])
    print(f"\n总体文件已保存到 {all_csv_path}，共 {len(all_deps_set)} 条唯一记录")
    pass


if __name__ == "__main__":
    main()
