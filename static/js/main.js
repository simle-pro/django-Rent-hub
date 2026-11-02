/* RentHub — интерактив: раскрытие карточек, закрытие баннеров, кнопка наверх */
(function () {
  "use strict";

  /* 1. Появление стеклянных карточек при скролле */
  var revealables = document.querySelectorAll(".glass");
  if ("IntersectionObserver" in window && revealables.length) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    revealables.forEach(function (el) { io.observe(el); });
  } else {
    revealables.forEach(function (el) { el.classList.add("in"); });
  }

  /* 2. Сообщения Django: автозакрытие + крестик */
  document.querySelectorAll(".msg").forEach(function (msg) {
    var close = document.createElement("button");
    close.type = "button";
    close.className = "msg-close";
    close.setAttribute("aria-label", "Закрыть");
    close.textContent = "✕";
    close.addEventListener("click", function () {
      msg.style.transition = "opacity .3s, transform .3s";
      msg.style.opacity = "0";
      msg.style.transform = "translateX(40px)";
      setTimeout(function () { msg.remove(); }, 320);
    });
    msg.appendChild(close);
    setTimeout(function () {
      if (msg.isConnected) close.click();
    }, 7000);
  });

  /* 3. Кнопка «наверх» */
  var topBtn = document.createElement("button");
  topBtn.type = "button";
  topBtn.className = "to-top";
  topBtn.setAttribute("aria-label", "Наверх");
  topBtn.textContent = "↑";
  document.body.appendChild(topBtn);
  topBtn.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  window.addEventListener("scroll", function () {
    topBtn.classList.toggle("show", window.scrollY > 400);
  }, { passive: true });

})();
