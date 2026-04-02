"""
建立时间: 2026-4-2
作用: 以libraries.io的API为标准,获取pypi包管理器下某个包的下游包名列表
TIPS: libraries.io由于性能关闭了服务,目前该文件难以测试到最终可用版本
"""
import requests
import time
from typing import List, Dict

# API Key
API_KEY = "0e96d6e7d260ac51431b2ef9137e9e41"
# Libraries.io API 基础 URL
BASE_URL = "https://libraries.io/api"


def test():
    # 请求路径和参数
    url = f"https://libraries.io/api/pypi/Docling/dependents?api_key={API_KEY}"
    # 发起请求
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        pass
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        pass

    # 返回数据
    data = response.json()
    print(f"data: {data}")
    pass


def get_dependents(platform: str, package_name: str, api_key: str) -> List[Dict]:
    """
    获取指定包的所有依赖者
    :param platform: 包管理器名称
    :param package_name: 包名称
    :param api_key
    :return: 依赖者列表
    """
    # 依赖列表
    dependents = []
    # 分页参数
    page = 1
    per_page = 100  # 每页最大返回数

    while True:
        # 请求路径和参数
        url = f"{BASE_URL}/{platform}/{package_name}/dependents"
        params = {
            "api_key": api_key,
            "page": page,
            "per_page": per_page
        }

        # 发起请求
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            pass
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            break
            pass

        # 返回数据
        data = response.json()
        print(f"data: {data}")
        # 没有更多数据
        if not data:
            break
            pass
        # 有数据
        dependents.extend(data)
        # 如果返回的数据条数小于per_page
        if len(data) < per_page:
            break
            pass
        page += 1
        # 适当延时,避免触发速率限制
        time.sleep(1)
        pass

    return dependents
    pass


def dependence():
    """
    获取包名列表的依赖方法
    :return: 包名的列表
    """
    # 包名列表
    packages = [
        {"platform": "pypi", "name": "PyPDF"},
        {"platform": "pypi", "name": "PDFPlumber"},
        {"platform": "pypi", "name": "PyPDFDirectry"}
    ]

    for pkg in packages:
        print(f"\n正在查询: {pkg['name']} (平台: {pkg['platform']})")
        dependents = get_dependents(pkg['platform'], pkg['name'], API_KEY)

        if not dependents:
            print("没有找到依赖者,或包不存在")
            pass
        else:
            print(f"共找到{len(dependents)}个依赖者:")
            print(f"列表:{dependents}")
            # for dep in dependents:
            #     # 获取name名字和plaform包管理器字段
            #     dep_name = dep.get('name', '未知')
            #     dep_platform = dep.get('platform', '未知')
            #     print(f"- {dep_name} ({dep_platform})")
            #     pass
            pass
        pass
    pass


if __name__ == "__main__":
    # dependence()
    test()
    pass
