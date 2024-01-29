const singerLoginForm = document.getElementById("singer-login-form");
const audienceLoginForm = document.getElementById("audience-login-form");
const audienceWrapper = document.getElementById("audience-wrapper")
const formMessages = document.getElementById("form-messages");
const toggleCheckbox = document.getElementById("ticket-type-toggle")
const toggleSlider = document.querySelector(".toggle-slider")


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
            window.location.replace("/home");
        })
        .catch(error => {
            formMessages.innerHTML = `<p>${error.message}</p>`;
        });
    }

singerLoginForm.addEventListener("submit", formListner)
audienceLoginForm.addEventListener("submit", formListner)

toggleCheckbox.addEventListener("change", e => {
    if (e.target.checked) {  // Singer
        const sliderWidth = getComputedStyle(document.documentElement).getPropertyValue('--slider-width')
        toggleSlider.style.left = `calc(100% - ${sliderWidth}`;
        singerLoginForm.style.display = 'block';
        setTimeout(() => {
            singerLoginForm.classList.add('active');
        }, 10);
        audienceWrapper.classList.remove('active');

    }
    else { // Audience
        toggleSlider.style.left = '0';
        singerLoginForm.classList.remove('active');
        audienceWrapper.classList.add('active');
        setTimeout(() => singerLoginForm.style.display = 'none', 30);
    }
})
