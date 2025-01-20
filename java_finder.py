import os
import subprocess
import re

def find_java_version(target_version):
    java_exe_path = ""
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
                    full_version = match.group(1).replace(".0", "").replace("1.", "")
                    # 比较完整版本号
                    if full_version == target_version:
                        java_exe_path = java_path
                        break
            except Exception as e:
                print(f"检查{java_path}时出现错误: {e}")
    
    if java_exe_path:
        print(f"在{java_exe_path}找到Java {target_version}")
    else:
        java_exe_path = input(f"未找到Java {target_version},请手动输入Java {target_version}的路径\n示例: C:\\Program Files\\Java\\jdk-11.0.1\\bin\\java.exe\n")
        if not os.path.isfile(java_exe_path):
            print(f"无效的Java路径: {java_exe_path}")
            exit(1)
    return java_exe_path

def get_java_exe_dict():
    java_exe_path_dict = {}
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
                    full_version = match.group(1).replace(".0", "").replace("1.", "")
                    java_exe_path_dict[java_path] = full_version
            except Exception as e:
                print(f"检查{java_path}时出现错误: {e}")
    return java_exe_path_dict

                    

if __name__ == "__main__":
    print(get_java_exe_dict())