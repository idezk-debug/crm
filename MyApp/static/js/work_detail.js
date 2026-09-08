        function openImageModal(imageUrl) {
            // Set the source of the image in the modal
            document.getElementById('fullResImage').src = imageUrl;

            // Trigger the Bootstrap Modal
            var myModal = new bootstrap.Modal(document.getElementById('imageViewerModal'));
            myModal.show();
        }