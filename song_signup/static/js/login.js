const singerFormWrapper = document.getElementById("singer-login-wrapper");
const audienceFormWrapper = document.getElementById("audience-login-wrapper");
const formMessages = document.querySelector(".form-messages");
const singerButton = document.querySelector(".ticket-button[value='singer']");
const audienceButton = document.querySelector(".ticket-button[value='audience']");
const ticketSelectionWrapper = document.getElementById("ticket-selection-wrapper");
const loginBack = document.getElementById("login-back")


const formListner =  e => {
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

singerFormWrapper.addEventListener("submit", formListner)
audienceFormWrapper.addEventListener("submit", formListner)


singerButton.addEventListener("click", e => {
    activateForm(singerFormWrapper, audienceFormWrapper)
});

audienceButton.addEventListener("click", e => {
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
    setTimeout(() => {
        loginBack.classList.remove('active');
        singerFormWrapper.classList.remove('active');
        audienceFormWrapper.classList.remove('active');
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