// Toggle menu with hamburger

const hamburger = document.getElementById('hamburger');
const menuWrapper = document.getElementById('menu-wrapper');
const menu = document.getElementById('menu');
const navbar = document.getElementById('navbar');
let showMenu = false;

hamburger.addEventListener('click', toggleMenu);

function toggleMenu() {
    if (!showMenu) {
        hamburger.classList.add('close');
        menuWrapper.classList.add('extend')
        menu.style.transitionDelay = '0.1s'; 
        navbar.style.position = 'relative';
        showMenu = true;
    } else{
        hamburger.classList.remove('close');
        menuWrapper.classList.remove('extend');
        menu.style.transitionDelay = '0s'; 
        navbar.style.position = 'fixed';
        showMenu = false;

    }
    
}

