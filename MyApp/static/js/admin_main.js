    // Toast notification function
    function showToast(message, type = 'success') {
        const container = document.querySelector('.toast-container') || (() => {
            const div = document.createElement('div');
            div.className = 'toast-container';
            document.body.appendChild(div);
            return div;
        })();

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠'
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type]}</span>
            <span class="toast-content">${message}</span>
            <button class="toast-close" type="button">×</button>
        `;

        container.appendChild(toast);

        const closeBtn = toast.querySelector('.toast-close');
        const removeToast = () => {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
        };

        closeBtn.addEventListener('click', removeToast);
        setTimeout(removeToast, 4000);
    }

    // Delete client
    document.querySelectorAll('.delete-client').forEach(button => {
        button.addEventListener('click', function (e) {
            e.preventDefault();
            const clientId = this.dataset.id;

            if (confirm("Are you sure you want to delete this client?")) {
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

                fetch(`/delete-client/${clientId}/`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken }
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            showToast('Client deleted successfully', 'success');
                            setTimeout(() => location.reload(), 1500);
                        } else {
                            showToast(data.message || 'Failed to delete client.', 'error');
                        }
                    })
                    .catch(() => showToast('Network error. Please try again.', 'error'));
            }
        });
    });

    // Add client
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOMContentLoaded - searching for addClientForm');
        const form = document.getElementById('addClientForm');
        
        if (!form) {
            console.error('addClientForm not found!');
            return;
        }
        
        console.log('Form found:', form);

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            console.log('Form submitted');

            const formData = new FormData(form);
            console.log('FormData created:', {
                client_name: formData.get('client_name'),
                client_id: formData.get('client_id')
            });
            
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            console.log('CSRF Token:', csrfToken ? 'Found' : 'NOT FOUND');

            fetch("/add-client/", {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData
            })
                .then(res => {
                    console.log('Response status:', res.status);
                    return res.json();
                })
                .then(data => {
                    console.log('Response data:', data);
                    if (data.status === 'success') {
                        showToast('Client added successfully!', 'success');
                        form.reset();
                        const modal = bootstrap.Modal.getInstance(document.getElementById('addClientModal'));
                        if (modal) modal.hide();
                        setTimeout(() => location.reload(), 1500);
                    } else {
                        showToast(data.message || 'Error occurred.', 'error');
                    }
                })
                .catch((err) => {
                    console.error('Fetch error:', err);
                    showToast('Network error. Please try again.', 'error');
                });
        });

        // Search client
        const searchInput = document.getElementById('clientSearch');
        const tableBody = document.getElementById('clientTable');
        
        if (searchInput && tableBody) {
            searchInput.addEventListener('keyup', function () {
                const filter = this.value.toUpperCase();
                const rows = tableBody.getElementsByClassName('client-row');

                Array.from(rows).forEach(row => {
                    const text = row.textContent || row.innerText;
                    row.style.display = text.toUpperCase().includes(filter) ? "" : "none";
                });
            });
        }
    });