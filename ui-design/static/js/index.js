// Toggle menu with hamburger

const hamburger = document.getElementById('hamburger');
const menuWrapper = document.getElementById('menu-wrapper');
const menu = document.getElementById('menu');
const navbar = document.getElementById('navbar');
const logo = document.querySelector('.logo');
let showMenu = false;

hamburger.addEventListener('click', toggleMenu);

function getRGBA(element, alpha, styleName='backgroundColor') {
    let rgb = window.getComputedStyle(element)[styleName];
    
    const colorParams =
      rgb.includes('a')
        ? rgb.substring(5, rgb.length - 1)
        : rgb.substring(4, rgb.length - 1);
    const [red, green, blue] = colorParams.replace(/\s/g, '').split(",");
    return `rgba(${red},${green},${blue},${alpha})`;

}

function flushCss(...elements) {
  elements.forEach((elem) => elem.offsetHeight);
}

function toggleMenu() {
    let navbarRBG;
    if (!showMenu) {
        hamburger.classList.add('close');
        menuWrapper.classList.add('extend')
        menu.style.transitionDelay = '0.1s'; 
        showMenu = true;
    } else{
        hamburger.classList.remove('close');
        menuWrapper.classList.remove('extend');
        menu.style.transitionDelay = '0s'; 
        navbar.style.position = 'fixed';
        showMenu = false;

    }
    
}

// Open up dashboard tips
const tips = document.getElementById('tips');
const dashboardWrapper = document.getElementById("dashboard-wrapper");
expandTips = false;
const originalHeight = window.getComputedStyle(dashboardWrapper).height;

document.getElementById("expand-tips").addEventListener('click', toggleTips);

function toggleTips() {
    console.log("HEllo");
    if (!expandTips) {
        tips.style.transform = "scaleY(1)";
        dashboardWrapper.style.height = "65vh";
        expandTips = true;
    } else {
        tips.style.transform = "scaleY(0)";
        dashboardWrapper.style.height = originalHeight;
        expandTips = false;
    }

}


// Just for UI viewing - toggling the dashboard
const btn = document.getElementById('manage-songs-btn');
const dashboard = document.getElementById('dashboard');
const noSong = document.getElementById('no-song');

btn.addEventListener('click', () =>{
    if (noSong.classList.contains('hidden')) {
    noSong.classList.remove('hidden');
    dashboard.classList.add('hidden');
    }
});





