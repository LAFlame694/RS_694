/* ==========================================================================
   RentMaster Create Invoice JavaScript - create_invoice.js
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function() {
    
    // DOM Elements
    const tenancySelect = document.getElementById('tenancySelect');
    const tenantPreview = document.getElementById('tenantPreview');
    const previewTenant = document.getElementById('previewTenant');
    const previewProperty = document.getElementById('previewProperty');
    const previewUnit = document.getElementById('previewUnit');
    const previewType = document.getElementById('previewType');
    const previewRent = document.getElementById('previewRent');

    const invoiceCategory = document.getElementById('invoiceCategory');
    const invoiceAmount = document.getElementById('invoiceAmount');
    const dueDate = document.getElementById('dueDate');
    const periodStart = document.getElementById('periodStart');
    const periodEnd = document.getElementById('periodEnd');

    // Summary Elements
    const summaryAmount = document.getElementById('summaryAmount');
    const summaryTenant = document.getElementById('summaryTenant');
    const summaryPropertyUnit = document.getElementById('summaryPropertyUnit');
    const summaryCategory = document.getElementById('summaryCategory');
    const summaryDueDate = document.getElementById('summaryDueDate');
    const summaryPeriod = document.getElementById('summaryPeriod');

    const createInvoiceForm = document.getElementById('createInvoiceForm');

    // Default Initialization on Load (Preselected John Kamau)
    if (tenancySelect && tenancySelect.value) {
        updateTenancyPreview();
    }
    updateSummary();
    setDefaultDueDate();

    // Event Listeners for Live Updates
    if (tenancySelect) {
        tenancySelect.addEventListener('change', function() {
            updateTenancyPreview();
            updateSummary();
        });
    }

    if (invoiceAmount) {
        invoiceAmount.addEventListener('input', updateSummary);
    }

    if (invoiceCategory) {
        invoiceCategory.addEventListener('change', updateSummary);
    }

    if (dueDate) {
        dueDate.addEventListener('change', updateSummary);
    }

    if (periodStart || periodEnd) {
        periodStart.addEventListener('change', updateBillingPeriodSummary);
        periodEnd.addEventListener('change', updateBillingPeriodSummary);
    }

    // Form Client-side Validation (Bootstrap requirement)
    if (createInvoiceForm) {
        createInvoiceForm.addEventListener('submit', function(event) {
            if (!createInvoiceForm.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            } else {
                event.preventDefault();
                alert('Frontend Demo: Invoice successfully validated and submitted!');
            }
            createInvoiceForm.classList.add('was-validated');
        }, false);
    }

    // Helper Functions
    function updateTenancyPreview() {
        const selectedOption = tenancySelect.options[tenancySelect.selectedIndex];
        if (selectedOption && selectedOption.value) {
            const tenant = selectedOption.getAttribute('data-tenant');
            const property = selectedOption.getAttribute('data-property');
            const unit = selectedOption.getAttribute('data-unit');
            const type = selectedOption.getAttribute('data-type');
            const rent = selectedOption.getAttribute('data-rent');

            previewTenant.textContent = tenant;
            previewProperty.textContent = property;
            previewUnit.textContent = unit;
            previewType.textContent = type;
            previewRent.textContent = rent;

            tenantPreview.classList.remove('d-none');
        } else {
            tenantPreview.classList.add('d-none');
        }
    }

    function updateSummary() {
        // Update Tenant & Property Summary
        const selectedOption = tenancySelect.options[tenancySelect.selectedIndex];
        if (selectedOption && selectedOption.value) {
            summaryTenant.textContent = selectedOption.getAttribute('data-tenant');
            summaryPropertyUnit.textContent = `${selectedOption.getAttribute('data-property')} (${selectedOption.getAttribute('data-unit')})`;
        } else {
            summaryTenant.textContent = 'Not selected';
            summaryPropertyUnit.textContent = '-';
        }

        // Update Amount Summary with KES Formatting
        const amountVal = parseFloat(invoiceAmount.value);
        if (!isNaN(amountVal)) {
            summaryAmount.textContent = `KES ${amountVal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        } else {
            summaryAmount.textContent = 'KES 0.00';
        }

        // Update Category Summary
        if (invoiceCategory && invoiceCategory.value) {
            summaryCategory.innerHTML = `<span class="badge bg-light text-dark border">${invoiceCategory.value}</span>`;
        }

        // Update Due Date Summary
        if (dueDate && dueDate.value) {
            summaryDueDate.textContent = dueDate.value;
        } else {
            summaryDueDate.textContent = 'Not specified';
        }
    }

    function updateBillingPeriodSummary() {
        const start = periodStart.value;
        const end = periodEnd.value;

        if (start && end) {
            summaryPeriod.textContent = `${formatDateShort(start)} - ${formatDateShort(end)}`;
        } else if (start) {
            summaryPeriod.textContent = `From ${formatDateShort(start)}`;
        } else if (end) {
            summaryPeriod.textContent = `Until ${formatDateShort(end)}`;
        } else {
            summaryPeriod.textContent = 'Not specified';
        }
    }

    function setDefaultDueDate() {
        const today = new Date();
        const nextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 5); // 5th of next month
        const yyyy = nextMonth.getFullYear();
        const mm = String(nextMonth.getMonth() + 1).padStart(2, '0');
        const dd = String(nextMonth.getDate()).padStart(2, '0');
        
        if (dueDate) {
            dueDate.value = `${yyyy}-${mm}-${dd}`;
            updateSummary();
        }
    }

    function formatDateShort(dateString) {
        const options = { day: 'numeric', month: 'short', year: 'numeric' };
        const date = new Date(dateString);
        return isNaN(date) ? dateString : date.toLocaleDateString('en-US', options);
    }

});
