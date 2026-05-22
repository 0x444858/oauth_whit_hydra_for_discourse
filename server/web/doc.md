# OAuth 开发者文档

## QuickStart

此教程将带你走完本站完整的OAuth流程。自主注册客户端请见[客户端注册](#registerclients)。下文使用预注册好的[测试客户端](#test_clients)中的[local_test](#local_test)。

### 将用户引导至授权页面

首先你需要在**后端**生成一个`state`，这是一个随机字符串，约20个URL安全字符，用于防止CSRF攻击。该字符串需要存储并与当前会话关联。

例如：

```js
// javascript
function getRandomString() {
    const arr = new Uint8Array(20);
    crypto.getRandomValues(arr);
    return btoa(String.fromCharCode(...arr))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
```

```python
# python
import secrets
def get_random_string():
    return secrets.token_urlsafe(20)
```

接着，根据需要的`scope`和`redirect_uri`构造出授权链接。

`scope`的详细说明参见[scope](#scope)。

示例：

```js
// javascript
const params = new URLSearchParams({
    response_type: 'code',
    client_id: 'local_test',
    redirect_uri: 'http://127.0.0.1:48484/oauth_callback',
    scope: 'openid profile',
    state: state
});
const link = 'https://oursite.com/oauth2/auth?' + params.toString();

// 生成的完整链接：
// https://oursite.com/oauth2/auth?response_type=code&client_id=local_test&redirect_uri=http%3A%2F%2F127.0.0.1%3A48484%2Foauth_callback&scope=openid+profile&state=abcd1234
```

然后要求前端跳转至此地址。之后用户将经历以下流程：

1. Hydra 将用户重定向到本站 `/call/login`，本站检查用户是否已登录 Discourse
2. 若未登录，跳转到 Discourse 登录页；登录后自动回到授权流程
3. 已登录后，本站将用户身份告知 Hydra，Hydra 重定向到 `/call/consent` 展示**授权页面**
4. 用户在授权页面上可勾选/取消部分 scope（必选 scope 不可取消），然后点击"允许"或"拒绝"
5. 完成后 Hydra 将用户重定向到你的回调地址

### 获取授权码

用户在授权页面点击"允许"后，浏览器将跳转到你在上一步指定的回调地址（如 `/oauth_callback`），并在 URL 上附带以下参数。

一个完整的回调地址：

```text
http://127.0.0.1:48484/oauth_callback?code=ory_ac_DtP2DfFhbnYVPNGueDOJUoJmqVW4BiGsTObrulKfZms.bMG4rEW1liNV02mpEWzgv01VTCQhW1tPVBE3YOCpksU&scope=openid+profile+offline_access&state=abcd1234
```

URL 参数说明：

| 参数 | 说明 |
| ---- | ---- |
| `code` | 授权码，稍后用于换取 token。**一次性使用，有效期短** |
| `scope` | 用户实际授权的范围。可能与请求的 scope 不一致——用户在授权页面取消了部分权限，或敏感 scope 冲突导致 `offline_access` 被自动移除 |
| `state` | 你最初传入的 state 值，**必须校验与第一步生成的 state 一致**，防止 CSRF 攻击 |

校验 `state` 通过后，通过它找到对应的用户会话，以便获取 token 后将其与你自己的账号系统关联。

### 授权码换token

向地址`https://oursite.com/oauth2/token`发送POST请求。

需要将 `client_id:client_secret` 进行 base64 编码后放入 Authorization 头中，type 为 Basic。

示例：

```bash
# bash
# -u "user:pass" 会自动设置 Authorization: Basic base64(user:pass) 头
curl -X POST https://oursite.com/oauth2/token \
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

### 注册新客户端

访问 `https://oursite.com/call/manage` 进入用户面板，在"我的应用"页面可以自主注册OAuth客户端。

注册需要提供以下参数：

| 参数 | 说明 | 限制 |
| ---- | ---- | ---- |
| `client_id` | 客户端唯一标识符 | 3-64个字符，仅允许字母、数字、下划线(`_`)和连字符(`-`) |
| `client_name` | 客户端显示名称 | 最长64个字符 |
| `redirect_uris` | 回调地址列表 | 不允许使用 `http://`（生产环境），不允许包含 `*` `#` `?` |
| `scope` | 请求的权限范围 | 空格分隔的scope列表，参见[scope](#scope) |

提交后，系统会返回 `client_secret`，请妥善保管，**该值仅显示一次**。

### 注册权限控制

管理员可通过系统设置控制注册行为：

- **allow_new_client_apply**：设为 `f` 时禁止所有非管理员用户注册新客户端
- **new_apply_allowed_group_ids**：JSON数组格式的群组ID白名单（如 `[12,50,51]`），仅这些群组的成员可以注册。留空则不限制

### 管理已有客户端

在用户面板的"我的应用"页面，可以对已注册的客户端进行以下操作：

- **修改基本信息**：修改 `client_name`、`redirect_uris`、`scope`
- **重置密钥**：生成新的 `client_secret`（旧密钥立即失效）
- **转让所有权**：管理员可将客户端转让给其他用户
- **删除客户端**：永久删除客户端，所有已颁发的token保持有效直到过期

所有操作均记录在变更日志中，可在管理面板查询。

### 授予类型

注册的客户端默认支持以下 OAuth 2.0 授予类型：

- **authorization_code**：授权码模式（推荐用于服务端应用）
- **refresh_token**：刷新令牌（需同时请求 `offline_access` scope）

客户端认证方式为 `client_secret_basic`（HTTP Basic Authentication）。

## scope

### 可用 scope 列表

| Scope | 说明 | 敏感 |
| ----- | ---- | ---- |
| `openid` | 验证用户身份，获取用户UID。**必须请求** | 否 |
| `profile` | 获取用户公开资料：UID、用户名、别名、头像、头衔、信任级别、管理员/版主状态、群组列表 | 否 |
| `active` | 获取用户活跃数据：注册时间、访问天数、被举报数、最后活动时间、获赞数、发帖数等。**需要先授权 `profile`** | 否 |
| `email_domain` | 获取用户邮箱的域名部分。**需要先授权 `email_domain` 才能请求 `email`** | 否 |
| `email` | 获取用户完整邮箱地址。**敏感scope** | 是 |
| `offline_access` | 允许使用 refresh_token 保持登录状态，无需用户反复授权 | 否 |

### scope 层级关系

scope 之间存在父子层级关系。用户取消父scope的授权时，子scope会被自动禁用：

```text
openid                    （独立，必须授权）
profile                   （独立）
  └── active              （需要先授权 profile）
email_domain              （独立）
  └── email               （需要先授权 email_domain，且为敏感scope）
offline_access            （独立）
```

### 敏感 scope 限制

被标记为**敏感scope**（当前仅有 `email`）具有以下限制：

- **不能与 `offline_access` 同时授权**：如果用户在授权页面同时勾选了 `email` 和 `offline_access`，系统会自动取消并禁用 `offline_access`
- **token 有效期受限**：包含敏感scope的token有效期仅为30秒（由配置项 `sensitive_token_exp` 控制），过期后需重新通过完整的授权流程获取

## userInfos

### GET /call/userinfo

获取用户资料。需要在请求头中携带 Bearer token（需包含 `profile` scope）。

**请求头：**

```http
Authorization: Bearer <access_token>
```

**查询参数：**

| 参数 | 说明 |
| ---- | ---- |
| `additional` | 设为 `active` 时，额外返回活跃数据（需token同时包含 `active` scope） |

**基础响应**（scope: `profile`）：

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
        {"id": 10, "name": "trust_level_0"},
        {"id": 11, "name": "trust_level_1"}
    ]
}
```

**附加字段**（`?additional=active`，scope: `profile active`）：

```json
{
    ...基础字段,
    "created_at": "注册时间",
    "days_visited": 访问天数,
    "flags_received_count": 被举报次数,
    "last_seen_at": "最后活动时间",
    "like_count": 获赞数,
    "like_given_count": 点赞数,
    "post_count": 发帖数,
    "posts_read_count": 阅读帖子数,
    "time_read": 阅读总秒数,
    "topic_count": 主题数,
    "topics_entered": 阅读主题数
}
```

### GET /call/userinfo/email

获取用户邮箱信息。需要在请求头中携带 Bearer token（需包含 `email_domain` scope）。

**请求头：**

```http
Authorization: Bearer <access_token>
```

**查询参数：**

| 参数 | 说明 |
| ---- | ---- |
| `additional` | 设为 `email` 时，返回完整邮箱地址（需token同时包含 `email` scope） |

**基础响应**（scope: `email_domain`）：

```json
{
    "email_domain": "example.com",
    "secondary_email_domains": ["other.com"]
}
```

**完整响应**（`?additional=email`，scope: `email_domain email`）：

```json
{
    "email": "user@example.com",
    "secondary_emails": ["user@other.com"]
}
```

## tokens

### Token 类型

| 类型 | 用途 | 说明 |
| ---- | ---- | ---- |
| `access_token` | 访问受保护资源 | JWT格式，有效期由Hydra配置决定 |
| `refresh_token` | 刷新 access_token | 仅当授权了 `offline_access` scope 时发放 |
| `id_token` | 身份信息 | JWT格式，包含用户身份声明 |

### 使用 refresh_token 刷新 access_token

向 `https://oursite.com/oauth2/token` 发送POST请求：

```bash
curl -X POST https://oursite.com/oauth2/token \
  -u "client_id:client_secret" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=<your_refresh_token>"
```

```python
import requests
from requests.auth import HTTPBasicAuth

response = requests.post(
    "https://oursite.com/oauth2/token",
    data={
        "grant_type": "refresh_token",
        "refresh_token": "<your_refresh_token>"
    },
    auth=HTTPBasicAuth(client_id, client_secret)
)
print(response.json())
```

返回格式与授权码换token相同，包含新的 `access_token` 和 `refresh_token`。

### 吊销 token

用户可以在 `https://oursite.com/call/manage` 的"已授权应用"页面主动吊销某个客户端的所有token，或吊销全部客户端的token。

吊销操作会立即生效，被吊销的 access_token 和 refresh_token 将无法再使用。

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
