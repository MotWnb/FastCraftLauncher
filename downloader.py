import aiohttp
import asyncio
import os
import json
import time
import hashlib
import logging
import platform
import zipfile

async def calculate_file_hash(path, hash_algorithm='sha1'):
    hash_func = hashlib.new(hash_algorithm)
    if not os.path.exists(path):
        logging.error(f"File {path} does not exist for hash calculation.")
        return None
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            hash_func.update(chunk)
    return hash_func.hexdigest()

async def download_file(session, url, path, expected_hash=None):
    logging.debug(f"Starting download: {url} -> {path}")
    if os.path.exists(path):
        if expected_hash:
            file_hash = await calculate_file_hash(path)
            if file_hash == expected_hash:
                logging.debug(f"File {path} already exists and hash matches, skipping download.")
                return
        else:
            logging.debug(f"File {path} already exists, skipping download.")
            return

    async with session.get(url) as response:
        if response.status == 200:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                while chunk := await response.content.read(1024):
                    if not chunk:
                        break
                    f.write(chunk)
            logging.debug(f"Finished download: {url} -> {path}")

    if expected_hash:
        file_hash = await calculate_file_hash(path)
        if file_hash != expected_hash:
            logging.debug(f"File {path} hash mismatch after download. Expected {expected_hash}, got {file_hash}.")
            await download_file(session, url, path, expected_hash)
        else:
            logging.debug(f"File {path} downloaded and hash matches.")

async def download_files(file_urls):
    async with aiohttp.ClientSession() as session:
        tasks = [download_file(session, url, path, expected_hash) for url, path, expected_hash in file_urls]
        await asyncio.gather(*tasks)

async def download_version_json(version_manifest_url, version):
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        async with session.get(version_manifest_url) as response:
            manifest = await response.json()
            version_info = next((v for v in manifest['versions'] if v['id'] == version), None)
            if version_info:
                async with session.get(version_info['url']) as version_response:
                    version_data = await version_response.json()
                    version_dir = f'.minecraft/versions/{version}'
                    os.makedirs(version_dir, exist_ok=True)
                    with open(f'{version_dir}/{version}.json', 'w') as f:
                        json.dump(version_data, f, indent=4)
                    logging.info(f"Downloaded version JSON in {time.time() - start_time:.2f} seconds")
                    return version_data
    logging.error(f"Failed to download version JSON in {time.time() - start_time:.2f} seconds")
    return None

async def download_assets(version_data):
    start_time = time.time()
    asset_index_url = version_data['assetIndex']['url']
    asset_index_path = f'.minecraft/assets/indexes/{version_data["assetIndex"]["id"]}.json'
    await download_files([(asset_index_url, asset_index_path, None)])
    
    with open(asset_index_path, 'r') as f:
        asset_index = json.load(f)
    
    asset_tasks = [(f'https://resources.download.minecraft.net/{asset["hash"][:2]}/{asset["hash"]}', 
                    f'.minecraft/assets/objects/{asset["hash"][:2]}/{asset["hash"]}', 
                    asset['hash']) for asset in asset_index['objects'].values()]
    
    await download_files(asset_tasks)
    logging.info(f"Downloaded assets in {time.time() - start_time:.2f} seconds")

def get_os_name():
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    
    if os_name == 'windows':
        return 'windows' if arch == 'amd64' else 'windows-x86' if arch == 'x86' else 'windows-arm64'
    elif os_name == 'linux':
        return 'linux'
    elif os_name == 'darwin':
        return 'macos-arm64' if arch == 'arm64' else 'macos'
    else:
        raise ValueError(f"Unsupported OS: {os_name}")

async def download_libraries(version_data, os_name):
    start_time = time.time()
    library_tasks = []
    natives_paths = []
    
    for library in version_data['libraries']:
        if 'downloads' in library:
            if 'artifact' in library['downloads']:
                artifact = library['downloads']['artifact']
                url = artifact['url']
                path = f'.minecraft/libraries/{artifact["path"]}'
                if "natives" in library['downloads']['artifact']['path']:
                    if f'natives-{os_name}.' in library['downloads']['artifact']['path']:
                        natives_paths.append(path)
                    else:
                        continue
                library_tasks.append((url, path, artifact.get('sha1')))
            if 'classifiers' in library['downloads']:
                for classifier_name, classifier in library['downloads']['classifiers'].items():
                    url = classifier['url']
                    path = f'.minecraft/libraries/{classifier["path"]}'
                    library_tasks.append((url, path, classifier.get('sha1')))
                    if f'natives-{os_name}.' in classifier['path']:
                        natives_paths.append(path)
    
    logging.info(f"Total libraries to download: {len(library_tasks)}")
    await download_files(library_tasks)
    logging.info(f"Downloaded libraries in {time.time() - start_time:.2f} seconds")
    
    return natives_paths

def extract_natives(natives_paths, version, arch):
    natives_dir = f'.minecraft/versions/{version}/{version}-natives'
    os.makedirs(natives_dir, exist_ok=True)
    
    for path in natives_paths:
        with zipfile.ZipFile(path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.startswith('META-INF/') or file_info.filename.endswith('.git') or file_info.filename.endswith('.sha1'):
                    continue
                if not file_info.filename:
                    continue
                if file_info.filename.endswith('/'):
                    continue
                if arch == 'amd64':
                    if '32' in file_info.filename:
                        continue
                    if 'x86' in file_info.filename:
                        continue
                if arch == 'x86':
                    if '32' in file_info.filename or 'x86' in file_info.filename:
                        file_info.filename = os.path.basename(file_info.filename)
                        zip_ref.extract(file_info, natives_dir)
                        continue
                    if '64' in file_info.filename:
                        continue
                file_info.filename = os.path.basename(file_info.filename)
                zip_ref.extract(file_info, natives_dir)

async def download_version_jar(version_data):
    start_time = time.time()
    version_jar_url = version_data['downloads']['client']['url']
    version_jar_path = f'.minecraft/versions/{version_data["id"]}/{version_data["id"]}.jar'
    await download_files([(version_jar_url, version_jar_path, version_data['downloads']['client'].get('sha1'))])
    end_time = time.time()
    logging.info(f"Downloaded version JAR in {end_time - start_time:.2f} seconds")

async def download_log4j(version_data):
    start_time = time.time()
    log4j_info = version_data.get('logging', {}).get('client', {}).get('file', {})
    if log4j_info:
        log4j_url = log4j_info['url']
        log4j_path = f'.minecraft/logs/{log4j_info["id"]}'
        await download_files([(log4j_url, log4j_path, log4j_info.get('sha1'))])
        logging.info(f"Downloaded log4j configuration in {time.time() - start_time:.2f} seconds")
        return log4j_path
    logging.error("Log4j configuration not found in version data")
    return None

async def download(version):
    version_manifest_url = 'https://piston-meta.mojang.com/mc/game/version_manifest.json'
    
    start_time = time.time()
    version_data = await download_version_json(version_manifest_url, version)
    if version_data:
        os_name = get_os_name()
        arch = platform.machine().lower()
        
        # 并行执行所有下载任务
        natives_paths, _, _, _ = await asyncio.gather(
            download_libraries(version_data, os_name),
            download_version_jar(version_data),
            download_assets(version_data),
            download_log4j(version_data)
        )
        extract_natives(natives_paths, version, arch)
    logging.info(f"Total time: {time.time() - start_time:.2f} seconds")