import os
import json
import uuid as uuid_lib
import subprocess
import re
import aiohttp
import auth
from java_finder import find_java_version

def format_log4j_event(line, printed_logs):
    match = re.search(r'<log4j:Message><!\[CDATA\[(.*?)\]\]></log4j:Message>\s', line, re.DOTALL)
    if match:
        message = match.group(1)
        if message not in printed_logs:
            printed_logs.add(message)
            information = f"{message}\n"
            return information
    return None

async def fetch_json(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()

async def find_java():
    java_path = None
    for path in os.environ['PATH'].split(';'):
        if os.path.exists(os.path.join(path, 'java.exe')):
            java_path = os.path.join(path, 'java.exe')
            break
    return java_path

def replace_and_clean_args(args, replacements):
    for key, value in replacements.items():
        args = args.replace(key, value)
    # 删除未被替换的变量
    args = re.sub(r'\$\{[^\}]+\}', '', args)
    return args

async def generate_and_run_bat(game_dir, version, auth_player_name, uuid, access_token):
    async with aiohttp.ClientSession() as session:
        # 获取版本json文件
        version_manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
        version_manifest = await fetch_json(session, version_manifest_url)
        version_url = next(v['url'] for v in version_manifest['versions'] if v['id'] == version)
        version_json = await fetch_json(session, version_url)

        log4j_path = f"{game_dir}\\logs\\{version_json.get('logging', {}).get('client', {}).get('file', {}).get('id')}"
        
        version_folder = os.path.join(game_dir, 'versions', version)

        version_name = version
        assets_root = os.path.join(game_dir, 'assets')
        assets_index_name = version_json['assetIndex']['id']
        userType = "msa"
        version_type = version_json['type']
        clientid = "00000000402b5328"

        natives_directory = os.path.join(game_dir, 'versions', version, f'{version}-natives')
        launcher_name = "FastCraftLauncher"
        launcher_version = "1.0"
        
        libraries = [os.path.join(game_dir, 'libraries', lib['downloads']['artifact']['path']) for lib in version_json['libraries'] if 'downloads' in lib and 'artifact' in lib['downloads']]
        libraries.append(f"{os.path.join(game_dir, 'versions', version, f'{version}.jar')}")
        classpath = ";".join(libraries)

        if "arguments" in version_json:
            game_args = ""
            java_args = " -XX:+UseG1GC -XX:-UseAdaptiveSizePolicy -XX:-OmitStackTraceInFastThrow -Djdk.lang.Process.allowAmbiguousCommands=true -Dfml.ignoreInvalidMinecraftCertificates=True -Dfml.ignorePatchDiscrepancies=True -Dlog4j2.formatMsgNoLookups=true"
            for arg in version_json["arguments"]["game"]:
                if not isinstance(arg, dict):
                    game_args += f" {arg}"
            for arg in version_json["arguments"]["jvm"]:
                if not isinstance(arg, dict):
                    java_args += f" {arg}"
        elif "minecraftArguments" in version_json:
            game_args = version_json["minecraftArguments"]
            java_args = " -Djava.library.path=${natives_directory} -cp ${classpath}"

        replacements = {
            "${auth_player_name}": auth_player_name,
            "${version_name}": version_name,
            "${game_directory}": game_dir,
            "${assets_root}": assets_root,
            "${assets_index_name}": assets_index_name,
            "${auth_uuid}": uuid,
            "${auth_access_token}": access_token,
            "${clientid}": clientid,
            "${auth_xuid}": "",
            "${user_type}": userType,
            "${natives_directory}": natives_directory,
            "${launcher_name}": launcher_name,
            "${launcher_version}": launcher_version,
            "${classpath}": classpath,
            "${version_type}": version_type
        }

        game_args = replace_and_clean_args(game_args, replacements)
        java_args = replace_and_clean_args(java_args, replacements)

        java_version = str(version_json["javaVersion"]["majorVersion"])
        java_path = find_java_version(java_version)
        print(f"Java路径: {java_path}")
        command = java_path + java_args + " net.minecraft.client.main.Main " + game_args

        bat_file_path = "launch_minecraft.bat"
        with open(bat_file_path, "w", encoding="utf-8") as bat_file:
            bat_file.write("@echo off\n")
            bat_file.write("echo Running Minecraft...\n")
            bat_file.write("echo Command: " + command + "\n")
            bat_file.write(command + "\n")
            bat_file.write("pause\n")

        options_path = os.path.join(game_dir, 'options.txt')
        if not os.path.exists(options_path):
            options = {
                "lang": "zh_CN",
                "gamma": "1.0",
                "maxFps": "260",
                "narrator": 0
            }
            with open(options_path, "w", encoding="utf-8") as options_file:
                for key, value in options.items():
                    options_file.write(f"{key}:{value}\n")
        print(f"Batch file created: {bat_file_path}")

        printed_logs = set()
        with subprocess.Popen([bat_file_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="latin-1") as proc:
            if proc.stdout:
                print("Minecraft启动中...")
                for line in proc.stdout:
                    line = line.replace('\r\n', '\n').replace('\r', '\n')
                    formatted_line = format_log4j_event(line, printed_logs)
                    if formatted_line:
                        print(formatted_line, end='')

            stdout, stderr = proc.communicate()
            print("游戏进程已结束")
            if stdout:
                for line in stdout.splitlines():
                    line = line.replace('\r\n', '\n').replace('\r', '\n')
                    formatted_line = format_log4j_event(line, printed_logs)
                    if formatted_line:
                        print(formatted_line, end='')

async def launch_game():
    # 先探测是否有versions
    if not os.path.exists('.minecraft/versions'):
        print("没有找到Minecraft版本，请先下载")
        return
    
    mode = input("请选择启动模式（1：离线启动，2：使用正版账户）：")
    if mode == '1':
        username = input("请输入用户名：")
        print("生成UUID和访问令牌...")
        uuid = str(uuid_lib.uuid3(uuid_lib.NAMESPACE_DNS, username))
        access_token = str(uuid_lib.uuid3(uuid_lib.NAMESPACE_DNS, username))
        print("UUID:", uuid)
    elif mode == '2':
        accounts = {}
        if os.path.exists('refresh_token.json'):
            with open('refresh_token.json', 'r') as f:
                accounts = json.load(f)

        if accounts:
            print("已保存的账户：")
            for i, account in enumerate(accounts.keys(), start=1):
                print(f"{i}: {account}")
            print(f"{len(accounts) + 1}: 添加新账户")
            choice = int(input("请选择账户："))

            if choice == len(accounts) + 1:
                auth_info = await auth.authenticate()
                accounts[auth_info['username']] = auth_info['refresh_token']
                with open('refresh_token.json', 'w') as f:
                    json.dump(accounts, f)
            else:
                selected_account = list(accounts.keys())[choice - 1]
                refresh_token = accounts[selected_account]
                access_token, new_refresh_token = await auth.refresh_access_token(refresh_token)
                if access_token:
                    print(f"使用refresh token获取新的access token成功，账户：{selected_account}")
                    accounts[selected_account] = new_refresh_token
                    with open('refresh_token.json', 'w') as f:
                        json.dump(accounts, f)
                    auth_info = {
                        'username': selected_account,
                        'uuid': str(uuid_lib.uuid3(uuid_lib.NAMESPACE_DNS, selected_account)),
                        'access_token': access_token,
                        'refresh_token': new_refresh_token
                    }
                else:
                    print(f"使用refresh token失败，重新认证，账户：{selected_account}")
                    auth_info = await auth.authenticate()
                    accounts[selected_account] = auth_info['refresh_token']
                    with open('refresh_token.json', 'w') as f:
                        json.dump(accounts, f)
        else:
            print("没有找到保存的账户，添加新账户")
            auth_info = await auth.authenticate()
            accounts[auth_info['username']] = auth_info['refresh_token']
            with open('refresh_token.json', 'w') as f:
                json.dump(accounts, f)

        username = auth_info['username']
        uuid = auth_info['uuid']
        access_token = auth_info['access_token']
    else:
        print("无效的选择")
        return

    # gamedir为当前目录下的.minecraft文件夹
    game_dir = os.path.join(os.getcwd(), '.minecraft')
    # 把versions目录下的文件夹名字做成列表
    versions = os.listdir(os.path.join(game_dir, 'versions'))
    version = input("请输入Minecraft版本 " + str(versions) + " ：")
    await generate_and_run_bat(
        game_dir=game_dir,
        version=version,
        auth_player_name=username,
        uuid=uuid,
        access_token=access_token
    )
