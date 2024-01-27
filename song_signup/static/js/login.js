const loginForm = document.getElementById("login-form");
const audienceWrapper = document.getElementById("audience-wrapper")
const formMessages = document.getElementById("form-messages");
const toggleCheckbox = document.getElementById("ticket-type-toggle")
const toggleSlider = document.querySelector(".toggle-slider")

loginForm.addEventListener("submit", e => {
    e.preventDefault();
    const formData = new FormData(loginForm);
    fetch("/login", { method: "POST", body: formData })
        .then(async response => {
            if (!response.ok) {
                const data = await response.json();
                throw Error(data.error);
            }
            window.location.replace("/home");
        })
        .catch(error => {
            formMessages.innerHTML = `<p>${error.message}</p>`;
        });
});

toggleCheckbox.addEventListener("change", e => {
    if (e.target.checked) {  // Singer
        const sliderWidth = getComputedStyle(document.documentElement).getPropertyValue('--slider-width')
        toggleSlider.style.left = `calc(100% - ${sliderWidth}`;
        loginForm.style.display = 'block';
        setTimeout(() => {
            loginForm.classList.add('active');
        }, 10);
        audienceWrapper.classList.remove('active');

    }
    else { // Audience
        toggleSlider.style.left = '0';
        loginForm.classList.remove('active');
        audienceWrapper.classList.add('active');
        setTimeout(() => loginForm.style.display = 'none', 30);
    }
})
