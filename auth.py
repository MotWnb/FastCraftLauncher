import requests
import json
import time
import webbrowser
import pyperclip

# Azure应用程序的客户端ID
client_id = 'de243363-2e6a-44dc-82cb-ea8d6b5cd98d'

async def authenticate():
    # 获取设备代码
    device_code_url = 'https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode'
    device_code_data = {
        'client_id': client_id,
        'scope': 'XboxLive.signin offline_access'
    }
    device_code_headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        device_code_response = requests.post(device_code_url, data=device_code_data, headers=device_code_headers)
        device_code_response.raise_for_status()
        device_code_info = device_code_response.json()

        # 打开授权网址
        webbrowser.open(device_code_info['verification_uri'])

        # 复制设备代码到剪贴板
        pyperclip.copy(device_code_info['user_code'])

        print(f"请在以下网址输入代码进行授权：{device_code_info['verification_uri']}")
        print(f"设备代码（已复制到剪贴板）：{device_code_info['user_code']}")
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
        print(f"Response content: {device_code_response.content}")
        exit(1)
    except Exception as err:
        print(f"Other error occurred: {err}")
        exit(1)

    # 轮询用户授权状态
    token_url = 'https://login.microsoftonline.com/consumers/oauth2/v2.0/token'
    token_data = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
        'client_id': client_id,
        'device_code': device_code_info['device_code']
    }
    token_headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    while True:
        try:
            token_response = requests.post(token_url, data=token_data, headers=token_headers)
            token_info = token_response.json()
            if 'access_token' in token_info:
                break
            elif token_info.get('error') in ['authorization_pending', 'slow_down']:
                time.sleep(device_code_info['interval'])
            else:
                raise Exception(f"授权失败: {token_info}")
        except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
            print(f"Response content: {token_response.content}")
            exit(1)
        except Exception as err:
            print(f"Other error occurred: {err}")
            exit(1)

    access_token = token_info['access_token']
    refresh_token = token_info['refresh_token']

    # Xbox Live身份验证
    xbl_auth_url = 'https://user.auth.xboxlive.com/user/authenticate'
    xbl_auth_data = {
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": f"d={access_token}"
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT"
    }
    xbl_auth_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    xbl_auth_response = requests.post(xbl_auth_url, json=xbl_auth_data, headers=xbl_auth_headers)
    xbl_auth_response.raise_for_status()
    xbl_auth_info = xbl_auth_response.json()

    xbl_token = xbl_auth_info['Token']
    uhs = xbl_auth_info['DisplayClaims']['xui'][0]['uhs']

    # XSTS身份验证
    xsts_auth_url = 'https://xsts.auth.xboxlive.com/xsts/authorize'
    xsts_auth_data = {
        "Properties": {
            "SandboxId": "RETAIL",
            "UserTokens": [xbl_token]
        },
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT"
    }
    xsts_auth_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    xsts_auth_response = requests.post(xsts_auth_url, json=xsts_auth_data, headers=xsts_auth_headers)
    xsts_auth_response.raise_for_status()
    xsts_auth_info = xsts_auth_response.json()

    xsts_token = xsts_auth_info['Token']

    # 获取Minecraft访问令牌
    mc_auth_url = 'https://api.minecraftservices.com/authentication/login_with_xbox'
    mc_auth_data = {
        "identityToken": f"XBL3.0 x={uhs};{xsts_token}"
    }
    mc_auth_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    mc_auth_response = requests.post(mc_auth_url, json=mc_auth_data, headers=mc_auth_headers)
    mc_auth_response.raise_for_status()
    mc_auth_info = mc_auth_response.json()

    mc_access_token = mc_auth_info['access_token']

    # 检查游戏拥有情况
    entitlements_url = 'https://api.minecraftservices.com/entitlements/mcstore'
    entitlements_headers = {
        'Authorization': f'Bearer {mc_access_token}'
    }
    entitlements_response = requests.get(entitlements_url, headers=entitlements_headers)
    entitlements_response.raise_for_status()
    entitlements_info = entitlements_response.json()

    if not any(item['name'] == 'product_minecraft' for item in entitlements_info['items']):
        print("用户没有Minecraft")
        exit(1)

    # 获取玩家UUID
    profile_url = 'https://api.minecraftservices.com/minecraft/profile'
    profile_headers = {
        'Authorization': f'Bearer {mc_access_token}'
    }
    profile_response = requests.get(profile_url, headers=profile_headers)
    profile_response.raise_for_status()
    profile_info = profile_response.json()

    return {
        'username': profile_info['name'],
        'uuid': profile_info['id'],
        'access_token': mc_access_token,
        'refresh_token': refresh_token
    }

async def refresh_access_token(refresh_token):
    token_url = 'https://login.microsoftonline.com/consumers/oauth2/v2.0/token'
    token_data = {
        'grant_type': 'refresh_token',
        'client_id': client_id,
        'refresh_token': refresh_token
    }
    token_headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        token_response = requests.post(token_url, data=token_data, headers=token_headers)
        token_response.raise_for_status()
        token_info = token_response.json()
        return token_info['access_token'], token_info['refresh_token']
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
        print(f"Response content: {token_response.content}")
        return None, None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None, None