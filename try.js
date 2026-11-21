/**
 * RentMaster - Invoice Detail JavaScript
 * Vanilla JS & Bootstrap 5.3.2 enhancements
 */

document.addEventListener('DOMContentLoaded', function () {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Interactive UI feedback for action buttons (placeholders)
    const actionButtons = document.querySelectorAll('button:not([data-bs-toggle]), .btn:not([data-bs-toggle])');
    actionButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (this.getAttribute('onclick') && this.getAttribute('onclick').includes('print')) {
                return;
            }
            
            const btnText = this.textContent.trim();
            if(btnText.includes('Download PDF') || btnText.includes('Cancel Invoice')) {
                e.preventDefault();
                showNotification(`Action simulated: "${btnText}" clicked. (Frontend placeholder mode)`, 'info');
            }
        });
    });

    // Helper function for simulated UI notifications
    function showNotification(message, type = 'info') {
        const alertContainer = document.createElement('div');
        alertContainer.className = `alert alert-${type} alert-dismissible fade show position-fixed bottom-0 end-0 m-3 shadow`;
        alertContainer.style.zIndex = '1080';
        alertContainer.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fa-solid fa-circle-info me-2"></i>
                <div>${message}</div>
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        document.body.appendChild(alertContainer);

        setTimeout(() => {
            if (alertContainer) {
                alertContainer.classList.remove('show');
                setTimeout(() => alertContainer.remove(), 300);
            }
        }, 4000);
    }
});
