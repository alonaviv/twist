const singerFormWrapper = document.getElementById("singer-login-wrapper");
const audienceFormWrapper = document.getElementById("audience-login-wrapper");
const formMessages = document.querySelector(".form-messages");
const singerButton = document.querySelector(".ticket-button[value='singer']");
const audienceButton = document.querySelector(".ticket-button[value='audience']");
const ticketSelectionWrapper = document.getElementById("ticket-selection-wrapper");
const loginBack = document.getElementById("login-back");
const audienceImagesCheckbox = document.getElementById("no-upload-audience");
const singerImagesCheckbox = document.getElementById("no-upload-singer");
const audienceUploadImageWrapper = document.getElementById("audience-image-upload-wrapper");
const singerUploadImageWrapper = document.getElementById("singer-image-upload-wrapper");

if ('scrollRestoration' in history) {
    history.scrollRestoration = 'manual'; // Disable browser's automatic scroll restoration
}

document.addEventListener("DOMContentLoaded", () => {
    window.scrollTo(0, 0);
});

const formListener =  e => {
    e.preventDefault();

    const form = e.target
    const formData = new FormData(form);
    fetch("/login", { method: "POST", body: formData })
        .then(async response => {
            if (!response.ok) {
                const data = await response.json();
                throw Error(data.error);
            }
            setTimeout(() => {
                window.location.replace("/home");
            }, 300);  // Allow the session cookie to be set
        })
        .catch(error => {
            formMessages.innerHTML = `<p>${error.message}</p>`;
            window.scrollTo(0, 0);
        });
    }

singerFormWrapper.addEventListener("submit", formListener)
audienceFormWrapper.addEventListener("submit", formListener)

audienceImagesCheckbox.parentNode.addEventListener("click", (e) => {
    if (e.target.checked) {
        audienceUploadImageWrapper.classList.remove("hidden");
    } else {
        audienceUploadImageWrapper.classList.add("hidden");
    }
})

singerImagesCheckbox.parentNode.addEventListener("click", (e) => {
    if (e.target.checked) {
        singerUploadImageWrapper.classList.remove("hidden");
    } else {
        singerUploadImageWrapper.classList.add("hidden");
    }
})


singerButton.addEventListener("click", e => {
    window.scrollTo(0, 0);
    activateForm(singerFormWrapper, audienceFormWrapper)
});

audienceButton.addEventListener("click", e => {
    window.scrollTo(0, 0);
    activateForm(audienceFormWrapper, singerFormWrapper)
});

loginBack.addEventListener("click", deactivateForm);

function activateForm(selectedForm, otherForm) {
    selectedForm.style.display = 'block';
    loginBack.style.display = 'block';
    setTimeout(() => {
        selectedForm.classList.add('active');
        loginBack.classList.add('active');
    }, 10);
    otherForm.classList.remove('active');
    ticketSelectionWrapper.classList.add('hidden');

}

function deactivateForm() {
    window.scrollTo(0, 0);
    setTimeout(() => {
        loginBack.classList.remove('active');
        singerFormWrapper.classList.remove('active');
        audienceFormWrapper.classList.remove('active');
        formMessages.innerHTML = "";
    }, 10);
    setTimeout(() => {
        loginBack.style.display = 'none';
        singerFormWrapper.style.display = 'none';
        audienceFormWrapper.style.display = 'none';
    }, 100);

    setTimeout(() => {
        ticketSelectionWrapper.classList.remove('hidden');
    }, 300);
}