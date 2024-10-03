import { getCookie } from "./utils.js";

const questionText = document.getElementById("question-text");
const triviaWrapper = document.getElementById("trivia-wrapper");
const answer1 = document.getElementById("answer1");
const answer2 = document.getElementById("answer2");
const answer3 = document.getElementById("answer3");
const answer4 = document.getElementById("answer4");

const answers = [answer1, answer2, answer3, answer4]
const originalAnswerColor = answer1.style.backgroundColor;

answers.forEach(answer => {
    answer.addEventListener('click', chooseAnswer)
})

const csrftoken = getCookie('csrftoken');

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
        await getUserAnswer();
        triviaWrapper.classList.remove('hidden');

    }
    else {
        triviaWrapper.classList.add('hidden');
    }
}

function colorAnswers(selectedAnswer) {
    answers.forEach(answer => {
        if (answer.dataset.answer === selectedAnswer) {
            answer.style.backgroundColor = '#00C575'; // Primary color
        }
        else {
            answer.style.backgroundColor = '#666';
        }
    })
}

function clearAnswers(selectedAnswer) {
    answers.forEach(answer => {
        answer.style.backgroundColor = originalAnswerColor;
    });
}

async function chooseAnswer(e) {
    e.preventDefault();
    const answerID = e.currentTarget.dataset.answer;

    const response = await fetch("/choose_trivia_question", {
        method: "POST",
        headers: {
            "X-CSRFToken": csrftoken,
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            "answer-id": answerID,
        }),
    })

    if (response.status === 201) {
        colorAnswers(answerID);
    }
}

async function getUserAnswer() {
    const response = await fetch("get_selected_answer");
    if (response.status === 200) {
        const data = await response.json();
        colorAnswers(data.choice.toString());
    } else {
        clearAnswers();
    }
}