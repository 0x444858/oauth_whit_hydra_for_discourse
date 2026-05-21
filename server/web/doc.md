# OAuth 开发者文档

## QuickStart

此教程将带你走完本站完整的OAuth流程。自主注册客户端请见[客户端注册](#registerclients)。下文使用预注册好的[测试客户端](#test_clients)中的[local_test](#local_test)。

### 将用户引导至本站

首先你需要在**后端**生成一个`state`，这是一个随机字符串，大约20个url安全字符，用于防止CSRF攻击。该字符串需要存储并于此次会话关联。
例如：

```js
// javascript
function getRandomString() {
    return Math.random().toString(36).substr(2) + Math.random().toString(36).substr(2);
}
```

```python
# python
import secrets
def get_random_string():
    return secrets.token_urlsafe(20)
```

接着，根据需要的`scope`和`redirect_uri`，构造出授权链接。

`scope`的详细说明参见[scope](#scope)。

示例：

```js
// javascript
// 链接格式
let link = 'https://oursite.com/oauth2/auth?'
    + 'response_type=code&' // 固定
    + 'client_id=local_test&' // 客户端id
    + 'redirect_uri=http%3A%2F%2F127.0.0.1%3A48484%2Foauth_callback&' // url编码后的回调地址
    + 'scope=' + encodeURIComponent(scope) + '&' // url编码后的scope
    + 'state=' + state; // 生成的state

// 一个完整链接的样子
const full_link = 'https://oursite.com/oauth2/auth?'
+ 'response_type=code&'
+ 'client_id=local_test&'
+ 'redirect_uri=http%3A%2F%2F127.0.0.1%3A48484%2Foauth_callback&'
+ 'scope=openid+profile&'
+ 'state=abcd1234';
```

接着要求前端跳转至此地址。等待用户授权完成。

### 获取授权码

授权完成后，用户将跳转到回调地址，此时会带上`code`参数。你需要实现回调地址的端点，例如上文中的`/oauth_callback`。

一个完整的回调地址如下

```text
http://127.0.0.1:48484/oauth_callback?code=ory_ac_DtP2DfFhbnYVPNGueDOJUoJmqVW4BiGsTObrulKfZms.bMG4rEW1liNV02mpEWzgv01VTCQhW1tPVBE3YOCpksU&scope=openid+profile+offline_access&state=abcd1234
```

其中，`code`为授权码，稍后换取`token`需要；`scope`为实际授权范围，与请求的范围不一定一致，可能减少；`state`为请求的`state`，应与最开始生成的state一致。

接着通过`state`判断出这是哪个用户的会话，以便获取`token`后将其与你自己的账号系统关联。

### 授权码换token

向地址`https://oursite.com/oauth2/token`发送POST请求。

需要将 `client_id:client_secret` 进行 base64 编码后放入 Authorization 头中，type 为 Basic。

示例：

```bash
# bash
# -u "user:pass" 会自动设置 Authorization: Basic base64(user:pass) 头
curl -X POST https://ouesite.com/oauth2/token \
  -u "local_test:ZPbZVRb5tYkGFSU4g-G.ESKhDt" \
  -d "grant_type=authorization_code" \
  -d "code=ory_ac_DtP2DfFhbnYVPNGueDOJUoJmqVW4BiGsTObrulKfZms.bMG4rEW1liNV02mpEWzgv01VTCQhW1tPVBE3YOCpksU" \
  -d "redirect_uri=http://127.0.0.1:48484/oauth_callback"

```

```js
// node.js
const https = require('https');
const querystring = require('querystring');

const postData = querystring.stringify({
    grant_type: 'authorization_code',
    code: 'ory_ac_DtP2DfFhbnYVPNGueDOJUoJmqVW4BiGsTObrulKfZms.bMG4rEW1liNV02mpEWzgv01VTCQhW1tPVBE3YOCpksU',
    redirect_uri: 'http://127.0.0.1:48484/oauth_callback'
});

const options = {
    hostname: 'oursite.com',
    port: 443,
    path: '/oauth2/token',
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': postData.length,
        'Authorization': 'Basic ' + Buffer.from('local_test:ZPbZVRb5tYkGFSU4g-G.ESKhDt').toString('base64')
    }
};

const req = https.request(options, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => console.log(JSON.parse(data)));
});

req.write(postData);
req.end();
```

```python
# python
import requests
from requests.auth import HTTPBasicAuth

token_url = "https://oursite.com/oauth2/token"
client_id = "local_test"
client_secret = "ZPbZVRb5tYkGFSU4g-G.ESKhDt"
auth_code = "ory_ac_DtP2DfFhbnYVPNGueDOJUoJmqVW4BiGsTObrulKfZms.bMG4rEW1liNV02mpEWzgv01VTCQhW1tPVBE3YOCpksU"
redirect_uri = "http://127.0.0.1:48484/oauth_callback"

data = {
    "grant_type": "authorization_code",
    "code": auth_code,
    "redirect_uri": redirect_uri
}

# HTTPBasicAuth 会自动将 client_id:client_secret 编码并放入 Authorization 头
response = requests.post(
    url=token_url,
    data=data,
    auth=HTTPBasicAuth(client_id, client_secret)
)

print("Status Code:", response.status_code)
print("Response JSON:", response.json())
```

如果正确，服务器会返回如下响应：

```json
{
    "access_token": "eyJhbGciOiJSUzI1NiIsImt...",
    "expires_in": 0,
    "id_token": "eyJhbGciOiJSUzI1NiIsImt...",
    "scope": "openid profile offline_access",
    "token_type": "bearer"
}
```

`refresh_token`的使用参见[token](#tokens)。

### 请求用户信息

地址：`https://oursite.com/call/userinfo`。

需要将token放入Authorization头中，type为Bearer。

```python
# python
import requests

url = "https://oursite.com/call/userinfo"
access_token = "eyJhbGciOiJSUzI1NiIsImt..."
response = requests.get(
    url,
    headers={'Authorization': f'Bearer {access_token}'}
)
print("Status Code:", response.status_code)
print("Response JSON:", response.json())
```

如果正确，服务器会返回如下响应：

```json
{
    "id": 0,
    "username": "用户名",
    "name": "别名",
    "avatar_template": "头像模板url",
    "title": "用户头衔",
    "trust_level": 4,
    "admin": false,
    "moderator": false,
    "groups": [
        {
            "id": 10,
            "name": "trust_level_0"
        },
        {
            "id": 11,
            "name": "trust_level_1"
        },
        {
            "id": 12,
            "name": "trust_level_2"
        },
        {
            "id": 13,
            "name": "trust_level_3"
        },
        {
            "id": 14,
            "name": "trust_level_4"
        }
    ]
}
```

用户信息的详细说明参见[用户信息](#userinfos)。

## RegisterClients

## scope

## userInfos

## tokens

## test_clients

此处公开预注册的测试客户端的信息，方便开发测试。

### local_test

| 参数 | 值 |
| --- | --- |
| client_id | local_test |
| client_name | 本地测试客户端 |
| redirect_uris | `http://127.0.0.1:48484/oauth_callback` |
| scope | `openid profile active offline_access email_domain email` |
| client_secret | `ZPbZVRb5tYkGFSU4g-G.ESKhDt` |
