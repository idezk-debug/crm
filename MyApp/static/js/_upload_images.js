      const uploadArea = document.getElementById("uploadArea");
      const fileInput = document.getElementById("fileInput");
      const previewGrid = document.getElementById("previewGrid");
      const error = document.getElementById("error");
      const submitBtn = document.getElementById("submitBtn");

      let filesArray = [];

      function renderPreview() {
        previewGrid.innerHTML = "";

        filesArray.forEach((file, index) => {
          const reader = new FileReader();

          reader.onload = function (e) {
            previewGrid.innerHTML += `
<div class="preview-card">
<img src="${e.target.result}">
<button class="remove-btn" onclick="removeImage(${index})">X</button>
</div>
`;
          };

          reader.readAsDataURL(file);
        });

        if (filesArray.length > 0) {
          submitBtn.disabled = false;
          submitBtn.classList.add("active");
        } else {
          submitBtn.disabled = true;
          submitBtn.classList.remove("active");
        }
      }

      function removeImage(index) {
        filesArray.splice(index, 1);
        renderPreview();
      }

      function handleFiles(files) {
        error.innerHTML = "";

        const validTypes = ["image/jpeg", "image/png", "image/jpg"];
        const maxSize = 2 * 1024 * 1024;

        Array.from(files).forEach((file) => {
          if (!validTypes.includes(file.type)) {
            error.innerHTML = "Only JPG, PNG allowed";
            return;
          }

          if (file.size > maxSize) {
            error.innerHTML = "Max size 2MB";
            return;
          }

          filesArray.push(file);
        });

        renderPreview();
      }

      fileInput.addEventListener("change", function () {
        handleFiles(this.files);
      });

      uploadArea.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadArea.classList.add("dragover");
      });

      uploadArea.addEventListener("dragleave", () => {
        uploadArea.classList.remove("dragover");
      });

      uploadArea.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadArea.classList.remove("dragover");
        handleFiles(e.dataTransfer.files);
      });

      document
        .getElementById("imageUploadForm")
        .addEventListener("submit", function (e) {
          e.preventDefault();

          let formData = new FormData();

          filesArray.forEach((file) => {
            formData.append("images", file);
          });

          formData.append(
            "csrfmiddlewaretoken",
            document.querySelector("[name=csrfmiddlewaretoken]").value,
          );

          fetch("/work/{{ work.id }}/upload-images/", {
            method: "POST",
            body: formData,
            headers: {
              "X-Requested-With": "XMLHttpRequest",
            },
          })
            .then((res) => res.json())
            .then((data) => {
              if (data.status === "success") {
                document.getElementById("uploadedImages").innerHTML = data.html;

                filesArray = [];
                renderPreview();
              } else {
                alert("Upload failed");
              }
            })
            .catch((err) => {
              console.log(err);
              alert("Upload error");
            });
        });

      function deleteImage(imageId) {
        fetch(`/delete-image/${imageId}/`, {
          method: "POST",

          headers: {
            "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
              .value,
            "X-Requested-With": "XMLHttpRequest",
          },
        })
          .then((res) => res.json())
          .then((data) => {
            if (data.status === "success") {
              document.getElementById(`img-${imageId}`).remove();
            } else {
              alert("Delete failed");
            }
          })

          .catch((err) => {
            console.log(err);
            alert("Delete error");
          });
      }