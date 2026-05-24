!function () {
    const cssLink = document.createElement('link');
    cssLink.rel = 'stylesheet';
    cssLink.href = 'css/admin.css';
    document.head.appendChild(cssLink);
    fetch('admin.html')
        .then(res => res.text())
        .then(html => {
            const parser = new DOMParser();
            const admin_doc = parser.parseFromString(html, 'text/html');
            setAdminParts(admin_doc);
        });
}();

function setAdminParts(doc) {
    const new_title = doc.title;
    document.title = new_title;
    document.getElementById('title').textContent = new_title;
    const new_sidebars = doc.getElementById('newSidebars');
    const links = new_sidebars.querySelectorAll('a');
    const sidebar = document.getElementById('sidebar');
    const sidebar_link_sep = document.getElementById('sidebarLinkSep');
    links.forEach(link => {
        if (link.dataset.tab) {
            link.addEventListener('click', handleMenuClick);
            sidebar.insertBefore(link, sidebar_link_sep);
        } else {
            link.target = '_blank';
            sidebar.appendChild(link);
        }
    });
    const new_tabs = doc.getElementById('newTabs');
    const tabs = new_tabs.querySelectorAll(':scope > div');
    const tab_content = document.getElementById('tabContent');
    tabs.forEach(tab => {
        if (tab_content) {
            tab_content.appendChild(tab);
        }
    });
    const uid_input_area = doc.getElementById('uidInputArea');
    const content_area = document.getElementById('contentArea');
    if (uid_input_area && content_area) {
        content_area.insertBefore(uid_input_area, content_area.firstChild);
    }
    initSettings();
}

function getExtraParams() {
    const uidInput = document.getElementById('uid');
    const uidAll = document.getElementById('uid_all');
    if (uidAll && uidAll.checked) {
        return { uid_all: 1 };
    }
    if (uidInput && uidInput.value) {
        return { uid: uidInput.value };
    }
    return {};
}

let _changeLogPage = 0;
let _changeLogHasMore = true;

function _changeLogOptionText(selectId, value) {
    const opt = document.querySelector('#' + selectId + ' option[value="' + value + '"]');
    return opt ? opt.textContent : value;
}

function _changeLogReadFilters() {
    const f = {};
    function g(id, key, fn) {
        const el = document.getElementById(id);
        if (!el || el.value === '') return;
        f[key] = fn ? fn(el.value) : el.value;
    }
    g('action_log_type', 'target_type');
    g('action_log_action', 'action_code');
    g('action_log_target_id', 'target_id');
    g('action_log_old_value', 'old_value');
    g('action_log_new_value', 'new_value');
    g('action_log_time_start', 'time_start', v => Math.floor(new Date(v).getTime() / 1000));
    g('action_log_time_end', 'time_end', v => Math.floor(new Date(v).getTime() / 1000));
    g('action_log_operator_uid', 'operator_uid');
    g('action_log_operator_username', 'operator_username');
    g('action_log_reason', 'reason');
    return f;
}

function _changeLogRender(data) {
    const tbody = document.getElementById('changeLogTableBody');
    if (!tbody) return;
    data.forEach(row => {
        const tr = document.createElement('tr');
        [
            _changeLogOptionText('action_log_type', row.target_type),
            _changeLogOptionText('action_log_action', row.action_code),
            row.target_id || '',
            row.old_value || '',
            row.new_value || '',
            formatDate(row.action_time),
            row.operator_uid,
            row.operator_username,
            row.reason || ''
        ].forEach(text => {
            const td = document.createElement('td');
            td.textContent = String(text);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

function _changeLogFetch() {
    const params = [];
    const filters = _changeLogReadFilters();
    for (const [k, v] of Object.entries(filters))
        params.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
    params.push('page=' + _changeLogPage);
    return fetch('/call/admin/changeLog?' + params.join('&'))
        .then(r => {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        })
        .then(data => {
            _changeLogRender(data);
            return data.length;
        });
}

function reloadChangeLog(button) {
    _changeLogPage = 1;
    _changeLogHasMore = true;
    const tbody = document.getElementById('changeLogTableBody');
    if (tbody) tbody.innerHTML = '';
    if (button) { button.disabled = true; button.textContent = '加载中...'; }
    _changeLogFetch().then(len => {
        _changeLogHasMore = len >= 20;
        if (button) { button.disabled = false; button.textContent = '重新加载数据'; }
    }).catch(e => {
        console.error('加载操作日志失败:', e);
        alert('加载操作日志失败：' + e.message);
        if (button) { button.disabled = false; button.textContent = '重新加载数据'; }
    });
}

function loadMoreChangeLog(button) {
    if (!_changeLogHasMore) {
        if (button) { button.disabled = true; button.textContent = '无更多数据'; }
        return;
    }
    _changeLogPage++;
    if (button) { button.disabled = true; button.textContent = '加载中...'; }
    _changeLogFetch().then(len => {
        _changeLogHasMore = len >= 20;
        if (button) {
            button.disabled = !_changeLogHasMore;
            button.textContent = _changeLogHasMore ? '加载更多' : '无更多数据';
        }
    }).catch(e => {
        _changeLogPage--;
        console.error('加载操作日志失败:', e);
        alert('加载操作日志失败：' + e.message);
        if (button) { button.disabled = false; button.textContent = '加载更多'; }
    });
}

function clearChangeLogFilter() {
    ['action_log_type', 'action_log_action', 'action_log_target_id', 'action_log_old_value',
        'action_log_new_value', 'action_log_time_start', 'action_log_time_end',
        'action_log_operator_uid', 'action_log_operator_username', 'action_log_reason']
        .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    reloadChangeLog();
}

// === 群组选择器 ===
let _serverGroupIds = [];
let _currentGroupIds = [];
let _allGroups = [];
let _groupCancelBtn = null;
let _groupSaveBtn = null;
let _serverDocUrl = '';
let _docUrlCancelBtn = null;
let _docUrlSaveBtn = null;

function _arraysEqual(a, b) {
    if (a.length !== b.length) return false;
    const sa = [...a].sort((x, y) => x - y);
    const sb = [...b].sort((x, y) => x - y);
    return sa.every((v, i) => v === sb[i]);
}

function _updateGroupActionButtons() {
    const changed = !_arraysEqual(_serverGroupIds, _currentGroupIds);
    if (_groupCancelBtn) _groupCancelBtn.disabled = !changed;
    if (_groupSaveBtn) _groupSaveBtn.disabled = !changed;
}

function _getGroupName(id) {
    const g = _allGroups.find(g => g.id === id);
    return g ? g.name : null;
}

function renderGroupPanels() {
    var selectedDiv = document.getElementById('new_apply_allowed_group_ids_selected');
    var availableDiv = document.getElementById('new_apply_allowed_group_ids_available');

    var existingIds = new Set(_allGroups.map(function (g) { return g.id; }));
    _currentGroupIds.forEach(function (id) {
        if (!existingIds.has(id)) {
            _allGroups.push({ id: id, name: null });
        }
    });

    if (selectedDiv) {
        selectedDiv.innerHTML = '';
        if (_currentGroupIds.length === 0) {
            selectedDiv.textContent = '无';
        } else {
            _currentGroupIds.forEach(function (id) {
                var btn = document.createElement('button');
                btn.className = 'c group-btn';
                var name = _getGroupName(id);
                if (name) {
                    btn.textContent = name;
                } else {
                    btn.textContent = '(ID: ' + id + ')';
                    btn.classList.add('ghost');
                }
                btn.onclick = function () { deselectGroup(this, id); };
                selectedDiv.appendChild(btn);
            });
        }
    }

    if (availableDiv) {
        availableDiv.innerHTML = '';
        if (_allGroups.length === 0) {
            availableDiv.textContent = '无可用群组';
        } else {
            _allGroups.forEach(function (g) {
                var btn = document.createElement('button');
                btn.className = 'c group-btn';
                var isGhost = g.name === null;
                if (isGhost) {
                    btn.textContent = '(ID: ' + g.id + ')';
                    btn.classList.add('ghost');
                    btn.disabled = true;
                } else {
                    btn.textContent = g.name;
                    if (_currentGroupIds.includes(g.id)) {
                        btn.disabled = true;
                    } else {
                        btn.onclick = function () { selectGroup(this, g.id); };
                    }
                }
                availableDiv.appendChild(btn);
            });
        }
    }

    _updateGroupActionButtons();
}

function selectGroup(btn, id) {
    if (!_currentGroupIds.includes(id)) {
        _currentGroupIds.push(id);
        renderGroupPanels();
    }
}

function deselectGroup(btn, id) {
    _currentGroupIds = _currentGroupIds.filter(function (x) { return x !== id; });
    renderGroupPanels();
}

function cancelGroupChanges(btn) {
    _currentGroupIds = [..._serverGroupIds];
    renderGroupPanels();
}

function saveGroupChanges(btn) {
    if (btn) { btn.disabled = true; btn.textContent = '保存中...'; }
    var value = JSON.stringify(_currentGroupIds);
    fetch('/call/admin/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'new_apply_allowed_group_ids', value: value })
    })
        .then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            _serverGroupIds = [..._currentGroupIds];
            _updateGroupActionButtons();
        })
        .catch(function (e) {
            alert('保存群组设置失败：' + e.message);
            _updateGroupActionButtons();
        })
        .finally(function () {
            if (btn) { btn.disabled = false; btn.textContent ='确认更改'; }
        });
}

function _updateDocUrlButtons() {
    const input = document.getElementById('doc_url');
    if (!input) return;
    const changed = input.value.trim() !== _serverDocUrl;
    if (_docUrlCancelBtn) _docUrlCancelBtn.disabled = !changed;
    if (_docUrlSaveBtn) _docUrlSaveBtn.disabled = !changed;
}

function saveDocUrl(btn) {
    if (btn) { btn.disabled = true; btn.textContent = '保存中...'; }
    const input = document.getElementById('doc_url');
    if (!input) return;
    const value = input.value.trim();
    fetch('/call/admin/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'doc_url', value: value })
    })
        .then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            _serverDocUrl = value;
            _updateDocUrlButtons();
        })
        .catch(function (e) {
            alert('保存文档URL失败：' + e.message);
            _updateDocUrlButtons();
        })
        .finally(function () {
            if (btn) { btn.disabled = false; btn.textContent = '确认更改'; }
        });
}

function cancelDocUrl(btn) {
    const input = document.getElementById('doc_url');
    if (!input) return;
    input.value = _serverDocUrl;
    _updateDocUrlButtons();
}

function _fetchAllGroups(page, accumulator) {
    var url = '/g.json';
    if (page > 0) url += '?page=' + page;
    return fetch(url)
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (data) {
            if (!data.groups || data.groups.length === 0) return accumulator;
            var groups = data.groups.map(function (g) { return { id: g.id, name: g.full_name || g.name }; });
            return _fetchAllGroups(page + 1, accumulator.concat(groups));
        });
}

function initSettings() {
    _groupCancelBtn = document.getElementById('groupCancelBtn');
    _groupSaveBtn = document.getElementById('groupSaveBtn');
    _docUrlCancelBtn = document.getElementById('docUrlCancelBtn');
    _docUrlSaveBtn = document.getElementById('docUrlSaveBtn');

    fetch('/call/admin/settings')
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (configs) {
            var cb = document.getElementById('allow_new_client_apply');
            if (cb) cb.checked = configs.allow_new_client_apply === 't';

            var idsStr = configs.new_apply_allowed_group_ids || '';
            try {
                _serverGroupIds = idsStr ? JSON.parse(idsStr) : [];
            } catch (e) {
                _serverGroupIds = [];
            }
            _currentGroupIds = [..._serverGroupIds];
            renderGroupPanels();

            var docUrlInput = document.getElementById('doc_url');
            _serverDocUrl = configs.doc_url || '';
            if (docUrlInput) {
                docUrlInput.value = _serverDocUrl;
                docUrlInput.addEventListener('input', _updateDocUrlButtons);
            }
        })
        .catch(function (e) { console.error('加载系统设置失败:', e); });

    _fetchAllGroups(0, [])
        .then(function (groups) {
            _allGroups = groups;
            renderGroupPanels();
        })
        .catch(function (e) {
            console.error('加载群组列表失败:', e);
            var availableDiv = document.getElementById('new_apply_allowed_group_ids_available');
            if (availableDiv) availableDiv.textContent = '加载失败';
        });

    document.getElementById('allow_new_client_apply')?.addEventListener('change', function () {
        var self = this;
        var value = self.checked ? 't' : 'f';
        fetch('/call/admin/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'allow_new_client_apply', value: value })
        })
            .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); })
            .catch(function (e) {
                alert('保存设置失败：' + e.message);
                self.checked = !self.checked;
            });
    });
}