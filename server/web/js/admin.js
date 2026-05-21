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

let _changeLogPage = 1;
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
    return fetch('/call/manage/changeLog?' + params.join('&'))
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
        console.error('加载操作日志失败:', e);
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