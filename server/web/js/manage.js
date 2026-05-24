function getExtraParams() {
    return {};
}

function objectToFormString(obj) {
    if (!obj || typeof obj !== 'object' || Object.keys(obj).length === 0) {
        return '';
    }
    const params = [];
    for (const [key, value] of Object.entries(obj)) {
        let encodedValue;
        if (value === null || value === undefined) {
            encodedValue = '';
        } else if (typeof value === 'object') {
            encodedValue = JSON.stringify(value);
        } else {
            encodedValue = String(value);
        }
        params.push(`${key}=${encodeURIComponent(encodedValue)}`);
    }
    return params.join('&');
}

// 撤销所有授权
function revoke_all(button) {
    if (!confirm('确定要撤销所有应用的授权吗？此操作不可逆')) {
        return;
    }
    const d = { all: true, ...getExtraParams() };
    revokeRequest(d, button, true);
}

// 撤销单个客户端授权
function revoke_token(button, client_id, client_name) {
    client = client_name && client_name != client_id ? `${client_name} (ID: ${client_id})` : client_id;
    if (!confirm(`确定要撤销应用 ${client} 的授权吗？`)) {
        return;
    }
    const d = { client_id: client_id, ...getExtraParams() };
    revokeRequest(d, button, false);
}

// 撤销执行授权请求
function revokeRequest(params, triggerButton, isRevokeAll) {
    triggerButton.disabled = true;
    triggerButton.textContent = '撤销中...';
    fetch('/call/manage/revoke', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(params)
    })
        .then(response => {
            if (response.status === 204) {
                if (isRevokeAll) {
                    const t_body = document.getElementById('authManagementTableBody');
                    if (t_body) {
                        const rows = t_body.querySelectorAll('tr');
                        rows.forEach(row => {
                            row.classList.add('disabled');
                            const btns = row.querySelectorAll('button');
                            btns.forEach(btn => {
                                btn.disabled = true;
                                btn.textContent = '已撤销';
                            });
                        });
                    }
                    triggerButton.disabled = true;
                    triggerButton.textContent = '已撤销';
                } else {
                    const row = triggerButton.closest('tr');
                    if (row) {
                        row.classList.add('disabled');
                        const btns = row.querySelectorAll('button');
                        btns.forEach(btn => {
                            btn.disabled = true;
                            btn.textContent = '已撤销';
                        });
                    }
                }
            } else {
                return response.text().then(text => {
                    throw new Error(text || `HTTP ${response.status}`);
                });
            }
        })
        .catch(error => {
            console.error('撤销请求失败:', error);
            alert('撤销失败：' + error.message);
            triggerButton.disabled = false;
            triggerButton.textContent = isRevokeAll ? '全部撤销' : '撤销';
        });
}

// 格式化时间戳为 YYYY-MM-DD HH:mm:ss
function formatDate(timestampSec) {
    const accessDate = new Date(timestampSec * 1000);
    const year = accessDate.getFullYear();
    const month = String(accessDate.getMonth() + 1).padStart(2, '0');
    const day = String(accessDate.getDate()).padStart(2, '0');
    const hours = String(accessDate.getHours()).padStart(2, '0');
    const minutes = String(accessDate.getMinutes()).padStart(2, '0');
    const seconds = String(accessDate.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

// 加载更多授权数据
function loadMoreAuthData(button) {
    const t_body = document.getElementById('authManagementTableBody');
    const scope_row = document.getElementById('authManagementScopeRow');
    button.disabled = true;
    button.textContent = '加载中...';
    let url = '/call/manage/authData'
    const p = objectToFormString(getExtraParams());
    if (p) url += '?' + p;
    fetch(url)
        .then(response => {
            if (!response.ok) {
                const msg = `HTTP error! status: ${response.status}`;
                alert(msg);
                button.disabled = false;
                button.textContent = '加载更多';
                throw new Error(msg);
            }
            return response.json();
        })
        .then(data => {
            const authDataList = data.auth_data || [];
            const clientDict = data.client_dict || {};
            const scopeList = [];
            if (scope_row) {
                const scopeThs = scope_row.querySelectorAll('th[data-type="scope"]');
                scopeThs.forEach(th => {
                    scopeList.push(th.textContent.trim());
                });
            }
            if (!authDataList || authDataList.length === 0) {
                button.disabled = true;
                button.textContent = '无更多数据';
                return;
            }
            authDataList.forEach(item => {
                const row = document.createElement('tr');
                const clientName = clientDict[item.client_id] || item.client_id;
                let tokenInfo = '';
                if (item.expires_at === 0) {
                    tokenInfo = '刷新令牌<br><small>长期有效</small>';
                } else {
                    const formattedDate = formatDate(item.expires_at);
                    tokenInfo = `访问令牌<br><small>${formattedDate}</small>`;
                }
                const grantedSet = new Set(item.granted_scope || []);
                const cellClientId = document.createElement('td');
                cellClientId.textContent = item.client_id;
                row.appendChild(cellClientId);
                const cellClientName = document.createElement('td');
                cellClientName.textContent = clientName;
                row.appendChild(cellClientName);
                const cellTokenInfo = document.createElement('td');
                cellTokenInfo.innerHTML = tokenInfo;
                row.appendChild(cellTokenInfo);
                scopeList.forEach(scope => {
                    const cellScope = document.createElement('td');
                    cellScope.textContent = grantedSet.has(scope) ? '✓' : '';
                    row.appendChild(cellScope);
                });
                const cellAction = document.createElement('td');
                const revokeBtn = document.createElement('button');
                revokeBtn.className = 'c';
                revokeBtn.textContent = '撤销';
                revokeBtn.onclick = () => revoke_token(revokeBtn, item.client_id, clientName);
                cellAction.appendChild(revokeBtn);
                row.appendChild(cellAction);
                t_body.appendChild(row);
            });
            button.disabled = true;
            button.textContent = '无更多数据';
        })
        .catch(error => {
            console.error(error);
            button.disabled = false;
            button.textContent = '加载更多';
            alert('加载授权数据失败，请稍后重试');
        });
}

// 加载更多日志数据
let lastLogTimestamp = null;
function loadMoreAppLog(button) {
    const t_body = document.getElementById('appLogsTableBody');
    const scope_row = document.getElementById('appLogsScopeRow');
    button.disabled = true;
    button.textContent = '加载中...';
    let url = '/call/manage/appLog';
    let pd = getExtraParams();
    if (lastLogTimestamp !== null) pd = { ...pd, time_limit: lastLogTimestamp };
    p = objectToFormString(pd);
    if (p) url += '?' + p;
    fetch(url)
        .then(response => {
            if (!response.ok) {
                const msg = `HTTP error! status: ${response.status}`;
                alert(msg);
                button.disabled = false;
                button.textContent = '加载更多';
                throw new Error(msg);
            }
            return response.json();
        })
        .then(data => {
            const logsList = data.logs || [];
            const clientDict = data.client_dict || {};
            const scopeList = [];
            if (scope_row) {
                const scopeThs = scope_row.querySelectorAll('th[data-type="scope"]');
                scopeThs.forEach(th => {
                    scopeList.push(th.textContent.trim());
                });
            }
            if (!logsList || logsList.length === 0) {
                button.disabled = true;
                button.textContent = '无更多数据';
                return;
            }
            const lastLog = logsList[logsList.length - 1];
            if (lastLog && lastLog.accessed_at) {
                lastLogTimestamp = lastLog.accessed_at;
            }
            logsList.forEach(item => {
                const row = document.createElement('tr');
                const clientName = clientDict[item.client_id] || item.client_id;
                const target = window.current_user.id === item.uid ? window.current_user.username : `(UID: ${item.uid})`;
                const formattedDate = formatDate(item.accessed_at);
                const scopeUsedSet = new Set(item.scope_used ? item.scope_used.split(' ') : []);
                const cellClientId = document.createElement('td');
                cellClientId.textContent = item.client_id;
                row.appendChild(cellClientId);
                const cellClientName = document.createElement('td');
                cellClientName.textContent = clientName;
                row.appendChild(cellClientName);
                const cellTarget = document.createElement('td');
                cellTarget.textContent = target;
                row.appendChild(cellTarget);
                const cellAccessTime = document.createElement('td');
                cellAccessTime.textContent = formattedDate;
                row.appendChild(cellAccessTime);
                scopeList.forEach(scope => {
                    const cellScope = document.createElement('td');
                    cellScope.textContent = scopeUsedSet.has(scope) ? '✓' : '';
                    row.appendChild(cellScope);
                });
                t_body.appendChild(row);
            });
            if (logsList.length < 20) {
                button.disabled = true;
                button.textContent = '无更多数据';
            } else {
                button.disabled = false;
                button.textContent = '加载更多';
            }
        })
        .catch(error => {
            console.error('加载应用日志失败:', error);
            button.disabled = false;
            button.textContent = '加载更多';
            alert('加载应用日志失败，请稍后重试');
        });
}

// 申请表单添加新的重定向URI
function addRedirectUri(uri = '') {
    const newApp_redirect_uris_list = document.getElementById('newApp_redirect_uris_list');
    if (newApp_redirect_uris_list) {
        const newSpan = document.createElement('span');
        newSpan.className = 'flex-container';
        const newInput = document.createElement('input');
        newInput.type = 'text';
        newInput.name = 'newApp_redirect_uris';
        newInput.placeholder = 'https://example.com/callback';
        newInput.className = 'flex-item';
        newInput.spellcheck = false;
        if (uri) newInput.value = uri;
        newSpan.appendChild(newInput);
        newApp_redirect_uris_list.appendChild(newSpan);
    }
}

// 申请表单重置重定向URI
function resetRedirectUris(do_add = true) {
    const newApp_redirect_uris_list = document.getElementById('newApp_redirect_uris_list');
    if (newApp_redirect_uris_list) {
        newApp_redirect_uris_list.innerHTML = '';
        if (do_add) addRedirectUri();
    }
}

// 申请表单提交
function applyNewApp(button) {
    const original_button_text = button.textContent;
    button.disabled = true;
    button.textContent = '加载中...';
    const client_id_input = document.getElementById('newApp_client_id');
    const client_name_input = document.getElementById('newApp_client_name');
    const redirect_uris_input = document.getElementsByName('newApp_redirect_uris');
    const scope_input = document.getElementById('newApp_scope');
    const error_massage_p = document.getElementById('newApp_error_message');
    if (!(client_id_input && client_name_input && redirect_uris_input && scope_input && error_massage_p)) {
        alert('内部错误，发生元素缺失');
        button.disabled = false;
        button.textContent = original_button_text;
        return;
    }
    let error_message = '';
    const client_id = client_id_input.value.trim();
    if (!client_id) error_message += '应用ID不能为空\n';
    if (client_id.length > 64 || client_id.length < 3) error_message += '应用ID应在3-64个字符之间\n';
    if (client_id.match(/[^a-z0-9\-_]/)) error_message += '应用ID只能包含小写字母、数字、连字符、下划线\n';
    if (!client_name_input.value.trim()) error_message += '应用名称不能为空\n';
    if (client_name_input.value.length > 64) error_message += '应用名称不能超过64个字符\n';
    const redirect_uris = [];
    redirect_uris_input.forEach(input => {
        const value = input.value.trim();
        if (!value) return;
        if (value.includes('*') || value.includes('#') || value.includes('?')) {
            error_message += `回调地址 ${value} 中不能包含 * 或 # 或 ?\n`;
            return;
        }
        try {
            const URI = new URL(value);
        }
        catch (_) {
            error_message += `回调地址 ${value} 不是一个有效的URI\n`;
            return;
        }
        if (value.startsWith('http://')) {
            error_message += '不允许使用 http 作为回调，若要测试，请使用现有的测试客户端\n';
            return;
        }
        redirect_uris.push(value);
    });
    if (redirect_uris.length === 0) error_message += '至少需要一个有效回调地址\n';
    if (!scope_input.value.trim()) error_message += '应用权限不能为空\n';
    if (error_message) {
        error_massage_p.textContent = error_message;
        button.disabled = false;
        button.textContent = original_button_text;
        return;
    }
    error_massage_p.textContent = '';
    const url = '/call/manage/applyNewApp';
    const data = {
        client_id: client_id_input.value,
        client_name: client_name_input.value,
        redirect_uris: redirect_uris,
        scope: scope_input.value
    };
    if (newAppPageMode === 'modify') {
        const reset_secret = document.getElementById('newApp_secret');
        if (reset_secret && reset_secret.checked) data.reset_secret = true;
        const newApp_owner = document.getElementById('newApp_owner');
        if (newApp_owner && newApp_owner.value && window.current_user.admin) data.new_owner = newApp_owner.value;
        return updateApp(data, button);
    }
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    alert(text + `请求失败: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            const newAppSuccessMsg = document.getElementById('newAppSuccessMsg');
            newAppSuccessMsg.style.display = 'block';
            const spans = newAppSuccessMsg.getElementsByTagName('span');
            const texts = [
                data.client_id,
                data.client_name,
                data.redirect_uris.join(', '),
                data.scope,
                data.client_secret,
                data.owner
            ];
            for (let i = 0; i < spans.length; i++) {
                spans[i].textContent = texts[i];
            }
            return;
        })
        .catch(error => {
            alert('申请新应用失败:', error);
            button.disabled = false;
            button.textContent = original_button_text;
        })
}

// 申请表单重置
function resetApplyNewApp(needConfirm = true) {
    if (needConfirm)
        if (!confirm('确定要清空已填写的表单吗？'))
            return;
    const page_title = document.getElementById('newAppPageTitle');
    if (page_title) page_title.textContent = '新应用申请';
    const client_id_input = document.getElementById('newApp_client_id');
    if (client_id_input) {
        client_id_input.value = '';
        client_id_input.disabled = false;
    }
    const client_name = document.getElementById('newApp_client_name');
    if (client_name) client_name.value = '';
    resetRedirectUris();
    const scope_input = document.getElementById('newApp_scope');
    if (scope_input) scope_input.value = '';
    const secret = document.getElementById('clientSecretRow');
    if (secret) secret.style.display = 'none';
    const secret_checkbox = document.getElementById('newApp_secret');
    if (secret_checkbox) secret_checkbox.checked = false;
    const error_message = document.getElementById('newApp_error_message');
    if (error_message) error_message.style.display = 'none';
    const clientOwnerRow = document.getElementById('clientOwnerRow');
    if (clientOwnerRow) clientOwnerRow.style.display = 'none';
    const deleteBtn = document.getElementById('deleteAppBtn');
    if (deleteBtn) deleteBtn.style.display = 'none';
    newAppPageMode = 'new';
}

// 加载更多我的应用
function loadMoreMyApps(button, page = null, reload = false) {
    if (reload) {
        myApps_page = 1;
        const t_body = document.getElementById('myAppTableBody');
        if (t_body) t_body.innerHTML = '';
    }
    if (page === null) page = myApps_page;
    const original_button_text = button.textContent;
    button.disabled = true;
    button.textContent = '加载中...';
    const scopeRow = document.getElementById('myAppScopeRow');
    const scopeList = [];
    if (scopeRow) {
        const scopeThs = scopeRow.querySelectorAll('th[data-type="scope"]');
        scopeThs.forEach(th => {
            scopeList.push(th.textContent.trim());
        });
    }
    const t_body = document.getElementById('myAppTableBody');
    let url = '/call/manage/MyApps';
    p = objectToFormString({ ...getExtraParams(), page: page })
    if (p) url += '?' + p;
    fetch(url)
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            if (!data || data.length === 0) {
                button.disabled = true;
                button.textContent = '无更多数据';
                return;
            }
            data.forEach(item => {
                window.client_data[item.id] = item;
                const row = document.createElement('tr');
                const cellId = document.createElement('td');
                cellId.textContent = item.id;
                row.appendChild(cellId);
                const cellName = document.createElement('td');
                cellName.textContent = item.client_name;
                row.appendChild(cellName);
                const cellOwner = document.createElement('td');
                cellOwner.textContent = item.owner === window.current_user.id ? window.current_user.username : `(UID: ${item.owner})`;
                row.appendChild(cellOwner);
                const cellTime = document.createElement('td');
                const createdStr = formatTimestamp(item.created_at);
                const updatedStr = formatTimestamp(item.updated_at);
                cellTime.innerHTML = `${createdStr}<br>${updatedStr}`;
                row.appendChild(cellTime);
                const cellUri = document.createElement('td');
                let urisText = '';
                if (Array.isArray(item.redirect_uris)) {
                    urisText = item.redirect_uris.join('\n');
                } else {
                    urisText = item.redirect_uris || '';
                }
                cellUri.textContent = urisText;
                row.appendChild(cellUri);
                const myScopes = new Set(item.scope ? item.scope.split(' ') : []);
                scopeList.forEach(scope => {
                    const cellScope = document.createElement('td');
                    cellScope.textContent = myScopes.has(scope) ? '✓' : '';
                    row.appendChild(cellScope);
                });
                const cellAction = document.createElement('td');
                const btn = document.createElement('button');
                btn.className = 'c';
                btn.textContent = '设置';
                btn.onclick = () => manageApp(item.id);
                cellAction.appendChild(btn);
                row.appendChild(cellAction);
                t_body.appendChild(row);
            });
            if (data.length < 20) {
                button.disabled = true;
                button.textContent = '无更多数据';
            } else {
                myApps_page = page + 1;
                button.disabled = false;
                button.textContent = original_button_text;
            }
        })
        .catch(error => {
            console.error('加载我的应用失败:', error);
            button.disabled = false;
            button.textContent = original_button_text;
            alert('加载失败，请稍后重试');
        });
}

// 填入已有的应用设置
function manageApp(client_id) {
    originClientData = window.client_data[client_id];
    if (originClientData === undefined) {
        alert(`Client ID: ${client_id} 无效`);
        return;
    }
    const page_title = document.getElementById('newAppPageTitle');
    const client_id_input = document.getElementById('newApp_client_id');
    const client_name = document.getElementById('newApp_client_name');
    const scope_input = document.getElementById('newApp_scope');
    const secret = document.getElementById('clientSecretRow');
    if (!(page_title && client_id_input && client_name && scope_input && secret)) {
        alert('内部错误，发生元素缺失');
        return;
    }
    resetApplyNewApp(false);
    newAppPageMode = 'modify';
    page_title.textContent = `设置应用 ${client_id}`;
    client_id_input.value = client_id;
    client_id_input.disabled = true;
    client_name.value = originClientData.client_name;
    scope_input.value = originClientData.scope;
    const redirect_uris = originClientData.redirect_uris;
    resetRedirectUris(false);
    redirect_uris.forEach(uri => {
        addRedirectUri(uri);
    });
    const clientSecretRow = document.getElementById('clientSecretRow');
    if (clientSecretRow) clientSecretRow.style.display = 'block';
    const clientOwnerRow = document.getElementById('clientOwnerRow');
    if (clientOwnerRow && window.current_user.admin) clientOwnerRow.style.display = 'block';
    const deleteBtn = document.getElementById('deleteAppBtn');
    if (deleteBtn) deleteBtn.style.display = 'inline-block';
    toggleNewAppTab();
}

// 删除应用
function deleteApp(triggerBtn) {
    const client_id_input = document.getElementById('newApp_client_id');
    if (!client_id_input || !client_id_input.value) {
        alert('无法获取应用ID');
        return;
    }
    const client_id = client_id_input.value;
    const client_name = document.getElementById('newApp_client_name')?.value || client_id;
    if (!confirm(`确定要删除应用 ${client_name} (ID: ${client_id}) 吗？此操作不可逆！`)) {
        return;
    }
    triggerBtn.disabled = true;
    triggerBtn.textContent = '删除中...';
    const formData = new URLSearchParams();
    formData.append('client_id', client_id);
    fetch('/call/manage/deleteApp', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
    })
        .then(response => {
            if (response.status === 204) {
                alert('应用已删除');
                resetApplyNewApp(false);
                toggleNewAppTab();
                loadMoreMyApps(document.querySelector('#myApp button.c'), 1, true);
            } else {
                return response.text().then(text => {
                    throw new Error(text || `HTTP ${response.status}`);
                });
            }
        })
        .catch(error => {
            console.error('删除应用失败:', error);
            alert('删除失败：' + error.message);
            triggerBtn.disabled = false;
            triggerBtn.textContent = '删除应用';
        });
}
function updateApp(data, button) {
    const client_id = data.client_id;
    originClientData = window.client_data[client_id];
    if (originClientData === undefined) {
        alert(`Client ID: ${client_id} 无效`);
        return;
    }
    const req_data = {};
    if (data.new_owner && window.current_user.admin) {
        const reason = prompt('您正在以管理员身份更改此应用的所有者，请输入操作理由\n留空自动取消操作');
        if (reason === null || !reason.trim()) return;
        req_data.new_owner = data.new_owner;
        req_data.reason = reason.trim();
    }
    req_data.client_name = data.client_name;
    req_data.scope = data.scope;
    req_data.redirect_uris = data.redirect_uris;
    if (data.reset_secret) req_data.reset_secret = true;
    const url = '/call/manage/updateApp';
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(req_data)
    })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    alert(text + `请求失败: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            const newAppSuccessMsg = document.getElementById('newAppSuccessMsg');
            newAppSuccessMsg.style.display = 'block';
            const spans = newAppSuccessMsg.getElementsByTagName('span');
            const texts = [
                data.client_id,
                data.client_name,
                data.redirect_uris.join(', '),
                data.scope,
                data.client_secret,
                data.owner
            ];
            for (let i = 0; i < spans.length; i++) {
                spans[i].textContent = texts[i];
            }
            return;
        })
        .catch(error => {
            alert('更改应用失败:', error);
            button.disabled = false;
            button.textContent = original_button_text;
        })
}