/**
 * App — Client-side interactions
 * Toast auto-dismiss, confirmation dialogs, sidebar toggle
 */
document.addEventListener('DOMContentLoaded', () => {

  // ── Toast auto-dismiss ───────────────────────────────────────
  document.querySelectorAll('.toast').forEach(toast => {
    setTimeout(() => {
      toast.style.transition = 'opacity .3s ease, transform .3s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(40px)';
      setTimeout(() => toast.remove(), 300);
    }, 5000);

    const closeBtn = toast.querySelector('.toast__close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 200);
      });
    }
  });


  // ── Sidebar toggle (mobile) ──────────────────────────────────
  const hamburger = document.querySelector('.hamburger');
  const sidebar = document.querySelector('.sidebar');
  if (hamburger && sidebar) {
    hamburger.addEventListener('click', () => sidebar.classList.toggle('open'));
    // Close on click outside
    document.addEventListener('click', (e) => {
      if (sidebar.classList.contains('open') &&
          !sidebar.contains(e.target) &&
          !hamburger.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }


  // ── Confirmation dialogs ─────────────────────────────────────
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const message = el.getAttribute('data-confirm') || 'Are you sure?';
      showConfirmDialog(message, () => {
        // If it's a form submit button, submit the form
        const form = el.closest('form');
        if (form) {
          form.submit();
        } else if (el.href) {
          window.location.href = el.href;
        }
      });
    });
  });


  // ── Status change buttons (AJAX) ─────────────────────────────
  document.querySelectorAll('[data-status-url]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const url = btn.getAttribute('data-status-url');
      const status = btn.getAttribute('data-status-value');
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify({ status }),
        });
        const data = await res.json();
        if (data.ok) {
          window.location.reload();
        } else {
          showToast((data.errors || ['Failed to change status.']).join(' '), 'danger');
        }
      } catch {
        showToast('Network error. Please try again.', 'danger');
      }
    });
  });
});


// ── Utility functions ────────────────────────────────────────────

function showConfirmDialog(message, onConfirm) {
  const overlay = document.createElement('div');
  overlay.className = 'dialog-overlay';
  overlay.innerHTML = `
    <div class="dialog">
      <h3>Confirm Action</h3>
      <p>${escapeHtml(message)}</p>
      <div class="dialog__actions">
        <button class="btn btn-secondary" data-role="cancel">Cancel</button>
        <button class="btn btn-danger" data-role="confirm">Confirm</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  overlay.querySelector('[data-role="cancel"]').addEventListener('click', () => overlay.remove());
  overlay.querySelector('[data-role="confirm"]').addEventListener('click', () => {
    overlay.remove();
    onConfirm();
  });
  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
}


function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span><button class="toast__close">&times;</button>`;
  container.appendChild(toast);

  toast.querySelector('.toast__close').addEventListener('click', () => toast.remove());
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}


function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
