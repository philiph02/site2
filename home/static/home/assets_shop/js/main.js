/*=============== SHOW MENU ===============*/
const navMenu = document.getElementById('nav-menu'),
      navToggle = document.getElementById('nav-toggle'),
      navClose = document.getElementById('nav-close')

/*===== MENU SHOW =====*/
/* Validate if constant exists */
if(navToggle) {
  navToggle.addEventListener("click", () => {
    navMenu.classList.add('show-menu')
  })
}

/*===== MENU HIDDEN =====*/
/* Validate if constant exists */
if(navClose) {
  navClose.addEventListener("click", () => {
    navMenu.classList.remove('show-menu')
  })
}

/*=============== SHOW CART ===============*/
const cart = document.getElementById('cart'),
      cartShop = document.getElementById('cart-shop'),
      cartClose = document.getElementById('cart-close')

/*===== CART SHOW =====*/
/* Validate if constant exists */
if(cartShop) {
  cartShop.addEventListener("click", () => {
    cart.classList.add('show-cart')
  })
}

/*===== CART HIDDEN =====*/
/* Validate if constant exists */
if(cartClose) {
  cartClose.addEventListener("click", () => {
    cart.classList.remove('show-cart')
  })
}

/*=============== SHOW LOGIN ===============*/
const login = document.getElementById('login'),
      loginButton = document.getElementById('login-button'),
      loginClose = document.getElementById('login-close')

/*===== LOGIN SHOW =====*/
/* Validate if constant exists */
if(loginButton) {
  loginButton.addEventListener("click", () => {
    login.classList.add('show-login')
  })
}

/*===== LOGIN HIDDEN =====*/
/* Validate if constant exists */
if(loginClose) {
  loginClose.addEventListener("click", () => {
    login.classList.remove('show-login')
  })
}

/*=============== HOME SWIPER ===============*/
var homeSwiper = new Swiper(".home-swiper", {
    spaceBetween: 30,
    loop: true,
    
    // --- ADDED AUTOPLAY CONFIGURATION ---
    autoplay: {
        delay: 7000, // 7 seconds
        disableOnInteraction: true, // Stop autoplay if user swipes/clicks
    },
    // ------------------------------------

    pagination: {
      el: ".home-pagination",
      clickable: true,
    },
});

/*=============== CHANGE BACKGROUND HEADER ===============*/
function scrollHeader() {
  const header = document.getElementById('header')
  // when the scroll is greater than 50 viewport height, add the scroll-header class to the header tag
  if(this.scrollY >= 50) header.classList.add('scroll-header'); else header.classList.remove('scroll-header')
}
window.addEventListener('scroll', scrollHeader)

/*=============== NEW SWIPER ===============*/
var printsSwiper = new Swiper('.new-swiper', {
    slidesPerView: 3,
    grid: { rows: 3, fill: 'row' },
    spaceBetween: 30,
    pagination: { el: '.prints-pagination', clickable: true },
    navigation: {
        nextEl: ".prints-swiper-wrapper .swiper-button-next",
        prevEl: ".prints-swiper-wrapper .swiper-button-prev",
    }
});



/*=============== SHOW SCROLL UP ===============*/ 
function scrollUp() {
  const scrollUp = document.getElementById('scroll-up');
  // when the scroll is higher than 350 viewport height, add the show-scroll class to a tag with the scroll-top class
  if(this.scrollY >= 350) scrollUp.classList.add('show-scroll'); else scrollUp.classList.remove('show-scroll')
}
window.addEventListener('scroll', scrollUp)

/*=============== LIGHT BOX ===============*/


/*=============== QUESTIONS ACCORDION ===============*/
const accordionItem = document.querySelectorAll('.questions__item')

accordionItem.forEach((item) => {
  const accordionHeader = item.querySelector('.questions__header')

  accordionHeader.addEventListener('click', () => {
    const openItem = document.querySelector('.accordion-open')

    toggleItem(item)

    if(openItem && openItem !== item) {
      toggleItem(openItem)
    }
  })
})

const toggleItem = (item) => {
  const accordionContent = item.querySelector('.questions__content')

  if(item.classList.contains('accordion-open')) {
    accordionContent.removeAttribute('style')
    item.classList.remove('accordion-open')
  }
  else {
    accordionContent.style.height = accordionContent.scrollHeight + 'px'
    item.classList.add('accordion-open')
  }
}

/*=============== STYLE SWITCHER ===============*/
const styleSwitcherToggle = document.querySelector(".style__switcher-toggler");
styleSwitcherToggle.addEventListener("click", () => {
  document.querySelector(".style__switcher").classList.toggle("open");
})

// HIDE STYLE SWITCHER ON SCROLL
window.addEventListener("scroll", () => {
  if(document.querySelector(".style__switcher").classList.contains("open")) {
    document.querySelector(".style__switcher").classList.remove("open");
  }
})

// THEME COLORS
function themeColors() {
  const colorStyle = document.querySelector(".js-color-style"),
        themeColorsContainer = document.querySelector(".js-theme-colors");
  themeColorsContainer.addEventListener("click", ({target}) => {
    if(target.classList.contains("js-theme-color-item")) {
      localStorage.setItem("color", target.getAttribute("data-js-theme-color"));
      setColors();
    }
  })
  function setColors() {
    let path = colorStyle.getAttribute("href").split("/");
    path = path.slice(0, path.length - 1);
    colorStyle.setAttribute("href", path.join("/") + "/" + localStorage.getItem("color") + ".css");

    if(document.querySelector(".js-theme-color-item.active")) {
      document.querySelector(".js-theme-color-item.active").classList.remove("active");
    }
    document.querySelector("[data-js-theme-color=" + localStorage.getItem("color") + "]").classList.add("active");
  }
  if(localStorage.getItem("color") !== null) {
    setColors();
  }
  else {
    const defaultColor = colorStyle.getAttribute("href").split("/").pop().split(".").shift();
    document.querySelector("[data-js-theme-color" + defaultColor + "]").classList.add("active");
  }
}

themeColors();

/* =========================================
   WARENKORB-JUMP-ANIMATION (NEUE VERSION)
   ========================================= */

/* Wir warten, bis das gesamte Fenster (inkl. Bilder) geladen ist, 
   um sicherzugehen, dass alle Buttons da sind. */
window.addEventListener('load', () => {
    
    const cartIcon = document.getElementById('cart-shop');
    
    // Findet ALLE "Add to Cart"-Buttons auf der Seite
    const addButtons = document.querySelectorAll('.add-to-cart-btn, #add-to-cart-btn');

    if (cartIcon) {
        // TEIL 1: PRÜFEN, ob wir gerade neu geladen haben
        if (sessionStorage.getItem('justAddedToCart') === 'true') {
            // Ja? Dann Animation abspielen!
            cartIcon.classList.add('is-jumping');
            
            // Flag löschen, damit es nicht bei jedem Neuladen springt
            sessionStorage.removeItem('justAddedToCart');

            // CSS-Klasse nach der Animation wieder entfernen
            cartIcon.addEventListener('animationend', () => {
                cartIcon.classList.remove('is-jumping');
            }, { once: true }); // 'once: true' entfernt den Listener automatisch
        }

        // TEIL 2: NEUE Klicks überwachen, um das Flag zu setzen
        addButtons.forEach(button => {
            button.addEventListener('click', () => {
                // Setzt das Flag, BEVOR die Seite neu lädt
                sessionStorage.setItem('justAddedToCart', 'true');
            });
        });
    }
});