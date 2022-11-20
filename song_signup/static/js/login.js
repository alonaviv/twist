const loginForm = document.getElementById("login-form");
const formMessages = document.getElementById("form-messages");

loginForm.addEventListener("submit", e => {
    e.preventDefault();
     if (confirm("Did you pay the entrance fee?")) {
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
     }
});
