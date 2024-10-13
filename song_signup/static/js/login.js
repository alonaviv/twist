const singerFormWrapper = document.getElementById("singer-login-wrapper");
const audienceFormWrapper = document.getElementById("audience-login-wrapper");
const singerButton = document.querySelector(".ticket-button[value='singer']");
const audienceButton = document.querySelector(".ticket-button[value='audience']");
const ticketSelectionWrapper = document.getElementById("ticket-selection-wrapper");
const loginBack = document.getElementById("login-back")

singerButton.addEventListener("click", e => {
    activateForm(singerFormWrapper)
});

audienceButton.addEventListener("click", e => {
    activateForm(audienceFormWrapper)
});

loginBack.addEventListener("click", deactivateForm);

function activateForm(selectedForm) {
    selectedForm.style.display = 'block';
    loginBack.style.display = 'block';
    setTimeout(() => {
        selectedForm.classList.add('active');
        loginBack.classList.add('active');
    }, 10);

    if (selectedForm === singerFormWrapper) {
        audienceFormWrapper.classList.remove('active');
    } else {
        singerFormWrapper.classList.remove('active');
    }

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