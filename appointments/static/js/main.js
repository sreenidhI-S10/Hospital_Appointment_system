// main.js - Premium UI interactions and loading states

document.addEventListener('DOMContentLoaded', () => {
    // 1. Loading indicators on form submissions
    const formsToValidate = document.querySelectorAll('form');
    formsToValidate.forEach(form => {
        form.addEventListener('submit', (e) => {
            // Check if form is valid before triggering loader
            if (form.checkValidity() && !form.classList.contains('no-loader')) {
                showGlobalLoader();
            }
        });
    });

    // 2. Pulse animations & alert auto-dismiss enhancements
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        alert.classList.add('pulse-loader');
        setTimeout(() => {
            alert.classList.remove('pulse-loader');
        }, 3000);
    });

    // 3. Search filter sidebar toggler for mobile
    const filterToggle = document.getElementById('filter-toggle');
    const sidebar = document.querySelector('.filter-sidebar');
    if (filterToggle && sidebar) {
        filterToggle.addEventListener('click', () => {
            sidebar.classList.toggle('d-none');
            sidebar.classList.toggle('d-block');
        });
    }
});

function showGlobalLoader() {
    let loader = document.getElementById('global-page-loader');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'global-page-loader';
        loader.innerHTML = `
            <div class="position-fixed top-0 start-0 w-100 h-100 d-flex flex-column align-items-center justify-content-center" style="background: rgba(15, 23, 42, 0.75); z-index: 9999; backdrop-filter: blur(5px);">
                <div class="glass-card p-5 text-center d-flex flex-column align-items-center justify-content-center" style="max-width: 350px; background: rgba(255, 255, 255, 0.95); border: 1px solid rgba(255, 255, 255, 0.8);">
                    <div class="spinner-border text-teal mb-3" role="status" style="width: 3.5rem; height: 3.5rem; color: #0d9488;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="spinner-grow text-primary spinner-grow-sm position-absolute" role="status" style="top: 3.25rem;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <h5 class="fw-bold text-dark mt-2 mb-1">HopeLife Secure Sync</h5>
                    <p class="text-muted small mb-0">Please wait while we safely process your medical information.</p>
                </div>
            </div>
        `;
        document.body.appendChild(loader);
    } else {
        loader.classList.remove('d-none');
    }
}
