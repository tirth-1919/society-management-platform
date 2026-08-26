document.addEventListener('DOMContentLoaded', () => {
    const csrf = () =>
        document.querySelector('input[name="csrf_token"]')?.value ||
        document.querySelector('meta[name="csrf-token"]')?.content || '';

    const showMessage = (node, text, isError = false, isSuccess = false) => {
        if (!node) return;
        node.textContent = text;
        node.style.display = text ? 'flex' : 'none';
        node.classList.toggle('error', isError);
        node.classList.toggle('success', isSuccess);
    };

    const apiError = async (response) => {
        const body = await response.json().catch(() => ({}));
        return body.error || 'The request could not be completed.';
    };

    // Fallback for failed images
    document.querySelectorAll('[data-image-fallback]').forEach((img) => {
        img.addEventListener('error', () => {
            img.classList.add('image-unavailable');
            img.alt = 'Image unavailable';
        });
    });

    // ----------------------------------------------------
    // LIVE COUNTDOWN TIMER
    // ----------------------------------------------------
    const initCountdowns = () => {
        document.querySelectorAll('[data-countdown]').forEach((node) => {
            const target = new Date(node.dataset.countdown);
            const textNode = node.querySelector('[data-countdown-text]');
            if (!textNode) return;

            const updateTimer = () => {
                const now = new Date();
                const diff = target - now;

                if (diff <= 0) {
                    textNode.textContent = 'Event Concluded';
                    return;
                }

                const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
                const minutes = Math.floor((diff / (1000 * 60)) % 60);

                if (days > 1) {
                    textNode.textContent = `Starts in ${days} days`;
                } else if (days === 1) {
                    textNode.textContent = 'Starts tomorrow';
                } else if (hours > 0) {
                    textNode.textContent = `Starts in ${hours}h ${minutes}m`;
                } else {
                    textNode.textContent = `Starts in ${Math.max(1, minutes)} minutes`;
                }
            };

            updateTimer();
            setInterval(updateTimer, 60000);
        });
    };
    initCountdowns();

    // ----------------------------------------------------
    // LIST VS CALENDAR VIEW TOGGLE
    // ----------------------------------------------------
    const listContainer = document.querySelector('[data-events-list]');
    const calendarContainer = document.querySelector('[data-event-calendar]');
    const viewButtons = document.querySelectorAll('[data-event-view]');

    viewButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
            const selectedView = btn.dataset.eventView;
            viewButtons.forEach((b) => b.classList.toggle('active', b === btn));

            if (selectedView === 'calendar') {
                if (listContainer) listContainer.hidden = true;
                if (calendarContainer) calendarContainer.hidden = false;
            } else {
                if (listContainer) listContainer.hidden = false;
                if (calendarContainer) calendarContainer.hidden = true;
            }
        });
    });

    // ----------------------------------------------------
    // DRAG & DROP AND RESIDENT MEDIA UPLOADS
    // ----------------------------------------------------
    const fileInput = document.querySelector('#photo-files');
    const uploadForm = fileInput?.closest('form');
    const previewContainer = document.querySelector('#photo-preview-list');
    const dropzoneBox = document.querySelector('.upload-dropzone-box');
    const progressContainer = document.querySelector('#upload-progress-container');
    const progressFill = document.querySelector('#upload-progress-fill');
    const progressStatusText = document.querySelector('#progress-status-text');

    if (fileInput && uploadForm && previewContainer) {
        // Replacement photo handler from session storage
        const replacementId = sessionStorage.getItem('event-photo-replacement');
        if (replacementId) {
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'replacement_for_id';
            hidden.value = replacementId;
            uploadForm.append(hidden);
            sessionStorage.removeItem('event-photo-replacement');
            const notice = uploadForm.querySelector('[data-upload-message]');
            showMessage(notice, 'Uploading replacement media. It will be reviewed by admin as a new submission.');
        }

        // Drag & drop events on dropzone
        if (dropzoneBox) {
            ['dragenter', 'dragover'].forEach((eventName) => {
                dropzoneBox.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropzoneBox.classList.add('drag-over');
                });
            });

            ['dragleave', 'drop'].forEach((eventName) => {
                dropzoneBox.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropzoneBox.classList.remove('drag-over');
                });
            });

            dropzoneBox.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                if (dt?.files?.length) {
                    fileInput.files = dt.files;
                    handleFilesSelected();
                }
            });
        }

        const handleFilesSelected = () => {
            previewContainer.innerHTML = '';
            const selectedFiles = Array.from(fileInput.files || []);
            const maxFiles = Number(uploadForm.dataset.maxFiles || 10);
            const maxBytes = Number(uploadForm.dataset.maxSize || 10) * 1024 * 1024;
            const messageBox = uploadForm.querySelector('[data-upload-message]');

            if (selectedFiles.length > maxFiles) {
                showMessage(messageBox, `Please select no more than ${maxFiles} media files at once.`, true);
                fileInput.value = '';
                return;
            }

            const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/quicktime', 'video/webm'];
            const invalidFile = selectedFiles.find(
                (f) => f.size > maxBytes || !allowedTypes.includes(f.type)
            );

            if (invalidFile) {
                showMessage(messageBox, `"${invalidFile.name}" is not a supported file format or exceeds the size limit.`, true);
                fileInput.value = '';
                return;
            }

            showMessage(messageBox, `${selectedFiles.length} file${selectedFiles.length === 1 ? '' : 's'} ready for upload.`);

            selectedFiles.forEach((file) => {
                const card = document.createElement('div');
                const label = document.createElement('small');
                const isVideo = file.type.startsWith('video/');
                label.textContent = `${isVideo ? 'VIDEO' : 'PHOTO'} · ${file.name}`;
                card.append(label);

                if (isVideo) {
                    const video = document.createElement('video');
                    video.src = URL.createObjectURL(file);
                    video.controls = false;
                    video.muted = true;
                    video.preload = 'metadata';
                    card.append(video);
                } else {
                    const img = document.createElement('img');
                    img.src = URL.createObjectURL(file);
                    img.alt = file.name;
                    card.append(img);
                }

                previewContainer.append(card);
            });
        };

        fileInput.addEventListener('change', handleFilesSelected);

        // Form Submit with Progress Tracking
        uploadForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (!fileInput.files.length) return;

            const submitBtn = uploadForm.querySelector('button[type="submit"]');
            const noticeBox = uploadForm.querySelector('[data-upload-message]');

            submitBtn.disabled = true;
            submitBtn.setAttribute('aria-busy', 'true');

            if (progressContainer) {
                progressContainer.style.display = 'block';
                if (progressFill) progressFill.style.width = '0%';
                if (progressStatusText) progressStatusText.textContent = 'Uploading... 0%';
            }

            const xhr = new XMLHttpRequest();
            xhr.open('POST', uploadForm.action);
            xhr.setRequestHeader('X-CSRFToken', csrf());

            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) {
                    const percent = Math.round((event.loaded / event.total) * 100);
                    if (progressFill) progressFill.style.width = `${percent}%`;
                    if (progressStatusText) progressStatusText.textContent = `Uploading... ${percent}%`;
                }
            };

            xhr.onload = async () => {
                let result = {};
                try {
                    result = JSON.parse(xhr.responseText);
                } catch (_) {}

                if (xhr.status < 200 || xhr.status >= 300) {
                    showMessage(noticeBox, result.error || 'Upload failed. Please retry.', true);
                    submitBtn.disabled = false;
                    submitBtn.removeAttribute('aria-busy');
                    if (progressContainer) progressContainer.style.display = 'none';
                    return;
                }

                const uploadedCount = result.items?.length || 1;
                if (progressFill) progressFill.style.width = '100%';
                if (progressStatusText) progressStatusText.textContent = 'Upload Complete (100%)';

                showMessage(
                    noticeBox,
                    `✓ Upload submitted for review (${uploadedCount} item${uploadedCount === 1 ? '' : 's'}). Your image/video is pending admin approval.`,
                    false,
                    true
                );

                fileInput.value = '';
                previewContainer.innerHTML = '';
                submitBtn.disabled = false;
                submitBtn.removeAttribute('aria-busy');

                // Reload after short delay to refresh "My Uploads"
                setTimeout(() => {
                    window.location.reload();
                }, 1800);
            };

            xhr.onerror = () => {
                showMessage(noticeBox, 'Upload failed due to a network issue. Please retry.', true);
                submitBtn.disabled = false;
                submitBtn.removeAttribute('aria-busy');
                if (progressContainer) progressContainer.style.display = 'none';
            };

            xhr.send(new FormData(uploadForm));
        });
    }

    document.querySelectorAll('[data-replacement-id]').forEach((link) => {
        link.addEventListener('click', () => {
            sessionStorage.setItem('event-photo-replacement', link.dataset.replacementId);
        });
    });

    // ----------------------------------------------------
    // LIGHTBOX VIEWER
    // ----------------------------------------------------
    const gallery = document.querySelector('[data-lightbox-gallery]');
    const lightboxModal = document.querySelector('#photo-lightbox');

    if (gallery && lightboxModal) {
        const items = [...gallery.querySelectorAll('[data-lightbox-src]')];
        const lightboxImg = lightboxModal.querySelector('img');
        const lightboxCaption = lightboxModal.querySelector('.lightbox-caption-text');
        let currentIndex = 0;
        let previousFocus = null;

        const showPhoto = () => {
            const item = items[currentIndex];
            if (!item) return;
            lightboxImg.src = item.dataset.lightboxSrc;
            lightboxImg.alt = item.querySelector('img')?.alt || 'Event photo';
            if (lightboxCaption) {
                lightboxCaption.textContent = item.dataset.lightboxCaption || '';
            }
        };

        const openLightbox = (index, trigger) => {
            currentIndex = index;
            previousFocus = trigger;
            showPhoto();
            lightboxModal.classList.add('open');
            lightboxModal.setAttribute('aria-hidden', 'false');
            lightboxModal.querySelector('.lightbox-close')?.focus();
        };

        const closeLightbox = () => {
            lightboxModal.classList.remove('open');
            lightboxModal.setAttribute('aria-hidden', 'true');
            if (previousFocus) previousFocus.focus();
        };

        items.forEach((item, idx) => {
            item.addEventListener('click', () => openLightbox(idx, item));
        });

        lightboxModal.querySelector('.lightbox-close')?.addEventListener('click', closeLightbox);

        lightboxModal.querySelector('.lightbox-prev')?.addEventListener('click', () => {
            currentIndex = (currentIndex + items.length - 1) % items.length;
            showPhoto();
        });

        lightboxModal.querySelector('.lightbox-next')?.addEventListener('click', () => {
            currentIndex = (currentIndex + 1) % items.length;
            showPhoto();
        });

        document.addEventListener('keydown', (e) => {
            if (!lightboxModal.classList.contains('open')) return;
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') lightboxModal.querySelector('.lightbox-prev')?.click();
            if (e.key === 'ArrowRight') lightboxModal.querySelector('.lightbox-next')?.click();
        });
    }

    // ----------------------------------------------------
    // REPORT PHOTO MODAL
    // ----------------------------------------------------
    const reportDialog = document.querySelector('#report-photo-dialog');
    const reportForm = document.querySelector('#report-photo-form');

    document.querySelectorAll('.report-photo-trigger').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (!reportDialog || !reportForm) return;
            reportForm.elements.photo_id.value = btn.dataset.photoId;
            const messageBox = reportForm.querySelector('[data-report-message]');
            showMessage(messageBox, '');
            reportDialog.showModal();
            reportForm.elements.reason.focus();
        });
    });

    reportForm?.querySelector('[data-dialog-close]')?.addEventListener('click', () => {
        reportDialog?.close();
    });

    reportForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = reportForm.querySelector('button[type="submit"]');
        const messageBox = reportForm.querySelector('[data-report-message]');

        if (!reportForm.elements.reason.value) {
            showMessage(messageBox, 'Please select a reason for reporting.', true);
            return;
        }

        submitBtn.disabled = true;
        showMessage(messageBox, 'Submitting report...');

        try {
            const photoId = reportForm.elements.photo_id.value;
            const response = await fetch(`/resident/photos/${photoId}/report`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf(),
                },
                body: JSON.stringify({
                    reason: reportForm.elements.reason.value,
                    description: reportForm.elements.description.value,
                }),
            });

            if (!response.ok) throw new Error(await apiError(response));

            showMessage(messageBox, 'Photo report submitted for admin review.', false, true);
            setTimeout(() => reportDialog?.close(), 900);
        } catch (err) {
            showMessage(messageBox, err.message, true);
        } finally {
            submitBtn.disabled = false;
        }
    });

    // ----------------------------------------------------
    // ADMIN MODERATION SHORTCUTS & ACTIONS
    // ----------------------------------------------------
    const rejectDialog = document.querySelector('#reject-dialog');
    const rejectForm = document.querySelector('#reject-form');

    document.querySelectorAll('[data-photo-action]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const action = btn.dataset.photoAction;
            const id = btn.dataset.photoId;

            if (action === 'reject' && rejectDialog && rejectForm) {
                rejectForm.querySelector('#reject-photo-id').value = id;
                rejectDialog.showModal();
                return;
            }

            await moderatePhoto(btn, id, action);
        });
    });

    rejectForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = rejectForm.querySelector('#reject-photo-id').value;
        const btn = document.querySelector(`[data-photo-action="reject"][data-photo-id="${id}"]`);
        if (!btn) return;
        const reason = rejectForm.querySelector('#reject-reason')?.value || '';
        const ok = await moderatePhoto(btn, id, 'reject', reason);
        if (ok) rejectDialog?.close();
    });

    async function moderatePhoto(btn, id, action, rejectionReason = '') {
        btn.disabled = true;
        btn.setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(`/admin/events/photos/${id}/${action}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf(),
                },
                body: JSON.stringify({ rejection_reason: rejectionReason }),
            });
            if (!response.ok) throw new Error(await apiError(response));
            window.location.reload();
            return true;
        } catch (err) {
            btn.disabled = false;
            const rowMessage = btn.closest('.moderation-row')?.querySelector('[data-action-message]');
            showMessage(rowMessage, err.message || 'Error moderating photo.', true);
            return false;
        } finally {
            btn.removeAttribute('aria-busy');
        }
    }

    document.querySelectorAll('[data-media-feature]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const featured = btn.dataset.featured !== 'true';
            const response = await fetch(`/admin/events/photos/${btn.dataset.mediaFeature}/feature`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({ featured }),
            });
            if (response.ok) window.location.reload();
        });
    });

    document.querySelectorAll('[data-media-cover]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const response = await fetch(`/admin/events/photos/${btn.dataset.mediaCover}/cover`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf() },
            });
            if (response.ok) window.location.reload();
        });
    });

    document.querySelectorAll('[data-bulk-action]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const ids = [...document.querySelectorAll('[data-media-select]:checked')].map((i) => Number(i.value));
            if (!ids.length) return;
            const action = btn.dataset.bulkAction;
            let rejectionReason = '';
            if (action === 'REJECT') {
                rejectionReason = window.prompt('Rejection reason:');
                if (!rejectionReason) return;
            }
            btn.disabled = true;
            try {
                const response = await fetch('/admin/events/photos/bulk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                    body: JSON.stringify({ ids, action, rejection_reason: rejectionReason }),
                });
                if (!response.ok) throw new Error(await apiError(response));
                window.location.reload();
            } catch (err) {
                window.alert(err.message);
                btn.disabled = false;
            }
        });
    });
});
