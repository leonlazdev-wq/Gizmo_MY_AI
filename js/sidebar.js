/* Scrollable left-side tab navigator for Gizmo */
(function () {
  'use strict';

  function getPrimaryTabButtons() {
    var navs = Array.from(document.querySelectorAll('.tabs > .tab-nav'));
    if (!navs.length) return [];

    // pick the tab nav with the most direct tab buttons (usually top-level app tabs)
    navs.sort(function (a, b) {
      return b.querySelectorAll(':scope > button,[role="tab"]').length - a.querySelectorAll(':scope > button,[role="tab"]').length;
    });

    var primary = navs[0];
    return Array.from(primary.querySelectorAll(':scope > button,[role="tab"]'));
  }

  function ensureSidebarRoot() {
    var sidebar = document.getElementById('gizmo-sidebar');
    if (!sidebar) {
      sidebar = document.createElement('div');
      sidebar.id = 'gizmo-sidebar';
      sidebar.className = 'gizmo-sidebar';
      document.body.appendChild(sidebar);
    }
    return sidebar;
  }

  function setActive(label) {
    document.querySelectorAll('#gizmo-sidebar .sidebar-nav-item').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.tabLabel === label);
    });
  }

  function renderSidebar() {
    var sidebar = ensureSidebarRoot();
    var tabs = getPrimaryTabButtons();
    if (!tabs.length) return;

    sidebar.innerHTML = '';

    var logo = document.createElement('div');
    logo.className = 'sidebar-logo';
    logo.textContent = '🤖 Gizmo MY-AI';
    sidebar.appendChild(logo);

    var nav = document.createElement('nav');
    nav.className = 'sidebar-nav';

    tabs.forEach(function (tabBtn) {
      var label = (tabBtn.textContent || '').trim();
      if (!label) return;

      var btn = document.createElement('button');
      btn.className = 'sidebar-nav-item';
      btn.dataset.tabLabel = label;
      btn.type = 'button';
      btn.textContent = label;

      if (tabBtn.classList.contains('selected') || tabBtn.getAttribute('aria-selected') === 'true') {
        btn.classList.add('active');
      }

      btn.addEventListener('click', function () {
        tabBtn.click();
        setActive(label);
      });

      nav.appendChild(btn);
    });

    sidebar.appendChild(nav);
  }

  function syncActiveFromTabBar() {
    var selected = document.querySelector('.tabs > .tab-nav > button.selected, .tabs > .tab-nav [role="tab"][aria-selected="true"]');
    if (selected) {
      var label = (selected.textContent || '').trim();
      if (label) setActive(label);
    }
  }

  function init() {
    renderSidebar();
    syncActiveFromTabBar();

    var mo = new MutationObserver(function () {
      renderSidebar();
      syncActiveFromTabBar();
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
