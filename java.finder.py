import os
import subprocess
import re

def find_java_version(target_version):
    # 获取环境变量PATH的内容
    path_dirs = os.environ['PATH'].split(os.pathsep)
    
    # 定义版本号匹配的正则表达式
    version_pattern = re.compile(r'version\s+"(\d+\.\d+)(?:\.\d+)?')

    # 遍历每个目录
    for dir in path_dirs:
        java_path = os.path.join(dir, 'java.exe')
        # 检查java.exe是否存在
        if os.path.isfile(java_path):
            try:
                # 获取java.exe的版本信息
                result = subprocess.run([java_path, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                # Java版本信息通常在stderr中
                output = result.stderr
                # 使用正则表达式匹配版本号
                match = version_pattern.search(output)
                if match:
                    # 提取完整版本号
                    full_version = match.group(1).replace(".0", "")
                    # 比较完整版本号
                    if full_version == target_version:
                        return java_path
            except Exception as e:
                print(f"Error checking version of {java_path}: {e}")
    
    return None

# 指定要查找的Java版本
target_version = '1.8'
java_exe_path = find_java_version(target_version)

if java_exe_path:
    print(f"Found Java {target_version} at: {java_exe_path}")
else:
    print(f"Java {target_version} not found in PATH.")
