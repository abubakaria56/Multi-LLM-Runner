(function () {
  var root = document.documentElement;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  function currentTheme() {
    var set = root.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  document.querySelectorAll(".theme-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("mlr-theme", next); } catch (e) {}
    });
  });

  var nav = document.getElementById("nav");
  function onScroll() { nav.classList.toggle("scrolled", window.scrollY > 8); }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  document.querySelectorAll(".copy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      var done = function () {
        btn.textContent = "Copied";
        btn.classList.add("done");
        setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("done"); }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {});
      }
    });
  });

  var revealed = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    revealed.forEach(function (el) { io.observe(el); });
  } else {
    revealed.forEach(function (el) { el.classList.add("in"); });
  }

  var stream = document.querySelector(".stream");
  if (stream) {
    var lines = stream.querySelectorAll(".ln");
    var playStream = async function () {
      for (var i = 0; i < lines.length; i++) {
        lines[i].classList.add("on");
        await sleep(i === 3 ? 700 : 420);
      }
    };
    if (reduceMotion || !("IntersectionObserver" in window)) {
      lines.forEach(function (l) { l.classList.add("on"); });
    } else {
      var so = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting) { so.disconnect(); playStream(); }
      }, { threshold: 0.35 });
      so.observe(stream);
    }
  }

  var demo = document.querySelector(".demo");
  if (!demo) return;

  var typed = demo.querySelector(".typed");
  var promptText = typed.getAttribute("data-text");
  var runBtn = demo.querySelector(".run");
  var cols = Array.prototype.map.call(demo.querySelectorAll(".col"), function (col) {
    var p = col.querySelector("p");
    p.innerHTML = "";
    var words = p.getAttribute("data-text").split(" ").map(function (word, i, all) {
      var span = document.createElement("span");
      span.className = "w";
      span.textContent = word + (i < all.length - 1 ? " " : "");
      p.appendChild(span);
      return span;
    });
    return {
      el: col,
      words: words,
      delay: parseInt(col.getAttribute("data-delay"), 10),
      timeText: col.getAttribute("data-time"),
      time: col.querySelector(".time"),
      thinking: col.querySelector(".thinking")
    };
  });

  function showFinal() {
    typed.textContent = promptText;
    cols.forEach(function (c) {
      c.words.forEach(function (w) { w.classList.add("on"); });
      c.time.textContent = c.timeText;
      c.time.classList.add("on");
      c.el.classList.add("done");
    });
  }

  if (reduceMotion) { showFinal(); return; }

  var visible = true;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      visible = entries[0].isIntersecting;
    }).observe(demo);
  }

  function reset() {
    typed.textContent = "";
    cols.forEach(function (c) {
      c.words.forEach(function (w) { w.classList.remove("on"); });
      c.time.classList.remove("on");
      c.thinking.classList.remove("on");
      c.el.classList.remove("done");
    });
  }

  async function streamColumn(c) {
    await sleep(c.delay);
    c.thinking.classList.remove("on");
    for (var i = 0; i < c.words.length; i++) {
      c.words[i].classList.add("on");
      await sleep(26);
    }
    c.time.textContent = c.timeText;
    c.time.classList.add("on");
    c.el.classList.add("done");
  }

  async function cycle() {
    reset();
    await sleep(500);
    for (var i = 1; i <= promptText.length; i++) {
      typed.textContent = promptText.slice(0, i);
      await sleep(38);
    }
    await sleep(350);
    runBtn.classList.add("pressed");
    await sleep(160);
    runBtn.classList.remove("pressed");
    cols.forEach(function (c) { c.thinking.classList.add("on"); });
    await Promise.all(cols.map(streamColumn));
    await sleep(4200);
  }

  (async function loop() {
    for (;;) {
      if (!visible || document.hidden) { await sleep(400); continue; }
      await cycle();
    }
  })();
})();
