// Shows a thin bar under the frame when the next page takes longer than 200 ms, marks the button
// that sent a form as busy, and keeps a form from being sent twice. Without JavaScript, links and
// forms work as before (specs/010.1-loading-feedback-pinned-frame, contracts/loading-script.md).

const DELAY = 200;
let pending = null; // the latest page load: { timer, form, button }
let sending = new WeakSet(); // POST forms sent from this page; a second send is cancelled
const busy = new Set(); // every button marked busy, so a restore can clear them all

function bar() {
  return document.querySelector("body > .frame > .loading-bar");
}

// Under the frame while it is in view; at the screen's top edge once it has scrolled away.
function place() {
  const frame = document.querySelector("body > .frame");
  const loading = bar();
  if (frame && loading) {
    loading.toggleAttribute("data-detached", frame.getBoundingClientRect().bottom <= 0);
  }
}

function show() {
  const loading = bar();
  if (loading) {
    place();
    loading.hidden = false;
    window.addEventListener("scroll", place, { passive: true });
  }
  // `aria-busy`, never `disabled`: the browser builds the form data after the submit event, and
  // a disabled button's value would be left out (the role and theme switches send theirs).
  if (pending.button) {
    pending.button.setAttribute("aria-busy", "true");
    busy.add(pending.button);
  }
}

function start(form, button) {
  if (pending) clearTimeout(pending.timer);
  pending = { form, button, timer: setTimeout(show, DELAY) };
}

function reset() {
  if (pending) clearTimeout(pending.timer);
  pending = null;
  window.removeEventListener("scroll", place);
  const loading = bar();
  if (loading) {
    loading.hidden = true;
    loading.removeAttribute("data-detached");
  }
  // Every form and button, not only the latest: a link followed after a slow form replaced it.
  for (const button of busy) button.removeAttribute("aria-busy");
  busy.clear();
  sending = new WeakSet();
}

// A link to another page of this site, in this window. New tabs and windows, downloads, other
// sites and moves within the page start nothing.
document.addEventListener("click", (event) => {
  if (event.defaultPrevented || event.button !== 0) return;
  if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const link = event.target.closest("a[href]");
  if (!link || link.hasAttribute("download")) return;
  if (link.target && link.target !== "_self") return;
  const url = new URL(link.href);
  if (url.origin !== location.origin) return;
  if (url.hash && url.pathname === location.pathname && url.search === location.search) return;
  start(null, null);
});

// A form the browser refuses as invalid fires no submit event, so it starts nothing. A POST form
// changes something, so it is sent once; a GET form (a list that submits itself) only chooses
// what to show, like a link, so a newer choice is sent again.
document.addEventListener("submit", (event) => {
  const form = event.target;
  const target = event.submitter?.getAttribute("formtarget") || form.target;
  if (event.defaultPrevented || (target && target !== "_self")) return;
  const method = (event.submitter?.getAttribute("formmethod") || form.method).toLowerCase();
  if (method === "post") {
    if (sending.has(form)) {
      event.preventDefault();
      return;
    }
    sending.add(form);
  }
  // The submitter is the default button when Enter was pressed, and null for a list.
  start(form, event.submitter);
});

// A page restored by Back or Forward comes back as it was frozen; it starts clean instead.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) reset();
});
