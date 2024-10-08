import { getCookie } from "./utils.js";

const questionText = document.querySelector(".question-text");
const questionImage = document.getElementById("question-image-base");
const triviaWrapper = document.querySelector(".trivia-wrapper");
const triviaQuestionsWrapper = document.querySelector(".trivia-questions-wrapper");
const triviaWinnerWrapper = document.querySelector(".trivia-winner-wrapper");
const triviaWinnerName = document.querySelector(".trivia-winner-name");
const triviaAnswer = document.querySelector(".trivia-answer");
const triviaAnswerTitle = document.querySelector(".trivia-answer-title");
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

    if (questionRes.status === 200 && isLoggedIn && !isSuperuser) {
        const question = await questionRes.json();
        const winner = question.winner;
        const image = question.image;

        if (winner === null) {
            if (image) {
                questionImage.src = image;
                questionImage.classList.remove('hidden');
            }
            else {
                questionImage.classList.add('hidden');
            }

            questionText.innerHTML = `<p>${question.question}</p>`;
            answer1.innerHTML = `<p>${question.choiceA}</p>`
            answer2.innerHTML = `<p>${question.choiceB}</p>`
            answer3.innerHTML = `<p>${question.choiceC}</p>`
            answer4.innerHTML = `<p>${question.choiceD}</p>`
            await getUserAnswer();
            triviaQuestionsWrapper.classList.remove('hidden');
            triviaWinnerWrapper.classList.add('hidden');

            triviaWinnerName.classList.remove('active');
            triviaAnswer.classList.remove('active');
            triviaAnswerTitle.classList.remove('active');
        }
        else {
            triviaWinnerName.innerHTML = `<p>${winner}</p>`
            triviaAnswer.innerHTML = `<p>${question.answer_text}</p>`
            triviaQuestionsWrapper.classList.add('hidden');
            triviaWinnerWrapper.classList.remove('hidden');

            setTimeout(() => {
                triviaWinnerName.classList.add('active');
                triviaAnswer.classList.add('active');
                triviaAnswerTitle.classList.add('active');
            }, 5000)
        }
        triviaWrapper.classList.remove('hidden');
        setTimeout(() => {
            triviaWrapper.classList.add('active');
        }, 5);
    }
    else {
        triviaWrapper.classList.remove('active')
        setTimeout(() => {
            triviaWrapper.classList.add('hidden');
        }, 500);
    }
}

function colorAnswers(selectedAnswer) {
    answers.forEach(answer => {
        if (answer.dataset.answer === selectedAnswer) {
            answer.style.backgroundColor = '#00b3c5'; // Secondary color
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