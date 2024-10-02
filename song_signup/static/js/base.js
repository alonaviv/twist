const questionText = document.getElementById("question-text");
const triviaWrapper = document.getElementById("trivia-wrapper");
const answer1 = document.getElementById("answer1");
const answer2 = document.getElementById("answer2");
const answer3 = document.getElementById("answer3");
const answer4 = document.getElementById("answer4");

setInterval(getQuestion, 500);

async function getQuestion() {
    const questionRes = await fetch("/get_active_question");

    if (questionRes.status === 200 && isLoggedIn) {
        const question = await questionRes.json();
        questionText.innerHTML = `<p>${question.question}</p>`;
        answer1.innerHTML = `<p>${question.choiceA}</p>`
        answer2.innerHTML = `<p>${question.choiceB}</p>`
        answer3.innerHTML = `<p>${question.choiceC}</p>`
        answer4.innerHTML = `<p>${question.choiceD}</p>`
        triviaWrapper.classList.remove('hidden');

    }
    else {
        triviaWrapper.classList.add('hidden');
    }
}
