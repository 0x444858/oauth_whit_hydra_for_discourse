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